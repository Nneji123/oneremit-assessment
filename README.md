# Oneremit Payout Dashboard — Assessment Submission

## What this is

A payout dashboard monorepo for the Oneremit engineering assessment. A Next.js
frontend talks to a Django REST API over a single `transfers` domain. Each
transfer is created `pending`, `submit`ted into `processing` (where a provider
id is assigned), and can only reach `completed` or `failed` via a **signed,
idempotent provider webhook**; it can also be `cancelled` while `pending`. Every
status change is enforced by one locked state machine service, never scattered
across views.

No real provider is called, no authentication is configured, and there is no
queue or cache layer. The provider is simulated by sending signed webhooks with
`curl`.

**Stack**

| Layer | Technology |
| --- | --- |
| Database | PostgreSQL 16 (SQLite fallback for direct local dev) |
| Backend | Django 5.2, Django REST Framework, drf-spectacular (OpenAPI), gunicorn |
| Frontend | Next.js 16 (App Router), React 19, TypeScript strict, Tailwind |
| Tests | pytest + pytest-django (backend), Vitest + Testing Library (frontend) |
| Orchestration | Docker Compose; GitHub Actions CI |

Current test status: **93 backend tests, 6 frontend tests** — all passing.

**Repository layout**

```
backend/                 Django + DRF API
  config/                settings, URL routing
  transfers/             models, state machine, views, serializers, tests
frontend/                Next.js dashboard
  app/                   routes (dashboard list, transfer detail)
  components/            UI + component tests
  lib/                   API client, types, formatting
docs/                    api.md, architecture.md, testing.md, assessment-checklist.md
.github/workflows/ci.yml CI quality gates
compose.yml              PostgreSQL + backend + frontend
Makefile                 dev shortcuts
```

## How to run with Docker Compose

Prerequisite: Docker with the Compose plugin.

```bash
docker compose up --build
```

This starts:

- `db` — PostgreSQL 16 (`postgres:16-alpine`), healthy-gated for the backend.
- `backend` — runs `migrate` then serves gunicorn on `http://localhost:8000`.
- `frontend` — Next.js standalone build served on `http://localhost:3000`.

Compose supplies development-only defaults for `SECRET_KEY`,
`PROVIDER_WEBHOOK_SECRET`, and `POSTGRES_PASSWORD` (`local-development-only`)
and points the frontend at `http://localhost:8000/api`. Override any of them
with environment variables, e.g.:

```bash
PROVIDER_WEBHOOK_SECRET=<your-secret> docker compose up --build
```

Useful commands:

```bash
docker compose down                 # stop the stack
docker compose logs -f              # follow logs
docker compose config --quiet       # validate the compose file
docker compose --profile test run --rm backend-test
docker compose exec backend sh      # shell in backend container
```

Useful Makefile shortcuts: `make up`, `make down`, `make logs`,
`make backend-shell`, `make frontend-shell` wrap the Compose commands above.
`make dev` instead runs the backend and frontend directly outside Docker and
does **not** load any environment variables, so set the backend env vars from
"Backend (direct local dev, SQLite fallback)" first.

## How to run backend and frontend independently

### Backend (direct local dev, SQLite fallback)

```bash
cd backend
# Local-only values; production must provide real secrets.
export ENVIRONMENT=local DEBUG=1 SECRET_KEY=local-development-only PROVIDER_WEBHOOK_SECRET=local-development-only
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

The API is then at `http://localhost:8000/api/...` and the health check at
`http://localhost:8000/health/`.

To run against PostgreSQL locally instead of SQLite, also export the
`POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`,
`POSTGRES_PORT` variables documented in `backend/config/settings.py` (or set
`DATABASE_URL`).

### Frontend (direct local dev)

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api npm run dev
```

The dashboard is then at `http://localhost:3000`.

## How to run all tests, lint, typecheck, schema validation, and builds

### Backend (run from `backend/`)

```bash
export ENVIRONMENT=local DEBUG=1 SECRET_KEY=local-development-only PROVIDER_WEBHOOK_SECRET=local-development-only

uv run pytest                       # 93 tests
uv run ruff check .                 # lint
uv run ruff format --check .        # formatting check
uv run python manage.py spectacular --validate   # OpenAPI schema validation
```

