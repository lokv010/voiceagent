from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.base.exceptions import TwilioException
import logging
from datetime import datetime
from typing import Dict, List, Optional

class TwilioVoiceHandler:
    def __init__(self, account_sid: str, auth_token: str, phone_number: str, webhook_url: str):
        """Initialize Twilio client"""
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.phone_number = phone_number
        self.webhook_url = webhook_url
        
        # Initialize Twilio client
        self.client = Client(account_sid, auth_token)
        
        # Verify phone number
        try:
            incoming_phone_numbers = self.client.incoming_phone_numbers.list()
            if not any(num.phone_number == phone_number for num in incoming_phone_numbers):
                logging.warning(f"Phone number {phone_number} not found in Twilio account")
        except Exception as e:
            logging.error(f"Error verifying Twilio phone number: {str(e)}")
        
        logging.info(f"Twilio Voice Handler initialized with number: {phone_number}")
    
    def initiate_outbound_call(self, to_number: str, prospect_context: Dict) -> Dict:
        """Initiate an outbound call"""
        try:
            # Prepare webhook URL with context
            webhook_with_params = f"{self.webhook_url}/voice-webhook"
            
            # Create call
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=webhook_with_params,
                method='POST',
                timeout=30,  # Ring for 30 seconds
                record=True,  # Record the call for quality assurance
                status_callback=f"{self.webhook_url}/voice-webhook/status",
                status_callback_event=[
                    'initiated', 'ringing', 'answered', 'completed', 'busy', 'failed', 'no-answer'
                ],
                status_callback_method='POST',
                machine_detection='Enable',  # Detect answering machines
                machine_detection_timeout=30
            )
            
            logging.info(f"Call initiated: {call.sid} to {to_number}")
            
            return {
                'success': True,
                'call_sid': call.sid,
                'status': call.status,
                'to': to_number,
                'from': self.phone_number
            }
            
        except TwilioException as e:
            logging.error(f"Twilio call initiation error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_code': getattr(e, 'code', None),
                'call_sid': None
            }
        except Exception as e:
            logging.error(f"Unexpected error initiating call: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'call_sid': None
            }
    
    def generate_twiml_response(self, message: str, gather_input: bool = True, 
                               timeout: int = 10, action_url: str = None,enable_partial: bool = True) -> str:
        """Generate TwiML response for voice interaction"""
        try:
            response = VoiceResponse()
            
            if gather_input:
                # Configure speech gathering
                action_url = action_url or f"{self.webhook_url}/inbound-webhook/process"
                
                gather = Gather(
                    input='speech',
                    action=action_url,
                    method='POST',
                    timeout=timeout,
                    speech_timeout=2,  # Silence after speech
                    language='en-US',
                    enhanced=True,  # Use enhanced speech recognition
                    speech_model='phone_call',  # Optimized for phone calls
                    partial_result_callback=f"{self.webhook_url}/inbound-webhook/process" if enable_partial else None,
                    partial_result_callback_method='POST' if enable_partial else None
                    )
                
                # Say the message and wait for response
                gather.say(
                    message, 
                    voice='Polly.Joanna',  # High-quality neural voice
                    language='en-US'
                )
                
                response.append(gather)
                
                # Fallback if no input is received
                response.say(
                    "I didn't receive any input. Thank you for your time. Goodbye.",
                    voice='Polly.Joanna'
                )
                response.hangup()
                
            else:
                # Just say message and hangup
                response.say(
                    message, 
                    voice='Polly.Joanna',
                    language='en-US'
                )
                response.hangup()
            
            return str(response)
            
        except Exception as e:
            logging.error(f"Error generating TwiML: {str(e)}")
            # Fallback TwiML
            fallback_response = VoiceResponse()
            fallback_response.say("Thank you for your time. Goodbye.")
            fallback_response.hangup()
            return str(fallback_response)
    
    def generate_transfer_twiml(self, transfer_number: str, message: str = None) -> str:
        """Generate TwiML to transfer call to human agent"""
        try:
            response = VoiceResponse()
            
            if message:
                response.say(message, voice='Polly.Joanna')
            
            # Dial the transfer number
            dial = response.dial(
                timeout=30,
                caller_id=self.phone_number,
                record='record-from-answer'
            )
            dial.number(transfer_number)
            
            # If transfer fails
            response.say(
                "I'm sorry, I couldn't connect you to an agent right now. Please try calling back later.",
                voice='Polly.Joanna'
            )
            response.hangup()
            
            return str(response)
            
        except Exception as e:
            logging.error(f"Error generating transfer TwiML: {str(e)}")
            fallback_response = VoiceResponse()
            fallback_response.say("Thank you for your time. Goodbye.")
            fallback_response.hangup()
            return str(fallback_response)
    
    def get_call_details(self, call_sid: str) -> Optional[Dict]:
        """Get details of a specific call"""
        try:
            call = self.client.calls(call_sid).fetch()
            
            return {
                'sid': call.sid,
                'status': call.status,
                'duration': call.duration,
                'start_time': call.start_time,
                'end_time': call.end_time,
                'direction': call.direction,
                'answered_by': call.answered_by,
                'price': float(call.price) if call.price else 0.0,
                'price_unit': call.price_unit,
                'forwarded_from': call.forwarded_from,
                'caller_name': call.caller_name,
                'uri': call.uri
            }
            
        except TwilioException as e:
            logging.error(f"Error fetching call details: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error fetching call details: {str(e)}")
            return None
    
    def get_call_recordings(self, call_sid: str) -> List[Dict]:
        """Get recordings for a specific call"""
        try:
            recordings = self.client.recordings.list(call_sid=call_sid)
            
            return [
                {
                    'sid': recording.sid,
                    'duration': recording.duration,
                    'date_created': recording.date_created,
                    'channels': recording.channels,
                    'uri': recording.uri,
                    'media_url': f"https://api.twilio.com{recording.uri.replace('.json', '.wav')}",
                    'file_size': getattr(recording, 'file_size', None)
                }
                for recording in recordings
            ]
            
        except TwilioException as e:
            logging.error(f"Error fetching recordings: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Unexpected error fetching recordings: {str(e)}")
            return []
    
    def update_call_status(self, call_sid: str, status: str) -> bool:
        """Update call status (complete, cancel)"""
        try:
            if status.lower() == 'cancel':
                self.client.calls(call_sid).update(status='canceled')
            elif status.lower() == 'complete':
                self.client.calls(call_sid).update(status='completed')
            
            logging.info(f"Updated call {call_sid} status to {status}")
            return True
            
        except TwilioException as e:
            logging.error(f"Error updating call status: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error updating call status: {str(e)}")
            return False
    
    def validate_phone_number(self, phone_number: str) -> Dict:
        """Validate phone number using Twilio Lookup API"""
        try:
            lookup = self.client.lookups.phone_numbers(phone_number).fetch()
            
            return {
                'valid': True,
                'phone_number': lookup.phone_number,
                'country_code': lookup.country_code,
                'national_format': lookup.national_format
            }
            
        except TwilioException as e:
            logging.error(f"Phone number validation error: {str(e)}")
            return {
                'valid': False,
                'error': str(e),
                'phone_number': phone_number
            }