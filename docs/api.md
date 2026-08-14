# Transfer API

Base URL: `/api/transfers/`

All endpoints accept and return JSON. Success responses use the following
transfer shape:

| Field | Type | Description |
| --- | --- | --- |
| `id` | string (UUID) | Transfer identifier. |
| `reference` | string | Human-friendly reference, e.g. `TRF-<hex>`. |
| `amount` | string (decimal) | Transfer amount, two decimal places. |
| `currency` | string | `NGN`, `USD`, `GBP`, or `EUR`. |
| `recipient_ref` | string | Recipient reference. |
| `status` | string | One of `pending`, `processing`, `completed`, `failed`, `cancelled`. |
| `provider_transfer_id` | string \| null | Provider id assigned on submit. |
| `created_at` / `updated_at` | string (ISO-8601) | Timestamps. |

## Response envelope

Every JSON response is wrapped in a consistent envelope:

| Field | Type | Description |
| --- | --- | --- |
| `success` | boolean | `true` for success responses, `false` for errors. |
| `message` | string | Human-readable message; empty on success unless noted. |
| `response_code` | integer | The HTTP status code for the response. |
| `data` | mixed | The response payload, e.g. a transfer object or an array of transfers for list endpoints. `null` on errors. |
| `pagination` | object \| null | Present on paginated list responses: `{count, next, previous}`. |

Errors use `success: false` with a `message` describing the problem; there is
no `{"detail": ...}` key. `data` is `null` for error responses.

## Create a transfer

`POST /api/transfers/`

Request fields:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `amount` | string (decimal) | yes | Greater than zero; at most two decimal places. |
| `currency` | string | yes | One of `NGN`, `USD`, `GBP`, `EUR` (case-insensitive). |
| `recipient_ref` | string | yes | Non-empty, at most 255 characters. |

Header `Idempotency-Key` is required and must be at most 255 characters.

Responses:

| Status | Meaning |
| --- | --- |
| `201` | Transfer created. |
| `200` | Idempotent replay: the key was already used with an identical request body; returns the original transfer. |
| `400` | Missing or too-long `Idempotency-Key`, or an invalid request body. |
| `409` | `Idempotency-Key` conflict: the key was already used with a different request body. |

### Idempotency-Key semantics

- The key must be unique per logical request. Reusing a key with a
  semantically identical body (same amount, currency, recipient reference,
  regardless of JSON key order or formatting) replays the original transfer
  and returns it with `200`.
- Reusing a key with a different request body returns `409 Conflict`.
- Keys longer than 255 characters are rejected with `400` before any data is
  written.
- A missing key is rejected with `400`.

## List transfers

`GET /api/transfers/`

Returns a paginated list of transfers, newest first. The results array is in
the envelope's `data` field, with `pagination` metadata (`count`, `next`,
`previous`). The page size is 20 by default.

## Retrieve a transfer

`GET /api/transfers/{id}/`

Returns a single transfer.

| Status | Meaning |
| --- | --- |
| `200` | Transfer found. |
| `404` | Transfer not found (including a malformed UUID identifier). |

## Submit a transfer

`POST /api/transfers/{id}/submit/`

Moves a `pending` transfer to `processing` and assigns a
`provider_transfer_id`.

| Status | Meaning |
| --- | --- |
| `200` | Transfer submitted; body contains the updated transfer. |
| `404` | Transfer not found (including a malformed UUID identifier). |
| `409` | Invalid state; the transfer is not `pending` and cannot be submitted. |

## Cancel a transfer

`POST /api/transfers/{id}/cancel/`

Moves a `pending` transfer to `cancelled`.

| Status | Meaning |
| --- | --- |
| `200` | Transfer cancelled; body contains the updated transfer. |
| `404` | Transfer not found (including a malformed UUID identifier). |
| `409` | Invalid state; the transfer is not `pending` and cannot be cancelled. |

## Simulate a provider event (local demo helper)

`POST /api/transfers/{id}/simulate-webhook/`

Drives a `processing` transfer to `completed` or `failed` from the detail UI.
This is a **local demo helper only**: it synthesizes an `event_id` and funnels
the payload through the same `process_provider_event` service as the signed
webhook, so the state machine and event-dedup semantics are identical. It is
**not** a replacement for the signed production webhook, and it refuses any
transfer that is not currently `processing`.

