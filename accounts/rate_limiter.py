# Rate Limiter for Login/Register
from django.core.cache import cache
from django.http import JsonResponse
from functools import wraps
import time

def rate_limit(max_attempts=5, window_seconds=900):
    """
    Rate limiter decorator
    max_attempts: Maximum attempts allowed (default: 5)
    window_seconds: Time window in seconds (default: 900 = 15 minutes)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Get client IP
            ip = get_client_ip(request)
            
            # Create cache key
            cache_key = f"rate_limit_{view_func.__name__}_{ip}"
            
            # Get current attempts
            attempts = cache.get(cache_key, {'count': 0, 'first_attempt': time.time()})
            
            current_time = time.time()
            
            # Reset if window expired
            if current_time - attempts['first_attempt'] > window_seconds:
                attempts = {'count': 0, 'first_attempt': current_time}
            
            # Check if limit exceeded
            if attempts['count'] >= max_attempts:
                remaining_time = int(window_seconds - (current_time - attempts['first_attempt']))
                return JsonResponse({
                    'error': f'Too many attempts. Please try again after {remaining_time // 60} minutes'
                }, status=429)
            
            # Increment attempts
            attempts['count'] += 1
            cache.set(cache_key, attempts, window_seconds)
            
            # Call the view
            response = view_func(request, *args, **kwargs)
            
            # Reset on successful login (status 200)
            if response.status_code == 200:
                cache.delete(cache_key)
            
            return response
        
        return wrapper
    return decorator

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
