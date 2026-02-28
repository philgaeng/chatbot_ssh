#!/bin/bash

# Stop the processes started by scripts/rest_api/launch_servers_celery.sh
# Stops: orchestrator, backend, Celery workers
# Postgres is NOT stopped. Redis is stopped only if STOP_REDIS=1 (project Redis via logs/redis.pid only).

set -e

BASE_DIR="/home/philg/projects/nepal_chatbot"
LOG_DIR="$BASE_DIR/logs"

# Optional: STOP_REDIS=1 to also stop project-managed Redis (process in logs/redis.pid)
STOP_REDIS="${STOP_REDIS:-0}"

echo "=== Stopping REST API + Celery stack ==="

stop_service() {
  local name="$1"
  local pid_file="$LOG_DIR/${name}.pid"

  if [ ! -f "$pid_file" ]; then
    echo "No PID file for $name ($pid_file); assuming not running."
    return
  fi

  local pid
  pid=$(cat "$pid_file" 2>/dev/null || true)
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
  echo "✅ $name stopped."
}

stop_celery_worker() {
  local queue_name="$1"
  local pid_file="$LOG_DIR/celery_${queue_name}.pid"

  if [ ! -f "$pid_file" ]; then
    echo "No PID file for celery_$queue_name ($pid_file)."
    return
  fi

  local pid
  pid=$(cat "$pid_file" 2>/dev/null || true)
  if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
    echo "Stopping celery_$queue_name (PID: $pid)..."
    kill "$pid" 2>/dev/null || true
    sleep 2
    if ps -p "$pid" > /dev/null 2>&1; then
      echo "Force stopping celery_$queue_name..."
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi

  rm -f "$pid_file"
  echo "✅ celery_$queue_name stopped."
}

# 1) Stop orchestrator and backend
stop_service "orchestrator_rest_api"
stop_service "backend_rest_api"

# 2) Stop Celery workers
echo
echo "Stopping Celery workers..."
stop_celery_worker "default"
stop_celery_worker "llm_queue"

# 3) Fallback: pkill if PID files missing
if pgrep -f "celery.*worker" > /dev/null 2>&1; then
  echo "Found remaining Celery worker processes; stopping..."
  pkill -f "celery.*worker" 2>/dev/null || true
  sleep 2
  pkill -9 -f "celery.*worker" 2>/dev/null || true
  rm -f "$LOG_DIR/celery_default.pid" "$LOG_DIR/celery_llm_queue.pid"
  echo "✅ Celery workers stopped."
fi

# 4) Optional: stop project Redis (only the process in logs/redis.pid)
if [ "$STOP_REDIS" = "1" ]; then
  REDIS_PID_FILE="$LOG_DIR/redis.pid"
  echo
  echo "Stopping project Redis..."
  if [ -f "$REDIS_PID_FILE" ]; then
    redis_pid=$(cat "$REDIS_PID_FILE" 2>/dev/null || true)
    if [ -n "$redis_pid" ] && ps -p "$redis_pid" > /dev/null 2>&1; then
      echo "Stopping Redis (PID: $redis_pid)..."
      kill "$redis_pid" 2>/dev/null || true
      sleep 2
      if ps -p "$redis_pid" > /dev/null 2>&1; then
        kill -9 "$redis_pid" 2>/dev/null || true
      fi
      echo "✅ Redis stopped."
    else
      echo "Redis PID $redis_pid not running; cleaning up PID file."
    fi
    rm -f "$REDIS_PID_FILE"
  else
    echo "No project Redis PID file ($REDIS_PID_FILE); nothing to stop."
  fi
fi

echo
echo "Orchestrator, backend, and Celery workers stopped."
if [ "$STOP_REDIS" != "1" ]; then
  echo "Redis not stopped (set STOP_REDIS=1 to stop project Redis)."
fi
echo "Postgres is NOT stopped."
