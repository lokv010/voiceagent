"""
Utilities package for Voice Bot Project

This package contains utility functions and helper classes.
"""

from .helpers import (
    validate_phone_number,
    format_phone_number,
    calculate_time_ago,
    sanitize_text,
    generate_unique_id,
    parse_form_data,
    format_currency,
    calculate_conversion_rate,
    get_business_hours,
    is_business_hours,
    encrypt_sensitive_data,
    decrypt_sensitive_data,
    rate_limit_check,
    log_api_call,
    create_pagination_info,
    validate_email,
    extract_keywords,
    calculate_similarity_score
)

__all__ = [
    'validate_phone_number',
    'format_phone_number', 
    'calculate_time_ago',
    'sanitize_text',
    'generate_unique_id',
    'parse_form_data',
    'format_currency',
    'calculate_conversion_rate',
    'get_business_hours',
    'is_business_hours',
    'encrypt_sensitive_data',
    'decrypt_sensitive_data',
    'rate_limit_check',
    'log_api_call',
    'create_pagination_info',
    'validate_email',
    'extract_keywords',
    'calculate_similarity_score'
]

# Package metadata
__version__ = '1.0.0'
__author__ = 'Voice Bot Team'
__description__ = 'Utility functions and helpers for Voice Bot'

# Constants
PHONE_NUMBER_REGEX = r'^\+?[1-9]\d{1,14}$'
EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
BUSINESS_HOURS_DEFAULT = {
    'start': '09:00',
    'end': '17:00',
    'timezone': 'UTC',
    'weekdays_only': True
}

# Error classes
class ValidationError(Exception):
    """Raised when data validation fails"""
    pass

class RateLimitError(Exception):
    """Raised when rate limit is exceeded"""
    pass

class EncryptionError(Exception):
    """Raised when encryption/decryption fails"""
    pass

# Export error classes
__all__.extend(['ValidationError', 'RateLimitError', 'EncryptionError'])

# Utility decorators
def timing_decorator(func):
    """Decorator to measure function execution time"""
    import time
    from functools import wraps
    
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        print(f"{func.__name__} took {end_time - start_time:.2f} seconds")
        return result
    return wrapper

def retry_decorator(max_retries=3, delay=1):
    """Decorator to retry function calls on failure"""
    import time
    from functools import wraps
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

# Export decorators
__all__.extend(['timing_decorator', 'retry_decorator'])