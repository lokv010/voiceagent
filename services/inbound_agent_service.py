"""
Inbound Call Handler Service

Handles incoming calls for lead qualification and routing
"""

import logging
from datetime import datetime, timedelta
import os
from typing import Dict, List, Optional
from services.conversation_engine import ConversationTemplates
from models.database import Prospect, CallHistory, ProspectSource, CallOutcome
from utils.helpers import format_phone_number, is_business_hours
import asyncio

class InboundCallHandler:
    def __init__(self, voice_bot, db_manager, config):
        """Initialize inbound call handler"""
        self.voice_bot = voice_bot
        self.db_manager = db_manager
        self.config = config
        
        # Inbound call configuration
        self.business_hours = {
            'start': 9,  # 9 AM
            'end': 17,   # 5 PM
            'timezone': 'UTC',
            'weekdays_only': True
        }
        
        # Call routing settings
        self.max_queue_time = 300  # 5 minutes
        self.agent_transfer_number = os.getenv('AGENT_TRANSFER_NUMBER', '+12267537919')
        
        # Inbound conversation templates
        self.inbound_templates = {
            'greeting': "Thank you for calling {company_name}. This is Sarah, your AI assistant. How can I help you today?",
            'after_hours': "Thank you for calling {company_name}. Our office hours are Monday through Friday, 9 AM to 5 PM. Please leave a message and we'll call you back, or press 1 to speak with our AI assistant.",
            'transfer_intro': "I'd be happy to connect you with one of our specialists. Please hold while I transfer your call.",
            'qualification_start': "I'd love to learn more about your needs to make sure I connect you with the right person. Do you have a few minutes to chat?",
        }
        
        logging.info("Inbound Call Handler initialized")
    
    async def handle_inbound_call(self, call_sid: str, request_data: Dict) -> str:
        """Handle incoming call routing and initial processing"""
        try:
            caller_number = request_data.get('From', '').strip()
            called_number = request_data.get('To', '').strip()
            call_status = request_data.get('CallStatus', '')
            
            logging.info(f"Inbound call received: {call_sid} from {caller_number}")
            
            # Format caller number
            formatted_number = format_phone_number(caller_number)
            if not formatted_number:
                formatted_number = caller_number
            
            # Check if this is a known prospect
            prospect_context = await self._get_or_create_inbound_prospect(formatted_number)
            
            # Initialize inbound call state
            call_state = {
                'phone_number': formatted_number,
                'prospect_context': prospect_context,
                'prospect_id': prospect_context['prospect_id'],
                'call_type': 'inbound',
                'conversation_history': [],
                'start_time': datetime.utcnow(),
                'current_turn': 0,
                'call_outcome': None,
                'answered_by_human': True,  # Inbound calls are always answered by humans
                'inbound_reason': None,
                'transfer_requested': False
            }
            
            # Store in active calls
            self.voice_bot.active_calls[call_sid] = call_state
            
            # Route the call based on business hours and availability
            return await self._route_inbound_call(call_sid, call_state)
            
        except Exception as e:
            logging.error(f"Error handling inbound call: {str(e)}")
            return self._generate_error_response()
    
    async def _route_inbound_call(self, call_sid: str, call_state: Dict) -> str:
        """Route inbound call based on business hours and configuration"""
        try:
            current_time = datetime.utcnow()
            
            # Check business hours
            if not is_business_hours(current_time):
                return await self._handle_after_hours_call(call_sid, call_state)
            
            # Check if prospect is on do not call list
            prospect = call_state['prospect_context']['prospect']
            if prospect.do_not_call:
                return await self._handle_dnc_caller(call_sid, call_state)
            
            # Start AI qualification process
            return await self._start_inbound_qualification(call_sid, call_state)
            
        except Exception as e:
            logging.error(f"Error routing inbound call: {str(e)}")
            return self._generate_error_response()
    
    async def _handle_after_hours_call(self, call_sid: str, call_state: Dict) -> str:
        """Handle calls outside business hours"""
        try:
            company_name = self._get_company_name()
            
            # Create menu for after hours
            after_hours_message = self.inbound_templates['after_hours'].format(
                company_name=company_name
            )
            
            # Log the after hours interaction
            call_state['conversation_history'].append({
                'turn': 0,
                'type': 'agent',
                'message': after_hours_message,
                'timestamp': datetime.utcnow(),
                'is_after_hours': True
            })
            
            # Generate TwiML with options
            return self.voice_bot.twilio_handler.generate_twiml_response(
                after_hours_message,
                gather_input=True,
                timeout=10,
                action_url=f"{self.config.WEBHOOK_URL}/inbound-webhook/after-hours"
            )
            
        except Exception as e:
            logging.error(f"Error handling after hours call: {str(e)}")
            return self._generate_error_response()
    
    async def _handle_dnc_caller(self, call_sid: str, call_state: Dict) -> str:
        """Handle callers on do not call list"""
        try:
            message = "Thank you for calling. As requested, we have you on our do not call list. If you'd like to be removed from this list, please press 1 to speak with an agent."
            
            call_state['conversation_history'].append({
                'turn': 0,
                'type': 'agent',
                'message': message,
                'timestamp': datetime.utcnow(),
                'is_dnc_caller': True
            })
            
            return self.voice_bot.twilio_handler.generate_twiml_response(
                message,
                gather_input=True,
                timeout=10,
                action_url=f"{self.config.WEBHOOK_URL}/inbound-webhook/dnc-options"
            )
            
        except Exception as e:
            logging.error(f"Error handling DNC caller: {str(e)}")
            return self._generate_error_response()
    
    async def _start_inbound_qualification(self, call_sid: str, call_state: Dict) -> str:
        """Start the inbound qualification process"""
        try:
            prospect = call_state['prospect_context']['prospect']
            company_name = self._get_company_name()
            
            # Generate personalized greeting
            if prospect.name and prospect.source != ProspectSource.WEBSITE_VISITOR.value:
                greeting = f"Thank you for calling {company_name}, {prospect.name}. This is Sarah, your AI assistant. How can I help you today?"
            else:
                greeting = self.inbound_templates['greeting'].format(
                    company_name=company_name
                )
            
            # Log the greeting
            call_state['conversation_history'].append({
                'turn': 0,
                'type': 'agent',
                'message': greeting,
                'timestamp': datetime.utcnow()
            })
            
            call_state['current_turn'] += 1
            
            return self.voice_bot.twilio_handler.generate_twiml_response(
                greeting,
                gather_input=True,
                timeout=15,
                action_url=f"{self.config.WEBHOOK_URL}/inbound-webhook/process"
            )
            
        except Exception as e:
            logging.error(f"Error starting inbound qualification: {str(e)}")
            return self._generate_error_response()
    
    async def handle_inbound_response(self, call_sid: str, request_data: Dict) -> str:
        """Process customer response during inbound call"""
        try:
            if call_sid not in self.voice_bot.active_calls:
                logging.error(f"Inbound call {call_sid} not found in active calls")
                return self._generate_error_response()
            
            call_state = self.voice_bot.active_calls[call_sid]
            
            # Extract customer speech
            customer_speech = request_data.get('SpeechResult', '').strip()
            speech_confidence = float(request_data.get('Confidence', 0.0))
            
            # Handle low confidence or empty speech
            if not customer_speech or speech_confidence < 0.4:
                retry_message = "I'm sorry, I didn't catch that clearly. Could you please repeat what you said?"
                return self.voice_bot.twilio_handler.generate_twiml_response(
                    retry_message, 
                    gather_input=True,
                    timeout=10
                )
            
            # Log customer response
            call_state['conversation_history'].append({
                'turn': call_state['current_turn'],
                'type': 'customer',
                'message': customer_speech,
                'confidence': speech_confidence,
                'timestamp': datetime.utcnow()
            })
            
            # Analyze customer intent
            intent = await self._analyze_inbound_intent(customer_speech, call_state)
            
            # Handle based on intent
            if intent == 'transfer_request':
                return await self._handle_transfer_request(call_sid, call_state)
            elif intent == 'complaint':
                return await self._handle_complaint(call_sid, call_state, customer_speech)
            elif intent == 'sales_inquiry':
                return await self._handle_sales_inquiry(call_sid, call_state, customer_speech)
            elif intent == 'support_request':
                return await self._handle_support_request(call_sid, call_state, customer_speech)
            else:
                return await self._continue_inbound_qualification(call_sid, call_state, customer_speech)
            
        except Exception as e:
            logging.error(f"Error processing inbound response: {str(e)}")
            return self._generate_error_response()
    
    async def _analyze_inbound_intent(self, customer_speech: str, call_state: Dict) -> str:
        """Analyze customer intent from their speech"""
        speech_lower = customer_speech.lower()
        
        # Transfer requests
        transfer_keywords = ['speak to', 'talk to', 'human', 'agent', 'representative', 'manager', 'person']
        if any(keyword in speech_lower for keyword in transfer_keywords):
            return 'transfer_request'
        
        # Complaints
        complaint_keywords = ['complaint', 'problem', 'issue', 'unhappy', 'dissatisfied', 'angry', 'frustrated']
        if any(keyword in speech_lower for keyword in complaint_keywords):
            return 'complaint'
        
        # Sales inquiries
        sales_keywords = ['buy', 'purchase', 'price', 'cost', 'product', 'service', 'interested in', 'information about']
        if any(keyword in speech_lower for keyword in sales_keywords):
            return 'sales_inquiry'
        
        # Support requests
        support_keywords = ['help', 'support', 'how to', 'technical', 'not working', 'broken']
        if any(keyword in speech_lower for keyword in support_keywords):
            return 'support_request'
        
        return 'general_inquiry'
    
    async def _handle_transfer_request(self, call_sid: str, call_state: Dict) -> str:
        """Handle request to transfer to human agent"""
        try:
            call_state['transfer_requested'] = True
            
            # Check if agents are available (simplified check)
            if is_business_hours():
                transfer_message = self.inbound_templates['transfer_intro']
                
                call_state['conversation_history'].append({
                    'turn': call_state['current_turn'],
                    'type': 'agent',
                    'message': transfer_message,
                    'timestamp': datetime.utcnow(),
                    'action': 'transfer_initiated'
                })
                
                # Generate transfer TwiML
                return self.voice_bot.twilio_handler.generate_transfer_twiml(
                    self.agent_transfer_number,
                    transfer_message
                )
            else:
                # After hours - offer callback
                callback_message = "I'd be happy to have someone call you back during business hours. Can you please provide your name and the best number to reach you?"
                
                return self.voice_bot.twilio_handler.generate_twiml_response(
                    callback_message,
                    gather_input=True,
                    timeout=15
                )
                
        except Exception as e:
            logging.error(f"Error handling transfer request: {str(e)}")
            return self._generate_error_response()
    
    async def _handle_sales_inquiry(self, call_sid: str, call_state: Dict, customer_speech: str) -> str:
        """Handle sales-related inquiries"""
        try:
            # Start qualification process for sales leads
            qualification_message = self.inbound_templates['qualification_start']
            
            call_state['conversation_history'].append({
                'turn': call_state['current_turn'],
                'type': 'agent',
                'message': qualification_message,
                'timestamp': datetime.utcnow(),
                'intent': 'sales_inquiry'
            })
            
            call_state['current_turn'] += 1
            call_state['inbound_reason'] = 'sales_inquiry'
            
            return self.voice_bot.twilio_handler.generate_twiml_response(
                qualification_message,
                gather_input=True,
                timeout=15
            )
            
        except Exception as e:
            logging.error(f"Error handling sales inquiry: {str(e)}")
            return self._generate_error_response()
    
    async def _continue_inbound_qualification(self, call_sid: str, call_state: Dict, customer_speech: str) -> str:
        """Continue the inbound lead qualification process"""
        try:
            # Use the existing conversation engine with inbound context
            ai_response = self.voice_bot.conversation_engine.generate_adaptive_response(
                customer_speech,
                call_state['prospect_context'],
                call_state['conversation_history']
            )
            
            # Add inbound-specific context to the response
            if call_state['current_turn'] <= 2:
                # Early in conversation - focus on understanding their needs
                ai_response = f"Thank you for calling us. {ai_response}"
            
            # Log AI response
            call_state['conversation_history'].append({
                'turn': call_state['current_turn'],
                'type': 'agent',
                'message': ai_response,
                'timestamp': datetime.utcnow()
            })
            
            call_state['current_turn'] += 1
            
            # Check if we should end or continue
            if call_state['current_turn'] >= 15:  # Longer conversations for inbound
                return await self._handle_inbound_call_ending(call_sid, call_state, 'max_turns')
            
            return self.voice_bot.twilio_handler.generate_twiml_response(
                ai_response,
                gather_input=True,
                timeout=12
            )
            
        except Exception as e:
            logging.error(f"Error continuing inbound qualification: {str(e)}")
            return self._generate_error_response()
    
    async def _handle_inbound_call_ending(self, call_sid: str, call_state: Dict, reason: str) -> str:
        """Handle ending of inbound call"""
        try:
            # Generate appropriate closing
            prospect_name = call_state['prospect_context']['prospect'].name or "there"
            
            if reason == 'transfer_completed':
                closing_message = "You're being transferred now. Thank you for calling!"
            elif call_state.get('transfer_requested'):
                closing_message = f"Thank you for calling, {prospect_name}. Someone will be with you shortly."
            else:
                closing_message = f"Thank you for calling, {prospect_name}. We appreciate your interest and someone from our team will follow up with you soon. Have a great day!"
            
            # Calculate and save call results
            call_results = await self._calculate_inbound_call_results(call_sid, call_state)
            await self._save_inbound_call_results(call_sid, call_state, call_results, reason)
            
            # Update prospect
            await self.voice_bot._update_prospect_after_call(call_state, call_results)
            
            # Clean up
            del self.voice_bot.active_calls[call_sid]
            
            return self.voice_bot.twilio_handler.generate_twiml_response(
                closing_message,
                gather_input=False
            )
            
        except Exception as e:
            logging.error(f"Error handling inbound call ending: {str(e)}")
            return self._generate_error_response()
    
    async def _get_or_create_inbound_prospect(self, phone_number: str) -> Dict:
        """Get existing prospect or create new one for inbound call"""
        try:
            # Try to get existing prospect
            prospect_context = self.voice_bot.prospect_manager.get_prospect_context(phone_number)
            
            if prospect_context:
                # Update source if this is their first inbound call
                prospect = prospect_context['prospect']
                if prospect.source == ProspectSource.COLD_LIST.value:
                    # Upgrade to inbound caller
                    session = self.db_manager.get_session()
                    try:
                        db_prospect = session.query(Prospect).filter(Prospect.id == prospect_context['prospect_id']).first()
                        if db_prospect:
                            db_prospect.source = ProspectSource.WEBSITE_VISITOR.value  # Or create new INBOUND_CALLER enum
                            session.commit()
                    except Exception as e:
                        logging.error(f"Error updating prospect source: {str(e)}")
                        session.rollback()
                    finally:
                        session.close()
                
                return prospect_context
            
            # Create new prospect for unknown caller
            session = self.db_manager.get_session()
            try:
                new_prospect = Prospect(
                    phone_number=phone_number,
                    source=ProspectSource.WEBSITE_VISITOR.value,  # Or create INBOUND_CALLER
                    source_data={'first_call_time': datetime.utcnow().isoformat()},
                    product_interest='general_inquiry',
                    product_category='general',
                    qualification_score=30,  # Higher base score for inbound
                    call_status='active',
                    created_at=datetime.utcnow()
                )
                
                session.add(new_prospect)
                session.commit()
                session.refresh(new_prospect)
                
                # Create context for new prospect
                prospect_data = {
                    'id': new_prospect.id,
                    'phone_number': new_prospect.phone_number,
                    'name': new_prospect.name,
                    'email': new_prospect.email,
                    'source': new_prospect.source,
                    'source_data': new_prospect.source_data,
                    'product_interest': new_prospect.product_interest,
                    'product_category': new_prospect.product_category,
                    'company': new_prospect.company,
                    'job_title': new_prospect.job_title,
                    'industry': new_prospect.industry,
                    'qualification_score': new_prospect.qualification_score,
                    'qualification_stage': new_prospect.qualification_stage,
                    'call_status': new_prospect.call_status,
                    'form_submitted_at': new_prospect.form_submitted_at,
                    'form_data': new_prospect.form_data,
                    'created_at': new_prospect.created_at,
                    'last_contacted': new_prospect.last_contacted,
                    'contact_attempts': new_prospect.contact_attempts,
                    'do_not_call': new_prospect.do_not_call
                }
                
                context = {
                    'prospect': type('ProspectData', (), prospect_data)(),
                    'prospect_id': new_prospect.id,
                    'call_history': [],
                    'is_warm_lead': False,
                    'previous_conversations': 0,
                    'last_call_outcome': None,
                    'last_call_score': None
                }
                
                logging.info(f"Created new inbound prospect: {new_prospect.id}")
                return context
                
            except Exception as e:
                logging.error(f"Error creating inbound prospect: {str(e)}")
                session.rollback()
                raise
            finally:
                session.close()
                
        except Exception as e:
            logging.error(f"Error getting/creating inbound prospect: {str(e)}")
            raise
    
    async def _calculate_inbound_call_results(self, call_sid: str, call_state: Dict) -> Dict:
        """Calculate results for inbound call"""
        try:
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
                'answered_by_human': call_state['answered_by_human'],
                'inbound_reason': call_state.get('inbound_reason', 'general_inquiry'),
                'transfer_requested': call_state.get('transfer_requested', False)
            }
            
            # Calculate lead score with inbound adjustments
            scoring_result = self.voice_bot.lead_scorer.calculate_comprehensive_score(
                call_state['prospect_context'], 
                conversation_data
            )
            
            # Boost score for inbound calls (they called us!)
            scoring_result['final_score'] = min(scoring_result['final_score'] + 15, 100)
            
            # Get call details
            call_details = self.voice_bot.twilio_handler.get_call_details(call_sid)
            
            # Generate summary
            conversation_summary = self._generate_inbound_summary(call_state['conversation_history'], conversation_data)
            
            return {
                'call_sid': call_sid,
                'call_details': call_details,
                'scoring_result': scoring_result,
                'conversation_data': conversation_data,
                'conversation_summary': conversation_summary,
                'call_type': 'inbound',
                'call_outcome': call_state.get('call_outcome', CallOutcome.COMPLETED.value)
            }
            
        except Exception as e:
            logging.error(f"Error calculating inbound call results: {str(e)}")
            return {
                'call_sid': call_sid,
                'error': str(e),
                'scoring_result': {'final_score': 30, 'component_scores': {}},  # Higher base for inbound
                'call_outcome': CallOutcome.FAILED.value
            }
    
    async def _save_inbound_call_results(self, call_sid: str, call_state: Dict, call_results: Dict, reason: str):
        """Save inbound call results to database"""
        try:
            # Use the existing save method but mark as inbound
            await self.voice_bot._save_call_results(call_sid, call_state, call_results, reason)
            logging.info(f"Inbound call results saved for {call_sid}")
            
        except Exception as e:
            logging.error(f"Error saving inbound call results: {str(e)}")
    
    def _generate_inbound_summary(self, conversation_history: List[Dict], conversation_data: Dict) -> str:
        """Generate summary specific to inbound calls"""
        try:
            summary_parts = []
            
            # Basic stats
            customer_responses = conversation_data.get('customer_responses', [])
            total_responses = len(customer_responses)
            call_duration = conversation_data.get('call_duration', 0)
            
            summary_parts.append(f"Inbound call with {total_responses} customer responses")
            summary_parts.append(f"Duration: {int(call_duration/60)}m {int(call_duration%60)}s")
            
            # Analyze reason for calling
            if conversation_data.get('inbound_reason'):
                summary_parts.append(f"Reason: {conversation_data['inbound_reason']}")
            
            # Check for transfer
            if conversation_data.get('transfer_requested'):
                summary_parts.append("Transfer requested")
            
            # Analyze sentiment and topics
            all_responses = ' '.join(customer_responses).lower()
            
            topics = []
            if any(word in all_responses for word in ['price', 'cost', 'budget']):
                topics.append('pricing discussed')
            if any(word in all_responses for word in ['buy', 'purchase', 'interested']):
                topics.append('purchase intent')
            if any(word in all_responses for word in ['problem', 'issue', 'help']):
                topics.append('support needed')
            
            if topics:
                summary_parts.append(f"Topics: {', '.join(topics)}")
            
            return '. '.join(summary_parts) + '.'
            
        except Exception as e:
            logging.error(f"Error generating inbound summary: {str(e)}")
            return "Inbound call summary generation failed"
    
    def _get_company_name(self) -> str:
        """Get company name from configuration or default"""
        return getattr(self.config, 'COMPANY_NAME', 'ProServices')
    
    def _generate_error_response(self) -> str:
        """Generate error response TwiML"""
        return self.voice_bot.twilio_handler.generate_twiml_response(
            "I'm sorry, we're experiencing technical difficulties. Please try calling back later.",
            gather_input=False
        )
    
    async def _handle_complaint(self, call_sid: str, call_state: Dict, customer_speech: str) -> str:
        """Handle customer complaints"""
        try:
            empathy_message = "I'm sorry to hear about your concern. I want to make sure we address this properly. Can you tell me more about what happened?"
            
            call_state['conversation_history'].append({
                'turn': call_state['current_turn'],
                'type': 'agent',
                'message': empathy_message,
                'timestamp': datetime.utcnow(),
                'intent': 'complaint_handling'
            })
            
            call_state['current_turn'] += 1
            call_state['inbound_reason'] = 'complaint'
            
            return self.voice_bot.twilio_handler.generate_twiml_response(
                empathy_message,
                gather_input=True,
                timeout=20  # Give them more time to explain
            )
            
        except Exception as e:
            logging.error(f"Error handling complaint: {str(e)}")
            return self._generate_error_response()
    
    async def _handle_support_request(self, call_sid: str, call_state: Dict, customer_speech: str) -> str:
        """Handle support requests"""
        try:
            support_message = "I'd be happy to help you with that. Can you describe the issue you're experiencing in more detail?"
            
            call_state['conversation_history'].append({
                'turn': call_state['current_turn'],
                'type': 'agent',
                'message': support_message,
                'timestamp': datetime.utcnow(),
                'intent': 'support_request'
            })
            
            call_state['current_turn'] += 1
            call_state['inbound_reason'] = 'support_request'
            
            return self.voice_bot.twilio_handler.generate_twiml_response(
                support_message,
                gather_input=True,
                timeout=15
            )
            
        except Exception as e:
            logging.error(f"Error handling support request: {str(e)}")
            return self._generate_error_response()