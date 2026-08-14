import uuid
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class TransferStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class TransferCurrency(models.TextChoices):
    NGN = "NGN", "Nigerian Naira"
    USD = "USD", "US Dollar"
    GBP = "GBP", "British Pound"
    EUR = "EUR", "Euro"


class ProviderEventStatus(models.TextChoices):
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class ProviderEventOutcome(models.TextChoices):
    APPLIED = "applied", "Applied"
    IGNORED_TERMINAL = "ignored_terminal", "Ignored terminal"


class ProviderEvent(models.Model):
    transfer = models.ForeignKey(
        "Transfer",
        on_delete=models.CASCADE,
        related_name="provider_events",
    )
    event_id = models.CharField(max_length=255, unique=True)
    provider_transfer_id = models.CharField(max_length=255, db_index=True)
    provider_status = models.CharField(
        max_length=16,
        choices=ProviderEventStatus.choices,
    )
    occurred_at = models.DateTimeField(null=True, blank=True)
    payload_fingerprint = models.CharField(max_length=255)
    outcome = models.CharField(
        max_length=32,
        choices=ProviderEventOutcome.choices,
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]


class Transfer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=40, unique=True, editable=False)
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.CharField(max_length=3, choices=TransferCurrency.choices)
    recipient_ref = models.CharField(max_length=255)
    status = models.CharField(
        max_length=16,
        choices=TransferStatus.choices,
        default=TransferStatus.PENDING,
    )
    provider_transfer_id = models.CharField(
        max_length=255, null=True, blank=True, unique=True
    )
    idempotency_key = models.CharField(max_length=255, unique=True)
    request_fingerprint = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="transfers_transfer_amount_gt_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=TransferStatus.values),
                name="transfers_transfer_status_valid",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"TRF-{uuid.uuid4().hex}"
        super().save(*args, **kwargs)
