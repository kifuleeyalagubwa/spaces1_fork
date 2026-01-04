# trends/middleware.py - Update with better local development handling
import threading
import re
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from .models import Institution

_thread_locals = threading.local()

def get_current_institution():
    return getattr(_thread_locals, 'institution', None)

def set_current_institution(institution):
    _thread_locals.institution = institution

def clear_current_institution():
    if hasattr(_thread_locals, 'institution'):
        delattr(_thread_locals, 'institution')

class InstitutionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        clear_current_institution()
        
        host = request.get_host().split(':')[0]  # Remove port
        institution = None
        
        # Debug info
        # print(f"DEBUG: Host: {host}, Path: {request.path}")
        
        # Method 1: Check for subdomain in development
        # Handle patterns like: testschool.127.0.0.1, testschool.localhost
        if settings.DEBUG:
            # Common local development patterns
            local_patterns = [
                r'^([a-zA-Z0-9-]+)\.127\.0\.0\.1$',
                r'^([a-zA-Z0-9-]+)\.localhost$',
                r'^([a-zA-Z0-9-]+)\.local$',
            ]
            
            for pattern in local_patterns:
                match = re.match(pattern, host)
                if match:
                    subdomain = match.group(1)
                    try:
                        institution = Institution.objects.get(
                            subdomain=subdomain,
                            is_active=True,
                            is_approved=True
                        )
                        break
                    except Institution.DoesNotExist:
                        continue
        
        # Method 2: Check session for manual institution selection
        if not institution and 'current_institution_id' in request.session:
            try:
                institution = Institution.objects.get(
                    id=request.session['current_institution_id'],
                    is_active=True,
                    is_approved=True
                )
            except Institution.DoesNotExist:
                pass
        
        # Method 3: Check user's profile for institution association
        if not institution and request.user.is_authenticated:
            try:
                if hasattr(request.user, 'profile') and request.user.profile.institution:
                    institution = request.user.profile.institution
                    # Store in session for future requests
                    request.session['current_institution_id'] = str(institution.id)
            except Exception:
                pass
        
        if institution:
            set_current_institution(institution)
            request.institution = institution
            # print(f"DEBUG: Institution set to: {institution.name}")
        
        return None
    
    def process_response(self, request, response):
        clear_current_institution()
        return response