#!/usr/bin/env bash
# Start backend + tunnel for internet access (GitHub Pages UI or local demo UI).
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

mkdir -p "$ROOT/.run"
API_LOG="$ROOT/.run/api.log"
WORKER_LOG="$ROOT/.run/worker.log"
TUNNEL_LOG="$ROOT/.run/tunnel.log"
UI_LOG="$ROOT/.run/demo-ui.log"
PORT="${API_PORT:-8000}"

stop_stale() {
  pkill -f "cloudflared tunnel --url http://127.0.0.1:${PORT}" 2>/dev/null || true
  # Keep one worker max when restarting
  if pgrep -f "apps.worker.main" >/dev/null 2>&1 && [ "${FORCE_RESTART:-}" = "1" ]; then
    pkill -f "apps.worker.main" 2>/dev/null || true
    sleep 1
  fi
}

wait_for_api() {
  local i
  for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "API did not become healthy — see $API_LOG"
  tail -20 "$API_LOG" 2>/dev/null || true
  exit 1
}

read_tunnel_url() {
  local url=""
  local i
  for i in $(seq 1 45); do
    url=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)
    if [ -n "$url" ]; then
      echo "$url"
      return 0
    fi
    sleep 1
  done
  return 1
}

echo "==> Underwrite Agent — internet session"
echo ""

# Postgres / Redis
if command -v brew >/dev/null 2>&1; then
  brew services start postgresql@14 2>/dev/null || brew services start postgresql 2>/dev/null || true
  brew services start redis 2>/dev/null || true
fi

stop_stale

# API
if curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "✓ API already running on :${PORT}"
else
  echo "→ Starting API (log: $API_LOG)"
  ./scripts/start-api.sh >"$API_LOG" 2>&1 &
  echo $! >"$ROOT/.run/api.pid"
  wait_for_api
  echo "✓ API ready"
fi

# Worker
if pgrep -f "apps.worker.main" >/dev/null 2>&1; then
  echo "✓ Worker already running"
else
  echo "→ Starting worker (log: $WORKER_LOG)"
  ./scripts/start-worker.sh >"$WORKER_LOG" 2>&1 &
  echo $! >"$ROOT/.run/worker.pid"
  sleep 2
  echo "✓ Worker started"
fi

# Tunnel
if ! command -v cloudflared >/dev/null 2>&1; then
  if command -v ngrok >/dev/null 2>&1 && ngrok config check >/dev/null 2>&1; then
    echo "→ Starting ngrok (foreground in this terminal)…"
    echo "  Copy the https URL → GitHub secret VITE_API_URL → re-run Pages deploy"
    exec ./scripts/tunnel-ngrok.sh
  fi
  echo "Install cloudflared: brew install cloudflared"
  exit 1
fi

echo "→ Starting Cloudflare tunnel (log: $TUNNEL_LOG)"
: >"$TUNNEL_LOG"
cloudflared tunnel --url "http://127.0.0.1:${PORT}" >>"$TUNNEL_LOG" 2>&1 &
echo $! >"$ROOT/.run/tunnel.pid"

TUNNEL_URL=""
if TUNNEL_URL=$(read_tunnel_url); then
  echo "✓ Tunnel: $TUNNEL_URL"
else
  echo "⚠ Tunnel URL not ready yet — check: tail -f $TUNNEL_LOG"
fi

# Optional local demo UI
if [ "${START_LOCAL_UI:-}" = "1" ]; then
  echo "→ Starting local demo UI (log: $UI_LOG)"
  ./scripts/start-demo-ui.sh >"$UI_LOG" 2>&1 &
  echo $! >"$ROOT/.run/demo-ui.pid"
  # shellcheck source=scripts/lib/network-urls.sh
  source "$ROOT/scripts/lib/network-urls.sh"
  network_print_access_urls
fi

# Update GitHub secret if gh is available and URL known
if [ -n "$TUNNEL_URL" ] && command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  if [ "${UPDATE_GITHUB_SECRET:-1}" = "1" ]; then
    echo "→ Updating GitHub secret VITE_API_URL"
    gh secret set VITE_API_URL --body "$TUNNEL_URL" 2>/dev/null || true
    gh secret set VITE_API_KEY --body "${API_KEY:-dev-api-key-change-me}" 2>/dev/null || true
    if [ -n "${UI_PASSWORD:-}" ]; then
      gh secret set UI_PASSWORD --body "$UI_PASSWORD" 2>/dev/null || true
    fi
    echo "→ Triggering GitHub Pages deploy…"
    gh workflow run deploy-demo-ui.yml 2>/dev/null || true
  fi
fi

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "alsy99/underwrite-agent")
REPO_NAME="${REPO##*/}"

echo ""
echo "════════════════════════════════════════════════════════"
echo "  GitHub Pages UI:  https://${REPO%%/*}.github.io/${REPO_NAME}/"
if [ -n "${UI_PASSWORD:-}" ]; then
  echo "  UI password:      (UI_PASSWORD in .env)"
else
  echo "  UI password:      underwrite-demo  (or set UI_PASSWORD in .env)"
fi
echo "  API tunnel:       ${TUNNEL_URL:-see $TUNNEL_LOG}"
echo "  API key (.env):   ${API_KEY:-dev-api-key-change-me}"
echo ""
echo "  Logs:  tail -f $API_LOG $WORKER_LOG $TUNNEL_LOG"
echo "  Stop:  ./scripts/stop-internet-session.sh"
echo "════════════════════════════════════════════════════════"