`uv sync` (dev group) is required once before the above. The exact environment
variables above are what the local backend commands and tests expect; the CI
workflow runs the same suite via `uv sync --locked --dev`.

### Frontend (run from `frontend/`)

```bash
npm install
npm run lint                        # ESLint
npm run typecheck                   # tsc --noEmit
npm test -- --run                   # Vitest, 6 tests
npm run build                       # production build
```

### Schema / configuration validation

```bash
docker compose config --quiet       # compose file validation (CI does the same)
```

### Everything at once (CI equivalent)

`.github/workflows/ci.yml` runs the full set: backend
`uv sync --locked --dev` → `ruff check` → `ruff format --check` → `pytest`;
frontend `npm ci` → `lint` → `typecheck` → `npm test -- --run` → `npm run
build`; and docker `docker compose config --quiet` → `docker compose build
backend` → `docker compose build frontend`.

## API endpoint summary

Base URL: `http://localhost:8000/api`. All endpoints accept and return JSON;
every response is wrapped in the envelope `{success, message, response_code,
data[, pagination]}` and errors use `success: false` with a `message`.

| Method | Path | Purpose | Success |
| --- | --- | --- | --- |
| `GET` | `/health/` | Liveness probe | `200` |
| `POST` | `/transfers/` | Create a transfer (requires `Idempotency-Key`) | `201` / `200` replay |
| `GET` | `/transfers/` | List transfers, newest first | `200` |
| `GET` | `/transfers/{id}/` | Retrieve one transfer | `200` / `404` |
| `POST` | `/transfers/{id}/submit/` | `pending` → `processing`, assign provider id | `200` / `404` / `409` |
| `POST` | `/transfers/{id}/cancel/` | `pending` → `cancelled` | `200` / `404` / `409` |
| `POST` | `/webhooks/provider/` | Provider outcome webhook (signed) | `200` / `400` / `401` / `404` / `409` |
| `GET` | `/schema/` | OpenAPI schema (drf-spectacular) | `200` |
| `GET` | `/docs/` | Swagger UI | `200` |

`PATCH`, `PUT`, and `DELETE` on `/transfers/` are rejected with `405`.

Full field-level documentation: [docs/api.md](docs/api.md).

## Signed webhook curl example

The provider webhook signs the **exact raw request body** with HMAC-SHA256
using `PROVIDER_WEBHOOK_SECRET`. The header format is `X-Provider-Signature:
sha256=<hex>`. The backend reads `request.body` raw bytes and verifies the
signature *before* parsing JSON or touching the database. Re-serializing the
body (for example via `jq`) breaks the signature.

The example below uses the local-only placeholder secret from the documented
test environment. Never commit a real secret.

```bash
export PROVIDER_WEBHOOK_SECRET=local-development-only

# 1. Create a transfer (any Idempotency-Key works for a one-off).
curl -s -X POST http://localhost:8000/api/transfers/ \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: curl-demo-$(date +%s)" \
  -d '{"amount":"100.00","currency":"NGN","recipient_ref":"recipient-123"}'

# 2. Submit it; copy provider_transfer_id from the response.
#    POST /api/transfers/<id>/submit/

# 3. Sign the exact body with no trailing newline, then POST it.
BODY='{"event_id":"evt_curl_001","provider_transfer_id":"<copy-from-step-2>","status":"completed","occurred_at":"2026-08-14T09:00:00Z"}'

SIG=$(python3 - "$BODY" <<'PY'
import hmac, hashlib, os, sys
secret = os.environ["PROVIDER_WEBHOOK_SECRET"].encode("utf-8")
digest = hmac.new(secret, sys.argv[1].encode("utf-8"), hashlib.sha256).hexdigest()
print("sha256=" + digest)
PY
)

curl -i -X POST http://localhost:8000/api/webhooks/provider/ \
  -H "Content-Type: application/json" \
  -H "X-Provider-Signature: $SIG" \
  --data-binary "$BODY"
```

