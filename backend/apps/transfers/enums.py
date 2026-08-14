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
