# Underwrite Agent

AI Underwriting Assistant — **Agentic Fraud Investigation MVP** for complex lending (SBA 7(a), CRE acquisition, specialty mortgage).

## Product pillars

1. **Unstructured cross-checking** — semantic contradictions across leases, VOEs, tax forms, and applications with cited evidence.
2. **Sherlock agentic workflow** — autonomous investigation building an auditable case file (hybrid OSINT profiling, registry, geocoding, address heuristics).
3. **Dynamic policy RAG** — bank policy documents ingested without code deploys; compliance findings at investigation time.

## Quick start

**Full local guide (Ollama + Homebrew Postgres/Redis):** [docs/LOCAL_TESTING_OLLAMA.md](docs/LOCAL_TESTING_OLLAMA.md)

**Postman:** import [postman/Underwrite-Agent.postman_collection.json](postman/Underwrite-Agent.postman_collection.json) + [environment](postman/Underwrite-Agent.postman_environment.json) — see [postman/README.md](postman/README.md)

```bash
cp .env.example .env
docker compose up -d   # or: brew services start postgresql@14 redis
pip install -e ".[dev]"
python scripts/seed_policies.py   # optional if policies not uploaded via API
uvicorn apps.api.main:app --reload --port 8000
# separate terminal:
python -m apps.worker.main
```

Secrets and provider keys live in the repo-root **`.env`** (see `.env.example` for every placeholder). API, worker, scripts, and demo UI all load from that file.

Run demo:

```bash
chmod +x scripts/run_demo.sh
./scripts/run_demo.sh
```

Fast happy path (no Ollama):

```bash
python scripts/run_happy_flow.py
```

## Demo UI (local only)

```bash
./scripts/start-api.sh          # terminal 1
./scripts/start-worker.sh       # terminal 2
./scripts/start-demo-ui.sh      # terminal 3 → http://localhost:5173
```

Features: case list, new investigation upload, live case file + audit trail viewer.

## Remote access (internet demo)

The **UI** is hosted on GitHub Pages. The **API + worker** run on your Mac and are exposed with a tunnel.

### One-time setup

1. Copy env and install deps (if you have not already):

   ```bash
   cp .env.example .env
   pip install -e ".[dev]"
   brew services start postgresql@14 redis
   brew install cloudflared   # tunnel (or ngrok + authtoken)
   ```

2. In `.env`, set at least:

   ```bash
   API_KEY=your-long-random-key
   CORS_GITHUB_PAGES=true
   UI_PASSWORD=your-demo-login-password   # optional; GitHub secret uses this name
   ```

3. On GitHub → repo **Settings → Secrets and variables → Actions**, add:

   | Secret | Value |
   |--------|--------|
   | `VITE_API_URL` | filled automatically by start script, or your tunnel URL |
   | `VITE_API_KEY` | same as `API_KEY` in `.env` |
   | `UI_PASSWORD` | same as demo login password |

4. Enable Pages: **Settings → Pages → Source → GitHub Actions**.

### Every demo session (start in order)

```bash
./scripts/start-internet-session.sh
```

This starts **API → worker → Cloudflare tunnel**, updates `VITE_API_URL` on GitHub (if `gh` is logged in), and triggers a Pages redeploy.

5. Open the app (wait ~1–2 min after deploy):

   **https://alsy99.github.io/underwrite-agent/**

   Use your `UI_PASSWORD` (GitHub secret). Hard-refresh on mobile if the layout looks wrong.

6. When finished:

   ```bash
   ./scripts/stop-internet-session.sh
   ```

### Same Wi‑Fi only (no GitHub Pages)

```bash
./scripts/start-api.sh
./scripts/start-worker.sh
./scripts/start-demo-ui.sh      # open http://<your-lan-ip>:5173 on phone
```

See [docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md) for LAN troubleshooting.

### More detail

