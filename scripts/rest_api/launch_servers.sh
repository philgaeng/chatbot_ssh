#!/bin/bash

# Lightweight launcher for the REST orchestrator stack (WSL/local)
# - Ensures local Postgres exists and is reachable
# - Starts orchestrator FastAPI
# - Starts backend/file server
# - Assumes nginx is configured with webchat_rest.conf to serve the two web UIs

set -e

BASE_DIR="/home/philg/projects/nepal_chatbot"
LOG_DIR="$BASE_DIR/logs"

mkdir -p "$LOG_DIR"

echo "=== REST API stack launcher ==="
echo "Base directory: $BASE_DIR"

LAUNCH_TIME="$(date +"%Y-%m-%d %H:%M:%S")"

########################################
# 1) Ensure local Postgres is ready
########################################

echo
echo "[1/3] Ensuring local PostgreSQL database is set up and reachable..."

if [ -x "$BASE_DIR/scripts/database/setup_local_db.sh" ]; then
  "$BASE_DIR/scripts/database/setup_local_db.sh"
else
  echo "Warning: scripts/database/setup_local_db.sh not found or not executable."
  echo "Please ensure your local Postgres is running and configured."
fi

########################################
# 2) Start orchestrator (FastAPI)
########################################

ORCH_LOG="$LOG_DIR/orchestrator_rest_api.log"
ORCH_PID_FILE="$LOG_DIR/orchestrator_rest_api.pid"
ORCH_PORT=8000

echo
echo "[2/3] Starting orchestrator FastAPI on port $ORCH_PORT..."

if [ -f "$ORCH_PID_FILE" ]; then
  OLD_PID="$(cat "$ORCH_PID_FILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" > /dev/null 2>&1; then
    echo "Stopping existing orchestrator process (PID: $OLD_PID)..."
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
  fi
fi

PYTHONPATH="$BASE_DIR" nohup python3 -m uvicorn backend.orchestrator.main:app \
  --host 0.0.0.0 \
  --port "$ORCH_PORT" \
  > "$ORCH_LOG" 2>&1 &

echo $! > "$ORCH_PID_FILE"
sleep 2

if ps -p "$(cat "$ORCH_PID_FILE")" > /dev/null 2>&1; then
  echo "✅ Orchestrator started (PID: $(cat "$ORCH_PID_FILE")), log: $ORCH_LOG"
else
  echo "❌ Failed to start orchestrator. Check log: $ORCH_LOG"
fi

########################################
# 3) Start backend/file server (Flask)
########################################

BACKEND_LOG="$LOG_DIR/backend_rest_api.log"
BACKEND_PID_FILE="$LOG_DIR/backend_rest_api.pid"
BACKEND_PORT=5001

echo
echo "[3/3] Starting backend/file server on port $BACKEND_PORT..."

if [ -f "$BACKEND_PID_FILE" ]; then
  OLD_PID="$(cat "$BACKEND_PID_FILE" 2>/dev/null || true)"
  if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" > /dev/null 2>&1; then
    echo "Stopping existing backend process (PID: $OLD_PID)..."
    kill "$OLD_PID" 2>/dev/null || true
    sleep 1
  fi
fi

PYTHONPATH="$BASE_DIR" nohup python3 "$BASE_DIR/backend/api/app.py" \
  > "$BACKEND_LOG" 2>&1 &

echo $! > "$BACKEND_PID_FILE"
sleep 2

if ps -p "$(cat "$BACKEND_PID_FILE")" > /dev/null 2>&1; then
  echo "✅ Backend started (PID: $(cat "$BACKEND_PID_FILE")), log: $BACKEND_LOG"
else
  echo "❌ Failed to start backend. Check log: $BACKEND_LOG"
fi

########################################
# 4) Summary: URLs and launch time
########################################

echo
echo "=== REST API stack launched at: $LAUNCH_TIME ==="
echo
echo "Assuming nginx is running with webchat_rest.conf on port 8083, you can open:"
echo "  • Bridge (Socket.IO webchat):  http://localhost:8083/"
echo "  • REST webchat client:         http://localhost:8083/rest-webchat/"
echo
echo "APIs:"
echo "  • Orchestrator REST API:       http://localhost:${ORCH_PORT}/message"
echo "  • Orchestrator health:         http://localhost:${ORCH_PORT}/health"
echo "  • Backend/file server:         http://localhost:${BACKEND_PORT}/"
echo
echo "To stop these processes, run: scripts/rest_api/stop_servers.sh"

