# Product roadmap

Phased path from investigation MVP → underwriter workflow → enterprise packaging.

## Phase 0 — Shipped

- Document ingest, cross-check, policy RAG, LangGraph investigation
- Hybrid OSINT + entity profiles + demo UI
- GTM / enterprise / MRM docs + OSINT golden eval

## Phase A — SSO / OIDC + RBAC (shipped)

- `AUTH_MODE=api_key|oidc|both`
- Principals from shared key, tenant API keys, or OIDC JWT
- Roles: admin / underwriter / reviewer
- Docs: [SSO.md](SSO.md)

## Phase B — Spreading (shipped)

- CSV/XLSX upload, canonical metrics, variance vs stated metadata
- Docs: [SPREADING.md](SPREADING.md)

## Phase C — Credit memo (shipped)

- Templated Markdown memos with citations from case file
- Docs: [MEMO.md](MEMO.md)

## Phase D — LOS generic (shipped)

- HMAC webhooks, case export, LOS ingest
- Docs: [LOS_WEBHOOKS.md](LOS_WEBHOOKS.md)

## Phase E — Later

- Encompass / nCino thin adapters on canonical export
- Contracted live OSINT vendors
- Exception queue UI (assign / SLA)

## Explicit non-goals (near term)

- Replacing core LOS origination
- Consumer soft-pull credit bureau product
- Unlicensed scraping of social networks
