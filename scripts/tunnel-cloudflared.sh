#!/usr/bin/env bash
# Expose the demo UI to the internet via Cloudflare quick tunnel (no account required).
set -euo pipefail

UI_PORT="${UI_PORT:-5173}"
TARGET="http://127.0.0.1:${UI_PORT}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared is not installed."
  echo ""
  echo "Install on macOS:"
  echo "  brew install cloudflared"
  echo ""
  echo "Then run this script again while the demo UI is running:"
  echo "  REMOTE_ACCESS=1 ./scripts/start-demo-ui.sh"
  echo "  ./scripts/tunnel-cloudflared.sh"
  exit 1
fi

echo "Tunneling ${TARGET} → public trycloudflare.com URL"
echo "Keep this terminal open. Share the https://*.trycloudflare.com link for remote access."
echo ""
exec cloudflared tunnel --url "$TARGET"
