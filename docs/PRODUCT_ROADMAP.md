# Product roadmap

Phased path from investigation MVP → fuller underwriting adjacent product. Dates intentionally relative.

## Phase 0 — Now (shipped)

- Document ingest, cross-check, policy RAG, LangGraph investigation
- Hybrid OSINT + entity profiles + demo UI
- GTM / enterprise / MRM docs + OSINT golden eval

## Phase 1 — Live OSINT depth (next)

- Contracted business registry + employment verification adapters
- Hardened OFAC refresh SLAs; adverse-media vendor option
- Expand golden set with anonymized lender-labeled cases
- Per-tenant API keys

## Phase 2 — Underwriter workflow

- Credit memo draft from case file (templated, citation-backed)
- Spreading import (CSV / Excel) with variance checks vs stated income
- Exception queue UI (review queue, assign, SLA)

## Phase 3 — LOS integration

- Outbound webhooks / REST for case status + findings
- Connectors: Encompass, nCino, or generic LOS document pull
- SSO (OIDC) and RBAC

## Explicit non-goals (near term)

- Replacing core LOS origination
- Consumer soft-pull credit bureau product
- Unlicensed scraping of social networks

## Buyers asking “when spreading / memo / LOS?”

Point here. Investigation layer remains the wedge until Phase 2–3 land.
