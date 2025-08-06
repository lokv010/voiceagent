import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from services.azure_speech import AzureSpeechProcessor
from services.twilio_handler import TwilioVoiceHandler
from services.conversation_engine import UnifiedConversationEngine
from services.lead_scorer import UnifiedLeadScorer
from models.prospect import ProspectManager
from models.database import CallHistory, CallOutcome, Prospect
from utils.helpers import serialize_conversation_log, DateTimeEncoder
import json

class UnifiedVoiceBot:
    def __init__(self, config, db_manager):
        """Initialize the unified voice bot with all services"""
        
        # Initialize all service components
        self.speech_processor = AzureSpeechProcessor(
            speech_key=config.AZURE_SPEECH_KEY,
            speech_region=config.AZURE_SPEECH_REGION,
            text_analytics_key=config.AZURE_TEXT_ANALYTICS_KEY,
            text_analytics_endpoint=config.AZURE_TEXT_ANALYTICS_ENDPOINT
        )
        
        self.twilio_handler = TwilioVoiceHandler(
            account_sid=config.TWILIO_ACCOUNT_SID,
            auth_token=config.TWILIO_AUTH_TOKEN,
            phone_number=config.TWILIO_PHONE_NUMBER,
            webhook_url=config.WEBHOOK_URL
        )
        
        self.conversation_engine = UnifiedConversationEngine(
            openai_api_key=config.OPENAI_API_KEY
        )
        
        self.lead_scorer = UnifiedLeadScorer()
        
        self.prospect_manager = ProspectManager(db_manager)
        self.db_manager = db_manager
        
        # Configuration
        self.max_conversation_turns = config.MAX_CONVERSATION_TURNS
        self.min_qualification_score = config.MIN_QUALIFICATION_SCORE
        
        # Call state management
        self.active_calls = {}
        
        logging.info("Unified Voice Bot initialized successfully")
    
    # Add this method to the UnifiedVoiceBot class in services/voice_bot.py

    async def initiate_call(self, phone_number: str, call_type: str = 'auto') -> Dict:
        """Initiate a call with proper session management"""
        try:
            # Get prospect context
            prospect_context = self.prospect_manager.get_prospect_context(phone_number)
            
            if not prospect_context:
                logging.error(f"No prospect found for {phone_number}")
                return {'success': False, 'error': 'No prospect found'}
            
            # Check do not call status
            if prospect_context['prospect'].do_not_call:
                logging.warning(f"Attempt to call DNC number: {phone_number}")
                return {'success': False, 'error': 'Number is on do not call list'}
            
            # Increment contact attempts using prospect_id
            self.prospect_manager.increment_contact_attempts(prospect_context['prospect_id'])
            
            # Initiate Twilio call
            call_result = self.twilio_handler.initiate_outbound_call(
                phone_number, prospect_context
            )
            
            if not call_result['success']:
                return call_result
            
            # Initialize call state with prospect_id for database operations
            call_sid = call_result['call_sid']
            self.active_calls[call_sid] = {
                'phone_number': phone_number,
                'prospect_context': prospect_context,
                'prospect_id': prospect_context['prospect_id'],  # Store ID separately
                'call_type': call_type,
                'conversation_history': [],
                'start_time': datetime.utcnow(),
                'current_turn': 0,
                'call_outcome': None,
                'answered_by_human': False
            }
            
            logging.info(f"Call initiated successfully: {call_sid} to {phone_number}")
            return call_result
            
        except Exception as e:
            logging.error(f"Error initiating call: {str(e)}")
            return {'success': False, 'error': str(e)}

    # Update the _save_call_results method in services/voice_bot.py



    async def _save_call_results(self, call_sid: str, call_state: Dict, call_results: Dict, reason: str):
        """Save call results with proper JSON serialization"""
        try:
            prospect_id = call_state['prospect_id']
            
            # Serialize conversation history properly
            conversation_log = serialize_conversation_log(call_state['conversation_history'])
            
            # Serialize component scores (ensure it's JSON serializable)
            component_scores = call_results['scoring_result'].get('component_scores', {})
            if component_scores:
                # Ensure all values are JSON serializable
                component_scores = {k: float(v) if isinstance(v, (int, float)) else v 
                                for k, v in component_scores.items()}
            
            # Create call history record using a new session
            session = self.db_manager.get_session()
            try:
                call_record = CallHistory(
                    prospect_id=prospect_id,
                    call_sid=call_sid,
                    call_type=call_state['call_type'],
                    call_duration=int(call_results['conversation_data']['call_duration']),
                    call_outcome=call_results.get('call_outcome', 'completed'),
                    conversation_log=conversation_log,  # Use serialized version
                    conversation_summary=call_results.get('conversation_summary', ''),
                    qualification_score=float(call_results['scoring_result']['final_score']),
                    component_scores=component_scores,  # Use serialized version
                    next_action=self._determine_next_action(call_results['scoring_result']),
                    called_at=call_state['start_time'],
                    completed_at=datetime.utcnow()
                )
                
                # Add recording URL if available
                if call_results.get('call_details'):
                    recordings = self.twilio_handler.get_call_recordings(call_sid)
                    if recordings:
                        call_record.recording_url = recordings[0]['media_url']
                        call_record.recording_duration = recordings[0]['duration']
                
                session.add(call_record)
                session.commit()
                
                logging.info(f"Call results saved for {call_sid}")
                
            except Exception as e:
                logging.error(f"Error saving call record: {str(e)}")
                session.rollback()
                raise
            finally:
                session.close()
                
        except Exception as e:
            logging.error(f"Error saving call results: {str(e)}")



    async def _update_prospect_after_call(self, call_state: Dict, call_results: Dict):
        """Update prospect after call with proper session management"""
        try:
            prospect_id = call_state['prospect_id']
            
            # Update prospect scores using the prospect manager
            self.prospect_manager.update_prospect_score(
                prospect_id,
                call_results['scoring_result']['final_score'],
                call_results['scoring_result']['component_scores']
            )
            
            # Update call status using separate session
            session = self.db_manager.get_session()
            try:
                prospect = session.query(Prospect).filter(Prospect.id == prospect_id).first()
                if prospect:
                    prospect.call_status = 'completed'
                    prospect.last_contacted = datetime.utcnow()
                    session.commit()
            except Exception as e:
                logging.error(f"Error updating prospect call status: {str(e)}")
                session.rollback()
            finally:
                session.close()
            
        except Exception as e:
            logging.error(f"Error updating prospect after call: {str(e)}")
    

    
    async def handle_webhook_call(self, call_sid: str, request_data: Dict) -> str:
        """Handle incoming webhook from Twilio"""
        try:
            if call_sid not in self.active_calls:
                logging.error(f"Call {call_sid} not found in active calls")
                return self.twilio_handler.generate_twiml_response(
                    "I'm sorry, there was an error. Please try again later.", 
                    gather_input=False
                )
            
            call_state = self.active_calls[call_sid]
            
            # Handle machine detection
            answered_by = request_data.get('AnsweredBy')
            if answered_by == 'machine_start':
                call_state['answered_by_human'] = False
                return await self._handle_answering_machine(call_sid, call_state)
            else:
                call_state['answered_by_human'] = True
            
            # Handle based on call stage
            if call_state['current_turn'] == 0:
                # First interaction - send opening message
                return await self._handle_opening_message(call_sid, call_state)
            else:
                # Process customer response
                return await self._handle_customer_response(call_sid, call_state, request_data)
                
        except Exception as e:
            logging.error(f"Error handling webhook: {str(e)}")
            return self.twilio_handler.generate_twiml_response(
                "I'm sorry, there was a technical issue. Goodbye.", 
                gather_input=False
            )
    
    async def _handle_answering_machine(self, call_sid: str, call_state: Dict) -> str:
        """Handle answering machine detection"""
        try:
            prospect_name = call_state['prospect_context']['prospect'].name
            company_name = self.conversation_engine.templates.get_template(
                call_state['prospect_context']['prospect'].product_category
            )['company_name']
            
            voicemail_message = f"""Hi {prospect_name}, this is Sarah from {company_name}. 
            You recently expressed interest in our services. I'd love to discuss how we can help you. 
            Please call me back at {self.twilio_handler.phone_number} or I'll try reaching you again soon. 
            Thank you!"""
            
            # Log voicemail
            call_state['conversation_history'].append({
                'turn': 0,
                'type': 'agent',
                'message': voicemail_message,
                'timestamp': datetime.utcnow(),
                'is_voicemail': True
            })
            
            call_state['call_outcome'] = CallOutcome.VOICEMAIL.value
            
            return self.twilio_handler.generate_twiml_response(
                voicemail_message, 
                gather_input=False
            )
            
        except Exception as e:
            logging.error(f"Error handling answering machine: {str(e)}")
            return self.twilio_handler.generate_twiml_response(
                "Thank you for your time.", 
                gather_input=False
            )
    
    async def _handle_opening_message(self, call_sid: str, call_state: Dict) -> str:
        """Handle the opening message of the call"""
        try:
            # Generate opening message
            opening_message = self.conversation_engine.generate_opening_message(
                call_state['prospect_context']
            )
            
            # Log the opening
            call_state['conversation_history'].append({
                'turn': 0,
                'type': 'agent',
                'message': opening_message,
                'timestamp': datetime.utcnow()
            })
            
            call_state['current_turn'] += 1
            
            # Generate TwiML response
            return self.twilio_handler.generate_twiml_response(
                opening_message, 
                gather_input=True,
                timeout=10
            )
            
        except Exception as e:
            logging.error(f"Error handling opening message: {str(e)}")
            # Fallback opening
            prospect_name = call_state['prospect_context']['prospect'].name
            fallback_message = f"Hello {prospect_name}, thank you for your interest. How can I help you today?"
            
            return self.twilio_handler.generate_twiml_response(
                fallback_message, 
                gather_input=True
            )
    
    async def _handle_customer_response(self, call_sid: str, call_state: Dict, request_data: Dict) -> str:
        """Process customer response and generate AI reply"""
        try:
            # Extract customer speech
            customer_speech = request_data.get('SpeechResult', '').strip()
            speech_confidence = float(request_data.get('Confidence', 0.0))
            
            # Handle low confidence or empty speech
            if not customer_speech or speech_confidence < 0.4:
                retry_message = "I'm sorry, I didn't catch that clearly. Could you please repeat what you said?"
                return self.twilio_handler.generate_twiml_response(
                    retry_message, 
                    gather_input=True,
                    timeout=8
                )
            
            # Log customer response
            call_state['conversation_history'].append({
                'turn': call_state['current_turn'],
                'type': 'customer',
                'message': customer_speech,
                'confidence': speech_confidence,
                'timestamp': datetime.utcnow()
            })
            
            # Analyze sentiment
            sentiment_result = await self.speech_processor.analyze_sentiment(customer_speech)
            
            # Check for immediate call ending conditions
            if self.conversation_engine.should_end_call(
                customer_speech, 
                call_state['current_turn'], 
                call_state['call_type']
            ):
                return await self._handle_call_ending(call_sid, call_state, 'customer_request')
            
            # Generate AI response
            ai_response = self.conversation_engine.generate_adaptive_response(
                customer_speech,
                call_state['prospect_context'],
                call_state['conversation_history']
            )
            
            # Log AI response
            call_state['conversation_history'].append({
                'turn': call_state['current_turn'],
                'type': 'agent',
                'message': ai_response,
                'sentiment': sentiment_result,
                'timestamp': datetime.utcnow()
            })
            
            call_state['current_turn'] += 1
            
            # Check if we should continue or end
            if call_state['current_turn'] >= self.max_conversation_turns:
                return await self._handle_call_ending(call_sid, call_state, 'max_turns')
            
            # Check for natural conversation ending
            if self._should_end_naturally(customer_speech, call_state):
                return await self._handle_call_ending(call_sid, call_state, 'natural_end')
            
            # Generate TwiML response
            return self.twilio_handler.generate_twiml_response(
                ai_response, 
                gather_input=True,
                timeout=10
            )
            
        except Exception as e:
            logging.error(f"Error processing customer response: {str(e)}")
            return self.twilio_handler.generate_twiml_response(
                "I apologize for the technical difficulty. Thank you for your time. Goodbye.", 
                gather_input=False
            )
    
    async def _handle_call_ending(self, call_sid: str, call_state: Dict, reason: str) -> str:
        """Handle call ending and cleanup"""
        try:
            # Generate appropriate closing message
            closing_message = self._generate_closing_message(call_state, reason)
            
            # Calculate call results
            call_results = await self._calculate_call_results(call_sid, call_state)
            
            # Save to database
            await self._save_call_results(call_sid, call_state, call_results, reason)
            
            # Update prospect
            await self._update_prospect_after_call(call_state, call_results)
            
            # Clean up active call
            del self.active_calls[call_sid]
            
            # Generate final TwiML
            return self.twilio_handler.generate_twiml_response(
                closing_message, 
                gather_input=False
            )
            
        except Exception as e:
            logging.error(f"Error handling call ending: {str(e)}")
            return self.twilio_handler.generate_twiml_response(
                "Thank you for your time. Goodbye!", 
                gather_input=False
            )
    
    def _generate_closing_message(self, call_state: Dict, reason: str) -> str:
        """Generate appropriate closing message based on call outcome"""
        prospect_name = call_state['prospect_context']['prospect'].name
        
        if reason == 'customer_request':
            return f"I understand, {prospect_name}. Thank you for your time and have a great day!"
        elif reason == 'max_turns':
            return f"Thank you for the conversation, {prospect_name}. I'll follow up with you soon. Have a great day!"
        else:  # natural_end or other
            return f"Perfect! Thank you for your time, {prospect_name}. Someone from our team will be in touch soon. Have a wonderful day!"
    
    async def _calculate_call_results(self, call_sid: str, call_state: Dict) -> Dict:
        """Calculate comprehensive call results"""
        try:
            # Extract conversation data
            conversation_data = {
                'customer_responses': [
                    h['message'] for h in call_state['conversation_history'] 
                    if h['type'] == 'customer'
                ],
                'agent_responses': [
                    h['message'] for h in call_state['conversation_history'] 
                    if h['type'] == 'agent'
                ],
                'total_turns': call_state['current_turn'],
                'call_duration': (datetime.utcnow() - call_state['start_time']).total_seconds(),
                'answered_by_human': call_state['answered_by_human']
            }
            
            # Calculate lead score
            scoring_result = self.lead_scorer.calculate_comprehensive_score(
                call_state['prospect_context'], 
                conversation_data
            )
            
            # Get call details from Twilio
            call_details = self.twilio_handler.get_call_details(call_sid)
            
            # Generate conversation summary
            conversation_summary = self._generate_conversation_summary(call_state['conversation_history'])
            
            return {
                'call_sid': call_sid,
                'call_details': call_details,
                'scoring_result': scoring_result,
                'conversation_data': conversation_data,
                'conversation_summary': conversation_summary,
                'call_type': call_state['call_type'],
                'call_outcome': call_state.get('call_outcome', CallOutcome.COMPLETED.value)
            }
            
        except Exception as e:
            logging.error(f"Error calculating call results: {str(e)}")
            return {
                'call_sid': call_sid,
                'error': str(e),
                'scoring_result': {'final_score': 0, 'component_scores': {}},
                'call_outcome': CallOutcome.FAILED.value
            }
      
    def _determine_next_action(self, scoring_result: Dict) -> str:
        """Determine next action based on comprehensive scoring"""
        score = scoring_result['final_score']
        
        if score >= 80:
            return 'schedule_demo'
        elif score >= 60:
            return 'send_information'
        elif score >= 40:
            return 'callback_scheduled'
        elif score >= 20:
            return 'nurture_sequence'
        else:
            return 'not_qualified'
    
    def _generate_conversation_summary(self, conversation_history: List[Dict]) -> str:
        """Generate a summary of the conversation"""
        customer_responses = [h['message'] for h in conversation_history if h['type'] == 'customer']
        
        if not customer_responses:
            return "No customer responses recorded"
        
        # Simple summary generation
        total_responses = len(customer_responses)
        avg_response_length = sum(len(r.split()) for r in customer_responses) / total_responses
        
        # Extract key topics mentioned
        all_responses = ' '.join(customer_responses).lower()
        
        topics = []
        if 'budget' in all_responses or 'cost' in all_responses:
            topics.append('budget discussed')
        if 'timeline' in all_responses or 'when' in all_responses:
            topics.append('timeline mentioned')
        if 'interested' in all_responses:
            topics.append('expressed interest')
        if 'not interested' in all_responses:
            topics.append('not interested')
        
        summary = f"Conversation had {total_responses} customer responses (avg {avg_response_length:.1f} words). "
        if topics:
            summary += f"Key topics: {', '.join(topics)}."
        
        return summary
    
    def _should_end_naturally(self, customer_speech: str, call_state: Dict) -> bool:
        """Check if conversation should end naturally"""
        # Look for buying signals or clear next steps
        buying_signals = [
            'sign me up', 'let\'s do it', 'sounds good', 'when can we start',
            'what\'s the next step', 'how do we proceed', 'i\'m ready'
        ]
        
        customer_lower = customer_speech.lower()
        return any(signal in customer_lower for signal in buying_signals)

    async def handle_call_status_update(self, call_sid: str, status: str, request_data: Dict):
        """Handle call status updates from Twilio"""
        try:
            if call_sid in self.active_calls:
                call_state = self.active_calls[call_sid]
                
                if status in ['completed', 'failed', 'busy', 'no-answer']:
                    # Update call outcome if not already set
                    if not call_state.get('call_outcome'):
                        call_state['call_outcome'] = status
                    
                    # If call ended without conversation, save minimal data
                    if status in ['failed', 'busy', 'no-answer'] and call_state['current_turn'] == 0:
                        await self._save_incomplete_call(call_sid, call_state, status)
                        del self.active_calls[call_sid]
                
                logging.info(f"Call {call_sid} status updated to {status}")
            
        except Exception as e:
            logging.error(f"Error handling call status update: {str(e)}")
    
    async def _save_incomplete_call(self, call_sid: str, call_state: Dict, outcome: str):
        """Save data for incomplete calls (no answer, busy, etc.)"""
        try:
            prospect = call_state['prospect_context']['prospect']
            
            call_record = CallHistory(
                prospect_id=prospect.id,
                call_sid=call_sid,
                call_type=call_state['call_type'],
                call_duration=0,
                call_outcome=outcome,
                conversation_log=[],
                conversation_summary=f"Call {outcome}",
                qualification_score=0,
                next_action='retry_later',
                called_at=call_state['start_time'],
                completed_at=datetime.utcnow()
            )
            
            session = self.db_manager.get_session()
            session.add(call_record)
            session.commit()
            
            logging.info(f"Incomplete call saved: {call_sid} - {outcome}")
            
        except Exception as e:
            logging.error(f"Error saving incomplete call: {str(e)}")