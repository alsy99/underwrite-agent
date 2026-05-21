#!/usr/bin/env bash
# Expose local API (port 8000) for GitHub Pages / remote UI.
# Prefers ngrok if authtoken is configured; otherwise uses Cloudflare quick tunnel.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PORT="${API_PORT:-8000}"

if ! curl -sf "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
  echo "API is not running on http://127.0.0.1:${PORT}"
  echo "  ./scripts/start-api.sh"
  echo "  ./scripts/start-worker.sh"
  exit 1
fi

if command -v ngrok >/dev/null 2>&1 && ngrok config check >/dev/null 2>&1; then
  echo "Using ngrok → port ${PORT}"
  exec ./scripts/tunnel-ngrok.sh
fi

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "Install a tunnel tool:"
  echo "  brew install ngrok/ngrok/ngrok && ngrok config add-authtoken <token>"
  echo "  brew install cloudflared"
  exit 1
fi

echo "ngrok not configured — using Cloudflare quick tunnel"
echo "Keep this terminal open. Copy the https://….trycloudflare.com URL into GitHub secret VITE_API_URL"
echo ""
exec cloudflared tunnel --url "http://127.0.0.1:${PORT}"
