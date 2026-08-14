class InvalidTransferTransition(Exception):
    """Raised when a transfer status transition is not allowed."""


_ALLOWED_TRANSITIONS = {
    "pending": {"processing", "cancelled"},
    "processing": {"completed", "failed"},
}


def transition_transfer(transfer, target_status):
    allowed = _ALLOWED_TRANSITIONS.get(transfer.status)
    if allowed is None or target_status not in allowed:
        raise InvalidTransferTransition(
            f"Cannot transition Transfer from {transfer.status!r} to {target_status!r}."
        )
    transfer.status = target_status
    transfer.save(update_fields=["status", "updated_at"])
    return transfer
