"""
Custom email backend to fix SSL certificate verification error on Windows
"""
import ssl
from django.core.mail.backends.smtp import EmailBackend as SMTPBackend


class CustomEmailBackend(SMTPBackend):
    """Email backend that skips SSL certificate verification"""
    
    def open(self):
        """Override to use unverified SSL context"""
        if self.connection:
            return False
        
        connection_params = {'timeout': self.timeout} if self.timeout else {}
        
        try:
            self.connection = self.connection_class(
                self.host, self.port, **connection_params
            )
            
            if self.use_tls:
                # Create unverified SSL context
                context = ssl._create_unverified_context()
                self.connection.starttls(context=context)
            
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            
            return True
        except Exception as e:
            if not self.fail_silently:
                raise
            return False
