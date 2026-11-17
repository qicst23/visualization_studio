#!/usr/bin/env bash
set -euo pipefail
for p in 8004 8005 8006 8007 8008 8009 8010; do
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 1 "http://127.0.0.1:${p}/api/shutdown" >/dev/null 2>&1 && echo "Stopped studio server on port ${p}" || true
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${p}/api/shutdown', timeout=0.8)" >/dev/null 2>&1 && echo "Stopped studio server on port ${p}" || true
  fi
done
