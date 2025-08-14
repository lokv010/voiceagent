"""
Python Voice Agent Service for Next.js Integration

This service provides core voice bot functionality and handles Twilio webhooks.
The Next.js application handles the main API layer and user interface.
"""

import time
from flask import Flask, request, jsonify
# from flask_cors import CORS
import os
import logging
import asyncio
from datetime import datetime, timedelta
import json

import websockets

# Import configuration
from config import config,get_config
from config import Config

# Import models
from models import DatabaseManager
from models.database import CallOutcome, CallbackRequest, Prospect, CallHistory, Campaign
from models.database import add_inbound_call_support

# Import services
from services import (
    UnifiedVoiceBot,
    UnifiedCampaignManager,
    ServiceHealthChecker
)

# Import utilities
from services.inbound_conversation_engine import InboundConversationEngine
from services.inbound_lead_scorer import InboundLeadScorer
from services.inbound_agent_service import InboundCallHandler
from services.callback_scheduler import CallbackScheduler
from utils import log_api_call, timing_decorator
from services.media_stream_handler import MediaStreamHandler
from services.webrtc_handler import WebRTCAudioHandler
from sqlalchemy import desc, text

from utils.helpers import is_business_hours

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('voice_agent.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Load configuration
config_name = os.getenv('FLASK_ENV', 'development')
app_config = get_config(config_name)  # Get config instance, not class
app.config.from_object(app_config)

# Enable CORS for Next.js frontend
# CORS(app, origins=[
#     'http://localhost:3000',
#     'https://your-production-domain.com',
#     '*'  # Remove in production
# ])

# Initialize services
try:
    db_manager = DatabaseManager(app_config.SQLALCHEMY_DATABASE_URI)
    voice_bot = UnifiedVoiceBot(app_config, db_manager)
    campaign_manager = UnifiedCampaignManager(voice_bot, db_manager)
    
    # Simple, fast, intelligent inbound handler
    inbound_handler = InboundCallHandler(voice_bot, db_manager, app_config)
    
    callback_scheduler = CallbackScheduler(voice_bot, db_manager, app_config)
    media_handler = MediaStreamHandler(voice_bot, voice_bot.speech_processor)
    webrtc_handler = WebRTCAudioHandler(voice_bot)

    #conversion_engine
    from services.conv_engine.flow_orch import FlowStateManager, FlowTransitionController, ConversationOrchestrator
    from services.conv_engine.flow_classfier import FlowClassificationEngine
    from services.conv_engine.pitch_flow import PitchAdaptationEngine
    from services.conv_engine.flow_models import FlowType


    flow_state_manager = FlowStateManager()
    transition_controller = FlowTransitionController(flow_state_manager)
    classification_engine = FlowClassificationEngine()
    orchestrator = ConversationOrchestrator(flow_state_manager, transition_controller)

    pitch_engine = PitchAdaptationEngine()
    orchestrator.register_flow_engine([FlowType.PITCH], pitch_engine)
    orchestrator.set_classification_engine(classification_engine)
    # Connect to existing handler
    inbound_handler.set_orchestrator(orchestrator, classification_engine)
    
    logger.info("Orchestrator system initialized successfully")

    add_inbound_call_support(db_manager)
    
    logger.info("Voice agent services initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize services: {e}")
    raise


    
    # WebSocket server for Media Streams
    async def start_websocket_server():
        server = await websockets.serve(
            media_handler.handle_media_stream,
            "0.0.0.0",
            8765
        )
        await server.wait_closed()

    logger.info("Voice agent services initialized successfully")


# ==================== HEALTH & STATUS ENDPOINTS ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for the voice service"""
    try:
        # Test database connection
        session = db_manager.get_session()
        session.execute(text('SELECT 1'))
        db_status = 'ok'
        
        # Test service health
        twilio_status = 'ok' if ServiceHealthChecker.check_twilio(voice_bot.twilio_handler) else 'error'
        openai_status = 'ok' if ServiceHealthChecker.check_openai(voice_bot.conversation_engine) else 'error'
        azure_status = 'ok' if ServiceHealthChecker.check_azure_speech(voice_bot.speech_processor) else 'error'
        
        services_status = {
            'database': db_status,
            'twilio': twilio_status,
            'openai': openai_status,
            'azure_speech': azure_status
        }
        
        overall_status = 'healthy' if all(
            status == 'ok' for status in services_status.values()
        ) else 'unhealthy'
        
        health_data = {
            'status': overall_status,
            'timestamp': datetime.utcnow().isoformat(),
            'services': services_status,
            'active_calls': len(voice_bot.active_calls),
            'service_name': 'python_voice_agent'
        }
        
        status_code = 200 if overall_status == 'healthy' else 503
        return jsonify(health_data), status_code
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.isoformat(),
            'service_name': 'python_voice_agent'
        }), 503

