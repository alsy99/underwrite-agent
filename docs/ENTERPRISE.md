# Enterprise packaging

Honest snapshot of multi-tenant / security posture today and what production buyers still need.

## What exists now

| Concern | Current state |
|---------|----------------|
| Auth | Single shared `API_KEY` (Bearer) for mutating API routes |
| Tenancy | Soft isolation via `tenant_id` string on cases, docs, policies, MinIO prefixes |
| Audit | Per-case immutable event log (actor, action, hashed inputs, outputs, prompt version) |
| PII | Regex redaction before LLM prompts ([`packages/documents/pii.py`](../packages/documents/pii.py)) |
| Deploy | Docker Compose (Postgres, Redis, MinIO, API, worker) or brew local services |
| UI gate | Optional demo password hash (`VITE_UI_PASSWORD_HASH` / `UI_PASSWORD`) — not bank IAM |

## Private deployment

1. Copy `.env.example` → `.env`; set strong `API_KEY`
2. `docker compose up -d` (or managed Postgres/Redis + MinIO/S3-compatible)
3. Run API + worker; optionally sync investigation with `SYNC_INVESTIGATION=true` for small installs
4. Keep OSINT in `fixture` or `auto` with reviewed live keys; prefer VPC egress allowlists for Nominatim / EDGAR / OFAC

See also [INTERNET_DEPLOY.md](INTERNET_DEPLOY.md) (demo tunnels — not production edge).

## Gaps (buyers will ask)

- SSO / OIDC (Okta, Azure AD)
- Per-tenant API keys and secrets rotation
- RBAC (underwriter vs reviewer vs admin)
- Row-level tenancy enforcement beyond client-supplied `tenant_id`
- Encryption at rest / CMEK story beyond storage defaults
- Formal SOC2 / ISO evidence pack
- Contracted OSINT/KYC vendors with SLAs and indemnities

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
