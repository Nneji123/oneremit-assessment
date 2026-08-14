import hashlib
import hmac
import json
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from transfers.enums import ProviderEventOutcome, TransferStatus
from transfers.models import ProviderEvent, Transfer


class InvalidTransferTransition(Exception):
    """Raised when a transfer status transition is not allowed."""


class TransferNotFound(Exception):
    """Raised when a transfer cannot be found by primary key."""


class IdempotencyConflict(Exception):
    """Raised when an Idempotency-Key is reused with a different body."""


class DuplicateProviderEvent(Exception):
    """Raised when an event_id is replayed with an identical payload."""


class ProviderEventConflict(Exception):
    """Raised when an event_id is reused with a different payload."""


class UnknownProviderTransfer(Exception):
    """Raised when a webhook targets a provider id we never issued."""


class TransferNotSubmitted(Exception):
    """Raised when a webhook targets a transfer that is still pending."""


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
                f"{locked.status!r} to {target_status.value!r}."
            )
        locked.status = target_status
        locked.save(update_fields=["status", "updated_at"])
        return locked


def request_fingerprint(validated_data):
    normalized = {
        "amount": format(validated_data["amount"], ".2f"),
        "currency": validated_data["currency"],
        "recipient_ref": validated_data["recipient_ref"],
    }
    canonical = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def create_transfer(validated_data, idempotency_key):
    fingerprint = request_fingerprint(validated_data)
    try:
        with transaction.atomic():
            transfer = Transfer.objects.create(
                amount=validated_data["amount"],
                currency=validated_data["currency"],
                recipient_ref=validated_data["recipient_ref"],
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
            )
        return transfer, True
    except IntegrityError:
        existing = Transfer.objects.filter(idempotency_key=idempotency_key).first()
        if existing is None:
            raise
        if existing.request_fingerprint == fingerprint:
            return existing, False
        raise IdempotencyConflict(
            "Idempotency-Key conflict: request body differs from original."
        ) from None


def get_transfer(pk):
    try:
        return Transfer.objects.get(pk=pk)
    except (Transfer.DoesNotExist, ValidationError):
        raise TransferNotFound from None


def submit_transfer(pk):
    transfer = get_transfer(pk)
    with transaction.atomic():
        locked = transition_transfer(transfer, TransferStatus.PROCESSING)
        locked.provider_transfer_id = f"prov_{uuid.uuid4().hex}"
        locked.save(update_fields=["provider_transfer_id", "updated_at"])
    return locked


def cancel_transfer(pk):
    return transition_transfer(get_transfer(pk), TransferStatus.CANCELLED)


def verify_provider_signature(body, signature):
    if not signature or not signature.startswith("sha256="):
        return False
    expected = signature[len("sha256=") :]
    secret = settings.PROVIDER_WEBHOOK_SECRET.encode("utf-8")
    digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest)


def provider_payload_fingerprint(validated_data):
    canonical = {
        "event_id": validated_data["event_id"],
        "provider_transfer_id": validated_data["provider_transfer_id"],
        "status": validated_data["status"],
        "occurred_at": (
            validated_data["occurred_at"].isoformat()
            if validated_data.get("occurred_at")
            else None
        ),
    }
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def process_provider_event(validated_data):
    event_id = validated_data["event_id"]
    provider_transfer_id = validated_data["provider_transfer_id"]
    fingerprint = provider_payload_fingerprint(validated_data)
    try:
        with transaction.atomic():
            existing = (
                ProviderEvent.objects.select_for_update()
                .filter(event_id=event_id)
                .first()
            )
            if existing is not None:
                if existing.payload_fingerprint == fingerprint:
                    raise DuplicateProviderEvent from None
                raise ProviderEventConflict from None

            transfer = (
                Transfer.objects.select_for_update()
                .filter(provider_transfer_id=provider_transfer_id)
                .first()
            )
            if transfer is None:
                raise UnknownProviderTransfer from None
            if transfer.status == TransferStatus.PENDING:
                raise TransferNotSubmitted from None

            if transfer.status == TransferStatus.PROCESSING:
                transition_transfer(transfer, validated_data["status"])
                outcome = ProviderEventOutcome.APPLIED
            else:
                outcome = ProviderEventOutcome.IGNORED_TERMINAL

            return ProviderEvent.objects.create(
                transfer=transfer,
                event_id=event_id,
                provider_transfer_id=provider_transfer_id,
                provider_status=validated_data["status"],
                occurred_at=validated_data.get("occurred_at"),
                payload_fingerprint=fingerprint,
                outcome=outcome,
            )
    except IntegrityError:
        with transaction.atomic():
            existing = ProviderEvent.objects.select_for_update().get(event_id=event_id)
        if existing.payload_fingerprint == fingerprint:
            raise DuplicateProviderEvent from None
        raise ProviderEventConflict from None
