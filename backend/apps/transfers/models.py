import uuid
from decimal import Decimal

from core.models import BaseModel
from django.core.validators import MinValueValidator
from django.db import models
from transfers.enums import (
    ProviderEventOutcome,
    ProviderEventStatus,
    TransferCurrency,
    TransferStatus,
)


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


class Transfer(BaseModel):
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
