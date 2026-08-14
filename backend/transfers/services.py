from django.db import transaction

from transfers.models import Transfer


class InvalidTransferTransition(Exception):
    """Raised when a transfer status transition is not allowed."""


_ALLOWED_TRANSITIONS = {
    "pending": {"processing", "cancelled"},
    "processing": {"completed", "failed"},
}


def transition_transfer(transfer, target_status):
    if transfer._state.adding:
        raise ValueError(
            "transition_transfer requires a persisted Transfer; "
            "save the Transfer before calling this function."
        )

    with transaction.atomic():
        locked = Transfer.objects.select_for_update().get(pk=transfer.pk)
        allowed = _ALLOWED_TRANSITIONS.get(locked.status)
        if allowed is None or target_status not in allowed:
            raise InvalidTransferTransition(
                f"Cannot transition Transfer from "
                f"{locked.status!r} to {target_status!r}."
            )
        locked.status = target_status
        locked.save(update_fields=["status", "updated_at"])
        return locked
