"""
Helper utilities for Voice Bot Project

This module contains utility functions used throughout the application.
"""

import re
import uuid
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any
import phonenumbers
from phonenumbers import NumberParseException
import logging
from functools import wraps
import time

# Configure logging
logger = logging.getLogger(__name__)

# Phone number validation
def validate_phone_number(phone_number: str) -> bool:
    """
    Validate phone number format using Google's libphonenumber.
    
    Args:
        phone_number: The phone number to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        parsed_number = phonenumbers.parse(phone_number, None)
        return phonenumbers.is_valid_number(parsed_number)
    except NumberParseException:
        return False

def format_phone_number(phone_number: str, format_type: str = 'E164') -> Optional[str]:
    """
    Format phone number to specified format.
    
    Args:
        phone_number: The phone number to format
        format_type: Format type ('E164', 'NATIONAL', 'INTERNATIONAL')
        
    Returns:
        str: Formatted phone number or None if invalid
    """
    try:
        parsed_number = phonenumbers.parse(phone_number, None)
        if not phonenumbers.is_valid_number(parsed_number):
            return None
            
        format_map = {
            'E164': phonenumbers.PhoneNumberFormat.E164,
            'NATIONAL': phonenumbers.PhoneNumberFormat.NATIONAL,
            'INTERNATIONAL': phonenumbers.PhoneNumberFormat.INTERNATIONAL
        }
        
        format_enum = format_map.get(format_type, phonenumbers.PhoneNumberFormat.E164)
        return phonenumbers.format_number(parsed_number, format_enum)
    except NumberParseException:
        return None

# Email validation
def validate_email(email: str) -> bool:
    """
    Validate email address format.
    
    Args:
        email: The email address to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email.strip()))

# Time utilities
def calculate_time_ago(timestamp: datetime) -> str:
    """
    Calculate human-readable time difference.
    
    Args:
        timestamp: The timestamp to compare
        
    Returns:
        str: Human-readable time difference
    """
    now = datetime.utcnow()
    diff = now - timestamp
    
    if diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"

def get_business_hours(timezone: str = 'UTC') -> Dict[str, str]:
    """
    Get business hours configuration.
    
    Args:
        timezone: Timezone for business hours
        
    Returns:
        dict: Business hours configuration
    """
    return {
        'start': '09:00',
        'end': '17:00',
        'timezone': timezone,
        'weekdays_only': True
    }

def is_business_hours(dt: datetime = None, timezone: str = 'UTC') -> bool:
    """
    Check if current time is within business hours.
    
    Args:
        dt: Datetime to check (defaults to now)
        timezone: Timezone to use
        
    Returns:
        bool: True if within business hours
    """
    if dt is None:
        dt = datetime.utcnow()
    
    # Simple business hours check (9 AM - 5 PM, weekdays only)
    if dt.weekday() >= 5:  # Weekend
        return False
    
    hour = dt.hour
    return 9 <= hour < 17

# Text processing
def sanitize_text(text: str, max_length: int = 1000) -> str:
    """
    Sanitize text input by removing harmful characters and limiting length.
    
    Args:
        text: Text to sanitize
        max_length: Maximum allowed length
        
    Returns:
        str: Sanitized text
    """
    if not text:
        return ""
    
    # Remove or replace potentially harmful characters
    sanitized = re.sub(r'[<>"\']', '', text)
    sanitized = re.sub(r'\s+', ' ', sanitized)  # Normalize whitespace
    sanitized = sanitized.strip()
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    
    return sanitized

def extract_keywords(text: str, max_keywords: int = 10) -> List[str]:
    """
    Extract keywords from text.
    
    Args:
        text: Text to extract keywords from
        max_keywords: Maximum number of keywords to return
        
    Returns:
        list: List of keywords
    """
    # Simple keyword extraction (in production, use NLP libraries)
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were',
        'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
        'to', 'from', 'with', 'by', 'for', 'of', 'in', 'on', 'at'
    }
    
    words = re.findall(r'\b\w+\b', text.lower())
    keywords = [word for word in words if word not in stop_words and len(word) > 2]
    
    # Return most frequent keywords
    from collections import Counter
    word_counts = Counter(keywords)
    return [word for word, _ in word_counts.most_common(max_keywords)]

