# Oneremit PayOut Assessment

A mock payout product for the Oneremit take-home: a customer creates a
transfer, an ops action submits it to a fake provider, and a signed provider
webhook (or local simulate action) resolves it to `completed`/`failed`. Built
with explicit transfer states, idempotent create requests, signed/idempotent
webhooks, and realtime status updates over WebSocket.

## 1. How to run

### Docker (everything at once)

```bash
docker compose up --build
```

- Frontend: `http://localhost:3000`
- API: `http://localhost:8000/api/`
- Health: `http://localhost:8000/health/`
- Swagger UI: `http://localhost:8000/api/docs/`
- WebSocket: `ws://localhost:8000/ws/transfers/<id>/`

Stop everything with `docker compose down`.

### Backend only (no Docker)

```bash
cd backend
export ENVIRONMENT=local DEBUG=1 SECRET_KEY=local-development-only PROVIDER_WEBHOOK_SECRET=local-development-only
uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```

Runs against a local SQLite file — no Postgres/Docker required for backend
development or tests.

### Frontend only (no Docker)

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api NEXT_PUBLIC_WS_BASE_URL=ws://localhost:8000 npm run dev
```

### Running the tests

```bash
# Backend — 101 tests, pytest, no Docker/Postgres needed
cd backend
uv run pytest

# Frontend — 18 tests, Vitest + Testing Library
cd frontend
npm test -- --run
```

Or via Docker: `docker compose --profile test run --rm backend-test`.

## 2. Assumptions

- **No authentication.** The brief explicitly allows an open local API; adding
  real auth (JWT/OAuth), authorization, and tenant isolation is left for a
  production follow-up rather than built and then bypassed.
- **SQLite for backend tests, Postgres for the Docker runtime.** Tests run
  against SQLite so they're fast and need no external service; the Docker
  Compose stack (and would-be production deploys) use Postgres. Both share the
  same Django models/migrations.
- **One customer, no multi-tenancy.** There's no user/account model — every
  transfer is globally visible, matching the "mock payout product" scope.
  `recipient_ref` is a free-text string, not a validated bank account/account
  number, since real payout rails are explicitly out of scope.
- **The "fake provider" is entirely simulated.** `submit` always succeeds and
  assigns a fake `provider_transfer_id` (`prov_<hex>`) — there's no real
  network call to model provider-side submission failures.
- **Currency is a closed enum** (`NGN`, `USD`, `GBP`, `EUR`) validated
  server-side, not a live FX/currency-lookup service.
- **A single ASGI worker in Docker.** The realtime channel layer is in-memory
  (no Redis, per the out-of-scope list), so the backend container intentionally
  runs one `uvicorn` worker — multiple workers would each hold a disconnected
  copy of the channel layer and WebSocket pushes would go missing.

## 3. What I built (architecture, short)

A three-service Compose stack — PostgreSQL, Django REST Framework, Next.js —
plus a `curl`-driven fake provider (see [Signed webhook](#signed-webhook)
below). All transfer logic lives in one Django app (`transfers`), layered so
each module only depends on the ones below it:

```text
enums.py → models.py → services.py → serializers.py → views.py → urls.py
```

- **`services.py`** is where the state machine, idempotency, and webhook
  processing actually live — `transition_transfer` takes a row lock
  (`SELECT ... FOR UPDATE`), re-reads the persisted status, applies exactly one
  allowed transition, and raises `InvalidTransferTransition` otherwise. Views
  are thin HTTP adapters that call into this; they don't re-implement the
  rules.
- **`core/`** holds shared, non-domain plumbing: `BaseModel` (UUID pk +
  timestamps), `ResponseMixin` (the `{success, message, response_code, data}`
  envelope every endpoint returns), and a pagination class that keeps that
  envelope shape on list endpoints.
- **Realtime**: Django Channels over ASGI. After a transaction that changes a
  transfer's status commits, the service layer broadcasts to a per-transfer
  group (`transfer_<id>`); a WebSocket consumer relays that to the frontend, so
  the detail page updates live instead of polling.
- **Frontend**: a dashboard (create form + transfer list) and a per-transfer
  detail page styled as a receipt, showing status, timestamps, provider id, a
  Created → Processing → Outcome progress timeline, Submit/Cancel actions that
  hide themselves when illegal for the current status, and local
  "Simulate completed" / "Simulate failed" buttons while a transfer is
  `processing`.

Full detail: [`docs/architecture.md`](docs/architecture.md) (data model, state
transition table, webhook handling rules, request flows, container diagram).
API reference: [`docs/api.md`](docs/api.md). Test matrix:
[`docs/testing.md`](docs/testing.md).

### API summary

Every response uses `{success, message, response_code, data[, pagination]}`.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/transfers/` | Create pending transfer; requires `Idempotency-Key` |
| `GET` | `/api/transfers/` | List transfers, paginated, newest first |
| `GET` | `/api/transfers/{id}/` | Retrieve transfer |
| `POST` | `/api/transfers/{id}/submit/` | `pending` → `processing`, assigns `provider_transfer_id` |
| `POST` | `/api/transfers/{id}/cancel/` | `pending` → `cancelled` only |
| `POST` | `/api/transfers/{id}/simulate-webhook/` | Local unsigned demo helper (drives `processing` → terminal from the UI) |
| `POST` | `/api/webhooks/provider/` | Signed provider webhook (the real path) |

