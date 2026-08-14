from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from transfers.enums import TransferStatus
from transfers.models import Transfer
from transfers.services import InvalidTransferTransition, transition_transfer

TRANSFER_STATUSES = (
    TransferStatus.PENDING,
    TransferStatus.PROCESSING,
    TransferStatus.COMPLETED,
    TransferStatus.FAILED,
    TransferStatus.CANCELLED,
)

ALLOWED_TRANSITIONS = {
    (TransferStatus.PENDING, TransferStatus.PROCESSING),
    (TransferStatus.PENDING, TransferStatus.CANCELLED),
    (TransferStatus.PROCESSING, TransferStatus.COMPLETED),
    (TransferStatus.PROCESSING, TransferStatus.FAILED),
}


def _make_transfer(**overrides):
    fields = {
        "amount": Decimal("100.00"),
        "currency": "NGN",
        "recipient_ref": "recipient-123",
        "idempotency_key": "key-123",
        "request_fingerprint": "fingerprint-123",
    }
    fields.update(overrides)
    return Transfer(**fields)


def _create_transfer(**overrides):
    transfer = _make_transfer(**overrides)
    transfer.save()
    return transfer


@pytest.mark.django_db
def test_transition_pending_to_processing():
    transfer = _create_transfer()

    result = transition_transfer(transfer, "processing")

    assert result.status == "processing"
    assert result.pk == transfer.pk
    transfer.refresh_from_db()
    assert transfer.status == "processing"


@pytest.mark.django_db
def test_transition_pending_to_cancelled():
    transfer = _create_transfer()

    result = transition_transfer(transfer, "cancelled")

    assert result.status == "cancelled"
    transfer.refresh_from_db()
    assert transfer.status == "cancelled"


@pytest.mark.django_db
def test_transition_processing_to_completed():
    transfer = _create_transfer(status="processing")

    result = transition_transfer(transfer, "completed")

    assert result.status == "completed"
    transfer.refresh_from_db()
    assert transfer.status == "completed"


@pytest.mark.django_db
def test_transition_processing_to_failed():
    transfer = _create_transfer(status="processing")

    result = transition_transfer(transfer, "failed")

    assert result.status == "failed"
    transfer.refresh_from_db()
    assert transfer.status == "failed"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "current,target",
    [
        (current, target)
        for current in TRANSFER_STATUSES
        for target in TRANSFER_STATUSES
        if (current, target) not in ALLOWED_TRANSITIONS
    ],
)
def test_forbidden_transitions_raise_invalid_transition(current, target):
    transfer = _create_transfer(status=current)

    with pytest.raises(InvalidTransferTransition):
        transition_transfer(transfer, target)


@pytest.mark.django_db
def test_invalid_transition_error_text_mentions_current_and_requested_statuses():
    transfer = _create_transfer(status="completed")

    with pytest.raises(InvalidTransferTransition) as excinfo:
        transition_transfer(transfer, TransferStatus.PROCESSING)

    assert "completed" in str(excinfo.value)
    assert "processing" in str(excinfo.value)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "amount", [Decimal("0.00"), Decimal("0"), Decimal("-1.00"), Decimal("-0.01")]
)
def test_amount_must_be_positive(amount):
    transfer = _make_transfer(amount=amount)

    with pytest.raises(ValidationError) as excinfo:
        transfer.full_clean()

    assert "amount" in excinfo.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize(
    "amount", [Decimal("100.00"), Decimal("0.01"), Decimal("999.99")]
)
def test_positive_amount_is_valid(amount):
    transfer = _make_transfer(amount=amount)

    transfer.full_clean()

    assert transfer.amount == amount


@pytest.mark.django_db
@pytest.mark.parametrize(
    "amount", [Decimal("10.555"), Decimal("10.001"), Decimal("0.999")]
)
def test_amount_rejects_more_than_two_decimal_places(amount):
    transfer = _make_transfer(amount=amount)

    with pytest.raises(ValidationError) as excinfo:
        transfer.full_clean()

    assert "amount" in excinfo.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize("amount", [Decimal("10.5"), Decimal("10.50"), Decimal("0.01")])
