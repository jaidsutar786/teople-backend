"""
Email Configuration Test Script
Run this to check if email is working
"""

import os
import sys
import django

# Setup Django
sys.path.append(r'c:\Users\admin\Downloads\src\manage')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'login_backend.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def test_email():
    print("=" * 60)
    print("📧 TESTING EMAIL CONFIGURATION")
    print("=" * 60)
    
    print(f"\n📋 Current Settings:")
    print(f"   EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"   EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"   EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    print(f"   DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print(f"   EMAIL_HOST_PASSWORD: {'*' * len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else 'NOT SET'}")
    
    print(f"\n🚀 Sending test email...")
    
    try:
        result = send_mail(
            subject='🧪 Test Email from Django - Teople Technologies',
            message='Hello!\n\nThis is a test email from your Django application.\n\nIf you receive this, your email configuration is working correctly!\n\nBest Regards,\nDjango Server',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.EMAIL_HOST_USER],  # Send to self
            fail_silently=False,
        )
        
        if result == 1:
            print(f"\n✅ SUCCESS! Email sent successfully!")
            print(f"   📬 Check inbox: {settings.EMAIL_HOST_USER}")
            print(f"   📊 Result: {result} email(s) sent")
            return True
        else:
            print(f"\n⚠️ WARNING: Email send returned {result}")
            print(f"   This might indicate a problem")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: Failed to send email")
        print(f"   Error Type: {type(e).__name__}")
        print(f"   Error Message: {str(e)}")
        
        # Detailed error analysis
        error_str = str(e).lower()
        
        if 'authentication' in error_str or '535' in error_str:
            print(f"\n💡 SOLUTION:")
            print(f"   1. Gmail App Password is wrong or expired")
            print(f"   2. Generate new App Password:")
            print(f"      → https://myaccount.google.com/security")
            print(f"      → Enable 2-Step Verification")
            print(f"      → Search 'App passwords'")
            print(f"      → Generate new password")
            print(f"   3. Update settings.py with new password (remove spaces)")
            
        elif 'certificate' in error_str or 'ssl' in error_str:
            print(f"\n💡 SOLUTION:")
            print(f"   SSL Certificate error detected")
            print(f"   Try using custom email backend:")
            print(f"   EMAIL_BACKEND = 'accounts.email_backend.CustomEmailBackend'")
            
        elif 'connection' in error_str or 'timeout' in error_str:
            print(f"\n💡 SOLUTION:")
            print(f"   1. Check internet connection")
            print(f"   2. Check firewall/antivirus blocking port 587")
            print(f"   3. Try different network")
            
        else:
            print(f"\n💡 GENERAL SOLUTIONS:")
            print(f"   1. Check Gmail App Password is correct")
            print(f"   2. Verify 2-Step Verification is enabled")
            print(f"   3. Check EMAIL_HOST_USER matches Gmail account")
            print(f"   4. Try console backend for testing:")
            print(f"      EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'")
        
        import traceback
        print(f"\n📋 Full Error Traceback:")
        traceback.print_exc()
        
        return False

if __name__ == '__main__':
    print("\n")
    success = test_email()
    print("\n" + "=" * 60)
    if success:
        print("✅ EMAIL CONFIGURATION IS WORKING!")
        print("   You can now send OTP emails to users")
    else:
        print("❌ EMAIL CONFIGURATION NEEDS FIXING")
        print("   Follow the solutions above")
    print("=" * 60)
    print("\n")
