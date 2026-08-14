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

Errors share a common shape: `{"detail": "<message>"}`.

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

Returns a JSON array of transfers, newest first.

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
