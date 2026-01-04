"""
ASGI config for classroom project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

# Set Django settings module before importing anything else
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'classroom.settings')

# Initialize Django
django.setup()

# Import after Django setup to avoid circular imports
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
import core.routing

# Get Redis URL for Railway
redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                core.routing.websocket_urlpatterns
            )
        )
    ),
})