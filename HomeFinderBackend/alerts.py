import smtplib
import logging
from email.mime.text import MIMEText
from django.conf import settings
from django.core.cache import cache
import requests

logger = logging.getLogger(__name__)

class AlertManager:
    """Handle system alerts and notifications"""
    
    ALERT_CACHE_PREFIX = 'alert_sent:'
    ALERT_THROTTLE_SECONDS = 3600  # Don't send same alert more than once per hour
    
    @classmethod
    def send_alert(cls, title, message, level='error', alert_key=None):
        """Send alert through configured channels"""
        if alert_key and cls._is_alert_throttled(alert_key):
            logger.info(f"Alert '{title}' throttled (sent too recently)")
            return False
            
        success = True
        
        # Send email alert if configured
        if hasattr(settings, 'ALERT_EMAIL_RECIPIENTS'):
            success &= cls._send_email_alert(title, message, level)
            
        # Send Slack alert if configured
        if hasattr(settings, 'SLACK_WEBHOOK_URL'):
            success &= cls._send_slack_alert(title, message, level)
            
        if alert_key and success:
            cls._mark_alert_sent(alert_key)
            
        return success
    
    @classmethod
    def _send_email_alert(cls, title, message, level):
        """Send alert via email"""
        try:
            msg = MIMEText(message)
            msg['Subject'] = f"[HomeFinder {level.upper()}] {title}"
            msg['From'] = settings.EMAIL_HOST_USER
            msg['To'] = ', '.join(settings.ALERT_EMAIL_RECIPIENTS)
            
            with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
                if settings.EMAIL_USE_TLS:
                    server.starttls()
                server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Failed to send email alert: {str(e)}")
            return False
    
    @classmethod
    def _send_slack_alert(cls, title, message, level):
        """Send alert to Slack"""
        try:
            color = {
                'error': '#ff0000',
                'warning': '#ffcc00',
                'info': '#36a64f'
            }.get(level, '#cccccc')
            
            payload = {
                "attachments": [{
                    "fallback": f"{title}: {message}",
                    "color": color,
                    "title": title,
                    "text": message,
                    "fields": [
                        {
                            "title": "Environment",
                            "value": settings.ENVIRONMENT,
                            "short": True
                        },
                        {
                            "title": "Level",
                            "value": level.upper(),
                            "short": True
                        }
                    ]
                }]
            }
            
            response = requests.post(
                settings.SLACK_WEBHOOK_URL,
                json=payload,
                timeout=5
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {str(e)}")
            return False
    
    @classmethod
    def _is_alert_throttled(cls, alert_key):
        """Check if an alert was sent too recently"""
        cache_key = f"{cls.ALERT_CACHE_PREFIX}{alert_key}"
        return bool(cache.get(cache_key))
    
    @classmethod
    def _mark_alert_sent(cls, alert_key):
        """Mark an alert as sent in cache"""
        cache_key = f"{cls.ALERT_CACHE_PREFIX}{alert_key}"
        cache.set(cache_key, True, cls.ALERT_THROTTLE_SECONDS)