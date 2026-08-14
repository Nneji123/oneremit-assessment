# AGENTS.md

## Project Overview

Oneremit assessment - payout dashboard with Django REST backend and Next.js frontend.

## Commands

### Backend

```bash
cd backend
# Local-only values; production must provide real secrets.
export ENVIRONMENT=local DEBUG=1 SECRET_KEY=local-development-only PROVIDER_WEBHOOK_SECRET=local-development-only
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

### Frontend

```bash
cd frontend
npm install
npm run dev
npm run build
npm run lint
npm run typecheck
npm test
```

### Docker Compose

```bash
docker compose up --build
docker compose down
docker compose run --rm backend pytest
docker compose config --quiet
```

## Configuration

- `ENVIRONMENT`: `local`, `development`, or `production`. Defaults to `local`.
- When `DEBUG=0`, or when `ENVIRONMENT=production`, `SECRET_KEY` and `PROVIDER_WEBHOOK_SECRET` must be real (non-placeholder) values or Django will refuse to start.
- Database: pass `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` individually. `settings.py` constructs the connection URL from these when `DATABASE_URL` is not set. SQLite is the fallback for direct local development; production requires a database URL or complete PostgreSQL settings with a real password.
- Compose supplies development-only defaults and passes the frontend API URL at image build time and runtime. Do not reuse those defaults outside local development.

## Code Style

- Backend: ruff for linting and formatting
- Frontend: ESLint with next config, TypeScript strict mode

## Testing

- Backend: pytest with pytest-django
- Frontend: Vitest with @testing-library/react
