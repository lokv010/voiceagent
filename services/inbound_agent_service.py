"""
OpenAI-Powered Inbound Call Handler

Simplified, fast, and intelligent inbound call handling using OpenAI directly
"""

from asyncio.log import logger
import logging
import json
from datetime import datetime
import os
from typing import Dict, List, Optional
import openai
import asyncio


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
        
        # Business rules
        self.business_hours = {'start': 9, 'end': 17, 'timezone': 'UTC'}
        self.agent_transfer_number = config.AGENT_TRANSFER_NUMBER
        
        logging.info("OpenAI Inbound Handler initialized")
    
    async def handle_inbound_call(self, call_sid: str, request_data: Dict) -> str:
        """Main inbound call handler - fast and intelligent"""
        try:
            caller_number = request_data.get('From', '').strip()
            
            # Get or create prospect context
            prospect_context = await self._get_prospect_context(caller_number)
            
            # Initialize call state
            call_state = {
                'phone_number': caller_number,
                'prospect_context': prospect_context,
                'prospect_id': prospect_context['prospect_id'],
                'call_type': 'inbound',
                'conversation_history': [],
                'start_time': datetime.utcnow(),
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
                'timestamp': datetime.utcnow()
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
                'timestamp': datetime.utcnow()
            })
            
            # Check for immediate actions (fast path)
            immediate_response = await self._check_immediate_actions(customer_speech, call_state)
            if immediate_response:
                return immediate_response
            
            logger.info("Generating OpenAI response")
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
                'timestamp': datetime.utcnow(),
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
        try:
            prospect = call_state['prospect_context']['prospect']
            conversation_history = call_state['conversation_history']
            
            # Build conversation context
            context_messages = []
            
            # System prompt - focused and effective
            system_prompt = f"""You are Sarah, a professional AI assistant handling an INBOUND solar consultation call.

CUSTOMER INFO:
- Name: {prospect.name or 'Unknown caller'}
- Phone: {prospect.phone_number}
- They called YOU (inbound = high intent)

CONVERSATION GOALS:
1. Understand why they called
2. Qualify their solar needs (homeowner, electric bill, timeline)
3. Build value and schedule next steps
4. Keep responses conversational and helpful

KEY GUIDELINES:
- Be warm but professional
- Ask ONE question at a time
- Listen to their needs first
- Focus on solar savings and benefits
- If they want human agent, offer transfer immediately
- Keep responses under 40 words for natural flow

CURRENT SITUATION: Customer just said: "{customer_input}"

Respond naturally and helpfully."""

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
            
            # Call OpenAI with optimized settings for speed
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # Faster than GPT-4
                messages=context_messages,
                max_tokens=100,  # Keep responses concise
                temperature=0.7,
                frequency_penalty=0.3,
                presence_penalty=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logging.error(f"OpenAI response generation error: {e}")
            return self._get_fallback_solar_response(customer_input)
    
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
                'timestamp': datetime.utcnow(),
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
            return f"Thank you for calling, {prospect.name}. This is Sarah from solar consultations. How can I help you today?"
        else:
            return self.response_cache['greeting']
    
    def _get_fallback_solar_response(self, customer_input: str) -> str:
        """Fallback solar responses when OpenAI is unavailable"""
        input_lower = customer_input.lower()
        
        if any(word in input_lower for word in ['price', 'cost', 'money', 'expensive']):
            return "Great question about cost! Most homeowners save money from day one. What's your average monthly electric bill?"
        
        elif any(word in input_lower for word in ['solar', 'panels', 'energy']):
            return "I'd love to help you with solar! First, do you own your home?"
        
        elif any(word in input_lower for word in ['bills', 'save', 'savings']):
            return "Solar can definitely help you save! What's your current monthly electric bill?"
        
        elif any(word in input_lower for word in ['roof', 'house', 'home']):
            return "Perfect! Do you own your home?"
        
        else:
            return "I'd be happy to help you explore solar options. Do you own your home?"
    
    def _should_end_conversation(self, customer_speech: str) -> bool:
        """Determine if conversation should end naturally"""
        speech_lower = customer_speech.lower()
        
        ending_signals = [
            'not interested', 'no thank', 'call back later', 'busy right now',
            'not a good time', 'remove me', 'stop calling'
        ]
        
        return any(signal in speech_lower for signal in ending_signals)
    
    async def _end_conversation(self, call_sid: str, call_state: Dict, final_message: str) -> str:
        """End conversation and cleanup"""
        try:
            if call_sid:
                # Calculate and save results
                call_results = await self._calculate_call_results(call_sid, call_state)
                await self._save_call_results(call_sid, call_state, call_results)
                
                # Cleanup
                del self.voice_bot.active_calls[call_sid]
            
            return self.voice_bot.twilio_handler.generate_twiml_response(
                final_message, gather_input=False
            )
            
        except Exception as e:
            logging.error(f"Error ending conversation: {e}")
            return self._generate_fallback_response()
    
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
                    created_at=datetime.utcnow()
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
                'call_duration': (datetime.utcnow() - call_state['start_time']).total_seconds(),
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