## 4. Decision log

### Why did you choose your rule for scenario B (completed then failed)?

Once a transfer reaches `completed`, I treat that as the true, final outcome —
a later `failed` event for the same transfer is acknowledged with `200` and
recorded (as `ProviderEvent.outcome = "ignored_terminal"`) but never regresses
the transfer's status. I chose this over "last write wins" because in a real
payout, `completed` usually corresponds to money having actually moved; if a
provider later sends a conflicting `failed` for the same transfer, that's a
signal of a flaky/misbehaving provider or an out-of-order delivery, not
grounds to silently flip a customer's transfer back to failed after they've
already been told it succeeded. The event is still stored (so it's visible for
investigation), and the response is a `200` — same as a duplicate — because
from the provider's point of view "the event was received and handled" is
true; a `409` here would look like a delivery failure and encourage the
provider to keep retrying an event that was already, correctly, ignored.

### For unknown `provider_transfer_id`, why 4xx vs soft-success?

I return `404` rather than a soft `200`. An unknown `provider_transfer_id` on a
*signed* webhook means the provider is telling us about a transfer we never
issued a provider id for — that's a configuration/environment mismatch (wrong
webhook URL pointed at the wrong environment, a provider-side data problem, or
a stale/replayed event from a different environment), not a normal race we
should quietly absorb. Soft-succeeding would hide that mismatch from whoever
operates this integration and make debugging a real incident much harder,
since silently-dropped events leave no signal that anything was wrong. A `404`
gives the provider (or whoever is watching webhook delivery logs/retries) a
clear, honest signal, and it costs nothing here since the event was never
going to be applied to any transfer either way.

### Where would you put webhook signature verification in a real Django codebase, and what do people get wrong?

I'd verify the signature as the very first thing inside the view, before
anything else touches the request — before JSON parsing, before any database
lookup, and before any business logic runs, which is exactly where
`ProviderWebhookView.post` does it in `views.py`. The common mistakes I've
seen (and deliberately avoided here): computing the HMAC over the
*re-serialized* `request.data` dict instead of the exact raw bytes DRF/Django
received (any change in key order, whitespace, or number formatting during
re-serialization silently breaks a signature that was actually valid);
comparing digests with `==` instead of `hmac.compare_digest`, which leaks
timing information an attacker can use to brute-force the signature
byte-by-byte; accepting a signature header with the wrong or missing
`sha256=` prefix instead of rejecting it outright; and doing expensive or
side-effecting work (DB writes, calling out to other services) *before*
verifying the signature, which turns the webhook endpoint into an unauthenticated
attack surface. In a larger codebase I'd wrap this as a small reusable
decorator/mixin (read `request.body` once, verify, then hand the verified
bytes to the view) so every webhook endpoint gets the same treatment instead
of each one reimplementing HMAC comparison slightly differently.

## 5. Intentional bug note

An early draft of `process_provider_event` deduplicated incoming webhooks by
`provider_transfer_id` instead of `event_id`, on the reasoning that "we only
care about one transfer's terminal state." That's wrong: it would have made
scenario D (two different `event_id`s, both `completed`, same
`provider_transfer_id`) indistinguishable from scenario A (the same
`event_id` delivered twice) — the second `completed` event for a transfer
would have been silently treated as *the same event replayed*, rather than
as a second, distinct event that happens to agree with the first. That
matters because a provider is allowed to send multiple genuinely different
events about the same transfer (e.g. a retry with a fresh `event_id` after a
timeout, not just an exact-byte replay), and collapsing "different event,
same outcome" into "duplicate of one event" would hide that from the
`ProviderEvent` audit trail — you'd only ever see one row instead of two,
and lose the signal that the provider sent redundant-but-distinct
notifications.

