#!/usr/bin/env bash
# Print LAN-reachable URLs for remote demo access (macOS + Linux).

network_primary_ip() {
  if command -v ipconfig >/dev/null 2>&1; then
    for iface in en0 en1 en2 bridge0; do
      local ip
      ip=$(ipconfig getifaddr "$iface" 2>/dev/null || true)
      if [ -n "$ip" ]; then
        echo "$ip"
        return 0
      fi
    done
  fi
  if command -v hostname >/dev/null 2>&1; then
    hostname -I 2>/dev/null | awk '{print $1}' && return 0
  fi
  return 1
}

network_print_access_urls() {
  local ui_port="${1:-5173}"
  local api_port="${2:-8000}"
  local ip
  ip=$(network_primary_ip || true)

  echo ""
  echo "==> Remote access (same Wi‑Fi / LAN)"
  if [ -n "$ip" ]; then
    echo "    Demo UI:  http://${ip}:${ui_port}"
    echo "    API:      http://${ip}:${api_port}/health"
  else
    echo "    Could not detect LAN IP — use: ifconfig | grep 'inet '"
    echo "    Demo UI:  http://<your-lan-ip>:${ui_port}"
    echo "    API:      http://<your-lan-ip>:${api_port}"
  fi
  echo ""
  echo "==> Internet (anywhere) — pick one:"
  echo "    • Cloudflare Tunnel:  ./scripts/tunnel-cloudflared.sh"
  echo "    • Router port-forward: forward TCP ${ui_port} → this Mac"
  echo ""
  echo "    Security: change API_KEY in .env; do not expose without a tunnel/password on public networks."
  echo ""
}