Request fields:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `status` | string | yes | One of `completed`, `failed`. |

No signature header is required.

Responses:

| Status | Meaning |
| --- | --- |
| `200` | Simulated event applied; body contains the updated transfer. |
| `400` | Missing or invalid `status` (anything other than `completed`/`failed`). |
| `404` | Transfer not found (including a malformed UUID identifier). |
| `409` | Transfer is not `processing` (e.g. still `pending`, or already terminal); nothing is recorded. |

## Status transitions

Transitions are enforced by a single state machine:

```
pending     -> processing, cancelled
processing  -> completed, failed
```

`completed`, `failed`, and `cancelled` are terminal.

## Unsupported methods

`PATCH`, `PUT`, and `DELETE` on `/api/transfers/` return `405 Method Not Allowed`.

# Provider webhook

`POST /api/webhooks/provider/`

Notifies the backend of a provider-side outcome for a submitted transfer.

Request fields:

| Field | Type | Required | Rules |
| --- | --- | --- | --- |
| `event_id` | string | yes | Provider event id; unique per event. |
| `provider_transfer_id` | string | yes | Id assigned to the transfer on submit. |
| `status` | string | yes | One of `completed`, `failed`. |
| `occurred_at` | string (ISO-8601) | no | When the event occurred at the provider. |

The `X-Provider-Signature` header is required and must equal
`sha256=<HMAC-SHA256 hex>` computed over the exact raw request body using the
`PROVIDER_WEBHOOK_SECRET`. Signatures are verified before the body is parsed or
any data is written. Raw payloads and signatures are never stored.

Responses:

| Status | Meaning |
| --- | --- |
| `200` | Event applied to a `processing` transfer, a duplicate of an already-recorded event, or an event ignored because the transfer is already terminal. |
| `400` | Malformed JSON or an invalid payload (e.g. a status other than `completed`/`failed`). |
| `401` | Missing, malformed, or invalid `X-Provider-Signature`. |
| `404` | No transfer exists with the given `provider_transfer_id`; no event is recorded. |
| `409` | The transfer is still `pending`, or the `event_id` was already used with a different payload; no event is recorded. |

Semantics:

- A `processing` transfer moves to `completed` or `failed`.
- A transfer that is already `completed`, `failed`, or `cancelled` stays
  unchanged; the event is recorded with outcome `ignored_terminal` and `200` is
  returned to acknowledge it.
- Replaying the same `event_id` with an identical payload returns `200` and
  records nothing new.
- Reusing an `event_id` with a different payload returns `409`.

# Realtime updates (WebSocket)

`ws://<host>/ws/transfers/{id}/`

The detail page subscribes to a per-transfer WebSocket to receive status
changes as they happen, instead of polling. The socket is intentionally
unauthenticated — the assessment API is local/open.

Connection flow:

1. Client opens `ws://<host>/ws/transfers/{id}/` for a transfer UUID.
2. The consumer accepts, joins the `transfer_<id>` group, and immediately sends
   an initial snapshot of the transfer.
3. On every committed status change (submit, cancel, signed webhook, or
   simulate) the backend broadcasts to the group.

Message contract (JSON):

| Field | Type | Description |
| --- | --- | --- |
| `type` | string | Always `transfer.status`. |
| `transfer` | object | The full transfer object (same shape as the REST detail response). |

Example:

```json
{
  "type": "transfer.status",
  "transfer": {
    "id": "0f1a2b3c-…",
    "reference": "TRF-abc123",
    "status": "completed",
    "amount": "100.00",
    "currency": "NGN",
    "recipient_ref": "recipient-123",
    "provider_transfer_id": "prov_…",
    "created_at": "2026-08-10T12:00:00Z",
    "updated_at": "2026-08-10T12:01:00Z"
  }
}
```

Notes:

- The channel layer is **in-memory** for this local assessment, so WebSockets
  only work against a single process (exactly one uvicorn worker).
- Broadcasts happen only *after* the status-changing transaction commits, so a
  client never observes an uncommitted state.
- The frontend opens this URL with
  `NEXT_PUBLIC_WS_BASE_URL ?? derived from NEXT_PUBLIC_API_BASE_URL`, e.g.
  `ws://localhost:8000/ws/transfers/<id>/`.
