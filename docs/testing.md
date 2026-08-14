# Testing

## Exact commands

### Backend (run from `backend/`)

```bash
# Local-only values; production must provide real secrets.
export ENVIRONMENT=local DEBUG=1 SECRET_KEY=local-development-only PROVIDER_WEBHOOK_SECRET=local-development-only

uv sync                                  # install incl. dev group
uv run pytest                            # 93 tests
uv run ruff check .                      # lint
uv run ruff format --check .             # formatting
uv run python manage.py spectacular --validate   # OpenAPI schema validation
```

Note: the backend test suite does **not** require Docker or PostgreSQL — it runs
against the SQLite fallback configured by `settings.py` in the `local` env.
`testpaths = tests transfers/tests` (from `pytest.ini`).

### Frontend (run from `frontend/`)

```bash
npm install
npm run lint                             # ESLint
npm run typecheck                        # tsc --noEmit
npm test -- --run                        # Vitest, 6 tests (CI mode: single run)
npm run build                            # production build (typecheck + lint are separate)
```

### Docker

```bash
docker compose run --rm backend pytest   # backend tests inside the Compose backend image
docker compose config --quiet            # validate compose file
```

### CI (GitHub Actions)

`.github/workflows/ci.yml` runs the full equivalent set on every push/PR:
backend `uv sync --locked --dev` → `ruff check` → `ruff format --check` →
`pytest`; frontend `npm ci` → `lint` → `typecheck` → `npm test -- --run` →
`npm run build`; plus `docker compose config --quiet` and image builds.

## Backend test matrix

**93 tests total**, split across three modules.

| Module | Tests | Covers |
| --- | --- | --- |
| `transfers/tests/test_state_machine.py` | 53 | every allowed/forbidden transition, row-lock/stale-read concurrency, amount/currency validation, uniqueness constraints, DB-level status rejection |
| `transfers/tests/test_transfers_api.py` | 25 | create + idempotency (replay, conflict, key length, JSON order), submit/cancel flows, 404/405/409 edge cases, submit delegates to the service |
| `transfers/tests/test_provider_webhooks.py` | 15 | signature verification (missing/invalid/prefix), raw-body signing, duplicate/conflicting event ids, unknown provider id, pending rejection, terminal-wins behavior, malformed JSON/payload |

## Frontend test matrix

**6 tests total**, three modules.

| Module | Tests | Covers |
| --- | --- | --- |
| `components/status-badge.test.tsx` | 1 | renders the right label for all five statuses |
| `components/transfer-actions.test.tsx` | 3 | pending shows Submit + Cancel; processing and terminal statuses hide them |
| `components/transfer-form.test.tsx` | 2 | surfaces API errors; submits payload and resets fields |

## Named webhook scenarios A–E

These are the explicit scenario tests in `test_provider_webhooks.py`; each maps
to a requirement behavior.

| Scenario | Test | Behavior |
| --- | --- | --- |
| **A** — duplicate event id | `test_scenario_a_duplicate_event_id_is_successful_noop` | Same `event_id` + same payload replayed → `200`, no new row, transfer unchanged. |
| **B** — completed then failed | `test_scenario_b_completed_then_failed_keeps_completed` | Two different event ids; the terminal `completed` wins; `failed` is acknowledged with outcome `ignored_terminal`. |
| **C** — unknown provider id | `test_scenario_c_unknown_provider_transfer_id_returns_404` | Signed event for a `provider_transfer_id` we never issued → `404`, nothing recorded. |
| **C** — pending with provider id | `test_scenario_c_pending_transfer_with_provider_id_rejects_409` | Event arrives for a `pending` transfer → `409`, status unchanged, nothing recorded. |
| **D** — second terminal event | `test_scenario_d_different_completed_events_same_provider_id_are_noop` | A second `completed` with a new event id after the transfer is terminal → `200`, outcome `ignored_terminal`. |
| **E** — cancel after submit | `test_scenario_e_cancel_after_submit_returns_409` | Submitting then cancelling → cancel `409`, transfer stays `processing`. |

Supporting webhook tests also cover: missing/invalid/malformed signatures
(`401`), signature computed over the exact raw body bytes, conflicting reuse of
an `event_id` with a different payload (`409`), and malformed JSON or invalid
status values (`400`).

## Verified status

- Backend: `93 passed` with the documented env vars and no Docker dependency.
- Frontend: `6 passed` with `npm test -- --run`.
- Compose: `docker compose config --quiet` succeeds.

Docker image builds and full `docker compose up` are covered by CI; unless
run in the current task they are documented as CI commands, not claimed as
locally verified.