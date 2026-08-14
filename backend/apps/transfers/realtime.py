"""Realtime status broadcasts over the Channels WebSocket layer.

``broadcast_transfer_status`` is the synchronous entry point the service layer
calls *after* a status-changing transaction has committed. It pushes a fresh
serialized snapshot to every client subscribed to ``transfer_<id>`` so the
detail page can update without polling.
"""

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from transfers.models import Transfer
from transfers.serializers import TransferSerializer

EVENT_TYPE = "transfer.status"


def broadcast_transfer_status(transfer_id):
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        transfer = Transfer.objects.get(pk=transfer_id)
    except (Transfer.DoesNotExist, ValueError):
        return
    message = {
        "type": EVENT_TYPE,
        "transfer": TransferSerializer(transfer).data,
    }
    async_to_sync(layer.group_send)(f"transfer_{transfer_id}", message)
