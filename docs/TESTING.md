# Testing

## Layers

| Layer | Backend | Frontend |
|-------|---------|----------|
| **Unit** | `tests/unit/` + existing `tests/test_*.py` (no DB) | Vitest: `src/**/*.test.ts(x)` |
| **Integration** | `tests/integration/` (FastAPI + Postgres) | Vitest page tests with mocked API |
| **E2E** | `tests/e2e/` (full investigation, heuristic LLM) | Playwright `e2e/smoke.spec.ts` (needs UI up) |

## Local test database

Integration/e2e use a **separate** DB so pytest never wipes app data:

| DB | Purpose |
|----|---------|
| `underwrite` | App / demo (`DATABASE_URL` in `.env`) |
| `underwrite_test` | Pytest only (`TEST_DATABASE_URL`) |

```bash
# One-time (also runs from setup_local_db.sh)
./scripts/setup_test_db.sh

# Or via test runner
./scripts/run_tests.sh setup-db
./scripts/run_tests.sh backend
```

Defaults (override with env):

```bash
TEST_DATABASE_URL=postgresql+asyncpg://underwrite:underwrite@localhost:5432/underwrite_test
```

`tests/conftest.py` sets `DATABASE_URL` from `TEST_DATABASE_URL` (or the default above) before tests run.

## Commands

```bash
# Backend unit (default CI)
PYTHONPATH=. python3.11 -m pytest tests -m "not integration and not e2e" -q

# Backend integration + e2e
./scripts/setup_test_db.sh
LLM_PROVIDER=heuristic OSINT_MODE=fixture \
  PYTHONPATH=. python3.11 -m pytest tests/integration tests/e2e -q

# All backend (auto-provisions underwrite_test)
./scripts/run_tests.sh backend

# Frontend
cd apps/demo-ui
npm install
npm test
npx playwright install chromium
npm run test:e2e         # skips if http://localhost:5173 is down
```

Helper: `./scripts/run_tests.sh unit|backend|frontend|all|setup-db`

## Deterministic modes

- `LLM_PROVIDER=heuristic` — no Ollama
- `OSINT_MODE=fixture` — corpus under `data/fixtures/osint/`
- Integration create-case uses `SYNC_INVESTIGATION=0` (queue only); e2e runs `InvestigationRunner` inline
