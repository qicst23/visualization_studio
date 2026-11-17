#!/usr/bin/env bash
set -euo pipefail

# Always anchor inside this dedicated visualization_studio folder
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PY_BIN=""
# 1. Prefer folder-local .venv if present
if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  PY_BIN="$SCRIPT_DIR/.venv/bin/python"
# 2. Prefer python3 / python with numpy available
elif command -v python3 >/dev/null 2>&1 && python3 -c "import numpy" >/dev/null 2>&1; then
  PY_BIN="python3"
elif command -v python >/dev/null 2>&1 && python -c "import numpy" >/dev/null 2>&1; then
  PY_BIN="python"
# 3. Any bare python3 / python (stdlib HTTP server mode)
elif command -v python3 >/dev/null 2>&1; then
  PY_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PY_BIN="python"
fi

if [[ -n "$PY_BIN" ]]; then
  # Pass --open-browser unless caller explicitly passed --no-browser or --check
  EXTRA_FLAG="--open-browser"
  for arg in "$@"; do
    if [[ "$arg" == "--no-browser" || "$arg" == "--check" ]]; then
      EXTRA_FLAG=""
    fi
  done
  exec "$PY_BIN" "$SCRIPT_DIR/run_visualization_studio.py" $EXTRA_FLAG "$@"
else
  echo "[Notice] Python 3 not found; opening standalone index.html in default browser..."
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$SCRIPT_DIR/index.html"
  else
    echo "Open file://$SCRIPT_DIR/index.html in Chrome, Edge, or Firefox."
  fi
fi
