# syntax=docker/dockerfile:1

# ---- base: shared toolchain (uv on a slim Python runtime) ----
FROM python:3.13-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# ---- builder: install ONLY runtime dependencies, frozen from uv.lock ----
FROM base AS builder

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ---- runtime: lean image with runtime deps, non-root, healthcheck ----
FROM base AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid 1000 --create-home appuser

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --chown=appuser:appuser ./config ./config
COPY --chown=appuser:appuser ./apps ./apps
COPY --chown=appuser:appuser ./manage.py ./manage.py

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# uvicorn with one worker so the in-memory channel layer stays in a single
# process (the local assessment's WebSocket transport).
CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# ---- test: full source + dev dependencies so the suite runs in-container ----
FROM base AS test

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

COPY . .

CMD ["uv", "run", "pytest", "-q"]
