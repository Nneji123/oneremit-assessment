# Architecture

Task 1 establishes a small Docker Compose monorepo with three services:

- `db`: PostgreSQL 16 for persistent application data.
- `backend`: Django and Django REST Framework, currently exposing only `/health/`.
- `frontend`: Next.js App Router shell for the future payout dashboard.

The transfer domain, API resources, and provider integration will be added in a
later task. No authentication, workers, or real providers are planned.
