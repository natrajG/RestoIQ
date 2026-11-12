#!/usr/bin/env bash
# Stops the tunnel (public link) and, optionally, the application containers.
# Usage: ./stop_app.sh          stop tunnel only (app keeps running on this PC)
#        ./stop_app.sh --all    stop tunnel and all containers (data is kept)
cd "$(dirname "$0")"
PIDFILE=".run/tunnel.pid"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  kill "$(cat "$PIDFILE")" && echo "Tunnel stopped. Public link is now closed."
else
  echo "No tunnel from start_app.sh is running."
fi
rm -f "$PIDFILE"

if [ "${1:-}" = "--all" ]; then
  echo "Stopping containers (data is kept)..."
  docker compose stop
fi
