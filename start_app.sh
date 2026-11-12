#!/usr/bin/env bash
# Starts RestoIQ and an HTTPS tunnel, then prints the public link for phones.
set -u
cd "$(dirname "$0")"
RUN_DIR=".run"
LOG="$RUN_DIR/tunnel.log"
PIDFILE="$RUN_DIR/tunnel.pid"
CF="$(command -v cloudflared || echo "$HOME/.local/bin/cloudflared")"
mkdir -p "$RUN_DIR"

[ -x "$CF" ] || { echo "cloudflared not found"; exit 1; }

if ! docker info >/dev/null 2>&1; then
  echo "Docker is not running. Starting it..."
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start docker 2>/dev/null || systemctl --user start docker-desktop 2>/dev/null
  fi
  echo -n "Waiting for Docker"
  for _ in $(seq 1 45); do
    docker info >/dev/null 2>&1 && break
    echo -n "."; sleep 2
  done
  echo
  docker info >/dev/null 2>&1 || { echo "Could not start Docker. Start it manually (Docker Desktop or: sudo systemctl start docker) and run again."; exit 1; }
fi

echo "Starting application containers..."
docker compose up -d || { echo "docker compose failed"; exit 1; }

echo -n "Waiting for the app"
for _ in $(seq 1 60); do
  curl -fs http://localhost:8180/api/v1/health >/dev/null 2>&1 && break
  echo -n "."; sleep 2
done
echo
curl -fs http://localhost:8180/api/v1/health >/dev/null 2>&1 || { echo "App did not become healthy. Check: docker compose logs api"; exit 1; }

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  kill "$(cat "$PIDFILE")" 2>/dev/null; sleep 1
fi

: > "$LOG"
nohup "$CF" tunnel --no-autoupdate --url http://localhost:8180 >"$LOG" 2>&1 &
echo $! > "$PIDFILE"

echo -n "Starting tunnel"
URL=""
for _ in $(seq 1 40); do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1)
  [ -n "$URL" ] && break
  echo -n "."; sleep 1
done
echo

if [ -z "$URL" ]; then
  echo "Tunnel did not start. See $LOG"; exit 1
fi

echo
echo "=============================================="
echo " PC (this computer):  http://localhost:8180"
echo " PHONES (open this):  $URL"
echo "=============================================="
echo " The link is public while the tunnel runs and changes each start."
echo " Stop everything with: ./stop_app.sh"
