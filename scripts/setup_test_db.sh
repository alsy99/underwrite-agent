#!/usr/bin/env bash
# Create dedicated local Postgres DB for pytest (integration + e2e).
# Does not touch the app DB (underwrite).
set -euo pipefail

DB_USER="${DB_USER:-underwrite}"
DB_PASS="${DB_PASS:-underwrite}"
DB_NAME="${TEST_DB_NAME:-underwrite_test}"
ADMIN_DB="${ADMIN_DB:-postgres}"

echo "==> Ensuring Postgres is up..."
brew services start postgresql@14 2>/dev/null || brew services start postgresql 2>/dev/null || true
sleep 1

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql not found. Install Postgres (e.g. brew install postgresql@14)."
  exit 1
fi

echo "==> Ensuring role '${DB_USER}' exists..."
psql "$ADMIN_DB" -v ON_ERROR_STOP=0 -c \
  "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}' CREATEDB;" 2>/dev/null || true

EXISTS=$(psql "$ADMIN_DB" -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" 2>/dev/null || echo "")
if [ "$EXISTS" != "1" ]; then
  echo "==> Creating database '${DB_NAME}'..."
  psql "$ADMIN_DB" -v ON_ERROR_STOP=1 -c \
    "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"
else
  echo "==> Database '${DB_NAME}' already exists"
fi

echo "==> Enabling extensions on '${DB_NAME}'..."
psql -d "${DB_NAME}" -v ON_ERROR_STOP=0 -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || {
  echo "WARNING: pgvector not installed (optional for basic tests)."
  echo "         brew install pgvector && re-run this script."
}

# Grant in case DB was created earlier as different owner
psql "$ADMIN_DB" -v ON_ERROR_STOP=0 -c \
  "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};" 2>/dev/null || true

URL="postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
echo ""
echo "==> Test DB ready."
echo "    TEST_DATABASE_URL=${URL}"
echo "    (pytest auto-uses this; app .env DATABASE_URL can stay on 'underwrite')"
echo ""
echo "Run:  ./scripts/setup_test_db.sh && ./scripts/run_tests.sh backend"
