"""
Tests package for Voice Bot Project

This package contains all test cases and testing utilities.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Test configuration
TEST_CONFIG = {
    'DATABASE_URL': 'sqlite:///:memory:',  # In-memory database for tests
    'OPENAI_API_KEY': 'test-key',
    'AZURE_SPEECH_KEY': 'test-key',
    'AZURE_SPEECH_REGION': 'test-region',
    'TWILIO_ACCOUNT_SID': 'test-sid',
    'TWILIO_AUTH_TOKEN': 'test-token',
    'TWILIO_PHONE_NUMBER': '+1234567890'
}

class BaseTestCase(unittest.TestCase):
    """Base test case with common setup and utilities"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.maxDiff = None
        self.test_start_time = datetime.utcnow()
        
    def tearDown(self):
        """Clean up after tests"""
        test_duration = datetime.utcnow() - self.test_start_time
        if test_duration.total_seconds() > 10:  # Warn about slow tests
            print(f"Warning: {self._testMethodName} took {test_duration.total_seconds():.2f}s")
    
    def create_mock_prospect(self, **kwargs):
        """Create a mock prospect for testing"""
        from models import Prospect, ProspectSource
        
        default_data = {
            'id': 1,
            'phone_number': '+1234567890',
            'name': 'Test User',
            'email': 'test@example.com',
            'source': ProspectSource.FORM_SUBMISSION.value,
            'product_interest': 'solar panels',
            'qualification_score': 25,
            'created_at': datetime.utcnow(),
            'do_not_call': False
        }
        
        prospect_data = {**default_data, **kwargs}
        
        # Create mock object with attributes
        mock_prospect = Mock()
        for key, value in prospect_data.items():
            setattr(mock_prospect, key, value)
        
        return mock_prospect
    
    def create_mock_call_history(self, **kwargs):
        """Create a mock call history for testing"""
        from models import CallHistory
        
        default_data = {
            'id': 1,
            'prospect_id': 1,
            'call_sid': 'test-call-sid',
            'call_type': 'form_follow_up',
            'call_duration': 300,
            'call_outcome': 'completed',
            'qualification_score': 75,
            'called_at': datetime.utcnow()
        }
        
        call_data = {**default_data, **kwargs}
        
        # Create mock object with attributes
        mock_call = Mock()
        for key, value in call_data.items():
            setattr(mock_call, key, value)
        
        return mock_call
    
    def assert_phone_number_valid(self, phone_number):
        """Assert that a phone number is valid"""
        from utils import validate_phone_number
        self.assertTrue(validate_phone_number(phone_number))
    
    def assert_api_response_valid(self, response, expected_keys=None):
        """Assert that an API response has valid structure"""
        self.assertIsInstance(response, dict)
        
        if expected_keys:
            for key in expected_keys:
                self.assertIn(key, response)

class MockServices:
    """Mock services for testing"""
    
    @staticmethod
    def create_mock_azure_speech():
        """Create mock Azure Speech service"""
        mock_speech = Mock()
        mock_speech.text_to_speech_stream.return_value = {
            'success': True,
            'audio_data': b'mock_audio_data',
            'audio_length': 1024
        }
        mock_speech.analyze_sentiment.return_value = {
            'sentiment': 'positive',
            'confidence_scores': {'positive': 0.8, 'neutral': 0.1, 'negative': 0.1},
            'overall_score': 0.7
        }
        return mock_speech
    
    @staticmethod
    def create_mock_twilio():
        """Create mock Twilio service"""
        mock_twilio = Mock()
        mock_twilio.initiate_outbound_call.return_value = {
            'success': True,
            'call_sid': 'test-call-sid',
            'status': 'initiated'
        }
        mock_twilio.generate_twiml_response.return_value = '<?xml version="1.0"?><Response><Say>Test</Say></Response>'
        return mock_twilio
    
    @staticmethod
    def create_mock_openai():
        """Create mock OpenAI service"""
        mock_openai = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Test response"
        mock_openai.chat.completions.create.return_value = mock_response
        return mock_openai

# Test utilities
def skip_if_no_credentials(test_func):
    """Decorator to skip tests if credentials are not available"""
    def wrapper(*args, **kwargs):
        if not all([
            os.getenv('OPENAI_API_KEY'),
            os.getenv('AZURE_SPEECH_KEY'), 
            os.getenv('TWILIO_ACCOUNT_SID')
        ]):
            return unittest.skip("API credentials not available")(test_func)(*args, **kwargs)
        return test_func(*args, **kwargs)
    return wrapper

def requires_database(test_func):
    """Decorator to skip tests if database is not available"""
    def wrapper(*args, **kwargs):
        try:
            from models import DatabaseManager
            db = DatabaseManager('sqlite:///:memory:')
            return test_func(*args, **kwargs)
        except Exception:
            return unittest.skip("Database not available")(test_func)(*args, **kwargs)
    return wrapper

# Export everything
__all__ = [
    'BaseTestCase',
    'MockServices', 
    'TEST_CONFIG',
    'skip_if_no_credentials',
    'requires_database'
]

# Test runner utilities
def run_all_tests():
    """Run all tests in the package"""
    loader = unittest.TestLoader()
    suite = loader.discover('.', pattern='test_*.py')
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

def run_integration_tests():
    """Run only integration tests"""
    from .test_integration import TestUnifiedVoiceBot, TestAPIEndpoints
    
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestUnifiedVoiceBot))
    suite.addTest(unittest.makeSuite(TestAPIEndpoints))
    
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

__all__.extend(['run_all_tests', 'run_integration_tests'])