# Enterprise packaging

Honest snapshot of multi-tenant / security posture today and what production buyers still need.

## What exists now

| Concern | Current state |
|---------|----------------|
| Auth | `AUTH_MODE=both`: shared `API_KEY`, tenant API keys, or OIDC JWT ([SSO.md](SSO.md)) |
| Tenancy | Soft isolation via `tenant_id`; OIDC/tenant keys bind tenant from identity |
| RBAC | `admin` / `underwriter` / `reviewer` on mutate vs read vs webhook admin |
| Audit | Per-case immutable event log (actor, action, hashed inputs, outputs, prompt version) |
| Spreading / memo | CSV/XLSX spreads + templated credit memos |
| LOS | HMAC webhooks + export/ingest ([LOS_WEBHOOKS.md](LOS_WEBHOOKS.md)) |
| PII | Regex redaction before LLM prompts |
| Deploy | Docker Compose or brew local services |
| UI gate | Demo password still for static Pages; API uses Bearer |

## Gaps (buyers will still ask)

- Full SSO UI redirect in demo SPA (API OIDC ready; UI still API-key Bearer)
- Formal SOC2 / ISO evidence pack
- Contracted OSINT/KYC vendors with SLAs
- Named Encompass/nCino connectors (Phase E)

## Recommended enterprise path

1. Put API behind API gateway + mTLS or private link
2. Replace shared key with IdP-issued tokens; map `tenant_id` from claims
3. Contract registry + sanctions + adverse-media providers; keep fixture mode for CI only
4. Wire model-risk package ([MRM_COMPLIANCE.md](MRM_COMPLIANCE.md)) into bank MRM inventory

## OSINT live sources — production viability

| Source | Viable in prod today? | Notes |
|--------|----------------------|-------|
| OFAC SDN cache / path | Yes, with legal review + refresh policy | Free Treasury data; cache under `OSINT_CACHE_DIR` |
| SEC EDGAR | Yes for public cos | Requires identifiable User-Agent |
| Nominatim | Careful | Respect usage policy; prefer commercial geocoder at scale |
| OpenCorporates | Pilot | Paid tiers / ToS for commercial use |
| NewsAPI | Pilot | Quotas; not a compliance media screen |
| Employer / LinkedIn-style | No | Heuristic / fixture only — use contracted employment verification |