`printf`/`python3` (no added newline) + `curl --data-binary` guarantee the
signed bytes are exactly the bytes the server verifies. The signing secret is
configured server-side only — it never appears in browser code.

## Assumptions

- **Open local API / no authentication.** The API is intentionally unauthenticated
  (`authentication_classes = []`) for this assessment. Production would front the
  API with session/JWT auth and per-customer authorization.
- **No real provider.** Submission only assigns a synthetic `prov_<hex>` id; the
  provider is simulated by signed webhooks. Real provider APIs, retries, and
  settlement reconciliation are out of scope.
- **No queue or cache.** There is no Redis/Celery. The frontend detail page
  polls every 2 s while a transfer is `processing`, which is how terminal
  states appear in the UI.
- **Single writer assumption.** Concurrent writes to one transfer are serialized
  by `SELECT ... FOR UPDATE` in the transition service; this is correct under
  this workload and the tests cover the stale-read race.
- **Client-supplied `Idempotency-Key`.** Create idempotency relies on the caller
  sending a stable key per logical request, like the frontend does with
  `crypto.randomUUID()`.

## Architecture sketch

```
┌─────────────┐   REST (JSON)   ┌──────────────────────────────────────┐
│   Next.js   │ ──────────────▶ │  Django + DRF  (gunicorn, :8000)    │
│ dashboard   │ ◀────────────── │  transfers app                       │
│  (:3000)    │  poll 2s while  │    viewset → transition_transfer()   │
└─────────────┘  processing     │    webhook  → verify HMAC → record   │
                                └──────────────┬───────────┬───────────┘
                                               │           │
                        PostgreSQL 16 (:5432)   ▼           ▼
                        Transfer, ProviderEvent        Provider (simulated)
                                                      signed webhook via curl

Events:
  POST /api/transfers/          -> create (pending)
  POST /api/transfers/{id}/submit/ -> pending -> processing + provider id
  POST /api/transfers/{id}/cancel/ -> pending -> cancelled
  POST /api/webhooks/provider/  -> processing -> completed | failed
  Frontend polls detail page    -> picks up terminal states
```

See [docs/architecture.md](docs/architecture.md) for the container diagram,
data model, state transition table, and request flows.

## Decision log

**Why the terminal state wins when completed is followed by failed.** Two
different provider events for the same transfer arrive out of order: a
`completed` and then a `failed`. Reverting a transfer from `completed` to
`failed` would silently destroy money-movement record keeping. The state
machine makes `completed`, `failed`, and `cancelled` terminal, so the later
event is acknowledged (`200`) but recorded with outcome `ignored_terminal`
instead of changing state. This is the standard "first terminal write wins"
model for settlement systems: the webhook always gets a success so the provider
stops retrying, but the recorded source of truth never regresses.

**Why an unknown `provider_transfer_id` returns 404 instead of soft-success.**
A signed event for a transfer id we have never issued is either a provider bug,
a wrong-secret/attacker replay attempt, or a coding error on our side. Swallowing
it with a `200` would hide the mismatch and make operational debugging much
harder. Returning `404` fails loudly, records nothing, and matches the API's uniform
response envelope (errors carry `success: false` with a `message`). It is
distinct from the `409` returned
when the transfer *is* known but not yet `processing`.

**Where signature verification belongs in a real Django codebase, and common
mistakes.** Verification must run before the body is parsed, deserialized, or
used for any write, and must hash the raw bytes (`request.body`) — not a
re-serialized dict. In a real codebase this is best placed in dedicated
middleware or a base `APIView`/decorator applied to webhook routes only, kept
out of generic view code. Common mistakes: hashing re-marshalled JSON (which
can differ from the wire bytes), accepting non-`sha256=` scheme prefixes,
comparing digests with `==` instead of `hmac.compare_digest`, letting signature
failures fall through to generic `400` instead of `401`, and logging or storing
the raw signed payload or secret.

## Idempotency semantics

