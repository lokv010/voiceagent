"""
Python Voice Agent Service for Next.js Integration

This service provides core voice bot functionality and handles Twilio webhooks.
The Next.js application handles the main API layer and user interface.
"""

from flask import Flask, request, jsonify
# from flask_cors import CORS
import os
import logging
import asyncio
from datetime import datetime, timedelta
import json

# Import configuration
from config import config,get_config
from config import Config

# Import models
from models import DatabaseManager
from models.database import Prospect, CallHistory, Campaign

# Import services
from services import (
    UnifiedVoiceBot,
    UnifiedCampaignManager,
    ServiceHealthChecker
)

# Import utilities
from utils import log_api_call, timing_decorator

from sqlalchemy import text

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
    logger.info("Voice agent services initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize services: {e}")
    raise

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