# Security Utilities for Login/Register
import re
from django.core.exceptions import ValidationError

def validate_password_strength(password):
    """Validate password strength"""
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long")
    
    if not re.search(r'[A-Z]', password):
        raise ValidationError("Password must contain at least one uppercase letter")
    
    if not re.search(r'[a-z]', password):
        raise ValidationError("Password must contain at least one lowercase letter")
    
    if not re.search(r'[0-9]', password):
        raise ValidationError("Password must contain at least one number")
    
    return True

def sanitize_input(text):
    """Sanitize user input to prevent XSS"""
    if not text:
        return text
    
    # Remove dangerous characters
    dangerous_chars = ['<', '>', '"', "'", '&', ';']
    for char in dangerous_chars:
        text = text.replace(char, '')
    
    return text.strip()

def validate_username(username):
    """Validate username format"""
    if not username or len(username) < 3:
        raise ValidationError("Username must be at least 3 characters long")
    
    if len(username) > 20:
        raise ValidationError("Username must be less than 20 characters")
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        raise ValidationError("Username can only contain letters, numbers, and underscores")
    
    return True