@app.route('/api/system/stats', methods=['GET'])
def get_system_stats():
    """Get system statistics"""
    try:
        stats = {
            'active_calls': len(voice_bot.active_calls),
            'total_prospects': campaign_manager.get_total_prospects(),
            'calls_today': campaign_manager.get_calls_today(),
            'qualified_leads_today': campaign_manager.get_qualified_leads_today(),
            'system_uptime': campaign_manager.get_system_uptime(),
            'last_updated': datetime.isoformat(),
            'service_name': 'python_voice_agent'
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Get system stats error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
#================Web rtc Handler=================
@app.route('/api/webrtc/answer', methods=['POST'])
async def handle_webrtc_answer():
    """Handle WebRTC answer from browser"""
    data = request.get_json()
    call_id = data.get('call_id')
    answer = data.get('answer')
    
    result = await webrtc_handler.handle_answer(call_id, answer)
    return jsonify(result)

# ==================== CORE VOICE BOT SERVICES ====================

@app.route('/api/start-call', methods=['POST'])
@timing_decorator
def start_call():
    """Start a voice call (called by Next.js API)"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        call_type = data.get('call_type', 'auto')
        
        if not phone_number:
            return jsonify({'success': False, 'error': 'Phone number required'}), 400
        
        logger.info(f"Starting call to {phone_number} with type {call_type}")
        
        # Start the call
        result = asyncio.run(voice_bot.initiate_call(phone_number, call_type))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Start call error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/form-webhook', methods=['POST'])
@timing_decorator
def form_webhook():
    """Handle form submissions (called by Next.js API)"""
    try:
        form_data = request.get_json()
        
        # Create prospect from form
        prospect = voice_bot.prospect_manager.create_prospect_from_form(form_data)
        
        # Schedule immediate call
        result = asyncio.run(voice_bot.initiate_call(
            prospect.phone_number, 
            'form_follow_up'
        ))
        
        response_data = {
            'status': 'received',
            'prospect_id': prospect.id,
            'call_initiated': result['success']
        }
        
        if result['success']:
            response_data['call_sid'] = result['call_sid']
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Form webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/upload-cold-leads', methods=['POST'])
@timing_decorator
def upload_cold_leads():
    """Upload cold leads (called by Next.js API)"""
    try:
        data = request.get_json()
        leads_list = data.get('leads', [])
        target_product = data.get('target_product', 'general')
        
        created_prospects = []
        errors = []
        
        for lead_data in leads_list:
            try:
                lead_data['target_product'] = target_product
                prospect = voice_bot.prospect_manager.create_prospect_from_cold_list(lead_data)
                created_prospects.append({
                    'prospect_id': prospect.id,
                    'phone': prospect.phone_number,
                    'name': prospect.name
                })
            except Exception as e:
                errors.append(f"Error: {str(e)}")
        
        return jsonify({
            'status': 'processed',
            'prospects_created': len(created_prospects),
            'prospects': created_prospects,
            'errors': errors
        })
        
    except Exception as e:
        logger.error(f"Upload cold leads error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add these endpoints to your app.py file





# ==================== INBOUND CALL WEBHOOKS ====================

@app.route('/inbound-webhook', methods=['POST'])
@timing_decorator
def inbound_voice_webhook():
    """Handle incoming calls - Direct from Twilio"""
    try:
        call_sid = request.form.get('CallSid')
        from_number = request.form.get('From')
        call_status = request.form.get('CallStatus')
        
        logger.info(f"Inbound call webhook: {call_sid} - {call_status} from {from_number}")
        
        # Use the OpenAI-powered handler
        twiml_response = asyncio.run(
            inbound_handler.handle_inbound_call(call_sid, request.form.to_dict())
        )
        return twiml_response, 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"Inbound voice webhook error: {str(e)}")
        # Better fallback that doesn't use complex handlers
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Gather input="speech" timeout="10" action="/inbound-webhook/process" method="POST">
                <Say voice="Polly.Joanna">Thank you for calling. How can I help you today?</Say>
            </Gather>
        </Response>''', 200, {'Content-Type': 'text/xml'}

@app.route('/inbound-webhook/process', methods=['POST'])
@timing_decorator
def process_inbound_speech():
    """Process inbound speech with OpenAI intelligence"""
    try:
        call_sid = request.form.get('CallSid')
        
        # Use OpenAI handler for fast, intelligent responses
        twiml_response = asyncio.run(
            inbound_handler.handle_inbound_response(call_sid, request.form.to_dict())
        )
        return twiml_response, 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"Speech processing error: {e}")
        # Improved fallback with better context handling
        return _generate_contextual_fallback(
            request.form.get('SpeechResult', ''),
            request.form.get('Confidence', '0.0')
        ), 200, {'Content-Type': 'text/xml'}
# ==================== FALLBACK HELPER FUNCTIONS ====================
   

def _generate_contextual_fallback(speech_result: str, confidence: str) -> str:
    """Generate better contextual fallback responses"""
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
def _generate_basic_response_fallback(speech_result):
    """Generate contextual fallback response"""
    try:
        speech_lower = speech_result.lower() if speech_result else ""
        
        if any(word in speech_lower for word in ['human', 'agent', 'person']):
            message = "Let me connect you with someone who can help you."
            return f'''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="Polly.Joanna">{message}</Say>
                <Dial>{os.getenv('AGENT_TRANSFER_NUMBER', '+12267537919')}</Dial>
            </Response>'''
        
        elif any(word in speech_lower for word in ['price', 'cost', 'money']):
            message = "I'd be happy to discuss solar pricing. What's your monthly electric bill?"
            
        elif any(word in speech_lower for word in ['solar', 'panels', 'energy']):
            message = "Great question about solar! Do you own your home?"
            
        elif any(word in speech_lower for word in ['yes', 'interested']):
            message = "Wonderful! To give you the best information, do you own your home?"
            
        elif any(word in speech_lower for word in ['no', 'not interested']):
            message = "I understand. Thank you for your time and have a great day!"
            return f'''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="Polly.Joanna">{message}</Say>
                <Hangup/>
            </Response>'''
            
        else:
            message = "How can I help you explore solar for your home today?"
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Gather input="speech" timeout="10" action="/inbound-webhook/process" method="POST">
                <Say voice="Polly.Joanna">{message}</Say>
            </Gather>
        </Response>'''
        
    except Exception as e:
        logging.error(f"Error generating fallback: {e}")
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Joanna">How can I help you today?</Say>
            <Gather input="speech" timeout="10" action="/inbound-webhook/process" method="POST"/>
        </Response>'''


@app.route('/inbound-webhook/after-hours', methods=['POST'])
@timing_decorator
def handle_after_hours_options():
    """Handle after-hours call options"""
    try:
        call_sid = request.form.get('CallSid')
        digits = request.form.get('Digits', '')
        speech_result = request.form.get('SpeechResult', '')
        
        logger.info(f"After hours option: {call_sid} - digits: '{digits}', speech: '{speech_result}'")
        
        # Check if they want to speak with AI assistant
        if digits == '1' or 'assistant' in speech_result.lower():
            # Start AI qualification even after hours
            return asyncio.run(
                inbound_handler._start_inbound_qualification(call_sid, voice_bot.active_calls.get(call_sid, {}))
            ), 200, {'Content-Type': 'text/xml'}
        else:
            # Set up voicemail or callback
            voicemail_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="Polly.Joanna">Please leave your name, number, and a brief message after the tone. We'll call you back during business hours.</Say>
                <Record maxLength="120" timeout="10" action="/inbound-webhook/voicemail-complete"/>
            </Response>'''
            return voicemail_twiml, 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"After hours options error: {str(e)}")
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Joanna">Thank you for calling. Goodbye.</Say>
            <Hangup/>
        </Response>''', 200, {'Content-Type': 'text/xml'}

@app.route('/inbound-webhook/voicemail-complete', methods=['POST'])
@timing_decorator
def handle_voicemail_complete():
    """Handle completed voicemail recording"""
    try:
        call_sid = request.form.get('CallSid')
        recording_url = request.form.get('RecordingUrl')
        recording_duration = request.form.get('RecordingDuration')
        
        logger.info(f"Voicemail completed: {call_sid} - {recording_duration}s - {recording_url}")
        
        # Save voicemail info to call history if call state exists
        if call_sid in voice_bot.active_calls:
            call_state = voice_bot.active_calls[call_sid]
            call_state['conversation_history'].append({
                'turn': call_state.get('current_turn', 0),
                'type': 'customer',
                'message': f"Voicemail left ({recording_duration}s)",
                'recording_url': recording_url,
                'timestamp': datetime.utcnow(),
                'is_voicemail': True
            })
            
            # Mark call as voicemail and save
            call_state['call_outcome'] = CallOutcome.VOICEMAIL.value
            
            # Calculate and save results
            call_results = asyncio.run(inbound_handler._calculate_inbound_call_results(call_sid, call_state))
            asyncio.run(inbound_handler._save_inbound_call_results(call_sid, call_state, call_results, 'voicemail'))
            
            # Clean up
            del voice_bot.active_calls[call_sid]
        
        # Thank them and hang up
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Joanna">Thank you for your message. We'll call you back during business hours. Have a great day!</Say>
            <Hangup/>
        </Response>''', 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"Voicemail complete error: {str(e)}")
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Joanna">Thank you for calling. Goodbye.</Say>
            <Hangup/>
        </Response>''', 200, {'Content-Type': 'text/xml'}

@app.route('/inbound-webhook/dnc-options', methods=['POST'])
@timing_decorator
def handle_dnc_options():
    """Handle do-not-call list options"""
    try:
        call_sid = request.form.get('CallSid')
        digits = request.form.get('Digits', '')
        
        if digits == '1':
            # Connect to agent to remove from DNC
            transfer_message = "Please hold while I connect you with an agent who can help remove you from our do not call list."
            return voice_bot.twilio_handler.generate_transfer_twiml(
                inbound_handler.agent_transfer_number,
                transfer_message
            ), 200, {'Content-Type': 'text/xml'}
        else:
            # Thank them and hang up
            return '''<?xml version="1.0" encoding="UTF-8"?>
            <Response>
                <Say voice="Polly.Joanna">Thank you for calling. We'll keep you on our do not call list as requested. Have a great day.</Say>
                <Hangup/>
            </Response>''', 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"DNC options error: {str(e)}")
        return '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Joanna">Thank you for calling. Goodbye.</Say>
            <Hangup/>
        </Response>''', 200, {'Content-Type': 'text/xml'}

@app.route('/inbound-webhook/status', methods=['POST'])
def inbound_call_status():
    """Handle inbound call status updates from Twilio"""
    try:
        call_sid = request.form.get('CallSid')
        call_status = request.form.get('CallStatus')
        duration = request.form.get('CallDuration')
        
        logger.info(f"Inbound call status update: {call_sid} - {call_status} (duration: {duration})")
        
        if call_status in ['completed', 'failed', 'busy', 'no-answer']:
            # Don't immediately remove from active_calls
            # Schedule cleanup after delay to handle late speech webhooks
            if call_sid in voice_bot.active_calls:
                call_state = voice_bot.active_calls[call_sid]
                call_state['call_outcome'] = call_status
                call_state['end_time'] = datetime.utcnow()
                call_state['duration'] = duration
                
                # Schedule delayed cleanup (30 seconds)
                def delayed_cleanup():
                    time.sleep(60)
                    if call_sid in voice_bot.active_calls:
                        logging.info(f"Delayed cleanup of call: {call_sid}")
                        # Save call results before cleanup
                        try:
                            asyncio.run(voice_bot.handle_call_status_update(call_sid, call_status, request.form.to_dict()))
                        except Exception as e:
                            logging.error(f"Error in delayed cleanup: {e}")
                        finally:
                            voice_bot.active_calls.pop(call_sid, None)
                
                # Run cleanup in background thread
                import threading
                cleanup_thread = threading.Thread(target=delayed_cleanup, daemon=True)
                cleanup_thread.start()
            else:
                # Call already cleaned up, just log
                logging.info(f"Status update for already cleaned call: {call_sid}")
        
        return jsonify({'status': 'received', 'call_sid': call_sid})
        
    except Exception as e:
        logging.error(f"Error handling call status: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inbound/call-states', methods=['GET'])
def get_call_states():
    """Monitor current call states"""
    try:
        active_count = len(voice_bot.active_calls)
        call_details = []
        
        for call_sid, call_state in voice_bot.active_calls.items():
            call_details.append({
                'call_sid': call_sid,
                'phone_number': call_state.get('phone_number', 'unknown'),
                'start_time': call_state.get('start_time', datetime.utcnow()).isoformat(),
                'current_turn': call_state.get('current_turn', 0),
                'conversation_stage': call_state.get('conversation_stage', 'unknown'),
                'call_outcome': call_state.get('call_outcome'),
                'duration_seconds': int((datetime.utcnow() - call_state.get('start_time', datetime.utcnow())).total_seconds()) if call_state.get('start_time') else 0
            })
        
        return jsonify({
            'active_calls_count': active_count,
            'calls': call_details,
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logging.error(f"Error getting call states: {e}")
        return jsonify({'error': str(e)}), 500


# ==================== INBOUND CALL MANAGEMENT APIs ====================

@app.route('/api/inbound/stats', methods=['GET'])
def get_inbound_stats():
    """Get simplified inbound call statistics"""
    try:
        days_back = int(request.args.get('days_back', 7))
        start_date = datetime.utcnow() - timedelta(days=days_back)
        
        session = db_manager.get_session()
        
        # Get inbound call stats
        inbound_calls = session.query(CallHistory).filter(
            CallHistory.call_type == 'inbound',
            CallHistory.called_at >= start_date
        ).all()
        
        total_inbound = len(inbound_calls)
        completed_calls = len([c for c in inbound_calls if c.call_outcome == 'completed'])
        avg_score = sum(c.qualification_score or 0 for c in inbound_calls) / total_inbound if total_inbound > 0 else 0
        qualified_leads = len([c for c in inbound_calls if (c.qualification_score or 0) >= 70])
        
        stats = {
            'total_inbound_calls': total_inbound,
            'completed_calls': completed_calls,
            'qualified_leads': qualified_leads,
            'avg_qualification_score': round(avg_score, 1),
            'conversion_rate': round((qualified_leads / completed_calls * 100) if completed_calls > 0 else 0, 1),
            'handler_type': 'openai_intelligent'
        }
        
        session.close()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Get inbound stats error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inbound/recent', methods=['GET'])
def get_recent_inbound_calls():
    """Get recent inbound calls"""
    try:
        limit = int(request.args.get('limit', 50))
        
        session = db_manager.get_session()
        
        # Get recent inbound calls with prospect info
        recent_calls = session.query(CallHistory).filter(
            CallHistory.call_type == 'inbound'
        ).order_by(desc(CallHistory.called_at)).limit(limit).all()
        
        calls_data = []
        for call in recent_calls:
            # Get prospect info
            prospect = session.query(Prospect).filter(Prospect.id == call.prospect_id).first()
            
            call_data = {
                'id': call.id,
                'call_sid': call.call_sid,
                'prospect_id': call.prospect_id,
                'prospect_name': prospect.name if prospect else 'Unknown Caller',
                'prospect_phone': prospect.phone_number if prospect else 'Unknown',
                'call_duration': call.call_duration,
                'call_outcome': call.call_outcome,
                'qualification_score': call.qualification_score,
                'called_at': call.called_at.isoformat() if call.called_at else None,
                'conversation_summary': call.conversation_summary,
                'next_action': call.next_action
            }
            calls_data.append(call_data)
        
        session.close()
        return jsonify({'calls': calls_data})
        
    except Exception as e:
        logger.error(f"Get recent inbound calls error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inbound/configure', methods=['POST'])
def configure_inbound_settings():
    """Configure OpenAI inbound settings"""
    try:
        settings = request.get_json()
        
        # Update handler settings
        if 'agent_transfer_number' in settings:
            inbound_handler.agent_transfer_number = settings['agent_transfer_number']
        
        if 'business_hours' in settings:
            inbound_handler.business_hours.update(settings['business_hours'])
        
        # Update response cache if provided
        if 'response_cache' in settings:
            inbound_handler.response_cache.update(settings['response_cache'])
        
        return jsonify({
            'status': 'updated',
            'handler_type': 'openai_intelligent',
            'settings': {
                'agent_transfer_number': inbound_handler.agent_transfer_number,
                'business_hours': inbound_handler.business_hours,
                'cache_size': len(inbound_handler.response_cache)
            }
        })
        
    except Exception as e:
        logger.error(f"Configure inbound settings error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/inbound/active', methods=['GET'])
def get_active_inbound_calls():
    """Get currently active inbound calls"""
    try:
        active_inbound = []
        
        for call_sid, call_state in voice_bot.active_calls.items():
            if call_state.get('call_type') == 'inbound':
                active_inbound.append({
                    'call_sid': call_sid,
                    'phone_number': call_state['phone_number'],
                    'prospect_name': call_state['prospect_context']['prospect'].name or 'Unknown',
                    'start_time': call_state['start_time'].isoformat(),
                    'current_turn': call_state['current_turn'],
                    'inbound_reason': call_state.get('inbound_reason', 'unknown'),
                    'transfer_requested': call_state.get('transfer_requested', False),
                    'duration_seconds': int((datetime.utcnow() - call_state['start_time']).total_seconds())
                })
        
        return jsonify({
            'active_calls': active_inbound,
            'count': len(active_inbound)
        })
        
    except Exception as e:
        logger.error(f"Get active inbound calls error: {str(e)}")
        return jsonify({'error': str(e)}), 500
# Add these callback management endpoints to your app.py file

from services.callback_scheduler import CallbackScheduler
from datetime import datetime, timedelta

# Initialize callback scheduler after existing services
callback_scheduler = CallbackScheduler(voice_bot, db_manager, app_config)

# ==================== CALLBACK MANAGEMENT APIs ====================

@app.route('/api/callbacks/request', methods=['POST'])
@timing_decorator
def request_callback():
    """Request a callback for a prospect"""
    try:
        data = request.get_json()
        
        # Validate required fields
        prospect_id = data.get('prospect_id')
        if not prospect_id:
            return jsonify({'success': False, 'error': 'prospect_id required'}), 400
        
        # Prepare callback data
        callback_data = {
            'requested_time': data.get('requested_time'),
            'time_preference': data.get('time_preference', 'anytime'),
            'reason': data.get('reason', 'Callback requested'),
            'urgency_level': data.get('urgency_level', 'normal'),
            'source': data.get('source', 'manual'),
            'notes': data.get('notes', ''),
            'timezone': data.get('timezone', 'UTC')
        }
        
        # Request the callback
        result = asyncio.run(callback_scheduler.request_callback(prospect_id, callback_data))
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Request callback error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/callbacks/schedule/<int:callback_id>', methods=['POST'])
@timing_decorator
def schedule_callback(callback_id):
    """Schedule a specific callback request"""
    try:
        data = request.get_json()
        
        # Get scheduling preferences
        requested_time_str = data.get('requested_time')
        if requested_time_str:
            try:
                requested_time = datetime.fromisoformat(requested_time_str.replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'success': False, 'error': 'Invalid datetime format'}), 400
        else:
            requested_time = None
        
        # Update callback request with new time
        session = db_manager.get_session()
        callback_request = session.query(CallbackRequest).filter(
            CallbackRequest.id == callback_id
        ).first()
        
        if not callback_request:
            session.close()
            return jsonify({'success': False, 'error': 'Callback not found'}), 404
        
        if requested_time:
            callback_request.requested_time = requested_time
        
        # Attempt to schedule
        result = asyncio.run(callback_scheduler._schedule_callback(callback_id, session))
        session.close()
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Schedule callback error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/callbacks/pending', methods=['GET'])
def get_pending_callbacks():
    """Get pending callback requests"""
    try:
        limit = int(request.args.get('limit', 50))
        
        callbacks = asyncio.run(callback_scheduler.get_pending_callbacks(limit))
        
        return jsonify({
            'callbacks': callbacks,
            'count': len(callbacks)
        })
        
    except Exception as e:
        logger.error(f"Get pending callbacks error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/callbacks/scheduled', methods=['GET'])
def get_scheduled_callbacks():
    """Get scheduled callbacks for a specific date"""
    try:
        date_str = request.args.get('date')
        if date_str:
            try:
                date = datetime.fromisoformat(date_str).date()
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400
        else:
            date = datetime.utcnow().date()
        
        callbacks = asyncio.run(callback_scheduler.get_scheduled_callbacks(date))
        
        return jsonify({
            'callbacks': callbacks,
            'date': date.isoformat(),
            'count': len(callbacks)
        })
        
    except Exception as e:
        logger.error(f"Get scheduled callbacks error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/callbacks/execute/<int:callback_id>', methods=['POST'])
@timing_decorator
def execute_callback(callback_id):
    """Execute a scheduled callback"""
    try:
        result = asyncio.run(callback_scheduler.execute_callback(callback_id))
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Execute callback error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/callbacks/reschedule/<int:callback_id>', methods=['POST'])
@timing_decorator
def reschedule_callback(callback_id):
    """Reschedule a callback"""
    try:
        data = request.get_json()
        
        # Parse new time
        new_time_str = data.get('new_time')
        if not new_time_str:
            return jsonify({'success': False, 'error': 'new_time required'}), 400
        
        try:
            new_time = datetime.fromisoformat(new_time_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid datetime format'}), 400
        
        reason = data.get('reason', 'Rescheduled by user')
        
        result = asyncio.run(callback_scheduler.reschedule_callback(
            callback_id, new_time, reason
        ))
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Reschedule callback error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/callbacks/cancel/<int:callback_id>', methods=['POST'])
@timing_decorator
def cancel_callback(callback_id):
    """Cancel a callback request"""
    try:
        data = request.get_json()
        reason = data.get('reason', 'Cancelled by user')
        
        session = db_manager.get_session()
        
        callback_request = session.query(CallbackRequest).filter(
            CallbackRequest.id == callback_id
        ).first()
        
        if not callback_request:
            session.close()
            return jsonify({'success': False, 'error': 'Callback not found'}), 404
        
        # Update status
        callback_request.status = 'cancelled'
        callback_request.notes = f"{callback_request.notes or ''}\nCancelled: {reason}"
        
        session.commit()
        session.close()
        
        return jsonify({
            'success': True,
            'callback_id': callback_id,
            'status': 'cancelled'
        })
        
    except Exception as e:
        logger.error(f"Cancel callback error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/callbacks/bulk-schedule', methods=['POST'])
@timing_decorator
def bulk_schedule_callbacks():
    """Schedule multiple callbacks in bulk"""
    try:
        data = request.get_json()
        callback_ids = data.get('callback_ids', [])
        default_time_preference = data.get('time_preference', 'anytime')
        
        if not callback_ids:
            return jsonify({'success': False, 'error': 'callback_ids required'}), 400
        
        results = []
        session = db_manager.get_session()
        
        for callback_id in callback_ids:
            try:
                # Update time preference if provided
                callback_request = session.query(CallbackRequest).filter(
                    CallbackRequest.id == callback_id
                ).first()
                
                if callback_request:
                    # Set default time preference if not specified
                    if not callback_request.requested_time:
                        callback_request.requested_time = callback_scheduler._parse_callback_time(
                            None, default_time_preference, 'UTC'
                        )
                    
                    # Attempt to schedule
                    result = asyncio.run(callback_scheduler._schedule_callback(callback_id, session))
                    results.append({
                        'callback_id': callback_id,
                        'success': result['success'],
                        'status': result.get('status'),
                        'error': result.get('error')
                    })
                else:
                    results.append({
                        'callback_id': callback_id,
                        'success': False,
                        'error': 'Callback not found'
                    })
                    
            except Exception as e:
                results.append({
                    'callback_id': callback_id,
                    'success': False,
                    'error': str(e)
                })
        
        session.close()
        
        successful_schedules = len([r for r in results if r['success']])
        
        return jsonify({
            'success': True,
            'total_processed': len(callback_ids),
            'successful_schedules': successful_schedules,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Bulk schedule callbacks error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/callbacks/stats', methods=['GET'])
def get_callback_stats():
    """Get callback statistics"""
    try:
        days_back = int(request.args.get('days_back', 7))
        start_date = datetime.utcnow() - timedelta(days=days_back)
        
        session = db_manager.get_session()
        
        # Get all callbacks in the date range
        callbacks = session.query(CallbackRequest).filter(
            CallbackRequest.requested_at >= start_date
        ).all()
        
        # Calculate stats
        total_requests = len(callbacks)
        scheduled_count = len([c for c in callbacks if c.status == 'scheduled'])
        completed_count = len([c for c in callbacks if c.status == 'completed'])
        pending_count = len([c for c in callbacks if c.status == 'pending'])
        cancelled_count = len([c for c in callbacks if c.status == 'cancelled'])
        
        # Priority breakdown
        priority_stats = {}
        for priority in ['urgent', 'high', 'normal', 'low']:
            priority_stats[priority] = len([c for c in callbacks if c.priority == priority])
        
        # Source breakdown
        source_stats = {}
        for callback in callbacks:
            source = callback.request_source or 'unknown'
            source_stats[source] = source_stats.get(source, 0) + 1
        
        # Completion rate
        completion_rate = (completed_count / total_requests * 100) if total_requests > 0 else 0
        
        # Average time to schedule
        scheduled_callbacks = [c for c in callbacks if c.scheduled_at and c.requested_at]
        avg_time_to_schedule = 0
        if scheduled_callbacks:
            total_seconds = sum(
                (c.scheduled_at - c.requested_at).total_seconds() 
                for c in scheduled_callbacks
            )
            avg_time_to_schedule = total_seconds / len(scheduled_callbacks) / 3600  # Convert to hours
        
        stats = {
            'total_requests': total_requests,
            'scheduled': scheduled_count,
            'completed': completed_count,
            'pending': pending_count,
            'cancelled': cancelled_count,
            'completion_rate': round(completion_rate, 1),
            'avg_time_to_schedule_hours': round(avg_time_to_schedule, 1),
            'priority_breakdown': priority_stats,
            'source_breakdown': source_stats,
            'date_range': {
                'start': start_date.isoformat(),
                'end': datetime.utcnow().isoformat(),
                'days': days_back
            }
        }
        
        session.close()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Get callback stats error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/callbacks/available-slots', methods=['GET'])
def get_available_callback_slots():
    """Get available time slots for callbacks"""
    try:
        # Parse query parameters
        date_str = request.args.get('date')
        if date_str:
            try:
                target_date = datetime.fromisoformat(date_str).date()
            except ValueError:
                return jsonify({'error': 'Invalid date format'}), 400
        else:
            target_date = datetime.utcnow().date()
        
        duration_hours = int(request.args.get('duration_hours', 8))  # Search window
        
        # Generate time slots for the day
        start_time = datetime.combine(target_date, datetime.min.time().replace(hour=9))
        end_time = start_time + timedelta(hours=duration_hours)
        
        available_slots = []
        current_time = start_time
        
        session = db_manager.get_session()
        
        while current_time < end_time:
            # Check if slot is available
            is_available = asyncio.run(callback_scheduler._is_slot_available(current_time, session))
            
            if is_available:
                available_slots.append({
                    'time': current_time.isoformat(),
                    'display_time': current_time.strftime('%I:%M %p'),
                    'is_business_hours': is_business_hours(current_time)
                })
            
            current_time += timedelta(minutes=30)  # 30-minute slots
        
        session.close()
        
        return jsonify({
            'date': target_date.isoformat(),
            'available_slots': available_slots,
            'total_slots': len(available_slots)
        })
        
    except Exception as e:
        logger.error(f"Get available slots error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/callbacks/configure', methods=['POST'])
@timing_decorator
def configure_callback_settings():
    """Configure callback scheduling settings"""
    try:
        data = request.get_json()
        
        # Update callback scheduler configuration
        if 'default_callback_window' in data:
            callback_scheduler.scheduling_config['default_callback_window'] = int(data['default_callback_window'])
        
        if 'max_callbacks_per_hour' in data:
            callback_scheduler.scheduling_config['max_callbacks_per_hour'] = int(data['max_callbacks_per_hour'])
        
        if 'min_callback_gap' in data:
            callback_scheduler.scheduling_config['min_callback_gap'] = int(data['min_callback_gap'])
        
        if 'business_hours_only' in data:
            callback_scheduler.scheduling_config['business_hours_only'] = bool(data['business_hours_only'])
        
        if 'time_preferences' in data:
            callback_scheduler.time_preferences.update(data['time_preferences'])
        
        # Save configuration to database or config file
        # Implementation depends on your preference for persistence
        
        return jsonify({
            'success': True,
            'message': 'Callback settings updated',
            'current_config': callback_scheduler.scheduling_config
        })
        
    except Exception as e:
        logger.error(f"Configure callback settings error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/callbacks/export', methods=['GET'])
def export_callbacks():
    """Export callback data for reporting"""
    try:
        # Parse query parameters
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        status_filter = request.args.get('status')
        format_type = request.args.get('format', 'json')  # json or csv
        
        # Parse dates
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str)
        else:
            start_date = datetime.utcnow() - timedelta(days=30)
        
        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str)
        else:
            end_date = datetime.utcnow()
        
        session = db_manager.get_session()
        
        # Build query
        query = session.query(CallbackRequest).filter(
            CallbackRequest.requested_at >= start_date,
            CallbackRequest.requested_at <= end_date
        )
        
        if status_filter:
            query = query.filter(CallbackRequest.status == status_filter)
        
        callbacks = query.order_by(CallbackRequest.requested_at.desc()).all()
        
        # Prepare export data
        export_data = []
        for callback in callbacks:
            # Get prospect info
            prospect = session.query(Prospect).filter(
                Prospect.id == callback.prospect_id
            ).first()
            
            callback_data = {
                'callback_id': callback.id,
                'prospect_id': callback.prospect_id,
                'prospect_name': prospect.name if prospect else 'Unknown',
                'prospect_phone': prospect.phone_number if prospect else 'Unknown',
                'prospect_email': prospect.email if prospect else '',
                'requested_at': callback.requested_at.isoformat() if callback.requested_at else '',
                'requested_time': callback.requested_time.isoformat() if callback.requested_time else '',
                'scheduled_at': callback.scheduled_at.isoformat() if callback.scheduled_at else '',
                'completed_at': callback.completed_at.isoformat() if callback.completed_at else '',
                'status': callback.status,
                'priority': callback.priority,
                'reason': callback.reason,
                'request_source': callback.request_source,
                'assigned_agent': callback.assigned_agent,
                'outcome': callback.outcome,
                'notes': callback.notes
            }
            export_data.append(callback_data)
        
        session.close()
        
        if format_type == 'csv':
            # Convert to CSV format
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=export_data[0].keys() if export_data else [])
            writer.writeheader()
            writer.writerows(export_data)
            
            csv_content = output.getvalue()
            output.close()
            
            response = app.response_class(
                csv_content,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=callbacks_{start_date.date()}_to_{end_date.date()}.csv'}
            )
            return response
        else:
            # Return JSON
            return jsonify({
                'callbacks': export_data,
                'total_count': len(export_data),
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'filters': {
                    'status': status_filter
                }
            })
        
    except Exception as e:
        logger.error(f"Export callbacks error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== WEBHOOK INTEGRATION FOR CALLBACKS ====================

@app.route('/api/callbacks/webhook/<int:callback_id>/confirm', methods=['POST'])
@timing_decorator
def confirm_callback_webhook(callback_id):
    """Webhook endpoint for callback confirmations (e.g., from SMS/email)"""
    try:
        data = request.get_json() or request.form.to_dict()
        
        # Verify callback exists
        session = db_manager.get_session()
        callback_request = session.query(CallbackRequest).filter(
            CallbackRequest.id == callback_id
        ).first()
        
        if not callback_request:
            session.close()
            return jsonify({'success': False, 'error': 'Callback not found'}), 404
        
        # Update status based on confirmation
        confirmed = data.get('confirmed', 'true').lower() in ['true', '1', 'yes']
        
        if confirmed:
            callback_request.status = 'confirmed'
            callback_request.notes = f"{callback_request.notes or ''}\nConfirmed via webhook"
        else:
            # Handle rejection - offer reschedule
            callback_request.status = 'pending'
            callback_request.notes = f"{callback_request.notes or ''}\nRejected via webhook - needs reschedule"
        
        session.commit()
        session.close()
        
        return jsonify({
            'success': True,
            'callback_id': callback_id,
            'status': callback_request.status,
            'confirmed': confirmed
        })
        
    except Exception as e:
        logger.error(f"Callback confirmation webhook error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== CAMPAIGN MANAGEMENT SERVICES ====================

@app.route('/api/campaign/start', methods=['POST'])
@timing_decorator
def start_campaign():
    """Start a campaign (called by Next.js API)"""
    try:
        campaign_params = request.get_json()
        campaign_type = campaign_params.get('type', 'mixed')
        
        if campaign_type == 'form_follow_up':
            result = campaign_manager.create_form_follow_up_campaign(
                hours_back=campaign_params.get('hours_back', 24),
                product_filter=campaign_params.get('product_filter'),
                max_calls=campaign_params.get('max_calls', 100)
            )
        elif campaign_type == 'cold_outreach':
            result = campaign_manager.create_cold_outreach_campaign(
                prospect_list=campaign_params.get('prospect_list', []),
                product_target=campaign_params.get('product_target'),
                call_schedule=campaign_params.get('call_schedule', 'business_hours'),
                max_calls=campaign_params.get('max_calls', 100)
            )
        else:  # mixed
            result = campaign_manager.create_mixed_campaign(
                include_forms=campaign_params.get('include_forms', True),
                include_cold=campaign_params.get('include_cold', True),
                max_calls=campaign_params.get('max_calls', 100)
            )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Start campaign error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaign/<int:campaign_id>/status', methods=['GET'])
def get_campaign_status(campaign_id):
    """Get campaign status (called by Next.js API)"""
    try:
        status = campaign_manager.get_campaign_status(campaign_id)
        return jsonify(status)
    except Exception as e:
        logger.error(f"Get campaign status error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/campaign/<int:campaign_id>/stop', methods=['POST'])
def stop_campaign(campaign_id):
    """Stop campaign (called by Next.js API)"""
    try:
        result = campaign_manager.stop_campaign(campaign_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Stop campaign error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== DATA RETRIEVAL SERVICES ====================

@app.route('/api/analytics/dashboard', methods=['GET'])
def get_dashboard_analytics():
    """Get analytics data (called by Next.js API)"""
    try:
        days_back = int(request.args.get('days_back', 30))
        start_date = datetime.isoformat() - timedelta(days=days_back)
        analytics = campaign_manager.get_analytics_data(start_date)
        return jsonify(analytics)
    except Exception as e:
        logger.error(f"Dashboard analytics error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/performance', methods=['GET'])
def get_performance_analytics():
    """Get performance analytics (called by Next.js API)"""
    try:
        # Get parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        source_filter = request.args.get('source')
        product_filter = request.args.get('product')
        
        # Parse dates
        if start_date:
            start_date = datetime.fromisoformat(start_date)
        else:
            start_date = datetime.isoformat() - timedelta(days=30)
        
        if end_date:
            end_date = datetime.fromisoformat(end_date)
        else:
            end_date = datetime.isoformat()
        
        performance = campaign_manager.get_performance_analytics(
            start_date, end_date, source_filter, product_filter
        )
        
        return jsonify(performance)
    except Exception as e:
        logger.error(f"Performance analytics error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prospects', methods=['GET'])
def get_prospects():
    """Get prospects (called by Next.js API)"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        source_filter = request.args.get('source')
        status_filter = request.args.get('status')
        search_query = request.args.get('search')
        
        prospects_data = campaign_manager.get_prospects_paginated(
            page, per_page, source_filter, status_filter, search_query
        )
        
        return jsonify(prospects_data)
    except Exception as e:
        logger.error(f"Get prospects error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prospects/<int:prospect_id>', methods=['GET'])
def get_prospect_details(prospect_id):
    """Get prospect details (called by Next.js API)"""
    try:
        prospect_details = campaign_manager.get_prospect_details(prospect_id)
        if not prospect_details:
            return jsonify({'error': 'Prospect not found'}), 404
        return jsonify(prospect_details)
    except Exception as e:
        logger.error(f"Get prospect details error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prospects/<int:prospect_id>/calls', methods=['GET'])
def get_prospect_calls(prospect_id):
    """Get prospect call history (called by Next.js API)"""
    try:
        calls = campaign_manager.get_prospect_call_history(prospect_id)
        return jsonify({'calls': calls})
    except Exception as e:
        logger.error(f"Get prospect calls error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/prospects/<int:prospect_id>/do-not-call', methods=['POST'])
def mark_do_not_call(prospect_id):
    """Mark prospect as do not call (called by Next.js API)"""
    try:
        result = campaign_manager.mark_prospect_do_not_call(prospect_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Mark do not call error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ==================== TWILIO WEBHOOKS (DIRECT FROM TWILIO) ====================

@app.route('/voice-webhook', methods=['POST'])
@timing_decorator
def voice_webhook():
    """
    Direct Twilio voice webhook - NOT proxied through Next.js
    This needs to be called directly by Twilio for real-time voice processing
    """
    try:
        call_sid = request.form.get('CallSid')
        from_number = request.form.get('From')
        call_status = request.form.get('CallStatus')
        
        logger.info(f"Direct Twilio webhook: {call_sid} - {call_status} from {from_number}")
        
        # Handle the call with real-time processing
        twiml_response = asyncio.run(
            voice_bot.handle_webhook_call(call_sid, request.form.to_dict())
        )
        
        return twiml_response, 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"Voice webhook error: {str(e)}")
        # Return fallback TwiML
        fallback_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Joanna">I'm sorry, there was an error. Please try again later.</Say>
            <Hangup/>
        </Response>'''
        return fallback_twiml, 200, {'Content-Type': 'text/xml'}

@app.route('/voice-webhook/process', methods=['POST'])
@timing_decorator
def process_speech():
    """Process speech input from customer"""
    try:
        call_sid = request.form.get('CallSid')
        speech_result = request.form.get('SpeechResult', '')
        confidence = request.form.get('Confidence', '0.0')
        
        logger.info(f"Speech processing: {call_sid} - '{speech_result}' (confidence: {confidence})")
        
        # Process customer response
        twiml_response = asyncio.run(
            voice_bot.handle_webhook_call(call_sid, request.form.to_dict())
        )
        
        return twiml_response, 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"Speech processing error: {str(e)}")
        fallback_twiml = '''<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Joanna">Thank you for your time. Goodbye!</Say>
            <Hangup/>
        </Response>'''
        return fallback_twiml, 200, {'Content-Type': 'text/xml'}
    






@app.route('/voice-webhook/status', methods=['POST'])
def call_status():
    """Handle call status updates from Twilio"""
    try:
        call_sid = request.form.get('CallSid')
        call_status = request.form.get('CallStatus')
        duration = request.form.get('CallDuration')
        
        logger.info(f"Call status update: {call_sid} - {call_status} (duration: {duration})")
        
        # Handle status update
        asyncio.run(
            voice_bot.handle_call_status_update(call_sid, call_status, request.form.to_dict())
        )
        
        return jsonify({'status': 'received', 'call_sid': call_sid})
        
    except Exception as e:
        logger.error(f"Status webhook error: {str(e)}")
        return jsonify({'error': str(e)}), 500


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    return jsonify({'error': 'An unexpected error occurred'}), 500

# ==================== MIDDLEWARE ====================

@app.after_request
def after_request(response):
    """Add CORS headers for all responses"""
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# ==================== STARTUP ====================

# @app.before_first_request
def startup():
    """Initialize service on startup"""
    logger.info("Python Voice Agent Service starting...")
    
    # Create database tables if they don't exist
    try:
        from models.database import Base
        Base.metadata.create_all(bind=db_manager.engine)
        logger.info("Database tables verified")
    except Exception as e:
        logger.error(f"Database setup error: {e}")
    
    logger.info("Python Voice Agent Service ready")

if __name__ == '__main__':
    # Configuration
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Python Voice Agent Service on port {port}")
    
    try:
        app.run(
            host='0.0.0.0',
            port=port,
            debug=debug_mode,
            threaded=True
        )
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise
# ==================== ENHANCED ANALYTICS ENDPOINTS ====================

@app.route('/api/inbound/intelligence-stats', methods=['GET'])
def get_intelligence_stats():
    """Get statistics on intelligence system performance"""
    try:
        days_back = int(request.args.get('days_back', 7))
        start_date = datetime.utcnow() - timedelta(days=days_back)
        
        session = db_manager.get_session()
        
        # Get inbound calls with intelligence metadata
        inbound_calls = session.query(CallHistory).filter(
            CallHistory.call_type == 'inbound',
            CallHistory.called_at >= start_date
        ).all()
        
        stats = {
            'total_calls': len(inbound_calls),
            'intelligence_enabled_calls': 0,
            'playbook_responses': 0,
            'ai_responses': 0,
            'fallback_responses': 0,
            'avg_response_confidence': 0,
            'scenario_breakdown': {},
            'strategy_effectiveness': {},
            'system_performance': {
                'enhanced_handler_success_rate': 0,
                'playbook_engine_availability': hasattr(inbound_handler, 'playbook_engine') and inbound_handler.playbook_engine is not None,
                'intent_analyzer_availability': hasattr(inbound_handler, 'intent_analyzer') and inbound_handler.intent_analyzer is not None
            }
        }
        
        confidence_scores = []
        intelligence_enabled = 0
        playbook_count = 0
        ai_count = 0
        fallback_count = 0
        
        for call in inbound_calls:
            try:
                if call.conversation_log:
                    # Parse conversation log
                    if isinstance(call.conversation_log, str):
                        conversation_data = json.loads(call.conversation_log)
                    else:
                        conversation_data = call.conversation_log
                    
                    # Check for intelligence indicators
                    has_intelligence = False
                    for interaction in conversation_data:
                        if isinstance(interaction, dict):
                            strategy = interaction.get('strategy_used', '')
                            if 'intelligent' in strategy or 'playbook' in strategy:
                                has_intelligence = True
                                
                            if 'playbook' in strategy:
                                playbook_count += 1
                            elif 'ai' in strategy:
                                ai_count += 1
                            elif 'fallback' in strategy:
                                fallback_count += 1
                    
                    if has_intelligence:
                        intelligence_enabled += 1
                    
                    # Track confidence scores
                    if call.qualification_score:
                        confidence_scores.append(call.qualification_score)
                        
            except Exception as e:
                logger.debug(f"Error parsing call log: {e}")
        
        # Update stats
        stats['intelligence_enabled_calls'] = intelligence_enabled
        stats['playbook_responses'] = playbook_count
        stats['ai_responses'] = ai_count
        stats['fallback_responses'] = fallback_count
        
        if confidence_scores:
            stats['avg_response_confidence'] = sum(confidence_scores) / len(confidence_scores)
        
        stats['system_performance']['enhanced_handler_success_rate'] = (
            intelligence_enabled / len(inbound_calls) * 100 if inbound_calls else 0
        )
        
        session.close()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Get intelligence stats error: {str(e)}")
        return jsonify({'error': str(e)}), 500
