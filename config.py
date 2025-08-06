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