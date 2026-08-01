#!/usr/bin/env bash
# Bootstrap local Postgres for underwrite-agent (Homebrew postgresql@14)
set -euo pipefail

DB_USER="${DB_USER:-underwrite}"
DB_PASS="${DB_PASS:-underwrite}"
DB_NAME="${DB_NAME:-underwrite}"

echo "==> Starting Postgres and Redis (Homebrew)..."
brew services start postgresql@14 2>/dev/null || brew services start postgresql 2>/dev/null || true
brew services start redis 2>/dev/null || true
sleep 2

echo "==> Creating role and database..."
psql postgres -v ON_ERROR_STOP=0 -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}' CREATEDB;" 2>/dev/null || true
psql postgres -v ON_ERROR_STOP=0 -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};" 2>/dev/null || true
psql -d "${DB_NAME}" -v ON_ERROR_STOP=0 -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || {
  echo "WARNING: pgvector extension not available. Install with: brew install pgvector"
  echo "         Then link to postgresql@14 and re-run this script."
}

echo "==> Done. DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"

# Also ensure isolated pytest DB exists
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -x "${SCRIPT_DIR}/setup_test_db.sh" ]; then
  echo ""
  echo "==> Also provisioning test database..."
  DB_USER="$DB_USER" DB_PASS="$DB_PASS" "${SCRIPT_DIR}/setup_test_db.sh"
fi
