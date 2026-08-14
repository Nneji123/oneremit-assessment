"""Domain exceptions for the transfers app.

Keeping exceptions in their own module separates the service layer's
failure semantics from its implementation and lets views, tests, and future
consumers depend on a stable, shared error contract.
"""


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
