"""
Services package for Voice Bot Project

This package contains all service classes for voice bot functionality.
"""

from services.inbound_agent_service import InboundCallHandler
from .azure_speech import AzureSpeechProcessor
from .twilio_handler import TwilioVoiceHandler
from .conversation_engine import (
    UnifiedConversationEngine,
    ConversationTemplates
)
from .lead_scorer import UnifiedLeadScorer
from .voice_bot import UnifiedVoiceBot
from .campaign_manager import UnifiedCampaignManager


__all__ = [
    'AzureSpeechProcessor',
    'TwilioVoiceHandler', 
    'UnifiedConversationEngine',
    'ConversationTemplates',
    'UnifiedLeadScorer',
    'UnifiedVoiceBot',
    'UnifiedCampaignManager',
    'InboundAgentService'
]

# Package metadata
__version__ = '1.0.0'
__author__ = 'Voice Bot Team'
__description__ = 'Core services for AI-powered voice bot functionality'




# Service factory functions
def create_voice_bot(config, db_manager):
    """
    Factory function to create a complete voice bot instance.
    
    Args:
        config: Application configuration object
        db_manager: Database manager instance
    
    Returns:
        UnifiedVoiceBot: Configured voice bot instance
    """
    return UnifiedVoiceBot(config, db_manager)

def create_campaign_manager(voice_bot, db_manager):
    """
    Factory function to create a campaign manager instance.
    
    Args:
        voice_bot: Voice bot instance
        db_manager: Database manager instance
    
    Returns:
        UnifiedCampaignManager: Configured campaign manager instance
    """
    return UnifiedCampaignManager(voice_bot, db_manager)

def create_inbound_agent_service(config, db_manager, existing_services=None):
    """
    Factory function to create an inbound agent service instance.
    
    Args:
        config: Application configuration object
        db_manager: Database manager instance
        existing_services: Dict of existing services to reuse
    
    Returns:
        InboundAgentService: Configured inbound agent service instance
    """
    return InboundAgentService(
        config=config,
        db_manager=db_manager,
        voice_service=existing_services.get('voice') if existing_services else None,
        ai_service=existing_services.get('ai') if existing_services else None,
        sentiment_service=existing_services.get('sentiment') if existing_services else None
    )

# Service health check utilities
class ServiceHealthChecker:
    """Utility class for checking service health"""
    
    @staticmethod
    def check_azure_speech(speech_processor):
        """Check Azure Speech Services health"""
        try:
            # Test TTS with a simple phrase
            import asyncio
            result = asyncio.run(speech_processor.text_to_speech_stream("Test"))
            return result['success']
        except Exception as e:
            print(f"Azure Speech health check failed: {e}")
            return False
    
    @staticmethod
    def check_twilio(twilio_handler):
        """Check Twilio service health"""
        try:
            # Test by fetching account info
            account = twilio_handler.client.api.accounts(
                twilio_handler.account_sid
            ).fetch()
            return account.status == 'active'
        except Exception as e:
            print(f"Twilio health check failed: {e}")
            return False
    
    @staticmethod
    def check_openai(conversation_engine):
        """Check OpenAI service health"""
        try:
            # Test with a simple completion
            response = conversation_engine.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            return bool(response.choices)
        except Exception as e:
            print(f"OpenAI health check failed: {e}")
            return False

# Export health checker
__all__.append('ServiceHealthChecker')