**Create requests (`POST /transfers/`).** The caller sends an `Idempotency-Key`
header (required, ≤ 255 chars). The backend stores a canonical fingerprint of
the normalized request body (amount to two decimals, uppercase currency,
recipient reference — independent of JSON key order/formatting) alongside the
key. On replay of the same key with an identical fingerprint it returns the
original transfer with `200`; with a different fingerprint it returns `409`
and writes nothing. The unique constraint on `idempotency_key` makes this race-safe
under `transaction.atomic()`.

**Provider event IDs.** `event_id` is unique per event. Replaying the same
`event_id` with an identical payload returns `200` and records nothing new.
Reusing an `event_id` with a different payload returns `409` (protecting against
two distinct events colliding on one id). Raw payloads and signatures are never
stored — only a SHA-256 fingerprint plus the derived outcome
(`applied`/`ignored_terminal`).

## What was deliberately left out

- Authentication, authorization, and any API keys — the local API is open.
- A real provider integration (or even a mock provider server).
- Redis, Celery, background jobs, and webhooks — no async worker layer exists.
- Email/SMS notifications and per-transfer audit display in the UI.
- Admin UI (`django.contrib.admin` is not installed).
- Database migrations for non-`transfers` apps; SQLite is only a dev fallback.
- Pagination on the transfers list is on by default (20 per page).
- Filtering on the transfers list (fine at assessment scale).

## What would be done differently with more time

- Run webhook signature verification in shared middleware for webhook routes and
  add unit tests at that layer.
- Add a replay/outbox table for failed or out-of-order provider events and a
  reconciliation job instead of only recording `ignored_terminal`.
- Replace frontend polling with server-sent events or WebSockets once a real
  provider/worker exists.
- Add real auth (sessions or JWT) and per-tenant isolation, plus filtering on
  the list endpoint.
- Break the single `views.py` into thin HTTP handlers plus a service layer, and
  extract the provider-facing surface into its own app.
- Add property-based tests for the state machine and load tests for the
  concurrency path against PostgreSQL.

## Known limitations and risks

- **`select_for_update` needs PostgreSQL.** The transition service relies on row
  locks. Under the SQLite dev fallback the concurrency guarantees are weaker,
  though the stale-read behavior is still covered by tests.
- **No retry/outbox.** If the backend is down when a provider event arrives, the
  event is lost (unless the provider retries); there is no durable outbox.
- **In-flight state on crash.** A transfer left `processing` with no terminal
  event would stay `processing` forever; there is no timeout/reconciliation
  sweep.
- **Webhook replay vs. transfer replay are independent** — correctly so, but
  worth restating: re-sending a webhook for an already-completed transfer is
  acknowledged as `ignored_terminal`, which is a deliberate, safe no-op.
- **No auth** means anyone who can reach the API can create, submit, or cancel
  transfers. Acceptable for the assessment; a hard blocker for real use.

## Intentional bug caught during implementation

The initial API implementation duplicated the `pending → processing` policy
inline inside the `submit` view (`views.py`) instead of delegating to the single
state-machine service. The test `test_submit_delegates_transition_to_service`
exposed the drift risk — it asserts `submit` calls `transition_transfer`
exactly once and surfaces `InvalidTransferTransition` as `409`. Commit
`ec23b6d` moved `submit` onto the single locked transition service so the policy
lives in exactly one place. **This was fixed before final submission** and is
covered by the backend suite.

## Incremental commit history

The work was built incrementally in the recorded order:

```
fc9b8c7 chore: scaffold clean assessment monorepo
60fcd3c fix: harden foundation containers and configuration
c4c95c5 feat: add transfer state machine
02ad31d fix: harden transfer transition concurrency
e991e56 feat: add transfer api and request idempotency
ec23b6d fix: harden transfer api edge cases
c0d2580 feat: add signed idempotent provider webhooks
efccd6a feat: add payout dashboard frontend
```

Each feature lands with its own tests and docs (`docs/api.md` grew alongside
the API); hardening commits tighten edge cases and concurrency rather than
rearchitecting. See `git log` for the full history.

## Total time spent

If not already recorded, the total time spent should be noted before
submission. It is intentionally not invented here.