- [docs/INTERNET_DEPLOY.md](docs/INTERNET_DEPLOY.md) — tunnels, secrets, ngrok
- [docs/REMOTE_ACCESS.md](docs/REMOTE_ACCESS.md) — LAN / firewall

## GTM / enterprise

- [docs/GTM_POSITIONING.md](docs/GTM_POSITIONING.md) — what we sell vs roadmap
- [docs/ENTERPRISE.md](docs/ENTERPRISE.md) — auth, tenancy, private deploy, gaps
- [docs/MRM_COMPLIANCE.md](docs/MRM_COMPLIANCE.md) — model-risk / compliance one-pager
- [docs/PRODUCT_ROADMAP.md](docs/PRODUCT_ROADMAP.md) — spreading / memo / LOS / SSO phases
- [docs/OSINT_EVAL.md](docs/OSINT_EVAL.md) — golden-set accuracy metrics (fixture corpus)
- [docs/SSO.md](docs/SSO.md) · [docs/SPREADING.md](docs/SPREADING.md) · [docs/MEMO.md](docs/MEMO.md) · [docs/LOS_WEBHOOKS.md](docs/LOS_WEBHOOKS.md)

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| POST | `/v1/cases` | Multipart: `vertical`, `tenant_id`, `metadata` (JSON), `documents[]` |
| GET | `/v1/cases` | List cases (demo UI) |
| GET | `/v1/cases/{id}` | Case status + case file |
| GET | `/v1/cases/{id}/audit` | Immutable audit timeline |
| GET | `/v1/cases/{id}/export` | LOS JSON export bundle |
| POST | `/v1/cases/{id}/spreads` | Upload financial spread CSV/XLSX |
| GET | `/v1/cases/{id}/spreads` | Latest spread + variances |
| POST | `/v1/cases/{id}/memo` | Generate credit memo draft |
| GET | `/v1/cases/{id}/memo` | Latest memo |
| POST | `/v1/los/webhooks` | Register HMAC webhook (admin) |
| POST | `/v1/los/ingest` | LOS document push → new case |
| POST | `/v1/tenants/{id}/policies` | Upload policy PDF/Markdown |
| GET | `/v1/tenants/{id}/policies` | List policies |

Auth: `Authorization: Bearer <API_KEY|OIDC_JWT>` (see `.env` `AUTH_MODE`, [docs/SSO.md](docs/SSO.md)).

**Verticals:** `sba_7a`, `cre_acquisition`, `specialty_mortgage_bank_statement`

## LLM providers

- **Ollama** (default): set `LLM_PROVIDER=ollama` and run Ollama locally.
- **Azure OpenAI:** set `LLM_PROVIDER=azure` and Azure env vars.
- **Heuristic fallback:** if no LLM responds, rule-based cross-check and policy evaluation still run.

## Compliance notes

- MVP outputs are **advisory**; human underwriters must review `review` and `decline` recommendations.
- OSINT is **hybrid**: deterministic fixture corpus by default (`OSINT_MODE=auto|fixture`), with live adapters when keys are set (`OPENCORPORATES_API_KEY`, `NEWS_API_KEY`, `OFAC_SDN_PATH`). Production use requires ToS-compliant providers and legal review.
- Case files include `entity_profiles` (business, employer, principal, address) with risk scores and signals.
- PII is redacted before LLM prompts; raw documents stored in MinIO per tenant prefix.

## Tests

```bash
pytest tests/ -q
OSINT_MODE=fixture python scripts/eval_osint.py   # OSINT golden metrics → output/
```

See [docs/OSINT_EVAL.md](docs/OSINT_EVAL.md) for baseline F1 numbers and disclaimer.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the pipeline diagram and product boundary.
Core flow: document ingest → cross-check → policy RAG → OSINT agent tools → case file with **entity profiles** + audit log.
This is an **investigation layer**, not a full spreading / memo / LOS product ([roadmap](docs/PRODUCT_ROADMAP.md)).
