#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

kill_pid_file() {
  local f="$1"
  if [ -f "$f" ]; then
    kill "$(cat "$f")" 2>/dev/null || true
    rm -f "$f"
  fi
}

kill_pid_file "$ROOT/.run/api.pid"
kill_pid_file "$ROOT/.run/worker.pid"
kill_pid_file "$ROOT/.run/tunnel.pid"
kill_pid_file "$ROOT/.run/demo-ui.pid"

pkill -f "cloudflared tunnel --url" 2>/dev/null || true
pkill -f "apps.worker.main" 2>/dev/null || true

echo "Stopped internet session processes (API may still run if started separately)."
