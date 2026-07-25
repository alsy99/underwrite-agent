# Credit memo

Deterministic Jinja Markdown drafts from the case file (+ optional spread). **Advisory** — not a final credit decision.

## API

- `POST /v1/cases/{id}/memo` — generate next version
- `GET /v1/cases/{id}/memo` — latest
- `GET /v1/cases/{id}/memo/{version}` — history

Templates live in `packages/memo/templates/` (`sba_7a.md.j2`, etc.). LLM polish is intentionally not required for generation (MRM-friendly).

Emits `case.memo_ready` webhook when endpoints exist.
