.PHONY: help dev up down logs backend-shell frontend-shell

help:
	@echo "Available commands:"
	@echo "  make dev          - Start development servers (backend + frontend)"
	@echo "  make up           - Start Docker Compose stack"
	@echo "  make down         - Stop Docker Compose stack"
	@echo "  make logs         - View Docker Compose logs"
	@echo "  make backend-shell - Open shell in backend container"
	@echo "  make frontend-shell - Open shell in frontend container"

dev:
	@echo "Starting backend..."
	cd backend && uv run python manage.py runserver &
	@echo "Starting frontend..."
	cd frontend && npm run dev

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

backend-shell:
	docker compose exec backend sh

frontend-shell:
	docker compose exec frontend sh
