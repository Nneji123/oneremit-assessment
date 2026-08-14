# AGENTS.md

## Project Overview

Oneremit assessment - payout dashboard with Django REST backend and Next.js frontend.

## Commands

### Backend

```bash
cd backend
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
```

## Code Style

- Backend: ruff for linting and formatting
- Frontend: ESLint with next config, TypeScript strict mode

## Testing

- Backend: pytest with pytest-django
- Frontend: Vitest with @testing-library/react
