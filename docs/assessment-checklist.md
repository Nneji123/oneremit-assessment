# Assessment Checklist

Maps each assessment requirement to the implementation, its tests, and the
supporting documentation. Everything below is implemented in `main`.

## Requirement → implementation map

### Foundation

| Requirement | Implementation | Tests | Docs |
| --- | --- | --- | --- |
| Fresh Git repository, clean history | git log (conventional, granular history) | — | git log |
| Docker Compose: PostgreSQL + Django + Next.js | `compose.yml` (db/backend/backend-test/frontend, health-gated `db`) | `docker compose config --quiet` | README "Run"; docs/architecture.md |
| Environment-based settings, real-secret guard | `backend/config/settings/` (`base.py` + `development.py`/`production.py` routed by `ENVIRONMENT`; `REQUIRE_SECRETS`, placeholder rejection) | — | README "Assessment Decisions", AGENTS.md |
| Health endpoint | `GET /health/` (`config/urls.py`) | — | README API summary |
| Dependency manifests + lockfiles | `backend/pyproject.toml` + `uv.lock`; `frontend/package.json` + `package-lock.json` | — | README intro |
| CI quality gates | `.github/workflows/ci.yml` (backend, frontend, docker jobs) | CI runs lint/format/pytest, lint/typecheck/test/build, compose config + image builds | README "Verification"; docs/testing.md |
| Shared core app (BaseModel, ResponseMixin, pagination) | `backend/apps/core/{models,mixins,pagination}.py` (`BaseModel`, `ResponseMixin`, `StandardResultsSetPagination`) | envelope shape asserted across API tests | docs/architecture.md "Code organization" |
| Uniform response envelope | `core.mixins.ResponseMixin` + `core.pagination.StandardResultsSetPagination` (`{success, message, response_code, data[, pagination]}`) | API tests assert `success`/`message`/`data` shape | docs/api.md "Response envelope" |
| Multi-stage Docker image + test target | `backend/Dockerfile` (`base` → `builder` → `runtime` → `test`); compose `backend-test` profile service | `docker compose --profile test run --rm backend-test` | README "Run"; docs/testing.md "Docker" |
| No auth, no Celery, no Redis, no real provider | empty `authentication_classes`/`permission_classes` on the local API views; no worker deps | — | README "Scope" |
| Realtime transport | Django Channels, ASGI `ProtocolTypeRouter`, per-transfer consumer and in-memory channel layer | WebSocket state updates exercised by the local runtime flow | docs/architecture.md; docs/api.md |

### Transfer domain

| Requirement | Implementation | Tests | Docs |
| --- | --- | --- | --- |
| `Transfer` model + constraints | `backend/apps/transfers/models.py`, migrations `0001`/`0002` | `test_state_machine.py` (uniqueness, validation, DB status check) | docs/architecture.md "Data model" |
| State machine with terminal states | `backend/apps/transfers/services.py` (`transition_transfer`, `select_for_update`, `InvalidTransferTransition`) | `test_state_machine.py` (53 tests incl. all transition pairs, stale-read race) | docs/architecture.md "State transition table" |
| Concurrency hardening | `select_for_update` + persisted-status read + `transaction.atomic()` | `test_stale_concurrent_transition_cannot_apply_invalid_transition`, `test_transition_reads_persisted_status_not_stale_memory` | docs/architecture.md |
| Domain layering (enums / exceptions / services) | `backend/apps/transfers/enums.py`, `exceptions.py`, `services.py` | — | docs/architecture.md "Code organization" |

### Transfer API

| Requirement | Implementation | Tests | Docs |
| --- | --- | --- | --- |
| Create transfer | `TransferViewSet.create` (`backend/apps/transfers/views.py`) | `test_transfers_api.py` create tests | docs/api.md, README API summary |
| Request idempotency (key + fingerprint) | `services.py` `request_fingerprint` + `create_transfer`, unique `idempotency_key`, `request_fingerprint` | replay `200`/conflict `409`/key-length/JSON-order tests | README "API"; docs/api.md |
| List / retrieve | `ListModelMixin` / `RetrieveModelMixin` | list newest-first, detail, 404 tests | docs/api.md |
| Submit (`pending → processing`, provider id) | `submit` action delegating to `transition_transfer`; `provider_transfer_id = prov_<hex>` | `test_submit_*`, `test_submit_delegates_transition_to_service` | docs/api.md |
| Cancel (`pending → cancelled`) | `cancel` action → service | `test_cancel_*` incl. terminal rejections | docs/api.md |
| Uniform `405` on PATCH/PUT/DELETE | `http_method_names = ["get", "post", "head", "options"]` | `test_update_and_delete_are_not_allowed` | docs/api.md |