def calculate_similarity_score(text1: str, text2: str) -> float:
    """
    Calculate similarity score between two texts.
    
    Args:
        text1: First text
        text2: Second text
        
    Returns:
        float: Similarity score between 0 and 1
    """
    # Simple Jaccard similarity
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    if not union:
        return 0.0
    
    return len(intersection) / len(union)

# ID generation
def generate_unique_id(prefix: str = "") -> str:
    """
    Generate a unique identifier.
    
    Args:
        prefix: Optional prefix for the ID
        
    Returns:
        str: Unique identifier
    """
    unique_id = str(uuid.uuid4()).replace('-', '')[:16]
    return f"{prefix}{unique_id}" if prefix else unique_id

# Data parsing
def parse_form_data(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse and validate form submission data.
    
    Args:
        form_data: Raw form data
        
    Returns:
        dict: Parsed and validated form data
    """
    parsed_data = {}
    
    # Required fields
    if 'phone' in form_data:
        phone = format_phone_number(form_data['phone'])
        if phone:
            parsed_data['phone'] = phone
        else:
            raise ValueError("Invalid phone number format")
    
    # Optional fields
    optional_fields = ['name', 'email', 'product', 'budget', 'timeline', 'company', 'message']
    for field in optional_fields:
        if field in form_data and form_data[field]:
            parsed_data[field] = sanitize_text(str(form_data[field]))
    
    # Validate email if provided
    if 'email' in parsed_data and not validate_email(parsed_data['email']):
        del parsed_data['email']  # Remove invalid email rather than failing
    
    return parsed_data

# Financial utilities
def format_currency(amount: Union[int, float], currency: str = 'USD') -> str:
    """
    Format amount as currency.
    
    Args:
        amount: Amount to format
        currency: Currency code
        
    Returns:
        str: Formatted currency string
    """
    if currency == 'USD':
        return f"${amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"

def calculate_conversion_rate(conversions: int, total: int) -> float:
    """
    Calculate conversion rate as percentage.
    
    Args:
        conversions: Number of conversions
        total: Total number of attempts
        
    Returns:
        float: Conversion rate as percentage
    """
    if total == 0:
        return 0.0
    return (conversions / total) * 100

# Security utilities
def encrypt_sensitive_data(data: str, key: str) -> str:
    """
    Encrypt sensitive data (simple implementation).
    
    Args:
        data: Data to encrypt
        key: Encryption key
        
    Returns:
        str: Encrypted data (base64 encoded)
    """
    # Simple encryption using hashlib (not for production use)
    hasher = hashlib.sha256()
    hasher.update(f"{data}{key}".encode())
    encrypted = base64.b64encode(hasher.digest()).decode()
    return encrypted

def decrypt_sensitive_data(encrypted_data: str, key: str) -> str:
    """
    Decrypt sensitive data (placeholder implementation).
    
    Args:
        encrypted_data: Encrypted data
        key: Decryption key
        
    Returns:
        str: Decrypted data
    """
    # This is a placeholder - implement proper decryption
    # For now, just return the encrypted data
    return encrypted_data

# Rate limiting
def rate_limit_check(identifier: str, limit: int = 100, window: int = 3600) -> bool:
    """
    Check if rate limit is exceeded.
    
    Args:
        identifier: Unique identifier for rate limiting
        limit: Maximum requests allowed
        window: Time window in seconds
        
    Returns:
        bool: True if within rate limit, False otherwise
    """
    # Simple in-memory rate limiting (use Redis in production)
    import time
    
    if not hasattr(rate_limit_check, 'requests'):
        rate_limit_check.requests = {}
    
    now = time.time()
    window_start = now - window
    
    # Clean old requests
    if identifier in rate_limit_check.requests:
        rate_limit_check.requests[identifier] = [
            req_time for req_time in rate_limit_check.requests[identifier]
            if req_time > window_start
        ]
    else:
        rate_limit_check.requests[identifier] = []
    
    # Check rate limit
    current_requests = len(rate_limit_check.requests[identifier])
    if current_requests >= limit:
        return False
    
    # Add current request
    rate_limit_check.requests[identifier].append(now)
    return True

# Logging utilities
def log_api_call(endpoint: str, method: str, status_code: int, duration: float):
    """
    Log API call details.
    
    Args:
        endpoint: API endpoint
        method: HTTP method
        status_code: Response status code
        duration: Request duration in seconds
    """
    logger.info(
        f"API Call: {method} {endpoint} - {status_code} - {duration:.3f}s"
    )

# Pagination utilities
def create_pagination_info(page: int, per_page: int, total: int) -> Dict[str, Any]:
    """
    Create pagination information.
    
    Args:
        page: Current page number
        per_page: Items per page
        total: Total number of items
        
    Returns:
        dict: Pagination information
    """
    total_pages = (total + per_page - 1) // per_page
    
    return {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
        'prev_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page < total_pages else None
    }

# Decorator utilities
def timing_decorator(func):
    """Decorator to measure function execution time"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.debug(f"{func.__name__} took {end_time - start_time:.3f} seconds")
        return result
    return wrapper

def retry_decorator(max_retries: int = 3, delay: float = 1.0):
    """Decorator to retry function calls on failure"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"{func.__name__} attempt {attempt + 1} failed: {e}")
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts")
            
            raise last_exception
        return wrapper
    return decorator

# Data validation utilities
class ValidationError(Exception):
    """Custom validation error"""
    pass

def validate_campaign_params(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate campaign parameters.
    
    Args:
        params: Campaign parameters to validate
        
    Returns:
        dict: Validated parameters
        
    Raises:
        ValidationError: If validation fails
    """
    validated = {}
    
    # Campaign type validation
    valid_types = ['form_follow_up', 'cold_outreach', 'mixed']
    if 'type' in params:
        if params['type'] not in valid_types:
            raise ValidationError(f"Invalid campaign type. Must be one of: {valid_types}")
        validated['type'] = params['type']
    
    # Numeric parameter validation
    numeric_params = ['max_calls', 'hours_back', 'days_back']
    for param in numeric_params:
        if param in params:
            try:
                value = int(params[param])
                if value < 0:
                    raise ValidationError(f"{param} must be non-negative")
                validated[param] = value
            except (ValueError, TypeError):
                raise ValidationError(f"{param} must be a valid integer")
    
    # Boolean parameter validation
    boolean_params = ['include_forms', 'include_cold']
    for param in boolean_params:
        if param in params:
            if isinstance(params[param], bool):
                validated[param] = params[param]
            elif str(params[param]).lower() in ['true', '1', 'yes']:
                validated[param] = True
            elif str(params[param]).lower() in ['false', '0', 'no']:
                validated[param] = False
            else:
                raise ValidationError(f"{param} must be a boolean value")
    
    return validated

# Export all functions
__all__ = [
    'validate_phone_number', 'format_phone_number', 'validate_email',
    'calculate_time_ago', 'get_business_hours', 'is_business_hours',
    'sanitize_text', 'extract_keywords', 'calculate_similarity_score',
    'generate_unique_id', 'parse_form_data', 'format_currency',
    'calculate_conversion_rate', 'encrypt_sensitive_data', 'decrypt_sensitive_data',
    'rate_limit_check', 'log_api_call', 'create_pagination_info',
    'timing_decorator', 'retry_decorator', 'ValidationError',
    'validate_campaign_params'
]