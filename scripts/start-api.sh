#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH=.
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PYTHON="${PYTHON:-}"
if [ -z "$PYTHON" ]; then
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      ver=$("$candidate" -c "import sys; print(sys.version_info[:2] >= (3, 11))" 2>/dev/null || echo False)
      if [ "$ver" = "True" ]; then
        PYTHON=$candidate
        break
      fi
    fi
  done
fi
PYTHON="${PYTHON:-python3}"
HOST="${BIND_HOST:-${API_HOST:-127.0.0.1}}"
PORT="${API_PORT:-8000}"
if [ "${REMOTE_ACCESS:-}" = "1" ] && [ "$HOST" = "127.0.0.1" ]; then
  HOST="0.0.0.0"
fi

echo "Using: $($PYTHON --version) at $(command -v $PYTHON)"
echo "API listening on http://${HOST}:${PORT}"
if [ "$HOST" = "0.0.0.0" ] || [ "${REMOTE_ACCESS:-}" = "1" ]; then
  # shellcheck source=scripts/lib/network-urls.sh
  source "$ROOT/scripts/lib/network-urls.sh"
  network_print_access_urls 5173 "$PORT"
fi
exec "$PYTHON" -m uvicorn apps.api.main:app --reload --host "$HOST" --port "$PORT"
