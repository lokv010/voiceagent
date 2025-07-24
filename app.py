"""
Main Flask application for Voice Bot Project

This is the main entry point for the voice bot web service.
"""

from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import os
import logging
import asyncio
from datetime import datetime, timedelta
import json
from typing import Dict, Any

# Import configuration
from config import config

# Import models
from models import DatabaseManager, ProspectManager
from models.database import Prospect, CallHistory, Campaign

# Import services
from services import (
    UnifiedVoiceBot,
    UnifiedCampaignManager,
    ServiceHealthChecker
)

# Import utilities
from utils import (
    log_api_call,
    timing_decorator,
    rate_limit_check,
    ValidationError,
    validate_campaign_params,
    create_pagination_info
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('voice_bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Load configuration
config_name = os.getenv('FLASK_ENV', 'development')
app.config.from_object(config[config_name])

# Enable CORS for all routes
CORS(app, origins=['http://localhost:3000', 'https://your-domain.com'])

# Initialize database
try:
    db_manager = DatabaseManager(app.config['SQLALCHEMY_DATABASE_URI'])
    logger.info("Database initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    raise

# Initialize voice bot
try:
    voice_bot = UnifiedVoiceBot(app.config, db_manager)
    logger.info("Voice bot initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize voice bot: {e}")
    raise

# Initialize campaign manager
try:
    campaign_manager = UnifiedCampaignManager(voice_bot, db_manager)
    logger.info("Campaign manager initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize campaign manager: {e}")
    raise

# Global error handlers
@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({'error': 'Not found', 'message': 'The requested resource was not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {str(error)}")
    return jsonify({'error': 'Internal server error', 'message': 'An unexpected error occurred'}), 500

@app.errorhandler(ValidationError)
def handle_validation_error(error):
    """Handle validation errors"""
    return jsonify({'error': 'Validation error', 'message': str(error)}), 400

@app.errorhandler(Exception)
def handle_exception(e):
    """Handle unexpected exceptions"""
    logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
    return jsonify({'error': 'An unexpected error occurred'}), 500

# Middleware for request logging
@app.before_request
def log_request():
    """Log incoming requests"""
    if request.path.startswith('/api/'):
        logger.info(f"API Request: {request.method} {request.path} from {request.remote_addr}")

@app.after_request
def log_response(response):
    """Log response details"""
    if request.path.startswith('/api/'):
        logger.info(f"API Response: {request.method} {request.path} - {response.status_code}")
    
    # Add CORS headers
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    
    return response

# ==================== TWILIO WEBHOOK ENDPOINTS ====================

@app.route('/voice-webhook', methods=['POST'])
@timing_decorator
def voice_webhook():
    """Handle Twilio voice webhook for call initiation"""
    try:
        call_sid = request.form.get('CallSid')
        from_number = request.form.get('From')
        call_status = request.form.get('CallStatus')
        
        logger.info(f"Voice webhook: {call_sid} - {call_status} from {from_number}")
        
        # Handle the call
        twiml_response = asyncio.run(
            voice_bot.handle_webhook_call(call_sid, request.form.to_dict())
        )
        
        return twiml_response, 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"Voice webhook error: {str(e)}")
        # Return fallback TwiML
        fallback_twiml = voice_bot.twilio_handler.generate_twiml_response(
            "I'm sorry, there was an error. Please try again later.",
            gather_input=False
        )
        return fallback_twiml, 200, {'Content-Type': 'text/xml'}

@app.route('/voice-webhook/process', methods=['POST'])
@timing_decorator
def process_speech():
    """Process speech input from customer during conversation"""
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
        fallback_twiml = voice_bot.twilio_handler.generate_twiml_response(
            "Thank you for your time. Goodbye!",
            gather_input=False
        )
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

# ==================== API ENDPOINTS ====================

@app.route('/api/start-call', methods=['POST'])
@timing_decorator
def start_call():
    """API endpoint to start a new call"""
    try:
        data = request.get_json()
        phone_number = data.get('phone_number')
        call_type = data.get('call_type', 'auto')
        
        # Validate input
        if not phone_number:
            return jsonify({'success': False, 'error': 'Phone number required'}), 400
        
        # Rate limiting
        if not rate_limit_check(f"start_call_{request.remote_addr}", limit=10, window=3600):
            return jsonify({'success': False, 'error': 'Rate limit exceeded'}), 429
        
        # Validate phone number format
        phone_validation = voice_bot.twilio_handler.validate_phone_number(phone_number)
        if not phone_validation.get('valid', True):
            return jsonify({
                'success': False,
                'error': 'Invalid phone number',
                'details': phone_validation.get('error')
            }), 400
        
        # Start the call
        result = asyncio.run(voice_bot.initiate_call(phone_number, call_type))
        
        if result['success']:
            logger.info(f"Call initiated via API: {result['call_sid']} to {phone_number}")
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Start call API error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/form-webhook', methods=['POST'])
@timing_decorator
def form_webhook():
    """Handle form submissions from website"""
    try:
        form_data = request.get_json()
        
        # Validate required fields
        required_fields = ['phone', 'product']
        missing_fields = [field for field in required_fields if not form_data.get(field)]
        
        if missing_fields:
            return jsonify({
                'success': False,
                'error': 'Missing required fields',
                'missing_fields': missing_fields
            }), 400
        
        # Create prospect from form
        prospect_manager = voice_bot.prospect_manager
        prospect = prospect_manager.create_prospect_from_form(form_data)
        
        # Determine call priority based on form data
        call_priority = 'high' if form_data.get('budget') and form_data.get('timeline') else 'normal'
        
        # Schedule immediate call
        result = asyncio.run(voice_bot.initiate_call(
            prospect.phone_number, 
            'form_follow_up'
        ))
        
        response_data = {
            'success': True,
            'status': 'received',
            'prospect_id': prospect.id,
            'call_initiated': result['success'],
            'call_priority': call_priority
        }
        
        if result['success']:
            response_data['call_sid'] = result['call_sid']
        
        logger.info(f"Form submission processed: prospect {prospect.id}, call initiated: {result['success']}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Form webhook error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/upload-cold-leads', methods=['POST'])
@timing_decorator
def upload_cold_leads():
    """Upload cold lead list for calling"""
    try:
        data = request.get_json()
        leads_list = data.get('leads', [])
        target_product = data.get('target_product', 'general')
        
        if not leads_list:
            return jsonify({'success': False, 'error': 'No leads provided'}), 400
        
        # Process leads
        prospect_manager = voice_bot.prospect_manager
        created_prospects = []
        errors = []
        
        for lead_data in leads_list:
            try:
                # Validate phone number
                if not lead_data.get('phone'):
                    errors.append(f"Missing phone number for {lead_data.get('name', 'unknown')}")
                    continue
                
                # Add target product
                lead_data['target_product'] = target_product
                
                # Create prospect
                prospect = prospect_manager.create_prospect_from_cold_list(lead_data)
                created_prospects.append({
                    'prospect_id': prospect.id,
                    'phone': prospect.phone_number,
                    'name': prospect.name
                })
                
            except Exception as e:
                errors.append(f"Error creating prospect for {lead_data.get('phone', 'unknown')}: {str(e)}")
        
        logger.info(f"Cold leads uploaded: {len(created_prospects)} created, {len(errors)} errors")
        
        return jsonify({
            'success': True,
            'status': 'processed',
            'prospects_created': len(created_prospects),
            'prospects': created_prospects,
            'errors': errors
        })
        
    except Exception as e:
        logger.error(f"Upload cold leads error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== CAMPAIGN MANAGEMENT ====================

@app.route('/api/campaign/start', methods=['POST'])
@timing_decorator
def start_campaign():
    """Start a unified campaign"""
    try:
        campaign_params = request.get_json()
        
        # Validate parameters
        validated_params = validate_campaign_params(campaign_params)
        campaign_type = validated_params.get('type', 'mixed')
        
        logger.info(f"Starting campaign: {campaign_type}")
        
        if campaign_type == 'form_follow_up':
            result = campaign_manager.create_form_follow_up_campaign(
                hours_back=validated_params.get('hours_back', 24),
                product_filter=campaign_params.get('product_filter'),
                max_calls=validated_params.get('max_calls', 100)
            )
        elif campaign_type == 'cold_outreach':
            result = campaign_manager.create_cold_outreach_campaign(
                prospect_list=campaign_params.get('prospect_list', []),
                product_target=campaign_params.get('product_target'),
                call_schedule=campaign_params.get('call_schedule', 'business_hours'),
                max_calls=validated_params.get('max_calls', 100)
            )
        elif campaign_type == 'mixed':
            result = campaign_manager.create_mixed_campaign(
                include_forms=validated_params.get('include_forms', True),
                include_cold=validated_params.get('include_cold', True),
                max_calls=validated_params.get('max_calls', 100)
            )
        else:
            return jsonify({'success': False, 'error': 'Invalid campaign type'}), 400
        
        logger.info(f"Campaign started: {campaign_type} - {result.get('campaign_id')}")
        
        return jsonify({'success': True, **result})
        
    except ValidationError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Start campaign error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/<int:campaign_id>/status', methods=['GET'])
def get_campaign_status(campaign_id):
    """Get campaign status and progress"""
    try:
        status = campaign_manager.get_campaign_status(campaign_id)
        
        if 'error' in status:
            return jsonify({'success': False, **status}), 404
        
        return jsonify({'success': True, **status})
        
    except Exception as e:
        logger.error(f"Get campaign status error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/campaign/<int:campaign_id>/stop', methods=['POST'])
def stop_campaign(campaign_id):
    """Stop a running campaign"""
    try:
        result = campaign_manager.stop_campaign(campaign_id)
        
        if 'error' in result:
            return jsonify({'success': False, **result}), 404
        
        logger.info(f"Campaign stopped: {campaign_id}")
        
        return jsonify({'success': True, **result})
        
    except Exception as e:
        logger.error(f"Stop campaign error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== ANALYTICS & REPORTING ====================

@app.route('/api/analytics/dashboard', methods=['GET'])
@timing_decorator
def get_dashboard_analytics():
    """Get dashboard analytics data"""
    try:
        # Get date range parameters
        days_back = int(request.args.get('days_back', 30))
        start_date = datetime.utcnow() - timedelta(days=days_back)
        
        # Get analytics data
        analytics = campaign_manager.get_analytics_data(start_date)
        
        return jsonify({'success': True, **analytics})
        
    except Exception as e:
        logger.error(f"Dashboard analytics error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/analytics/performance', methods=['GET'])
def get_performance_analytics():
    """Get detailed performance analytics"""
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
            start_date = datetime.utcnow() - timedelta(days=30)
        
        if end_date:
            end_date = datetime.fromisoformat(end_date)
        else:
            end_date = datetime.utcnow()
        
        # Get performance data
        performance = campaign_manager.get_performance_analytics(
            start_date, end_date, source_filter, product_filter
        )
        
        return jsonify({'success': True, **performance})
        
    except Exception as e:
        logger.error(f"Performance analytics error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== PROSPECT MANAGEMENT ====================

@app.route('/api/prospects', methods=['GET'])
def get_prospects():
    """Get prospects with filtering and pagination"""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        source_filter = request.args.get('source')
        status_filter = request.args.get('status')
        search_query = request.args.get('search')
        
        # Get prospects
        prospects_data = campaign_manager.get_prospects_paginated(
            page, per_page, source_filter, status_filter, search_query
        )
        
        return jsonify({'success': True, **prospects_data})
        
    except Exception as e:
        logger.error(f"Get prospects error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/prospects/<int:prospect_id>', methods=['GET'])
def get_prospect_details(prospect_id):
    """Get detailed prospect information"""
    try:
        prospect_details = campaign_manager.get_prospect_details(prospect_id)
        
        if not prospect_details:
            return jsonify({'success': False, 'error': 'Prospect not found'}), 404
        
        return jsonify({'success': True, **prospect_details})
        
    except Exception as e:
        logger.error(f"Get prospect details error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/prospects/<int:prospect_id>/calls', methods=['GET'])
def get_prospect_calls(prospect_id):
    """Get call history for a prospect"""
    try:
        calls = campaign_manager.get_prospect_call_history(prospect_id)
        return jsonify({'success': True, 'calls': calls})
        
    except Exception as e:
        logger.error(f"Get prospect calls error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/prospects/<int:prospect_id>/do-not-call', methods=['POST'])
def mark_do_not_call(prospect_id):
    """Mark prospect as do not call"""
    try:
        result = campaign_manager.mark_prospect_do_not_call(prospect_id)
        
        logger.info(f"Prospect {prospect_id} marked as do not call")
        
        return jsonify({'success': True, **result})
        
    except Exception as e:
        logger.error(f"Mark do not call error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== SYSTEM MONITORING ====================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        session = db_manager.get_session()
        session.execute('SELECT 1')
        db_status = 'ok'
        
        # Test Twilio connection
        twilio_status = 'ok'
        try:
            if ServiceHealthChecker.check_twilio(voice_bot.twilio_handler):
                twilio_status = 'ok'
            else:
                twilio_status = 'error'
        except Exception as e:
            twilio_status = f'error: {str(e)}'
        
        # Test OpenAI connection
        openai_status = 'ok'
        try:
            if ServiceHealthChecker.check_openai(voice_bot.conversation_engine):
                openai_status = 'ok'
            else:
                openai_status = 'error'
        except Exception as e:
            openai_status = f'error: {str(e)}'
        
        # Test Azure Speech
        azure_status = 'ok'
        try:
            if ServiceHealthChecker.check_azure_speech(voice_bot.speech_processor):
                azure_status = 'ok'
            else:
                azure_status = 'error'
        except Exception as e:
            azure_status = f'error: {str(e)}'
        
        # Determine overall health
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
            'active_calls': len(voice_bot.active_calls)
        }
        
        status_code = 200 if overall_status == 'healthy' else 503
        return jsonify(health_data), status_code
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
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
            'last_updated': datetime.utcnow().isoformat()
        }
        
        return jsonify({'success': True, **stats})
        
    except Exception as e:
        logger.error(f"Get system stats error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== WEB ROUTES (Optional) ====================

@app.route('/')
def index():
    """Main dashboard page"""
    return jsonify({
        'message': 'Voice Bot API is running',
        'version': '1.0.0',
        'status': 'healthy',
        'endpoints': {
            'health': '/health',
            'start_call': '/api/start-call',
            'form_webhook': '/api/form-webhook',
            'voice_webhook': '/voice-webhook',
            'analytics': '/api/analytics/dashboard'
        }
    })

# ==================== STARTUP & CLEANUP ====================

@app.before_first_request
def startup():
    """Initialize application on startup"""
    logger.info("Voice Bot application starting up...")
    
    # Verify configuration
    required_config = [
        'OPENAI_API_KEY', 'AZURE_SPEECH_KEY', 'AZURE_SPEECH_REGION',
        'TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER'
    ]
    
    missing_config = [key for key in required_config if not getattr(app.config, key, None)]
    
    if missing_config:
        logger.error(f"Missing required configuration: {missing_config}")
        raise ValueError(f"Missing required configuration: {missing_config}")
    
    # Create database tables if they don't exist
    try:
        from models.database import Base
        Base.metadata.create_all(bind=db_manager.engine)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.error(f"Database setup error: {e}")
    
    logger.info("Voice Bot application started successfully")

@app.teardown_appcontext
def cleanup(error):
    """Clean up resources"""
    if error:
        logger.error(f"Application error: {str(error)}")
    
    # Close database session
    try:
        db_manager.close_session()
    except Exception as e:
        logger.error(f"Error closing database session: {str(e)}")

if __name__ == '__main__':
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('voice_bot.log'),
            logging.StreamHandler()
        ]
    )
    
    # Run the application
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"Starting Voice Bot application on port {port}")
    
    try:
        app.run(
            host='0.0.0.0', 
            port=port, 
            debug=debug_mode,
            threaded=True  # Enable threading for better performance
        )
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise