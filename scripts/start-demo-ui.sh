#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/apps/demo-ui"
if [ -f "$ROOT/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi
if [ ! -d node_modules ]; then
  echo "Installing demo UI dependencies…"
  npm install
fi

REMOTE_UI=0
if [ "${REMOTE_ACCESS:-}" = "1" ] || [ "${API_HOST:-}" = "0.0.0.0" ]; then
  export REMOTE_ACCESS=1
  REMOTE_UI=1
fi

echo "Demo UI → http://localhost:5173 (API proxied to :8000)"
if [ "$REMOTE_UI" = "1" ]; then
  # shellcheck source=scripts/lib/network-urls.sh
  source "$ROOT/scripts/lib/network-urls.sh"
  network_print_access_urls
  echo "Open on your phone: http://$(network_primary_ip):5173"
  exec npm run dev -- --host 0.0.0.0
fi
exec npm run dev
