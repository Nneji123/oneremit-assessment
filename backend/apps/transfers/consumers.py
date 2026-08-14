"""WebSocket consumer for per-transfer status updates.

Intentionally unauthenticated: the assessment API is local/open, so any client
may subscribe to ``ws/transfers/<uuid>/``. The consumer joins the
``transfer_<id>`` group, accepts, sends an initial snapshot of the transfer, and
relays ``transfer.status`` group events pushed by the service layer.
"""

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from transfers.realtime import EVENT_TYPE


@database_sync_to_async
def _transfer_snapshot(transfer_id):
    from transfers.models import Transfer
    from transfers.serializers import TransferSerializer

    try:
        transfer = Transfer.objects.get(pk=transfer_id)
    except (Transfer.DoesNotExist, ValueError):
        return None
    return TransferSerializer(transfer).data


class TransferStatusConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.transfer_id = self.scope["url_route"]["kwargs"]["transfer_id"]
        self.group_name = f"transfer_{self.transfer_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        snapshot = await _transfer_snapshot(self.transfer_id)
        if snapshot is not None:
            await self.send_json({"type": EVENT_TYPE, "transfer": snapshot})

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def transfer_status(self, event):
        await self.send_json({"type": EVENT_TYPE, "transfer": event["transfer"]})
