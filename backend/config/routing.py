"""WebSocket URL routing for the Channels ASGI application."""

from django.urls import path
from transfers.consumers import TransferStatusConsumer

websocket_urlpatterns = [
    path("ws/transfers/<uuid:transfer_id>/", TransferStatusConsumer.as_asgi()),
]
