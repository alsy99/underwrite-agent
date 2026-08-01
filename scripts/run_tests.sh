#!/usr/bin/env bash
# Run test suites. Usage:
#   ./scripts/run_tests.sh           # unit only (backend + frontend)
#   ./scripts/run_tests.sh all       # unit + integration + e2e (needs Postgres)
#   ./scripts/run_tests.sh backend
#   ./scripts/run_tests.sh frontend
#   ./scripts/run_tests.sh setup-db  # create underwrite_test only
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=.
export LLM_PROVIDER="${LLM_PROVIDER:-heuristic}"
export OSINT_MODE="${OSINT_MODE:-fixture}"

# Isolated test DB (do not use app DB `underwrite`)
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+asyncpg://underwrite:underwrite@localhost:5432/underwrite_test}"
export DATABASE_URL="${DATABASE_URL:-$TEST_DATABASE_URL}"

TARGET="${1:-unit}"
PYTHON="${PYTHON:-python3.11}"
command -v "$PYTHON" >/dev/null 2>&1 || PYTHON=python3

ensure_test_db() {
  echo "==> Ensuring local test database (underwrite_test)"
  chmod +x "$ROOT/scripts/setup_test_db.sh"
  "$ROOT/scripts/setup_test_db.sh"
}

run_backend_unit() {
  echo "==> Backend unit"
  "$PYTHON" -m pytest tests/unit tests -m "not integration and not e2e" -q --tb=short
}

run_backend_full() {
  ensure_test_db
  echo "==> Backend unit + integration + e2e (DATABASE_URL=$DATABASE_URL)"
  "$PYTHON" -m pytest tests -q --tb=short
}

run_frontend() {
  echo "==> Frontend Vitest"
  (cd apps/demo-ui && npm test)
}

case "$TARGET" in
  setup-db)
    ensure_test_db
    ;;
  unit)
    run_backend_unit
    if [ -d apps/demo-ui/node_modules ]; then
      run_frontend
    else
      echo "Skip frontend (npm install in apps/demo-ui first)"
    fi
    ;;
  backend) run_backend_full ;;
  frontend) run_frontend ;;
  all)
    run_backend_full
    run_frontend
    if command -v npx >/dev/null 2>&1; then
      echo "==> Frontend Playwright e2e (skips if UI down)"
      (cd apps/demo-ui && npm run test:e2e) || true
    fi
    ;;
  *)
    echo "Usage: $0 [unit|backend|frontend|all|setup-db]"
    exit 1
    ;;
esac
