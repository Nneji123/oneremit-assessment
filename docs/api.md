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
