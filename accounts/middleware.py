from django.utils import timezone
from django.contrib import messages
from datetime import timedelta

class UpdateLastSeenMiddleware:
    """Middleware to update user's last_seen timestamp on each request."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        if request.user.is_authenticated:
            # Update last_seen timestamp
            # Only update if last update was more than 1 minute ago to reduce DB writes
            if not request.user.last_seen or \
               (timezone.now() - request.user.last_seen) > timedelta(minutes=1):
                request.user.last_seen = timezone.now()
                request.user.save(update_fields=['last_seen'])
        
        return response


class SessionTimeoutMiddleware:
    """Middleware to handle session timeout warnings and automatic logout."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Get session age (time since last activity)
            session_key = '_session_last_activity'
            last_activity = request.session.get(session_key)
            
            if last_activity:
                # Calculate time since last activity
                elapsed = (timezone.now() - timezone.datetime.fromisoformat(last_activity)).total_seconds()
                
                # Warn user if session is about to expire (within 2 minutes)
                if 720 < elapsed < 900:  # Between 12-15 minutes
                    if not request.session.get('_session_warning_shown'):
                        messages.warning(
                            request, 
                            "Your session will expire soon due to inactivity. Please refresh the page to stay logged in."
                        )
                        request.session['_session_warning_shown'] = True
            
            # Update last activity time
            request.session[session_key] = timezone.now().isoformat()
            request.session['_session_warning_shown'] = False
        
        response = self.get_response(request)
        return response
