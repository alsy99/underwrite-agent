#!/usr/bin/env bash
# Start API + demo UI bound for LAN/remote access (Postgres, Redis, worker still required).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
export REMOTE_ACCESS=1
export BIND_HOST="${API_HOST:-0.0.0.0}"
export API_HOST="${API_HOST:-0.0.0.0}"
export CORS_ALLOW_ALL="${CORS_ALLOW_ALL:-true}"

# shellcheck source=scripts/lib/network-urls.sh
source "$ROOT/scripts/lib/network-urls.sh"

echo "Underwrite Agent — remote / LAN mode"
echo "  BIND_HOST=0.0.0.0  CORS_ALLOW_ALL=true"
echo ""
echo "Start these in separate terminals (or use START_ALL=1 below):"
echo "  1. brew services start postgresql@14 redis   # if not already running"
echo "  2. REMOTE_ACCESS=1 ./scripts/start-api.sh"
echo "  3. ./scripts/start-worker.sh"
echo "  4. REMOTE_ACCESS=1 ./scripts/start-demo-ui.sh"
echo ""
echo "For internet access without port forwarding:"
echo "  ./scripts/tunnel-cloudflared.sh   # after demo UI is up on :5173"
echo ""
network_print_access_urls

if [ "${START_ALL:-}" != "1" ]; then
  exit 0
fi

mkdir -p "$ROOT/.run"
API_LOG="$ROOT/.run/remote-api.log"
UI_LOG="$ROOT/.run/remote-ui.log"

cleanup() {
  echo ""
  echo "Stopping remote services…"
  [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
  [ -n "${UI_PID:-}" ] && kill "$UI_PID" 2>/dev/null || true
  [ -n "${WORKER_PID:-}" ] && kill "$WORKER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Starting API (background, log: $API_LOG)"
REMOTE_ACCESS=1 BIND_HOST=0.0.0.0 CORS_ALLOW_ALL=true ./scripts/start-api.sh >"$API_LOG" 2>&1 &
API_PID=$!

echo "==> Starting worker (background)"
./scripts/start-worker.sh &
WORKER_PID=$!

sleep 2
echo "==> Starting demo UI (background, log: $UI_LOG)"
REMOTE_ACCESS=1 ./scripts/start-demo-ui.sh >"$UI_LOG" 2>&1 &
UI_PID=$!

sleep 2
network_print_access_urls
echo "Logs: tail -f $API_LOG $UI_LOG"
echo "Press Ctrl+C to stop API, worker, and UI."

wait