I caught this while writing
`test_scenario_d_different_completed_events_same_provider_id_are_noop`
(`backend/apps/transfers/tests/test_provider_webhooks.py`): asserting
`ProviderEvent.objects.get(event_id="evt_d1").outcome == "applied"` and a
second row for `evt_d2` only passes if dedup happens on `event_id` first,
*before* any transfer-level "is this still processing" check — with the
provider-id-keyed draft, the second event never reached the point where a
second `ProviderEvent` row would be created, since it looked identical to
the first at the dedup step. The fix — now in `services.py::process_provider_event`
— is a strict two-stage check: (1) look up and dedupe by `event_id` under
`select_for_update()`, and only if that's a genuinely new event id, (2) look
up the transfer by `provider_transfer_id` and decide `applied` vs.
`ignored_terminal` based on its current status. Scenario A is entirely
handled by stage 1; scenarios B and D are both handled by stage 2, and stage
1 running first is what keeps them from being conflated.

## 6. What I deliberately left out

Per the assessment's out-of-scope list: real KYC, wallets, FX rates, ledgers,
Celery/Redis background workers, production auth (JWT/OAuth), admin
dashboards, pixel-perfect design, and cloud deployment. Concretely, that
means: no user accounts or permissions (the API is open, as the brief allows
and asks to be documented — see [Assumptions](#2-assumptions)); no real
provider integration (submit always "succeeds" against a fake provider id);
no background task queue (transitions and webhook processing run
synchronously inside the request); and no horizontal scaling for the realtime
layer (see [Known limitations](#8-known-limitations--risks)).

## 7. What I would do differently with more time

- **Redis-backed channel layer** so the backend could run more than one ASGI
  worker/replica without losing WebSocket broadcasts, plus a reconnect-and-refetch
  fallback on the frontend for any status change missed while a socket was
  down (today a page refresh covers that gap, but it's manual).
- **Structured audit log for webhook events** beyond the current
  `ProviderEvent` rows — e.g. a queryable timeline of every signature failure,
  duplicate, and conflict per transfer, which is exactly the kind of thing an
  ops team would want when investigating a provider incident.
- **Rate limiting / basic auth on the webhook endpoint** in addition to HMAC
  verification, so a compromised or misconfigured client can't hammer the
  endpoint even with signature checks in place.
- **Currency-aware amount formatting and input masking on the frontend**
  (currently a plain decimal string with client-side digit filtering) and
  exchange-rate display, if FX were ever brought into scope.
- **A management command that fires a burst of realistic, occasionally
  out-of-order webhook deliveries** for local load/chaos testing, instead of
  the current one-shot signed-curl example.

## 8. Known limitations / risks

- **Single ASGI worker in Docker.** The in-memory Channels layer means the
  `backend` service must run with exactly one `uvicorn` worker (see
  `compose.yml`); a second worker/replica would maintain its own disconnected
  channel layer and silently miss broadcasts meant for a socket connected to
  the other worker. Production would need a shared channel layer (Redis) to
  scale horizontally.
- **No rate limiting.** Neither the transfer API nor the webhook endpoint is
  rate-limited; a real deployment would want this in front of both, especially
  the open (no-auth) transfer-creation endpoint.
- **Idempotency and dedupe keys are unbounded, in-database uniqueness
  constraints** (`idempotency_key`, `event_id`) with no expiry/cleanup job —
  fine at this scale, but a long-lived production table would eventually want
  a retention policy.
- **The simulate-webhook endpoint is unauthenticated and unsigned by design**
  (it exists purely so the UI/README demo doesn't require a signed `curl`
  round-trip) — it must never exist in a real deployment, since it lets anyone
  who can reach the API resolve any `processing` transfer without going
  through the real provider or its signature check.
- **No monitoring/alerting** on webhook signature failures or repeated
  `ignored_terminal` outcomes, both of which would be useful early warning
  signs of a misbehaving provider integration in production.

## Signed webhook

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

`provider_transfer_id` must match a transfer that has already been submitted
(`POST /api/transfers/{id}/submit/`), and `PROVIDER_WEBHOOK_SECRET` must match
the backend's env var.

## Project structure

```text
backend/config/settings/        base, development, production
backend/apps/core/              BaseModel, response envelope, pagination
backend/apps/transfers/         enums, exceptions, models, services, views
frontend/app/                   dashboard and receipt/detail routes
frontend/components/            UI, simulation, WebSocket, tests
frontend/lib/                   REST, WebSocket, and notification helpers
docs/                           API, architecture, testing, DoD
```

## Docs

- [`docs/api.md`](docs/api.md) — REST, simulation, signed webhook, and
  WebSocket contracts.
- [`docs/architecture.md`](docs/architecture.md) — backend layers, state
  machine, and realtime flow.
- [`docs/testing.md`](docs/testing.md) — exact test commands, test matrix, and
  named scenarios A–E.
