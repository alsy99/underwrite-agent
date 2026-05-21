#!/usr/bin/env bash
# Expose local API (port 8000) to the internet via ngrok for GitHub Pages / remote UI.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PORT="${API_PORT:-8000}"

if ! command -v ngrok >/dev/null 2>&1; then
  echo "ngrok is not installed."
  echo ""
  echo "  brew install ngrok/ngrok/ngrok"
  echo "  ngrok config add-authtoken <token>   # https://dashboard.ngrok.com/get-started/your-authtoken"
  echo ""
  exit 1
fi

if ! curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "API is not reachable on http://127.0.0.1:${PORT} — start it first:"
  echo "  ./scripts/start-api.sh"
  echo "  ./scripts/start-worker.sh"
  exit 1
fi

ARGS=(http "$PORT")
if [ -n "${NGROK_BASIC_AUTH:-}" ]; then
  ARGS+=(--basic-auth="$NGROK_BASIC_AUTH")
  echo "ngrok basic auth enabled (user:pass from NGROK_BASIC_AUTH)"
fi

echo ""
echo "==> Tunneling http://127.0.0.1:${PORT}"
echo "    After ngrok starts, copy the https://….ngrok-free.app URL"
echo ""
echo "    GitHub Pages build secrets:"
echo "      VITE_API_URL = https://<your-ngrok-host>   (no trailing slash)"
echo "      VITE_API_KEY = (same as API_KEY in .env)"
echo "      UI_PASSWORD  = (demo login password)"
echo ""
echo "    .env on this Mac:"
echo "      CORS_GITHUB_PAGES=true"
echo "      API_KEY=<strong random value>"
echo ""

exec ngrok "${ARGS[@]}"
