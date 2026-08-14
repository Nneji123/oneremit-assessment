# Architecture

Task 1 establishes a small Docker Compose monorepo with three services:

- `db`: PostgreSQL 16 for persistent application data.
- `backend`: Django and Django REST Framework, currently exposing only `/health/`.
- `frontend`: Next.js App Router shell for the future payout dashboard, built
  with standalone output.

Both application containers run as non-root users. Compose passes PostgreSQL
connection parts individually; the backend only uses `DATABASE_URL` when it is
explicitly supplied and otherwise builds the connection from those parts.
When `DEBUG=0` or `ENVIRONMENT=production`, missing or placeholder application,
webhook, or PostgreSQL password configuration stops startup instead of selecting
predictable defaults.

The transfer domain, API resources, and provider integration will be added in a
later task. No authentication, workers, or real providers are planned.