### Provider webhooks

| Requirement | Implementation | Tests | Docs |
| --- | --- | --- | --- |
| Signed webhook, HMAC over raw body | `services.py` `verify_provider_signature` + `ProviderWebhookView.post` (verify before parsing) | `test_provider_webhooks.py` signature tests; `test_signature_is_computed_from_raw_request_body` | README "Signed Webhook"; docs/api.md |
| Event idempotency (event ids + payload fingerprint) | `ProviderEvent.event_id` unique; `payload_fingerprint`; duplicate/conflict handling | duplicate `200`, conflicting reuse `409` tests | README "API"; docs/api.md |
| Outcome recording | `ProviderEvent.outcome` (`applied` / `ignored_terminal`) | scenarios A/B/D assert outcomes | docs/architecture.md "Webhook handling rules" |
| Scenarios A–E | — | named scenario tests (see docs/testing.md) | docs/testing.md "Named webhook scenarios A–E" |

### Frontend

| Requirement | Implementation | Tests | Docs |
| --- | --- | --- | --- |
| Dashboard list + create form | `app/page.tsx`, `components/transfer-form.tsx`, `transfer-list.tsx` | `transfer-form.test.tsx` | README "UI" |
| Detail page rendered as a receipt | `app/transfers/[id]/page.tsx`, `components/transfer-detail.tsx` (brandbar, total payout, dashed metadata grid, progress timeline) | `transfer-detail.test.tsx` | docs/architecture.md "Frontend realtime updates" |
| Detail page with actions | `components/transfer-actions.tsx`, `transfer-simulate.tsx` | action and simulation component tests | docs/architecture.md "Frontend realtime updates" |
| Loading / error / not-found states | list + detail page states, `ApiError` | — | README "UI" |
| Status badge for all statuses | `components/status-badge.tsx` | `status-badge.test.tsx` | — |
| Realtime status updates | detail page WebSocket subscription to `/ws/transfers/{id}/` | `connection-status.test.tsx`, runtime smoke flow | docs/architecture.md "Frontend realtime updates" |
| Native completion notification | `frontend/lib/notifications.ts` uses browser `Notification` API after completed transition | completion transition handled in WebSocket client | README "UI" |
| No webhook secret in browser | secret is server-side only; frontend simulation uses a separate local endpoint | — | README "Signed Webhook" |

### Documentation

| Requirement | Implementation |
| --- | --- |
| API reference | `docs/api.md` |
| Architecture, data model, state table, flows, containers | `docs/architecture.md` |
| Test commands + matrix + scenarios A–E | `docs/testing.md` |
| This mapping + DoD | `docs/assessment-checklist.md` |
| Submission runbook | `README.md` |

## Definition of Done

- [x] All 101 backend tests pass (`uv run pytest`, SQLite fallback, documented env vars).
- [x] All 18 frontend tests pass (`npm test -- --run`).
- [x] Backend lint and formatting pass (`ruff check .`, `ruff format --check .`).
- [x] OpenAPI schema validates (`python manage.py spectacular --validate`).
- [x] Compose file validates (`docker compose config --quiet`).
- [x] Frontend builds (`npm run build`); lint and typecheck pass.
- [x] CI workflow exercises the same gates on push/PR.
- [x] No real provider, no auth, no Redis/Celery; provider simulated via signed webhooks.
- [x] No secrets or sensitive data committed (only `.env.example`).
- [x] Signed webhook example computes HMAC over the exact raw body without exposing a secret.
- [x] Intentional submit-drift bug documented and fixed before submission (commit `ec23b6d`).
- [x] No scratch files, caches, node_modules, `.next`, or `db.sqlite3` tracked.
