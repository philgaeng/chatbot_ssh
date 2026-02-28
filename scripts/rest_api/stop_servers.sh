#!/bin/bash

# Stop the processes started by scripts/rest_api/launch_servers.sh

set -e

BASE_DIR="/home/philg/projects/nepal_chatbot"
LOG_DIR="$BASE_DIR/logs"

echo "=== Stopping REST API stack processes ==="

stop_service() {
  local name="$1"
  local pid_file="$LOG_DIR/${name}.pid"

  if [ ! -f "$pid_file" ]; then
    echo "No PID file for $name ($pid_file); assuming not running."
    return
  fi

  local pid
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -z "$pid" ]; then
    echo "Empty PID in $pid_file for $name; removing file."
    rm -f "$pid_file"
    return
  fi

  if ps -p "$pid" > /dev/null 2>&1; then
    echo "Stopping $name (PID: $pid)..."
    kill "$pid" 2>/dev/null || true
    sleep 2
    if ps -p "$pid" > /dev/null 2>&1; then
      echo "Force stopping $name..."
      kill -9 "$pid" 2>/dev/null || true
    fi
  else
    echo "$name PID $pid not running; cleaning up PID file."
  fi

  rm -f "$pid_file"
  echo "✅ $name stopped (PID file removed)."
}

stop_service "orchestrator_rest_api"
stop_service "backend_rest_api"

echo
echo "Note: This script does not stop Postgres or nginx."
echo "If needed, manage those with systemctl (e.g. sudo systemctl stop postgresql nginx)."

