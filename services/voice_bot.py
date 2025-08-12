import asyncio
import logging
from datetime import datetime, timedelta
import os
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
    # Add new method for inbound call state management
    def get_call_state(self, call_sid: str) -> Dict:
        """Get call state from either outbound or inbound active calls"""
        return self.active_calls.get(call_sid) or self.inbound_active_calls.get(call_sid)
    
    def set_call_state(self, call_sid: str, call_state: Dict):
        """Set call state in appropriate collection"""
        if call_state.get('call_type') == 'inbound':
            self.inbound_active_calls[call_sid] = call_state
        else:
            self.active_calls[call_sid] = call_state
    
    def remove_call_state(self, call_sid: str):
        """Remove call state from all collections"""
        self.active_calls.pop(call_sid, None)
        self.inbound_active_calls.pop(call_sid, None)
        self.call_cleanup_tasks.pop(call_sid, None)
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
        """Save call results with proper JSON serialization - supports both inbound and outbound"""
        try:
            prospect_id = call_state.get('prospect_id')
            if not prospect_id:
                logging.warning(f"No prospect_id found for call {call_sid}")
                return
            
            # Serialize conversation history properly
            conversation_log = serialize_conversation_log(call_state['conversation_history'])
            
            # Serialize component scores (ensure it's JSON serializable)
            component_scores = call_results['scoring_result'].get('component_scores', {})
            if component_scores:
                component_scores = {k: float(v) if isinstance(v, (int, float)) else v 
                                for k, v in component_scores.items()}
            
            # Create call history record using a new session
            session = self.db_manager.get_session()
            try:
                call_record = CallHistory(
                    prospect_id=prospect_id,
                    call_sid=call_sid,
                    call_type=call_state.get('call_type', 'outbound'),
                    call_duration=int(call_results.get('conversation_data', {}).get('call_duration', 0)),
                    call_outcome=call_results.get('call_outcome', 'completed'),
                    conversation_log=conversation_log,
                    conversation_summary=call_results.get('conversation_summary', ''),
                    qualification_score=float(call_results['scoring_result'].get('final_score', 0)),
                    component_scores=component_scores,
                    next_action=self._determine_next_action(call_results['scoring_result']),
                    called_at=call_state.get('start_time', datetime.utcnow()),
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
                
                logging.info(f"Call results saved for {call_sid} (type: {call_state.get('call_type', 'outbound')})")
                
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
            prospect_id = call_state.get('prospect_id')
            if not prospect_id:
                logging.warning("No prospect_id found, skipping prospect update")
                return
            
            # Update prospect scores using the prospect manager
            self.prospect_manager.update_prospect_score(
                prospect_id,
                call_results['scoring_result']['final_score'],
                call_results['scoring_result'].get('component_scores', {})
            )
            
            # Update call status using separate session
            session = self.db_manager.get_session()
            try:
                prospect = session.query(Prospect).filter(Prospect.id == prospect_id).first()
                if prospect:
                    prospect.call_status = 'completed'
                    prospect.last_contacted = datetime.utcnow()
                    session.commit()
                    logging.info(f"Updated prospect {prospect_id} after call")
                else:
                    logging.warning(f"Prospect {prospect_id} not found for update")
            except Exception as e:
                logging.error(f"Error updating prospect call status: {str(e)}")
                session.rollback()
            finally:
                session.close()
            
        except Exception as e:
            logging.error(f"Error updating prospect after call: {str(e)}")
    
    # Add helper method for call cleanup
    async def cleanup_call(self, call_sid: str, delay_seconds: int = 30):
        """Schedule delayed cleanup of call state"""
        try:
            await asyncio.sleep(delay_seconds)
            
            # Check if call still exists and clean up
            if call_sid in self.active_calls or call_sid in self.inbound_active_calls:
                logging.info(f"Performing delayed cleanup for call: {call_sid}")
                self.remove_call_state(call_sid)
                
        except Exception as e:
            logging.error(f"Error in call cleanup: {e}")
    
    def schedule_call_cleanup(self, call_sid: str, delay_seconds: int = 30):
        """Schedule background cleanup task"""
        if call_sid not in self.call_cleanup_tasks:
            task = asyncio.create_task(self.cleanup_call(call_sid, delay_seconds))
            self.call_cleanup_tasks[call_sid] = task
    

    
    async def handle_webhook_call(self, call_sid: str, request_data: Dict) -> str:
        """Handle incoming webhook from Twilio - supports both inbound and outbound"""
        try:
            # Check both active call collections
            call_state = self.get_call_state(call_sid)
            
            if not call_state:
                logging.error(f"Call {call_sid} not found in active calls")
                return self.twilio_handler.generate_twiml_response(
                    "I'm sorry, there was an error. Please try again later.", 
                    gather_input=False
                )
            
            # Handle based on call type
            if call_state.get('call_type') == 'inbound':
                # For inbound calls, delegate to the inbound handler
                # This method should not be called directly for inbound calls
                # as they use the OpenAI handler, but keeping for safety
                return await self._handle_inbound_fallback(call_sid, call_state, request_data)
            else:
                # Handle outbound calls as before
                return await self._handle_outbound_call(call_sid, call_state, request_data)
                
        except Exception as e:
            logging.error(f"Error handling webhook: {str(e)}")
            return self.twilio_handler.generate_twiml_response(
                "I'm sorry, there was a technical issue. Goodbye.", 
                gather_input=False
            )
        
    async def _handle_inbound_fallback(self, call_sid: str, call_state: Dict, request_data: Dict) -> str:
        """Fallback handler for inbound calls when OpenAI handler isn't available"""
        try:
            customer_speech = request_data.get('SpeechResult', '').strip()
            
            # Simple fallback responses for inbound calls
            if not customer_speech:
                return self.twilio_handler.generate_twiml_response(
                    "I'm sorry, I didn't catch that. How can I help you today?",
                    gather_input=True
                )
            
            # Basic intent detection
            speech_lower = customer_speech.lower()
            
            if any(word in speech_lower for word in ['human', 'agent', 'person']):
                return self.twilio_handler.generate_transfer_twiml(
                    os.getenv('AGENT_TRANSFER_NUMBER', '+12267537919'),
                    "I'll connect you with a specialist right away."
                )
            
            elif any(word in speech_lower for word in ['not interested', 'no thank']):
                return self.twilio_handler.generate_twiml_response(
                    "Thank you for your time. Have a great day!",
                    gather_input=False
                )
            
            else:
                # General solar response
                return self.twilio_handler.generate_twiml_response(
                    "I'd be happy to help you explore solar options. Do you own your home?",
                    gather_input=True
                )
                
        except Exception as e:
            logging.error(f"Error in inbound fallback: {e}")
            return self.twilio_handler.generate_twiml_response(
                "Thank you for calling. Goodbye!",
                gather_input=False
            )
        
    async def _handle_outbound_call(self, call_sid: str, call_state: Dict, request_data: Dict) -> str:
        """Handle outbound calls (existing logic)"""
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

    # Update handle_call_status_update to support both call types
    async def handle_call_status_update(self, call_sid: str, status: str, request_data: Dict):
        """Handle call status updates from Twilio - supports both inbound and outbound"""
        try:
            call_state = self.get_call_state(call_sid)
            
            if call_state:
                if status in ['completed', 'failed', 'busy', 'no-answer']:
                    # Update call outcome if not already set
                    if not call_state.get('call_outcome'):
                        call_state['call_outcome'] = status
                    
                    # If call ended without conversation, save minimal data
                    if status in ['failed', 'busy', 'no-answer'] and call_state.get('current_turn', 0) == 0:
                        await self._save_incomplete_call(call_sid, call_state, status)
                    
                    # Schedule cleanup with delay to handle late webhooks
                    self.schedule_call_cleanup(call_sid, delay_seconds=60)
                
                logging.info(f"Call {call_sid} status updated to {status} (type: {call_state.get('call_type', 'unknown')})")
            else:
                logging.info(f"Status update for unknown call: {call_sid}")
            
        except Exception as e:
            logging.error(f"Error handling call status update: {str(e)}")
    
    # Add method to get all active calls (both inbound and outbound)
    def get_all_active_calls(self) -> Dict:
        """Get all active calls regardless of type"""
        all_calls = {}
        all_calls.update(self.active_calls)
        all_calls.update(self.inbound_active_calls)
        return all_calls
    
    # Add method to get active call count
    def get_active_call_count(self) -> Dict:
        """Get count of active calls by type"""
        return {
            'outbound': len(self.active_calls),
            'inbound': len(self.inbound_active_calls),
            'total': len(self.active_calls) + len(self.inbound_active_calls)
        }
    
    async def _save_incomplete_call(self, call_sid: str, call_state: Dict, outcome: str):
        """Save data for incomplete calls (no answer, busy, etc.) - supports both call types"""
        try:
            prospect_id = call_state.get('prospect_id')
            if not prospect_id:
                logging.warning(f"No prospect_id for incomplete call {call_sid}")
                return
            
            call_record = CallHistory(
                prospect_id=prospect_id,
                call_sid=call_sid,
                call_type=call_state.get('call_type', 'outbound'),
                call_duration=0,
                call_outcome=outcome,
                conversation_log=[],
                conversation_summary=f"Call {outcome}",
                qualification_score=0,
                next_action='retry_later',
                called_at=call_state.get('start_time', datetime.utcnow()),
                completed_at=datetime.utcnow()
            )
            
            session = self.db_manager.get_session()
            try:
                session.add(call_record)
                session.commit()
                logging.info(f"Incomplete call saved: {call_sid} - {outcome}")
            finally:
                session.close()
            
        except Exception as e:
            logging.error(f"Error saving incomplete call: {str(e)}")
