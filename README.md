# Underwrite Agent

AI Underwriting Assistant — **Agentic Fraud Investigation MVP** for complex lending (SBA 7(a), CRE acquisition, specialty mortgage).

## Product pillars

1. **Unstructured cross-checking** — semantic contradictions across leases, VOEs, tax forms, and applications with cited evidence.
2. **Sherlock agentic workflow** — autonomous investigation building an auditable case file (registry/OSINT stubs, geocoding, address heuristics).
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

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness |
| POST | `/v1/cases` | Multipart: `vertical`, `tenant_id`, `metadata` (JSON), `documents[]` |
| GET | `/v1/cases` | List cases (demo UI) |
| GET | `/v1/cases/{id}` | Case status + case file |
| GET | `/v1/cases/{id}/audit` | Immutable audit timeline |
| POST | `/v1/tenants/{id}/policies` | Upload policy PDF/Markdown |
| GET | `/v1/tenants/{id}/policies` | List policies |

Auth: `Authorization: Bearer <API_KEY>` (see `.env`).

**Verticals:** `sba_7a`, `cre_acquisition`, `specialty_mortgage_bank_statement`

## LLM providers

- **Ollama** (default): set `LLM_PROVIDER=ollama` and run Ollama locally.
- **Azure OpenAI:** set `LLM_PROVIDER=azure` and Azure env vars.
- **Heuristic fallback:** if no LLM responds, rule-based cross-check and policy evaluation still run.

## Compliance notes

- MVP outputs are **advisory**; human underwriters must review `review` and `decline` recommendations.
- OSINT tools are **stubs** in v1 — production requires ToS-compliant providers and legal review.
- PII is redacted before LLM prompts; raw documents stored in MinIO per tenant prefix.

## Tests

```bash
pytest tests/ -q
```

## Architecture

See plan document for pipeline diagram. Core flow: document ingest → cross-check → policy RAG → agent tools → case file + audit log.
