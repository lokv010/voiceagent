"""
OpenAI-Powered Inbound Call Handler

Simplified, fast, and intelligent inbound call handling using OpenAI directly
"""

from asyncio.log import logger
import logging
import json
from datetime import datetime
import time
import os
from pathlib import Path
from typing import Dict, List, Optional
import openai
import asyncio
from services.conv_engine.flow_models import CustomerContext



class InboundCallHandler:
    def __init__(self, voice_bot, db_manager, config):
        """Initialize with OpenAI-powered intelligence"""
        self.voice_bot = voice_bot
        self.db_manager = db_manager
        self.config = config
        
        # OpenAI setup
        self.openai_client = openai.AsyncOpenAI(api_key=config.OPENAI_API_KEY)
        
        # Fast response cache for common queries
        self.response_cache = {
            'greeting': "Thank you for calling. This is Sarah, your AI assistant. How can I help you today?",
            'pricing': "I'd be happy to discuss pricing. What's your average monthly electric bill?",
            'not_interested': "I understand. Thank you for your time and have a great day!",
            'transfer_request': "I'll connect you with a specialist right away."
        }

        self.conversation_templates = {}
        self.template_cache = {}
        self._load_conversation_templates()
        

        # Business rules
        self.business_hours = {'start': 9, 'end': 17, 'timezone': 'UTC'}
        self.agent_transfer_number = config.AGENT_TRANSFER_NUMBER
        
        logging.info("OpenAI Inbound Handler initialized")
    
    async def handle_inbound_call(self, call_sid: str, request_data: Dict) -> str:
        """Main inbound call handler - fast and intelligent"""
        try:
            caller_number = request_data.get('From', '').strip()
            clean_phone = caller_number.replace('+', '').replace(' ', '').replace('-', '')
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{clean_phone}"
            # Get or create prospect context
            prospect_context = await self._get_prospect_context(caller_number)
            
            # Initialize call state
            call_state = {
                'session_id':session_id,
                'phone_number': caller_number,
                'prospect_context': prospect_context,
                'prospect_id': prospect_context['prospect_id'],
                'call_type': 'inbound',
                'conversation_history': [],
                'start_time': datetime.now(),
                'current_turn': 0,
                'answered_by_human': True
            }
            
            # Store in active calls
            self.voice_bot.active_calls[call_sid] = call_state
            
            # Generate intelligent greeting
            greeting = await self._generate_smart_greeting(prospect_context)

          
            
            # Log interaction
            call_state['conversation_history'].append({
                'turn': 0,
                'type': 'agent',
                'message': greeting,
                'timestamp': datetime.now()
            })
            
            call_state['current_turn'] += 1
            
            return self.voice_bot.twilio_handler.generate_twiml_response(
                greeting, gather_input=True, timeout=12, 
                action_url=f"{self.config.WEBHOOK_URL}/inbound-webhook/process"
            )
            
        except Exception as e:
            logging.error(f"Error handling inbound call: {str(e)}")
            return self._generate_fallback_response()
    
    async def handle_inbound_response(self, call_sid: str, request_data: Dict) -> str:
        """Handle customer responses with OpenAI intelligence"""
        try:

            if call_sid not in self.voice_bot.active_calls:
                return self._handle_orphaned_request(request_data.get('SpeechResult', ''))
            
            call_state = self.voice_bot.active_calls[call_sid]
            session_id = call_state.get('session_id')
            if not session_id:
                logging.error(f"SIB_SERVICE->handle_inbound_response->Session ID missing from call_state for {call_sid}")
                return self._generate_fallback_response()

            customer_speech = request_data.get('SpeechResult', '').strip()
            confidence = float(request_data.get('Confidence', 0.0))
            logger.info(f"Customer speech: '{customer_speech}' (confidence: {confidence})")

            if confidence < 0.4 or not customer_speech:
                return self._generate_clarification_response()
            
            # Log customer input
            call_state['conversation_history'].append({
                'turn': call_state['current_turn'],
                'type': 'customer',
                'message': customer_speech,
                'confidence': confidence,
                'timestamp': datetime.now()
            })
            
            # Check for immediate actions (fast path)
            immediate_response = await self._check_immediate_actions(customer_speech, call_state)
            if immediate_response:
                return immediate_response

            logger.info("Generating Claude proactive response")

            # NEW: Try Claude engine first (replaces orchestrator)
            claude_response = await self._try_claude_response(customer_speech, call_state, session_id)
            logger.info(f"Claude response: {claude_response}")
            if claude_response:
                # Log Claude success
                call_state['conversation_history'].append({
                    'turn': call_state['current_turn'],
                    'type': 'agent',
                    'message': claude_response,
                    'timestamp': datetime.now(),
                    'strategy': 'claude_proactive'
                })
                call_state['current_turn'] += 1
                logger.info("Claude proactive response generated successfully")
                
                # Check if conversation should end
                # if call_state['current_turn'] >= 12 or self._should_end_conversation(customer_speech):
                #     return await self._end_conversation(call_sid, call_state, claude_response)
                
                return self.voice_bot.twilio_handler.generate_twiml_response(
                    claude_response, gather_input=True, timeout=12
                )

            
            logger.info("Claude failed generating OpenAI response")
            # response = await self._generate_openai_response(customer_speech, call_state)
            try:
                response = await self._generate_openai_response(customer_speech, call_state)
                logger.info(f"OpenAI generated response: '{response}'")
            except Exception as openai_error:
                logger.error(f"OpenAI error: {openai_error}, using fallback")
                response = self._get_fallback_solar_response(customer_speech)
            
            # Log agent response
            call_state['conversation_history'].append({
                'turn': call_state['current_turn'],
                'type': 'agent',
                'message': response,
                'timestamp': datetime.now(),
                'strategy': 'openai_intelligent'
            })
            
            call_state['current_turn'] += 1
            
            # Check if conversation should end
            if call_state['current_turn'] >= 12 or self._should_end_conversation(customer_speech):
                return await self._end_conversation(call_sid, call_state, response)
            
            return self.voice_bot.twilio_handler.generate_twiml_response(
                response, gather_input=True, timeout=12
            )
            
        except Exception as e:
            logger.error(f"Error in OpenAI handler: {e}", exc_info=True)
        # Use contextual fallback instead of generic error
        return self._generate_contextual_fallback(
            request_data.get('SpeechResult', ''),
            request_data.get('Confidence', '0.0')
        )
    
    def _generate_contextual_fallback(speech_result: str, confidence: str) -> str:

        try:
            confidence_float = float(confidence) if confidence else 0.0
            speech_lower = speech_result.lower() if speech_result else ""
            
            logger.info(f"Generating fallback for: '{speech_result}' (confidence: {confidence})")
            
            # Handle low confidence
            if confidence_float < 0.4 or not speech_result:
                return '''<?xml version="1.0" encoding="UTF-8"?>
                <Response>
                    <Gather input="speech" timeout="10" action="/inbound-webhook/process" method="POST">
                        <Say voice="Polly.Joanna">I'm sorry, I didn't catch that clearly. Could you please repeat?</Say>
                    </Gather>
                </Response>'''
            
            # Handle specific intents
            if any(word in speech_lower for word in ['human', 'agent', 'person', 'transfer', 'speak to someone']):
                agent_number = os.getenv('AGENT_TRANSFER_NUMBER', '+12267537919')
                return f'''<?xml version="1.0" encoding="UTF-8"?>
                <Response>
                    <Say voice="Polly.Joanna">I'll connect you with a specialist right away.</Say>
                    <Dial>{agent_number}</Dial>
                </Response>'''
            
            # Handle not interested
            if any(phrase in speech_lower for phrase in ['not interested', 'no thank', 'remove me', 'stop calling']):
                return '''<?xml version="1.0" encoding="UTF-8"?>
                <Response>
                    <Say voice="Polly.Joanna">I understand. Thank you for your time and have a great day!</Say>
                    <Hangup/>
                </Response>'''
            
            # Solar-specific responses based on keywords
            if any(word in speech_lower for word in ['price', 'cost', 'money', 'expensive', 'bill']):
                response = "Great question about pricing! What's your average monthly electric bill?"
            elif any(word in speech_lower for word in ['solar', 'panels', 'energy', 'electricity']):
                response = "I'd love to help you with solar! Do you own your home?"
            elif any(word in speech_lower for word in ['yes', 'interested', 'tell me more']):
                response = "Wonderful! To give you the best information, do you own your home?"
            elif any(word in speech_lower for word in ['save', 'saving', 'savings']):
                response = "Solar can definitely help you save money! What's your monthly electric bill?"
            else:
                # Vary the response to avoid repetition
                responses = [
                    "I'd be happy to help you explore solar options. Do you own your home?",
                    "Great that you called! Are you interested in learning about solar for your home?",
                    "I can help you with solar information. Do you currently own your home?",
                    "Let me help you with solar options. First, are you a homeowner?"
                ]
                import random
                response = random.choice(responses)
            
            return f'''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Gather input="speech" timeout="10" action="/inbound-webhook/process" method="POST">
                    <Say voice="Polly.Joanna">{response}</Say>
                </Gather>
            </Response>'''
            
        except Exception as e:
            logger.error(f"Error generating contextual fallback: {e}")
            return '''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Gather input="speech" timeout="10" action="/inbound-webhook/process" method="POST">
                    <Say voice="Polly.Joanna">How can I help you today?</Say>
                </Gather>
            </Response>'''
    
    async def _generate_openai_response(self, customer_input: str, call_state: Dict) -> str:
        """Generate intelligent response using OpenAI"""
        logging.info("=== OPENAI RESPONSE GENERATION START ===")
        try:
            prospect = call_state['prospect_context']['prospect']
            conversation_history = call_state['conversation_history']

            # Get relevant template context (NEW)
            template_context = self._get_relevant_template_context(customer_input, call_state)
            logging.info(f"OPENAI_GEN: Template context length: {len(template_context)}")
            if template_context:
                logging.info("OPENAI_GEN: Using template-enhanced prompt")
            else:
                logging.warning("OPENAI_GEN: No template context - using basic prompt")
            # Build conversation context
            context_messages = []
            
            # System prompt - focused and effective
            system_prompt = f"""You are Sarah, a professional AI assistant handling an INBOUND {self._get_business_type()} consultation call.
                


CUSTOMER INFO:
- Name: {prospect.name or 'Unknown caller'}
- Phone: {prospect.phone_number}
- They called YOU (inbound = high intent)


CURRENT SITUATION: Customer just said: "{customer_input}"

RESPONSE INSTRUCTIONS:
1. Use the conversation template below as your response guide
2. Adapt the template language to respond to their specific input
3. Keep the warm, professional tone from the template
4. Keep natural tone and enthusiasm as shown in the template
{template_context}

Respond using the template style above, adapted for their input."""
            
            logging.info(f"OPENAI_GEN: System prompt length: {len(system_prompt)}")
            logging.info(f"OPENAI_GEN: Template context included: {'Yes' if template_context else 'No'}")
            context_messages.append({"role": "system", "content": system_prompt})
            
            # Add recent conversation history (last 6 exchanges)
            recent_history = conversation_history[-6:] if len(conversation_history) > 6 else conversation_history
            
            for interaction in recent_history:
                if interaction['type'] == 'customer':
                    context_messages.append({"role": "user", "content": interaction['message']})
                elif interaction['type'] == 'agent':
                    context_messages.append({"role": "assistant", "content": interaction['message']})
            
            # Add current customer input
            context_messages.append({"role": "user", "content": customer_input})
            logging.info(f"OPENAI_GEN: Sending {len(context_messages)} messages to OpenAI")
            # Call OpenAI with optimized settings for speed
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # Faster than GPT-4
                messages=context_messages,
                max_tokens=100,  # Keep responses concise
                temperature=0.7,
                frequency_penalty=0.3,
                presence_penalty=0.3
            )

            logging.info(f"OPENAI_GEN: Generated response: '{response.choices[0].message.content.strip()}'")
            logging.info("=== OPENAI RESPONSE GENERATION COMPLETE ===")
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logging.error(f"OpenAI response generation error: {e}")
            template_response = self._get_template_fallback_response(customer_input)
            if template_response and template_response != customer_input:
                logging.info(f"Using template fallback response: {template_response}")
                return template_response
                # FALLBACK: Original method if template fails
            return self._get_fallback_solar_response(customer_input)
        
     #ADD method to determine business type
    def _get_business_type(self) -> str:
        return self.config.BUSINESS_TYPE or "business opportunity"

    def _get_business_context(self) -> str:
        business_contexts = {
            "solar": "Focus on solar savings, homeownership, electric bills",
            "franchise": "Focus on investment, experience, location, timeline",
            "insurance": "Focus on coverage needs, current policies, family situation",
            "burger franchise": "Focus on convincing customer to sell the franchise",
        }
        return business_contexts.get(os.getenv('BUSINESS_TYPE'), "General business consultation")
    async def _check_immediate_actions(self, customer_speech: str, call_state: Dict) -> Optional[str]:
        """Check for immediate actions that don't need OpenAI (fast path)"""
        speech_lower = customer_speech.lower()
        
        # Transfer requests - immediate action
        if any(word in speech_lower for word in ['human', 'agent', 'person', 'transfer', 'speak to someone']):
            call_state['transfer_requested'] = True
            transfer_msg = "I'll connect you with a specialist right away. Please hold."
            
            call_state['conversation_history'].append({
                'turn': call_state['current_turn'],
                'type': 'agent',
                'message': transfer_msg,
                'timestamp': datetime.now(),
                'action': 'transfer'
            })
            
            return self.voice_bot.twilio_handler.generate_transfer_twiml(
                self.agent_transfer_number, transfer_msg
            )
        
        # Not interested - immediate end
        if any(phrase in speech_lower for phrase in ['not interested', 'no thank', 'remove me', 'stop calling']):
            return await self._end_conversation(
                None, call_state, 
                "I understand. Thank you for your time and have a great day!"
            )
        
        # Simple yes/no responses - use cache
        if speech_lower.strip() in ['yes', 'yeah', 'yep', 'sure']:
            return None  # Continue with OpenAI for context-aware response
        
        return None
    
    async def _generate_smart_greeting(self, prospect_context: Dict) -> str:
        """Generate contextual greeting based on prospect info"""
        prospect = prospect_context['prospect']
        
        if prospect.name and prospect.source != 'unknown_caller':
            return f"Thank you for calling, {prospect.name}. This is Sarah from {os.getenv('BUSINESS_NAME')}. How can I help you today?"
        else:
            return self.response_cache['greeting']
    
    def _get_fallback_solar_response(self, customer_input: str) -> str:
    
        """Dynamic fallback based on business type"""
        input_lower = customer_input.lower()
        business_type = self.config.BUSINESS_TYPE
        response_templates = {
            "solar": {
                "price": "What's your average monthly electric bill?",
                "default": "Do you own your home?"
            },
            "franchise": {
                "price": "What's your investment budget range?", 
                "experience": "Do you have business or restaurant experience?",
                "default": "Are you looking to open in a specific location?"
            },
            "insurance": {
                "price": "What coverage amount are you considering?",
                "default": "Tell me about your current insurance situation?"
            }
        }

        templates = response_templates.get(business_type, response_templates["franchise"])

        if any(word in input_lower for word in ['price', 'cost', 'money', 'expensive']):
            templates.get("price", templates["default"])
        
        elif business_type == "franchise" and any(word in input_lower for word in ['experience', 'background']):
            return templates.get("experience", templates["default"])
        
        elif any(word in input_lower for word in ['solar', 'panels', 'energy']):
            return "I'd love to help you with solar! First, do you own your home?"
        
        elif any(word in input_lower for word in ['bills', 'save', 'savings']):
            return "Solar can definitely help you save! What's your current monthly electric bill?"
        
        elif any(word in input_lower for word in ['roof', 'house', 'home']):
            return "Perfect! Do you own your home?"
        
        else:
            return templates["default"]
    
    def _should_end_conversation(self, customer_speech: str) -> bool:
        """Determine if conversation should end naturally"""
        speech_lower = customer_speech.lower()
        
        ending_signals = [
            'not interested', 'no thank', 'call back later', 'busy right now',
            'not a good time', 'remove me', 'stop calling'
        ]
        
        return any(signal in speech_lower for signal in ending_signals)
    
    # async def _end_conversation(self, call_sid: str, call_state: Dict, final_message: str) -> str:
    #     """End conversation and cleanup"""
    #     try:
    #         if call_sid:
    #             # Calculate and save results
    #             call_results = await self._calculate_call_results(call_sid, call_state)
    #             await self._save_call_results(call_sid, call_state, call_results)
                
    #             # Cleanup
    #             del self.voice_bot.active_calls[call_sid]
            
    #         return self.voice_bot.twilio_handler.generate_twiml_response(
    #             final_message, gather_input=False
    #         )
            
    #     except Exception as e:
    #         logging.error(f"Error ending conversation: {e}")
    #         return self._generate_fallback_response()
    
    async def _get_prospect_context(self, phone_number: str) -> Dict:
        """Get or create prospect context quickly"""
        try:
            # Try existing prospect
            context = self.voice_bot.prospect_manager.get_prospect_context(phone_number)
            if context:
                return context
            
            # Create new inbound prospect
            session = self.db_manager.get_session()
            try:
                from models.database import Prospect, ProspectSource
                
                new_prospect = Prospect(
                    phone_number=phone_number,
                    source=ProspectSource.WEBSITE_VISITOR.value,
                    qualification_score=35,  # Higher base for inbound
                    call_status='active',
                    created_at=datetime.now()
                )
                
                session.add(new_prospect)
                session.commit()
                session.refresh(new_prospect)
                
                # Build context
                prospect_data = {
                    'id': new_prospect.id,
                    'phone_number': phone_number,
                    'name': new_prospect.name,
                    'source': new_prospect.source,
                    'qualification_score': new_prospect.qualification_score,
                    'call_status': new_prospect.call_status,
                    'created_at': new_prospect.created_at,
                    'do_not_call': False
                }
                
                return {
                    'prospect': type('ProspectData', (), prospect_data)(),
                    'prospect_id': new_prospect.id,
                    'call_history': [],
                    'previous_conversations': 0
                }
                
            finally:
                session.close()
                
        except Exception as e:
            logging.error(f"Error getting prospect context: {e}")
            # Return minimal context to keep call going
            return {
                'prospect': type('ProspectData', (), {
                    'id': None, 'phone_number': phone_number, 'name': None,
                    'source': 'unknown_caller', 'do_not_call': False
                })(),
                'prospect_id': None,
                'call_history': [],
                'previous_conversations': 0
            }
    
    def _generate_clarification_response(self) -> str:
        """Generate clarification request for low confidence speech"""
        return self.voice_bot.twilio_handler.generate_twiml_response(
            "I'm sorry, I didn't catch that clearly. Could you please repeat?",
            gather_input=True, timeout=10
        )
    
    def _handle_orphaned_request(self, speech_result: str) -> str:
        """Handle speech requests for calls no longer in active state"""
        speech_lower = speech_result.lower() if speech_result else ""
        
        if any(word in speech_lower for word in ['human', 'agent', 'person']):
            response = "Let me connect you with someone who can help."
            return f'''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="Polly.Joanna">{response}</Say>
                <Dial>{self.agent_transfer_number}</Dial>
            </Response>'''
        
        elif any(word in speech_lower for word in ['not interested', 'no thank']):
            return f'''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="Polly.Joanna">Thank you for your time. Have a great day!</Say>
                <Hangup/>
            </Response>'''
        
        else:
            return f'''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Gather input="speech" timeout="10" action="/inbound-webhook/process" method="POST">
                    <Say voice="Polly.Joanna">How can I help you with solar for your home today?</Say>
                </Gather>
            </Response>'''
    
    def _generate_fallback_response(self) -> str:
        """Generate fallback TwiML for errors"""
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Joanna">Thank you for calling. Please try again later.</Say>
            <Hangup/>
        </Response>'''
    
    async def _calculate_call_results(self, call_sid: str, call_state: Dict) -> Dict:
        """Calculate call results for database storage"""
        try:
            conversation_data = {
                'customer_responses': [h['message'] for h in call_state['conversation_history'] if h['type'] == 'customer'],
                'total_turns': call_state['current_turn'],
                'call_duration': (datetime.now() - call_state['start_time']).total_seconds(),
                'answered_by_human': True,
                'strategy_used': 'openai_intelligent'
            }
            
            # Simple scoring based on conversation quality
            score = self._calculate_simple_score(conversation_data, call_state)
            
            return {
                'call_sid': call_sid,
                'scoring_result': {'final_score': score, 'component_scores': {'engagement': score}},
                'conversation_data': conversation_data,
                'conversation_summary': self._generate_summary(call_state['conversation_history']),
                'call_type': 'inbound',
                'call_outcome': 'completed'
            }
            
        except Exception as e:
            logging.error(f"Error calculating call results: {e}")
            return {
                'call_sid': call_sid,
                'scoring_result': {'final_score': 40, 'component_scores': {}},
                'call_outcome': 'failed'
            }
    
    def _calculate_simple_score(self, conversation_data: Dict, call_state: Dict) -> int:
        """Simple but effective scoring for inbound calls"""
        base_score = 45  # Higher base for inbound calls
        
        # Engagement factors
        num_responses = len(conversation_data['customer_responses'])
        if num_responses >= 3:
            base_score += 20
        elif num_responses >= 2:
            base_score += 10
        
        # Quality factors
        all_responses = ' '.join(conversation_data['customer_responses']).lower()
        
        if 'interested' in all_responses or 'yes' in all_responses:
            base_score += 15
        if any(word in all_responses for word in ['own', 'house', 'home']):
            base_score += 10
        if any(word in all_responses for word in ['bill', 'electric', 'energy']):
            base_score += 10
        
        # Transfer requests are still valuable
        if call_state.get('transfer_requested'):
            base_score += 15
        
        return min(base_score, 100)
    
    def _generate_summary(self, conversation_history: List[Dict]) -> str:
        """Generate simple conversation summary"""
        customer_responses = [h['message'] for h in conversation_history if h['type'] == 'customer']
        
        if not customer_responses:
            return "No customer responses recorded"
        
        summary_parts = [f"Inbound call with {len(customer_responses)} responses"]
        
        all_responses = ' '.join(customer_responses).lower()
        if 'interested' in all_responses:
            summary_parts.append("showed interest")
        if 'price' in all_responses or 'cost' in all_responses:
            summary_parts.append("discussed pricing")
        if 'not interested' in all_responses:
            summary_parts.append("not interested")
        
        return '. '.join(summary_parts) + '.'
    
    async def _save_call_results(self, call_sid: str, call_state: Dict, call_results: Dict):
        """Save call results to database"""
        try:
            # Use the existing voice bot save method
            await self.voice_bot._save_call_results(call_sid, call_state, call_results, 'completed')
            await self.voice_bot._update_prospect_after_call(call_state, call_results)
            
        except Exception as e:
            logging.error(f"Error saving call results: {e}")

    #conversation engine supporting functions
    def set_orchestrator(self, orchestrator, classification_engine):
        """Connect orchestrator system for enhanced conversation flow"""
        self.orchestrator = orchestrator
        self.classification_engine = classification_engine
        self.orchestrator_enabled = True
        logging.info("Orchestrator connected to inbound handler")

    async def _try_orchestrator_response(self, customer_speech: str, call_state: Dict) -> Optional[str]:
        """Try orchestrator-enhanced response generation"""
        try:
            session_id = call_state.get('session_id')
            logging.info(f"IB_SERVICE->_try_orchestrator_response: Using session_id={session_id}")
            logging.info(f"IB_SERVICE->_try_orchestrator_response: call_state keys={list(call_state.keys())}")
            if not session_id:
                logging.error("IB_SERVICE->_try_orchestrator_response->Session ID missing from call_state in orchestrator call")
                return None
            # Initialize orchestrator session if needed
            if session_id not in self.orchestrator.state_manager.active_sessions:
                customer_context = self._create_customer_context(call_state)
                initialized_session_id = self.orchestrator.state_manager.initialize_conversation_flow('inbound_call', customer_context,session_id)
                if initialized_session_id != session_id:
                        logging.error(f"IB_SERVICE->_try_orchestrator_response:Session ID mismatch: expected {session_id}, got {initialized_session_id}")
            # Process input through orchestrator
            result = self.orchestrator.process_customer_input(session_id, customer_speech)
            #process customer input through orchestrator log
            logging.info(f"IB_SERVICE->_try_orchestrator_response:Orchestrator result keys: {result.keys() if result else 'None'}")
            logging.info(f"IB_SERVICE->_try_orchestrator_response:Orchestrator result: {result}")


            if result.get('success') and result.get('execution_result', {}).get('customer_response'):

                execution_result = result.get('execution_result', {})

                # Extract response text from orchestrator result log
                logging.info(f"Execution result keys: {result['execution_result'].keys()}")
                logging.info(f"Execution result: {result['execution_result']}")
                
                response_text = (
                                execution_result.get('customer_response') or 
                                execution_result.get('message') or
                                execution_result.get('response') or
                                execution_result.get('step_result', {}).get('message') or
                                execution_result.get('first_step', {}).get('message')
    )
                if response_text:

                    logging.info(f"Using orchestrator response: {response_text}")
                    # ... rest unchanged
                else:
                    logging.warning(f"No response text found in execution_result: {execution_result}")
                    return None

                # Update call state with orchestrator insights
                call_state['orchestrator_insights'] = {
                    'classification': result.get('classification'),
                    'confidence': result.get('classification', {}).get('confidence_score', 0),
                    'recommended_flow': result.get('classification', {}).get('primary_flow')
                }
                
                return self.voice_bot.twilio_handler.generate_twiml_response(
                    response_text, gather_input=True, timeout=12
                )
                
        except Exception as e:
            logging.warning(f"Orchestrator response failed: {e}")
            return None

    def _create_customer_context(self, call_state: Dict):
        """Convert call_state to CustomerContext for orchestrator"""

        
        prospect = call_state['prospect_context']['prospect']
        return CustomerContext(
            customer_id=prospect.phone_number,
            industry=getattr(prospect, 'industry', None),
            company_size=getattr(prospect, 'company_size', None),
            technical_background=getattr(prospect, 'technical_background', None),
            previous_interactions=call_state['prospect_context'].get('call_history', []),
            pain_points=call_state.get('discovered_pain_points', []),
            goals=call_state.get('customer_goals', [])
        )
    #Extended context base for openAI to refer template
    # ADD: New template loading methods
    def _load_conversation_templates(self):
        """Load and cache conversation templates for OpenAI context"""
        try:
            template_paths = {
                'franchise': 'playbook/pitch_flow.json',
                'solar': 'playbook/salesplaybook.json',
                'general': 'playbook/pitch_flow.json',
                'burger': 'playbook/pitch_flow.json' # fallback
            }
            
            business_type = getattr(self.config, 'BUSINESS_TYPE', 'general')
            logging.info(f"Loading conversation template for business type: {business_type}")
            template_path = template_paths.get(business_type, template_paths['general'])
            logging.info(f"TEMPLATE_LOAD: Using template path: {template_path}")

            if Path(template_path).exists():
                logging.info(f"TEMPLATE_LOAD: Template file exists: {template_path}")
                with open(template_path, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)
                    logging.info(f"TEMPLATE_LOAD: JSON loaded successfully. Keys: {list(template_data.keys())}")
                    
                self.conversation_templates[business_type] = template_data
                self._build_template_cache(template_data, business_type)

                logging.info(f"TEMPLATE_LOAD: Successfully loaded template for {business_type}")
                logging.info(f"TEMPLATE_LOAD: Cache keys created: {list(self.template_cache.get(business_type, {}).keys())}")
                
                logging.info(f"Loaded conversation template for {business_type}")
            else:
                logging.warning(f"Template file not found: {template_path}")
                
        except Exception as e:
            logging.error(f"Error loading conversation templates: {e}")

        
    def _build_template_cache(self, template_data: Dict, business_type: str):
        """Build efficient template cache for token optimization"""
        try:
            logging.info(f"CACHE_BUILD: Template data keys: {list(template_data.keys())}")
            if 'conversation_flow' in template_data:
                logging.info("CACHE_BUILD: Found 'conversation_flow' key")
                flow_data = template_data['conversation_flow']
                logging.info(f"CACHE_BUILD: Flow data keys: {list(flow_data.keys())}")
                steps = flow_data.get('steps', [])
                logging.info(f"CACHE_BUILD: Found {len(steps)} steps in conversation_flow")
            elif 'steps' in template_data:
                logging.info("CACHE_BUILD: Found direct 'steps' key")
                steps = template_data['steps']
                logging.info(f"CACHE_BUILD: Found {len(steps)} steps directly")
            else:
                logging.error("CACHE_BUILD: No 'conversation_flow' or 'steps' key found")
                return
            
            cache = {
                'greeting_steps': [],
                'qualification_steps': [],
                'engagement_steps': [],
                'objection_responses': [],
                'closing_steps': []
            }
            
            for i, step in enumerate(steps):
                logging.info(f"CACHE_BUILD: Processing step {i+1}: {step.get('step_id', 'unknown')}")
            
                step_type = step.get('step_type', 'general')
                step_id = step.get('step_id', '')
                message_variants = step.get('message_variants', [])
            
                logging.info(f"CACHE_BUILD: Step {i+1} - ID: {step_id}, Type: {step_type}, Messages: {len(message_variants)}")
            
                if not message_variants:
                    logging.warning(f"CACHE_BUILD: Step {step_id} has no message_variants!")
                    continue
            
                step_info = {
                    'step_id': step_id,
                    'messages': message_variants,
                    'purpose': step.get('step_name', ''),
                    'data_collection': step.get('data_collection', {})
                }

                # Enhanced categorization with logging
                category = self._categorize_step_with_logging(step_id, step_type, i+1)
                cache[category].append(step_info)
                
            for category, items in cache.items():
                logging.info(f"CACHE_BUILD: {category}: {len(items)} items")
                for item in items:
                    logging.info(f"CACHE_BUILD:   - {item['step_id']}: {item['purpose']}")
        
            self.template_cache[business_type] = cache
            logging.info("=== TEMPLATE CACHE BUILDING COMPLETE ===")
    
        except Exception as e:
            logging.error(f"CACHE_BUILD: Error building template cache: {e}", exc_info=True)
    
    def _get_relevant_template_context(self, customer_input: str, call_state: Dict) -> str:
        """Extract relevant template context for OpenAI (token-efficient)"""
        logging.info("=== TEMPLATE CONTEXT EXTRACTION START ===")
        try:
            business_type = getattr(self.config, 'BUSINESS_TYPE', 'general')
            logging.info(f"CONTEXT_EXTRACT: Business type: {business_type}")

            if not hasattr(self, 'template_cache'):
                logging.warning("template_cache not initialized, using empty context")
                return ""
            

            logging.info(f"CONTEXT_EXTRACT: template_cache keys: {list(self.template_cache.keys())}")
            cache = self.template_cache.get(business_type, {})
            logging.info(f"CONTEXT_EXTRACT: Cache for {business_type}: {list(cache.keys())}")
            if not cache:
                logging.warning(f"No template cache for business_type: {business_type}")
                return ""
            
            for category, items in cache.items():
                logging.info(f"CONTEXT_EXTRACT: {category}: {len(items)} items")
        
            conversation_stage = self._determine_conversation_stage(customer_input, call_state)
        
            # FIX: The key mismatch issue
            stage_to_cache_key = {
                'greeting': 'greeting_steps',
                'qualification': 'qualification_steps',
                'engagement': 'engagement_steps',
                'objection': 'objection_responses',
                'closing': 'closing_steps'
            }
           
            



            cache_key = stage_to_cache_key.get(conversation_stage, 'qualification_steps')
            logging.info(f"CONTEXT_EXTRACT: Stage '{conversation_stage}' -> Cache key '{cache_key}'")
            relevant_steps = cache.get(cache_key, [])
            logging.info(f"CONTEXT_EXTRACT: Found {len(relevant_steps)} relevant steps")
            
            if not relevant_steps:
                logging.warning(f"CONTEXT_EXTRACT: No steps found for cache_key: {cache_key}")
                # Try fallback to qualification
                relevant_steps = cache.get('qualification_steps', [])
                logging.info(f"CONTEXT_EXTRACT: Fallback to qualification_steps: {len(relevant_steps)} items")
            
            # Build concise context
            context_parts = []
            for i, step in enumerate(relevant_steps[:2]):  # Limit to 2 steps
                logging.info(f"CONTEXT_EXTRACT: Processing step {i+1}: {step['step_id']}")
            
            if step['messages']:
                example_msg = step['messages'][0]
                context_parts.append(f"- {step['purpose']}: \"{example_msg}\"")
                logging.info(f"CONTEXT_EXTRACT: Added context for {step['step_id']}")
            else:
                logging.warning(f"CONTEXT_EXTRACT: Step {step['step_id']} has no messages")
        
            if context_parts:
                template_context = f"\nRELEVANT CONVERSATION PATTERNS:\n" + "\n".join(context_parts)
                logging.info(f"CONTEXT_EXTRACT: Generated template context ({len(template_context)} chars)")
                logging.info(f"CONTEXT_EXTRACT: Template context preview: {template_context[:200]}...")
                return template_context
            else:
                logging.warning("CONTEXT_EXTRACT: No context parts generated")
                return ""
        
        except Exception as e:
            logging.error(f"CONTEXT_EXTRACT: Error getting template context: {e}", exc_info=True)
            return ""
        
    def _determine_conversation_stage(self, customer_input: str, call_state: Dict) -> str:
        """Determine current conversation stage for template selection"""
        input_lower = customer_input.lower()
        turn_count = call_state.get('current_turn', 0)
        logging.info(f"STAGE_DETECT: Input: '{customer_input}' (turn {turn_count})")
        # Early conversation
        if turn_count <= 2:
            return 'greeting'
        
        # Stage based on customer input signals
        if turn_count <= 2:
            stage = 'greeting'
            logging.info(f"STAGE_DETECT: Early conversation -> {stage}")
        elif any(word in input_lower for word in ['price', 'cost', 'money', 'expensive', 'budget']):
            stage = 'qualification'
            logging.info(f"STAGE_DETECT: Price/cost keywords -> {stage}")
        elif any(word in input_lower for word in ['not interested', 'busy', 'not now', 'concern']):
            stage = 'objection'
            logging.info(f"STAGE_DETECT: Objection keywords -> {stage}")
        elif any(word in input_lower for word in ['interested', 'tell me more', 'sounds good', 'yes']):
            stage = 'engagement'
            logging.info(f"STAGE_DETECT: Engagement keywords -> {stage}")
        elif any(word in input_lower for word in ['when', 'next step', 'schedule', 'meet']):
            stage = 'closing'
            logging.info(f"STAGE_DETECT: Closing keywords -> {stage}")
        else:
            stage = 'qualification'
            logging.info(f"STAGE_DETECT: Default -> {stage}")
            # Default to qualification for middle conversation
        return stage
        
    def _get_template_fallback_response(self, customer_input: str) -> str:
        """Get fallback response using template patterns"""
        try:
            business_type = getattr(self.config, 'BUSINESS_TYPE', 'general')
            cache = self.template_cache.get(business_type, {})
            
            input_lower = customer_input.lower()
            
            # Use template patterns for fallback
            if 'price' in input_lower or 'cost' in input_lower:
                qualification_steps = cache.get('qualification_steps', [])
                for step in qualification_steps:
                    if 'investment' in step['step_id'] or 'budget' in step['step_id']:
                        if step['messages']:
                            return step['messages'][0]
            
            elif 'not interested' in input_lower:
                objection_steps = cache.get('objection_responses', [])
                if objection_steps and objection_steps[0]['messages']:
                    return objection_steps[0]['messages'][0]
            
            # Default to first qualification message
            qualification_steps = cache.get('qualification_steps', [])
            if qualification_steps and qualification_steps[0]['messages']:
                return qualification_steps[0]['messages'][0]
            
        except Exception as e:
            logging.error(f"Template fallback error: {e}")
        
        # Final fallback to existing method
        return self._get_fallback_solar_response(customer_input)
    
    def _categorize_step_with_logging(self, step_id: str, step_type: str, step_num: int) -> str:
        """Categorize step with detailed logging"""
        
        # Categorization logic with logging
        if 'greeting' in step_id or 'consent' in step_id:
            category = 'greeting_steps'
            logging.info(f"CATEGORIZE: Step {step_num} ({step_id}) -> {category} (greeting/consent)")
        elif 'qualification' in step_type or any(q in step_id for q in ['experience', 'investment', 'location']):
            category = 'qualification_steps'
            logging.info(f"CATEGORIZE: Step {step_num} ({step_id}) -> {category} (qualification)")
        elif 'engagement' in step_type or 'motivation' in step_id:
            category = 'engagement_steps'
            logging.info(f"CATEGORIZE: Step {step_num} ({step_id}) -> {category} (engagement)")
        elif 'objection' in step_type or 'concern' in step_id:
            category = 'objection_responses'
            logging.info(f"CATEGORIZE: Step {step_num} ({step_id}) -> {category} (objection)")
        elif 'booking' in step_type or 'closing' in step_id or 'recap' in step_id:
            category = 'closing_steps'
            logging.info(f"CATEGORIZE: Step {step_num} ({step_id}) -> {category} (booking/closing)")
        else:
            category = 'qualification_steps'  # Default
            logging.info(f"CATEGORIZE: Step {step_num} ({step_id}) -> {category} (default)")
        
        return category
    
    #Claude Haiku integration
    async def _try_claude_response(self, customer_speech: str, call_state: dict, session_id: str) -> str:
        """Try to generate response using Claude proactive engine"""
        try:
            # Initialize Claude engine if not exists
            if not hasattr(self, 'claude_engine'):
                api_key = os.getenv('ANTHROPIC_API_KEY')
                if not api_key:
                    logger.warning("ANTHROPIC_API_KEY not set, skipping Claude engine")
                    return None
                from .claude_haiku.FastClassificationEngine import ProactiveConversationService
                self.claude_engine = ProactiveConversationService(api_key)
            
            # Convert call_state to Claude-compatible format
            claude_session_data = self._convert_to_claude_format(call_state)
            
            # Get proactive response from Claude (single function call)
            start_time = time.time()
            result = await self.claude_engine.handle_customer_interaction(
                customer_speech, 
                session_id
            )
            
            processing_time = (time.time() - start_time) * 1000
            logger.info(f"Claude processing time: {processing_time:.0f}ms")
            
            # Update call_state with Claude conversation data
            self._update_call_state_from_claude(call_state, result)
            
            # Return Claude's response if successful
            if result.get('agent_response') and result.get('conversation_continues', True):
                return result['agent_response']
            
            # Claude indicates call should end
            if result.get('call_completed', False):
                call_state['claude_completion'] = True
                return result.get('agent_response', "Thank you for your interest. We'll follow up soon.")
            
            return None
            
        except Exception as e:
            logger.error(f"Claude engine error: {e}")
            return None

    def _convert_to_claude_format(self, call_state: dict) -> dict:
        """Convert call_state format to Claude engine format (minimal conversion)"""
        try:
            # Extract conversation history in Claude format
            conversation_history = []
            for entry in call_state.get('conversation_history', []):
                if entry.get('type') == 'customer':
                    conversation_history.append({
                        'role': 'customer', 
                        'message': entry.get('message', ''),
                        'timestamp': entry.get('timestamp', time.time())
                    })
                elif entry.get('type') == 'agent':
                    conversation_history.append({
                        'role': 'agent', 
                        'message': entry.get('message', ''),
                        'timestamp': entry.get('timestamp', time.time())
                    })
            
            # Determine current stage based on turn count (simple heuristic)
            turn_count = call_state.get('current_turn', 0)
            if turn_count <= 2:
                current_stage = 'GREETING'
            elif turn_count <= 6:
                current_stage = 'DISCOVERY'
            elif turn_count <= 10:
                current_stage = 'PRESENTATION'
            else:
                current_stage = 'CLOSING'
            
            return {
                'conversation_history': conversation_history,
                'customer_data': call_state.get('customer_data', {}),
                'current_stage': current_stage,
                'session_start': call_state.get('call_start_time', time.time())
            }
            
        except Exception as e:
            logger.error(f"Format conversion error: {e}")
            return {
                'conversation_history': [],
                'customer_data': {},
                'current_stage': 'GREETING',
                'session_start': time.time()
            }

    def _update_call_state_from_claude(self, call_state: dict, claude_result: dict):
        """Update call_state with insights from Claude (lightweight update)"""
        try:
            # Update customer data if Claude extracted new information
            if claude_result.get('customer_data'):
                if 'customer_data' not in call_state:
                    call_state['customer_data'] = {}
                call_state['customer_data'].update(claude_result['customer_data'])
            
            # Track Claude conversation stage
            if claude_result.get('current_stage'):
                call_state['claude_stage'] = claude_result['current_stage']
            
            # Track processing metrics
            if claude_result.get('processing_time_ms'):
                call_state['last_claude_time_ms'] = claude_result['processing_time_ms']
            
            # Track conversation quality
            if claude_result.get('conversation_length'):
                call_state['claude_conversation_length'] = claude_result['conversation_length']
                
        except Exception as e:
            logger.error(f"Call state update error: {e}")

    def _should_end_conversation(self, customer_speech: str) -> bool:
        """Enhanced conversation ending detection (includes Claude insights)"""
        speech_lower = customer_speech.lower()
        
        # Explicit ending signals
        ending_phrases = [
            'thank you', 'goodbye', 'bye', 'that\'s all', 
            'i\'ll think about it', 'not interested', 
            'call me back', 'send information', 'i\'m done'
        ]
        
        if any(phrase in speech_lower for phrase in ending_phrases):
            return True
        
        # Check if Claude indicated completion
        for call_state in self.voice_bot.active_calls.values():
            if call_state.get('claude_completion', False):
                return True
        
        return False

    async def _end_conversation(self, call_sid: str, call_state: dict, final_response: str) -> str:
        """Enhanced conversation ending with Claude insights"""
        try:
            # Log conversation summary
            logger.info(f"Ending conversation {call_sid}")
            logger.info(f"Total turns: {call_state.get('current_turn', 0)}")
            logger.info(f"Claude stage: {call_state.get('claude_stage', 'unknown')}")
            logger.info(f"Customer data: {call_state.get('customer_data', {})}")
            
            # Cleanup Claude session if exists
            if hasattr(self, 'claude_engine'):
                session_id = call_state.get('session_id')
                if session_id and session_id in self.claude_engine.session_data:
                    # Export for CRM before cleanup
                    conversation_summary = self.claude_engine.get_session_summary(session_id)
                    call_state['claude_summary'] = conversation_summary
                    
                    # Cleanup session data
                    del self.claude_engine.session_data[session_id]
            
            # Remove from active calls
            if call_sid in self.voice_bot.active_calls:
                del self.voice_bot.active_calls[call_sid]
            
            # Generate final TwiML (no gather, conversation ends)
            return self.voice_bot.twilio_handler.generate_twiml_response(
                final_response, gather_input=False, timeout=0
            )
            
        except Exception as e:
            logger.error(f"Error ending conversation: {e}")
            return self.voice_bot.twilio_handler.generate_twiml_response(
                "Thank you for calling. Goodbye!", gather_input=False
            )

    async def cleanup_claude_engine(self):
        """Cleanup Claude engine resources"""
        try:
            if hasattr(self, 'claude_engine'):
                await self.claude_engine.close()
                self.claude_engine = None
                logger.info("Claude engine cleaned up successfully")
        except Exception as e:
            logger.error(f"Claude engine cleanup error: {e}")
            if hasattr(self, 'claude_engine'):
                self.claude_engine = None

    # Optional: Initialize Claude engine at service startup for faster first response
    def initialize_claude_engine(self):
        """Pre-initialize Claude engine for faster response times"""
        try:
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if api_key:
                from .claude_haiku.FastClassificationEngine import ProactiveConversationService
                self.claude_engine = ProactiveConversationService(api_key)
                logger.info("Claude engine pre-initialized")
            else:
                logger.warning("ANTHROPIC_API_KEY not set, Claude engine will be lazy-loaded")
                self.claude_engine = None
        except Exception as e:
            logger.error(f"Claude engine initialization error: {e}")
            self.claude_engine = None