#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.

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
echo "Using: $($PYTHON --version)"
exec "$PYTHON" -m apps.worker.main
