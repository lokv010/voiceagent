import os
from dotenv import load_dotenv

load_dotenv()

class Config:
  
    # Database
   

    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://voice_bot_user:voiceroot@localhost:5432/voice_bot_db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_timeout': 20,
        'pool_recycle': -1,
        'pool_pre_ping': True
    }
    
    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Azure Services
    AZURE_SPEECH_KEY = os.getenv('AZURE_SPEECH_KEY')
    AZURE_SPEECH_REGION = os.getenv('AZURE_SPEECH_REGION')
    AZURE_TEXT_ANALYTICS_ENDPOINT = os.getenv('AZURE_TEXT_ANALYTICS_ENDPOINT')
    AZURE_TEXT_ANALYTICS_KEY = os.getenv('AZURE_TEXT_ANALYTICS_KEY')
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    
    # Application settings
    SECRET_KEY = os.getenv('SECRET_KEY')or 'voice-agent-secret-key'

    #webhook settings
    WEBHOOK_URL = os.getenv('WEBHOOK_URL') or 'http://localhost:5000'
    # Campaign settings
    MAX_CALLS_PER_HOUR = int(os.getenv('MAX_CALLS_PER_HOUR', '50'))
    MAX_CONVERSATION_TURNS = int(os.getenv('MAX_CONVERSATION_TURNS', '12'))
    MIN_QUALIFICATION_SCORE = int(os.getenv('MIN_QUALIFICATION_SCORE', '70'))
    
       # Service configuration
    SERVICE_NAME = 'python_voice_agent'
    SERVICE_VERSION = '1.0.0'
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')


    # Inbound Call Configuration
    COMPANY_NAME = os.getenv('COMPANY_NAME', 'Your Company')
    AGENT_TRANSFER_NUMBER = os.getenv('AGENT_TRANSFER_NUMBER', '+1234567890')
    ENABLE_INBOUND_CALLS = os.getenv('ENABLE_INBOUND_CALLS', 'true').lower() == 'true'
    
    # Business Hours
    BUSINESS_HOURS_START = os.getenv('BUSINESS_HOURS_START', '09:00')
    BUSINESS_HOURS_END = os.getenv('BUSINESS_HOURS_END', '17:00')
    BUSINESS_TIMEZONE = os.getenv('BUSINESS_TIMEZONE', 'UTC')
    
    # Call Queue Settings
    MAX_QUEUE_TIME = int(os.getenv('MAX_QUEUE_TIME', '300'))
    MAX_CONCURRENT_CALLS = int(os.getenv('MAX_CONCURRENT_CALLS', '10'))
    
    # Callback Settings
    ENABLE_CALLBACKS = os.getenv('ENABLE_CALLBACKS', 'true').lower() == 'true'
    CALLBACK_CONFIRMATION_SMS = os.getenv('CALLBACK_CONFIRMATION_SMS', 'false').lower() == 'true'

    # Performance optimizations
    ENABLE_RESPONSE_STREAMING = True
    ENABLE_TTS_CACHE = True
    MAX_TTS_CACHE_SIZE = 100  # MB
    ENABLE_PARALLEL_PROCESSING = True

    # Reduced timeouts for faster response
    SPEECH_RECOGNITION_TIMEOUT = 2000  # ms (reduced from 3000)
    MAX_AI_RESPONSE_TIME = 1500  # ms

    # Pre-warming settings
    PREWARM_COMMON_RESPONSES = True
    PREWARM_ON_STARTUP = True

    # Playbook settings
    PLAYBOOK_PDF_PATH = os.getenv('PLAYBOOK_PDF_PATH', 'playbook/sales_playbook.pdf')
    PLAYBOOK_CACHE_DIR = os.getenv('PLAYBOOK_CACHE_DIR', 'playbook/cache')
    PLAYBOOK_INDEX_UPDATE_HOURS = 24  # Re-index every 24 hours
    USE_PLAYBOOK_FIRST = True  # Prioritize playbook over AI
    PLAYBOOK_CONFIDENCE_THRESHOLD = 0.7
    PLAYBOOK_CONFIDENCE_THRESHOLD = 0.7
    SCENARIO_MATCH_THRESHOLD = 0.6
    MAX_RESPONSE_TIME_MS = 3000  # Keep under Twilio's 15s limit
    
    @staticmethod
    def validate_config():
        """Validate required configuration"""
        required_vars = [
            'OPENAI_API_KEY',
            'AZURE_SPEECH_KEY', 
            'AZURE_SPEECH_REGION',
            'TWILIO_ACCOUNT_SID',
            'TWILIO_AUTH_TOKEN',
            'TWILIO_PHONE_NUMBER'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
        return True

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    
    # Enable verbose logging in development
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    
    # Production-specific settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        **Config.SQLALCHEMY_ENGINE_OPTIONS,
        'pool_size': 20,
        'max_overflow': 30
    }

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    
    # Use in-memory database for tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable external API calls in tests
    OPENAI_API_KEY = 'test-key'
    AZURE_SPEECH_KEY = 'test-key'
    TWILIO_ACCOUNT_SID = 'test-sid'

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """Get configuration object"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    config_class = config.get(config_name, config['default'])
    
    # Validate configuration
    try:
        config_class.validate_config()
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise
    
    return config_class