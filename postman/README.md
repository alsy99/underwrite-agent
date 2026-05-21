# Postman — ready to test

## Prerequisites (before Postman)

```bash
cd ~/underwrite-agent
cp .env.example .env
brew services start postgresql@14 redis
bash scripts/setup_local_db.sh
pip install -e ".[dev]"
```

**Two terminals** (cases stay `queued` forever without the worker):

```bash
# Terminal 1 — API (use project script — picks Python 3.11+)
cd ~/underwrite-agent
./scripts/start-api.sh

# Terminal 2 — Worker
./scripts/start-worker.sh
```

Optional: `ollama serve` and `OLLAMA_MODEL=llama3.2:3b` in `.env`.

---

## Import (one time)

1. Postman → **Import**
2. Select:
   - `Underwrite-Agent.postman_collection.json`
   - `Underwrite-Agent.postman_environment.json`
3. Top-right environment: **Underwrite Agent - Local**
4. Keep the collection file inside `postman/` so `fixtures/` paths resolve

---

## Test flow (3 minutes)

| Step | Request | Expected |
|------|---------|----------|
| 1 | **0 - Start Here → Health Check** | `200`, `service: underwrite-agent` |
| 2 | **Policies → Upload Policy — SBA (JSON) ★** | `201` |
| 3 | **Cases → Create Case — SBA Fraudulent** | `202`, saves `caseId` |
| 4 | **Cases → Get Case** — click **Send** every ~10s | `status: completed` (~60–120s with Ollama) |
| 5 | **Cases → Get Case Audit Trail** | JSON array of audit events |

Or run **Workflows → 2 — Fraud investigation flow** in Collection Runner (add **10s delay** on the Get Case step).

---

## Variables

| Variable | Default | Set by |
|----------|---------|--------|
| `baseUrl` | `http://127.0.0.1:8000` | environment |
| `apiKey` | `dev-api-key-change-me` | must match `.env` `API_KEY` |
| `tenantId` | `default` | environment |
| `caseId` | (empty) | auto after Create Case |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Health fails | Start Terminal 1 (uvicorn) |
| Case stuck `queued` | Start Terminal 2 (worker) |
| `401` on POST | Match `apiKey` to `.env` `API_KEY` |
| File upload missing | Re-select files from `postman/fixtures/` |
| Slow investigation | Normal with Ollama; use worker logs for `200 OK` on port 11434 |

---

## Bundled fixtures

All upload paths point to `postman/fixtures/` (shipped with the collection).
