# Testing Foundation

Tests are intentionally not implemented in Task 1. The backend is configured
for `pytest` and `pytest-django`; the frontend is configured for Vitest and
React Testing Library.

The CI workflow leaves explicit TODO-aware guards around future test commands
without manufacturing passing tests. Future work must add state-machine,
idempotency, webhook-signature, and meaningful UI tests.
