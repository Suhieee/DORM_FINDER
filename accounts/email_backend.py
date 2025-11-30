"""
Custom email backend using SendGrid HTTP API instead of SMTP.
This works on Railway free tier because it uses HTTPS, not SMTP ports.
"""
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class SendGridHTTPBackend(BaseEmailBackend):
    """
    SendGrid HTTP API backend that works on Railway free tier.
    Uses SendGrid's REST API instead of SMTP.
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.sendgrid_api_key = getattr(settings, 'SENDGRID_API_KEY', None)
        self.default_from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@dormfinder.com')
    
    def send_messages(self, email_messages):
        """Send messages using SendGrid HTTP API."""
        if not self.sendgrid_api_key:
            if not self.fail_silently:
                raise ValueError('SENDGRID_API_KEY is not set')
            return 0
        
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=self.sendgrid_api_key)
            sent_count = 0
            
            for message in email_messages:
                try:
                    # Get email content
                    subject = message.subject
                    from_email = message.from_email or self.default_from_email
                    to_emails = message.to
                    
                    # Get HTML or plain text content
                    if hasattr(message, 'alternatives') and message.alternatives:
                        # HTML email
                        html_content = message.alternatives[0][0]
                        text_content = message.body
                    else:
                        # Plain text email
                        html_content = None
                        text_content = message.body
                    
                    # Create SendGrid mail object
                    mail = Mail(
                        from_email=from_email,
                        to_emails=to_emails,
                        subject=subject,
                    )
                    
                    if html_content:
                        mail.add_content(Content("text/html", html_content))
                    if text_content:
                        mail.add_content(Content("text/plain", text_content))
                    
                    # Send email
                    response = sg.send(mail)
                    
                    if response.status_code in [200, 202]:
                        sent_count += 1
                        logger.info(f'✅ Email sent via SendGrid HTTP API to {to_emails}')
                    else:
                        logger.error(f'❌ SendGrid API error: {response.status_code} - {response.body}')
                        if not self.fail_silently:
                            raise Exception(f'SendGrid API error: {response.status_code}')
                
                except Exception as e:
                    logger.error(f'❌ Error sending email via SendGrid: {str(e)}', exc_info=True)
                    if not self.fail_silently:
                        raise
            
            return sent_count
            
        except ImportError:
            error_msg = 'sendgrid package not installed. Install with: pip install sendgrid'
            logger.error(error_msg)
            if not self.fail_silently:
                raise ImportError(error_msg)
            return 0
        except Exception as e:
            logger.error(f'❌ SendGrid HTTP API error: {str(e)}', exc_info=True)
            if not self.fail_silently:
                raise
            return 0

