#!/usr/bin/env bash
# Print SHA-256 hex for VITE_UI_PASSWORD_HASH (local dev / GitHub secret setup).
set -euo pipefail
if [ -z "${1:-}" ]; then
  echo "Usage: ./scripts/hash-ui-password.sh 'your-password'"
  exit 1
fi
printf '%s' "$1" | shasum -a 256 | awk '{print $1}'
