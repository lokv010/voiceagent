import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/voice_bot')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
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
    SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL', 'https://your-domain.com')
    
    # Campaign settings
    MAX_CALLS_PER_HOUR = int(os.getenv('MAX_CALLS_PER_HOUR', '50'))
    MAX_CONVERSATION_TURNS = int(os.getenv('MAX_CONVERSATION_TURNS', '12'))
    MIN_QUALIFICATION_SCORE = int(os.getenv('MIN_QUALIFICATION_SCORE', '70'))
    
    # Redis for Celery
    CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}