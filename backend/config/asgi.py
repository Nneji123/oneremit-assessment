"""ASGI entrypoint.

Bootstrap Django first (``get_asgi_application``) so models/settings are ready,
then wire the Channels protocol router: plain HTTP is served by Django's ASGI
handler, and the WebSocket routes in :mod:`config.routing` handle realtime
transfer status updates.
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

from config.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(websocket_urlpatterns),
    }
)
