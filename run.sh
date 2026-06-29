#!/usr/bin/env bash
# Start the Field Day Logger. All operators point their browsers at this host.
set -e
cd "$(dirname "$0")"

PORT="${PORT:-8073}"

# Use a venv if present, otherwise system python3.
PY=python3
if [ -d .venv ]; then PY=.venv/bin/python; fi

# Show the LAN address operators should connect to.
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo "============================================================"
echo "  Field Day Logger starting on port ${PORT}"
[ -n "$IP" ] && echo "  Operators connect to:  http://${IP}:${PORT}/"
echo "  This machine:          http://localhost:${PORT}/"
echo "============================================================"

PORT="$PORT" exec "$PY" app.py
