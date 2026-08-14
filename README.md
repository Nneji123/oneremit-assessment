# Oneremit PayOut Assessment

A focused payout dashboard demonstrating explicit transfer states, idempotent
requests, signed provider webhooks, local simulation, and realtime status
updates.

## Run

```bash
docker compose up --build
```

Open `http://localhost:3000`.

Useful endpoints:

- API: `http://localhost:8000/api/`
- Health: `http://localhost:8000/health/`
- Swagger: `http://localhost:8000/api/docs/`
- WebSocket: `ws://localhost:8000/ws/transfers/<id>/`

Run backend tests in the dev/test image:

```bash
docker compose --profile test run --rm backend-test
```

Stop everything with `docker compose down`.

## Structure

```text
backend/config/settings/        base, development, production
backend/apps/core/              BaseModel, response envelope, pagination
backend/apps/transfers/         enums, exceptions, models, services, views
frontend/app/                   dashboard and receipt/detail routes
frontend/components/            UI, simulation, WebSocket, tests
frontend/lib/                   REST, WebSocket, and notification helpers
frontend/public/                Oneremit logo/favicon/illustration assets
docs/                           API, architecture, testing, design audit, DoD
```

Views are thin HTTP adapters. Business logic lives in

The backend runs Django Channels over ASGI with one uvicorn worker. The local
in-memory channel layer is intentionally single-process. Production scaling
would use Redis or another shared channel layer.

## UI

The frontend uses the Oneremit visual system audited in `docs/design-audit.md`:

- Albert Sans.
- Forest canvas `#032620` / `#043028`.
- Mint accents `#beffc4` / `#92ff9d`.
- Off-white 20px cards, map/globe artwork, status pills, and responsive layouts.
- Native browser notifications when a transfer becomes completed.

The dashboard has equal desktop columns for creation and transfer activity,
stacking below `960px`. The transfer page renders as a receipt — Oneremit
brandbar, prominent total payout and recipient, dashed metadata grid, and a
three-step progress timeline — connects to a per-transfer WebSocket, shows
connection state, and exposes local `Simulate completed` / `Simulate failed`
controls while processing.

## API

Every JSON response uses:

```json
{
  "success": true,
  "message": "Transfer created",
  "response_code": 201,
  "data": {}
}
```

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/transfers/` | Create pending transfer; requires `Idempotency-Key` |
| `GET` | `/api/transfers/` | List transfers, paginated |
| `GET` | `/api/transfers/{id}/` | Retrieve transfer |
| `POST` | `/api/transfers/{id}/submit/` | Submit pending transfer |
| `POST` | `/api/transfers/{id}/cancel/` | Cancel pending transfer |
| `POST` | `/api/transfers/{id}/simulate-webhook/` | Local unsigned demo helper |
| `POST` | `/api/webhooks/provider/` | Signed provider webhook |

The simulation endpoint is local-only. The signed webhook remains the real
provider path.

## Assessment Decisions

**Completed then failed:** terminal state wins. A later contradictory event is
acknowledged with `200` and recorded as `ignored_terminal`, but cannot regress a
completed transfer.

**Unknown provider ID:** return `404` instead of soft-success. An unknown ID is
a provider/configuration mismatch; acknowledging it would hide an operational
error and prevent useful retries.

**Signature verification:** the view reads raw request bytes and delegates HMAC
verification to the transfer service before JSON parsing or database work.
Common mistakes are signing re-serialized JSON, using ordinary equality instead
of `compare_digest`, accepting malformed prefixes, logging secrets/payloads, or
performing side effects before verification.

**Open local API:** authentication is intentionally omitted for the assessment.
Production would add authentication, authorization, rate limits, and tenant
isolation.

## Signed Webhook

```bash
export PROVIDER_WEBHOOK_SECRET=local-development-only
BODY='{"event_id":"evt_001","provider_transfer_id":"prov_abc","status":"completed","occurred_at":"2026-08-14T09:00:00Z"}'
SIG=$(python3 - "$BODY" <<'PY'
import hashlib, hmac, os, sys
print("sha256=" + hmac.new(os.environ["PROVIDER_WEBHOOK_SECRET"].encode(), sys.argv[1].encode(), hashlib.sha256).hexdigest())
PY
)
curl -X POST http://localhost:8000/api/webhooks/provider/ \
  -H "Content-Type: application/json" \
  -H "X-Provider-Signature: $SIG" \
  --data-binary "$BODY"
```

## Verification

Backend:

```bash
cd backend
export ENVIRONMENT=local DEBUG=1 SECRET_KEY=test-secret PROVIDER_WEBHOOK_SECRET=test-secret
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python manage.py check
uv run python manage.py spectacular --validate
```

Frontend:

```bash
cd frontend
npm ci
npm test -- --run
npm run lint
npm run typecheck
npm run build
```

Current suite: 101 backend tests and 18 frontend tests.

## Scope

Excluded intentionally: real provider integrations, auth, wallets, FX, KYC,
ledgers, Celery, Redis, admin dashboards, cloud deployment, and horizontal
WebSocket scaling.

The runtime image is production-oriented: multi-stage build, runtime-only
dependencies, non-root user, healthcheck, and ASGI server. The separate test
target contains development dependencies.

## Intentional Bug

The first API version duplicated the `pending` to `processing` rule in the view.
`test_submit_delegates_transition_to_service` caught the drift risk, and commit
`ec23b6d` moved the action behind the locked state-machine service.

## Docs

- `docs/api.md`: REST, simulation, signed webhook, and WebSocket contracts.
- `docs/architecture.md`: backend layers, state machine, and realtime flow.
- `docs/design-audit.md`: audited Oneremit tokens and responsive rules.
- `docs/testing.md`: test matrix and scenarios A–E.
- `docs/assessment-checklist.md`: requirement mapping and DoD.
