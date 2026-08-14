from decimal import Decimal

from rest_framework import serializers

from transfers.models import Transfer

SUPPORTED_CURRENCIES = {"NGN", "USD", "GBP", "EUR"}


class TransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transfer
        fields = [
            "id",
            "reference",
            "amount",
            "currency",
            "recipient_ref",
            "status",
            "provider_transfer_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class CreateTransferSerializer(serializers.Serializer):
    amount = serializers.DecimalField(
        max_digits=20,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    currency = serializers.CharField(max_length=3)
    recipient_ref = serializers.CharField(max_length=255)

    def validate_currency(self, value):
        normalized = value.upper()
        if normalized not in SUPPORTED_CURRENCIES:
            supported = ", ".join(sorted(SUPPORTED_CURRENCIES))
            raise serializers.ValidationError(
                f"Unsupported currency. Must be one of: {supported}."
            )
        return normalized

    def validate_recipient_ref(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("recipient_ref is required.")
        return value
