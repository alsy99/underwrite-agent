# Local testing with Ollama

Step-by-step guide to run **Underwrite Agent** on your Mac and test with **Ollama** as the LLM.

---

## 1. Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | `brew install python@3.11` |
| PostgreSQL | 14+ | `brew install postgresql@14` |
| Redis | 7+ | `brew install redis` |
| Ollama | latest | [https://ollama.com](https://ollama.com) or `brew install ollama` |

Docker is optional (MinIO falls back to local disk at `/tmp/underwrite-agent/storage`).

---

## 2. Start infrastructure

### 2.1 PostgreSQL and Redis

```bash
brew services start postgresql@14
brew services start redis
```

One-time database setup:

```bash
cd ~/underwrite-agent
bash scripts/setup_local_db.sh
```

### 2.2 Ollama

Open the **Ollama app**, or in a terminal:

```bash
ollama serve
```

Pull the model (must match `.env` — tag included):

```bash
ollama pull llama3.2:3b
ollama list   # confirm llama3.2:3b appears
```

Quick sanity check:

```bash
curl http://localhost:11434/api/chat -d '{
  "model": "llama3.2:3b",
  "messages": [{"role": "user", "content": "Say OK"}],
  "stream": false
}'
```

You should get a JSON response with `"content"` — not `"model not found"`.

---

## 3. Configure the project

```bash
cd ~/underwrite-agent
cp .env.example .env
```

Edit `.env` and confirm:

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
API_KEY=dev-api-key-change-me
DATABASE_URL=postgresql+asyncpg://underwrite:underwrite@localhost:5432/underwrite
REDIS_URL=redis://localhost:6379
```

Install dependencies:

```bash
/opt/homebrew/opt/python@3.11/bin/python3.11 -m pip install -e ".[dev]"
```

Initialize tables (first run only):

```bash
PYTHONPATH=. python3.11 -c "import asyncio; from packages.db.session import init_db; asyncio.run(init_db())"
```

---

## 4. Postman (optional)

Import from `postman/`:

- `Underwrite-Agent.postman_collection.json`
- `Underwrite-Agent.postman_environment.json`

See [postman/README.md](../postman/README.md).

---

## 5. Run unit tests (no Ollama required)

```bash
cd ~/underwrite-agent
PYTHONPATH=. python3.11 -m pytest tests/ -q
```

Expected: **12 passed**.

---

## 6. Option A — Fast happy path (no Ollama, ~40s)

Good for a quick smoke test without waiting on the LLM:

```bash
cd ~/underwrite-agent
PYTHONPATH=. python3.11 scripts/run_happy_flow.py
```

Uses `LLM_PROVIDER=heuristic` inside the script. Check:

- `output/happy_flow_report.md` → **APPROVE**
- `output/happy_flow_case_file.json`

---

## 7. Option B — Full stack with Ollama (API + worker)

Use **three terminals**.

### Terminal 1 — API

```bash
cd ~/underwrite-agent
PYTHONPATH=. python3.11 -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

Verify: `curl http://127.0.0.1:8000/health`

### Terminal 2 — Background worker

```bash
cd ~/underwrite-agent
PYTHONPATH=. python3.11 -m apps.worker.main
```

Leave this running. It processes cases from Redis and calls Ollama.

### Terminal 3 — Submit a test case

**Upload policy (once):**

```bash
export API=http://127.0.0.1:8000
export KEY=dev-api-key-change-me
export FIXTURES=~/underwrite-agent/data/fixtures

curl -X POST "$API/v1/tenants/default/policies" \
  -H "Authorization: Bearer $KEY" \
  -F "title=SBA Policy" \
  -F "file=@$FIXTURES/policies/sba_policy_seed.md"
```

**Fraudulent SBA package (expect REVIEW + contradictions):**

```bash
curl -X POST "$API/v1/cases" \
  -H "Authorization: Bearer $KEY" \
  -F "vertical=sba_7a" \
  -F "tenant_id=default" \
  -F 'metadata={"business_name":"Acme Consulting LLC","employer":"Acme Consulting LLC","address":"1200 Market Street Suite 400 Wilmington DE","stated_employer":"Acme Consulting LLC"}' \
  -F "documents=@$FIXTURES/sba/fraudulent/form_1919.txt" \
  -F "documents=@$FIXTURES/sba/fraudulent/profit_loss.txt" \
  -F "documents=@$FIXTURES/sba/fraudulent/employment_letter.txt" \
  -F "documents=@$FIXTURES/sba/fraudulent/bank_statement.txt"
```

Copy `case_id` from the response, then poll until `status` is `completed` (typically **60–120 seconds** with Ollama):

```bash
CASE_ID=<paste-case-id-here>
curl -s "$API/v1/cases/$CASE_ID" -H "Authorization: Bearer $KEY" | python3 -m json.tool
```

**Audit trail:**

```bash
curl -s "$API/v1/cases/$CASE_ID/audit" -H "Authorization: Bearer $KEY" | python3 -m json.tool
```

**Clean SBA package (expect APPROVE or low-risk REVIEW):**

```bash
curl -X POST "$API/v1/cases" \
  -H "Authorization: Bearer $KEY" \
  -F "vertical=sba_7a" \
  -F "tenant_id=default" \
  -F 'metadata={"business_name":"Sunrise Bakery LLC","employer":"Sunrise Bakery LLC","address":"88 Main Street Portland OR","stated_employer":"Sunrise Bakery LLC"}' \
  -F "documents=@$FIXTURES/sba/clean/form_1919.txt" \
  -F "documents=@$FIXTURES/sba/clean/profit_loss.txt" \
  -F "documents=@$FIXTURES/sba/clean/employment_letter.txt"
```

### Automated API test suite (all fixtures)

```bash
cd ~/underwrite-agent
PYTHONPATH=. python3.11 scripts/run_api_tests.py
```

Requires API + worker running. Allow **~5–10 minutes** for three Ollama-backed cases.

---

## 8. Option C — Single-case script (Ollama, no API)

Run investigation inline (no Redis worker). Still uses Ollama if `LLM_PROVIDER=ollama` in `.env`:

```bash
cd ~/underwrite-agent
# ensure .env has LLM_PROVIDER=ollama and OLLAMA_MODEL=llama3.2:3b
PYTHONPATH=. python3.11 -c "
import asyncio, uuid, json
from pathlib import Path
from packages.db.session import init_db, _get_engine
from packages.db.models import CaseRecord
from packages.documents.pipeline import DocumentPipeline
from packages.agent.investigation import InvestigationRunner
from packages.schemas.case import LoanVertical

async def run():
    await init_db()
    _, f = _get_engine()
    cid = str(uuid.uuid4())
    FIX = Path('data/fixtures/sba/fraudulent')
    async with f() as s:
        s.add(CaseRecord(id=cid, tenant_id='default', vertical='sba_7a', status='queued', metadata_json={'business_name':'Acme Consulting LLC','employer':'Acme Consulting LLC','address':'1200 Market Street Wilmington DE','stated_employer':'Acme Consulting LLC'}))
        await s.flush()
        p = DocumentPipeline(s, cid, 'default')
        for file in sorted(FIX.glob('*.txt')):
            await p.ingest_file(file.name, file.read_bytes())
        await s.commit()
        cf = await InvestigationRunner(s, cid).run()
        print(json.dumps(cf.model_dump(), indent=2)[:3000])

asyncio.run(run())
"
```

---

## 9. What to look for (Ollama working)

| Signal | Ollama ON | Ollama OFF / wrong model |
|--------|-----------|-------------------------|
| Worker logs | `POST http://localhost:11434/api/chat HTTP/1.1 200 OK` | `404 Not Found` |
| Executive summary | Natural language, case-specific | Contains *"Heuristic mode"* |
| Contradictions | LLM + rules on fraud package | Rules only |

---

## 10. Troubleshooting

### `model 'llama3.2' not found`

Use the full tag from `ollama list`, e.g. `llama3.2:3b`, in `.env`:

```env
OLLAMA_MODEL=llama3.2:3b
```

Restart the **worker** after changing `.env`.

### Case stuck on `queued`

Worker not running. Start Terminal 2 (`python -m apps.worker.main`) or set in `.env`:

```env
SYNC_INVESTIGATION=true
```

Then create cases via API (investigation runs inside the API process).

### Very slow (~90s+ per case)

Normal for MVP: multiple Ollama calls + embedding model load. First run after worker restart is slowest. For quick demos use `scripts/run_happy_flow.py`.

### PostgreSQL / pgvector errors

Use Homebrew Postgres with `scripts/setup_local_db.sh`. The app uses `ARRAY` embeddings (no pgvector extension required).

### MinIO connection errors

Ignored automatically — files stored under `/tmp/underwrite-agent/storage`.

---

## 11. Fixture reference

| Path | Purpose |
|------|---------|
| `data/fixtures/sba/fraudulent/` | Employer + revenue mismatches → **REVIEW** |
| `data/fixtures/sba/clean/` | Aligned docs → **APPROVE** (fast/heuristic) |
| `data/fixtures/cre/fraudulent/` | CRE guarantor mismatch |
| `data/fixtures/policies/sba_policy_seed.md` | Policy RAG seed |

Pre-built reports from earlier runs:

- `output/happy_flow_report.md`
- `output/investigation_report_fraudulent_sba.md`

---

## 12. Stop services

```bash
brew services stop postgresql@14   # optional
brew services stop redis           # optional
# Ctrl+C on uvicorn and worker terminals
```
