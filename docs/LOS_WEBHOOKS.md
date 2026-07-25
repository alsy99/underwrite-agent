# LOS webhooks & export

LOS-agnostic integration. Named Encompass/nCino connectors are a later thin adapter layer.

## Outbound events

| Event | When |
|-------|------|
| `case.completed` | Investigation finalize |
| `case.memo_ready` | Memo generated |
| `spread.variance_high` | High-severity spread variance |
| `recommendation.updated` | Reserved |

## Admin API

- `POST /v1/los/webhooks` — register URL + HMAC secret + event filter (`*` = all)
- `GET /v1/los/webhooks`
- `GET /v1/los/deliveries`

Headers on delivery:

- `X-Underwrite-Signature` — HMAC-SHA256 hex of raw body
- `X-Underwrite-Event` — event type

## Pull / push

- `GET /v1/cases/{id}/export` — full JSON bundle
- `POST /v1/los/ingest` — LOS pushes docs (same shape as case create)

Verify signatures with `packages.los.verify_signature`.