def test_amount_accepts_two_or_fewer_decimal_places(amount):
    transfer = _make_transfer(amount=amount)

    transfer.full_clean()


def test_currency_choices_are_uppercase():
    choices = Transfer._meta.get_field("currency").choices

    assert {value for value, _label in choices} == {"NGN", "USD", "GBP", "EUR"}


@pytest.mark.django_db
@pytest.mark.parametrize("currency", ["ngn", "usd", "gbp", "eur", "XXX"])
def test_non_uppercase_currency_is_rejected(currency):
    transfer = _make_transfer(currency=currency)

    with pytest.raises(ValidationError) as excinfo:
        transfer.full_clean()

    assert "currency" in excinfo.value.message_dict


@pytest.mark.django_db
def test_provider_transfer_id_is_nullable():
    transfer = _make_transfer(provider_transfer_id=None)
    transfer.full_clean()
    transfer.save()

    assert Transfer.objects.get(id=transfer.id).provider_transfer_id is None


@pytest.mark.django_db
def test_provider_transfer_id_is_unique():
    Transfer.objects.create(
        amount=Decimal("100.00"),
        currency="NGN",
        recipient_ref="recipient-123",
        idempotency_key="key-a",
        request_fingerprint="fingerprint-a",
        provider_transfer_id="prov-1",
    )

    with pytest.raises(IntegrityError):
        Transfer.objects.create(
            amount=Decimal("100.00"),
            currency="NGN",
            recipient_ref="recipient-456",
            idempotency_key="key-b",
            request_fingerprint="fingerprint-b",
            provider_transfer_id="prov-1",
        )


@pytest.mark.django_db
def test_idempotency_key_is_unique():
    Transfer.objects.create(
        amount=Decimal("100.00"),
        currency="NGN",
        recipient_ref="recipient-123",
        idempotency_key="dup-key",
        request_fingerprint="fingerprint-a",
    )

    with pytest.raises(IntegrityError):
        Transfer.objects.create(
            amount=Decimal("100.00"),
            currency="NGN",
            recipient_ref="recipient-456",
            idempotency_key="dup-key",
            request_fingerprint="fingerprint-b",
        )


@pytest.mark.django_db
def test_transition_rejects_unsaved_transfer():
    transfer = _make_transfer()

    with pytest.raises(
        ValueError, match="transition_transfer requires a persisted Transfer"
    ):
        transition_transfer(transfer, "processing")


@pytest.mark.django_db
def test_transition_returns_locked_persisted_transfer():
    transfer = _create_transfer()

    result = transition_transfer(transfer, "processing")

    fresh = Transfer.objects.get(pk=transfer.pk)
    assert result is not transfer
    assert result.status == fresh.status == "processing"
    assert result.pk == transfer.pk


@pytest.mark.django_db
def test_transition_reads_persisted_status_not_stale_memory():
    transfer = _create_transfer()
    Transfer.objects.filter(pk=transfer.pk).update(status="processing")
    assert transfer.status == "pending"

    result = transition_transfer(transfer, "completed")
    assert result.status == "completed"


@pytest.mark.django_db
def test_stale_concurrent_transition_cannot_apply_invalid_transition():
    first_caller = _create_transfer()
    second_caller = Transfer.objects.get(pk=first_caller.pk)

    transition_transfer(first_caller, "processing")

    with pytest.raises(InvalidTransferTransition):
        transition_transfer(second_caller, TransferStatus.CANCELLED)

    assert Transfer.objects.get(pk=first_caller.pk).status == "processing"


@pytest.mark.django_db
def test_invalid_status_rejected_at_db_level():
    transfer = _create_transfer()

    with pytest.raises(IntegrityError):
        Transfer.objects.filter(pk=transfer.pk).update(status="bogus")
