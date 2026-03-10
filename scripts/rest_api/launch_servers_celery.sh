#!/bin/bash

# REST orchestrator stack + Redis + Celery workers (for LLM grievance classification)
# Based on scripts/rest_api/launch_servers.sh
# Stack: Postgres, Redis, both webchats (via nginx), backend, orchestrator,
#        Celery default (concurrency 2), Celery llm_queue (concurrency 6)
# Does NOT include Rasa or Rasa actions (REST stack replaces them)
#
# Recommended: conda activate chatbot-rest (or set VENV_DIR) before running.
#
# Option B (default): single project Redis with password (recommended for deployment).
#   START_REDIS=1 (default): start project Redis from scripts/local/redis.conf. Requires
#   REDIS_PASSWORD in env.local matching redis.conf requirepass. If system Redis is on
#   port 6379, the script stops it so only project Redis runs. Logs: logs/redis.log.
#   START_REDIS=0: only check existing Redis; do not start or stop anything.
#
# Redis auth: Script probes Redis (no-auth then env.local REDIS_PASSWORD) and sets
# CELERY_BROKER_URL/CELERY_RESULT_BACKEND to match.
# - With START_REDIS=1 you must set REDIS_PASSWORD in env.local (copy from redis.conf requirepass).
# - With START_REDIS=0: if Redis has no password leave REDIS_PASSWORD unset; if it has requirepass set it.

set -e

BASE_DIR="/home/philg/projects/nepal_chatbot"
LOG_DIR="$BASE_DIR/logs"
# Prefer VENV_DIR; then chatbot-rest (conda), then rasa-env, then .venv
VENV_DIR="${VENV_DIR:-}"
if [ -z "$VENV_DIR" ] && [ -n "$CONDA_PREFIX" ] && [[ "$CONDA_PREFIX" == *"chatbot-rest"* ]]; then
  VENV_DIR="$CONDA_PREFIX"
fi
if [ -z "$VENV_DIR" ] || [ ! -d "$VENV_DIR" ]; then
  VENV_DIR="${VENV_DIR:-$BASE_DIR/rasa-env}"
fi
if [ ! -d "$VENV_DIR" ]; then
  VENV_DIR="$BASE_DIR/.venv"
fi

mkdir -p "$LOG_DIR"

# Load env.local entries needed for orchestrator and Celery (so orchestrator sees ENABLE_CELERY_CLASSIFICATION)
if [ -f "$BASE_DIR/env.local" ]; then
  if [ -z "$REDIS_PASSWORD" ]; then
    REDIS_PASSWORD="$(grep -E '^REDIS_PASSWORD=' "$BASE_DIR/env.local" | sed 's/^REDIS_PASSWORD=//' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    export REDIS_PASSWORD
  fi
  if [ -z "$ENABLE_CELERY_CLASSIFICATION" ]; then
    ENABLE_CELERY_CLASSIFICATION="$(grep -E '^ENABLE_CELERY_CLASSIFICATION=' "$BASE_DIR/env.local" | sed 's/^ENABLE_CELERY_CLASSIFICATION=//')"
    export ENABLE_CELERY_CLASSIFICATION
  fi
fi

# Treat empty or whitespace-only REDIS_PASSWORD as unset
REDIS_PASSWORD_RAW="$(echo "${REDIS_PASSWORD:-}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
export REDIS_HOST="${REDIS_HOST:-localhost}"
export REDIS_PORT="${REDIS_PORT:-6379}"
export REDIS_DB="${REDIS_DB:-0}"

# NOTE: Celery broker/result URLs are set AFTER Redis is running (see probe below).
# We avoid guessing from env.local alone - that causes "AUTH without password configured"
# when env.local has REDIS_PASSWORD but the running Redis has no requirepass.
echo "=== REST API stack + Celery launcher ==="
echo "Base directory: $BASE_DIR"
LAUNCH_TIME="$(date +"%Y-%m-%d %H:%M:%S")"

########################################
# 1) Ensure local Postgres
########################################
echo
echo "[1/6] Ensuring local PostgreSQL database..."

if [ -x "$BASE_DIR/scripts/database/setup_local_db.sh" ]; then
  "$BASE_DIR/scripts/database/setup_local_db.sh"
else
  echo "Warning: scripts/database/setup_local_db.sh not found or not executable."
fi

########################################
# 2) Ensure Redis is running (Option B: project Redis with password when START_REDIS=1)
########################################
START_REDIS="${START_REDIS:-1}"
REDIS_PID_FILE="$LOG_DIR/redis.pid"
REDIS_CONF="$BASE_DIR/scripts/local/redis.conf"

echo
echo "[2/6] Ensuring Redis is running..."

# Probes: no-auth first, then with env REDIS_PASSWORD (single source of truth)
_probe_ping_no_auth() {
  redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null | grep -q PONG
}
_probe_ping_with_auth() {
  [ -n "$REDIS_PASSWORD_RAW" ] && redis-cli -a "$REDIS_PASSWORD_RAW" -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>/dev/null | grep -q PONG
}
check_redis_any() {
  _probe_ping_no_auth || _probe_ping_with_auth
}

# Option B: when starting project Redis, we need REDIS_PASSWORD in env.local (matches redis.conf requirepass)
if [ "$START_REDIS" = "1" ] && [ -f "$REDIS_CONF" ]; then
  if [ -z "$REDIS_PASSWORD_RAW" ]; then
    echo "❌ START_REDIS=1 (project Redis) requires REDIS_PASSWORD in env.local to match scripts/local/redis.conf (requirepass)."
    echo "   See env.local.example. Add to env.local: REDIS_PASSWORD=<value from redis.conf requirepass>"
    exit 1
  fi
fi

# Stop project Redis (process we started previously; pid file from redis.conf or our convention)
_stop_project_redis() {
  if [ -f "$REDIS_PID_FILE" ]; then
    local pid
    pid=$(cat "$REDIS_PID_FILE" 2>/dev/null || true)
    if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
      echo "Stopping existing project Redis (PID: $pid)..."
      kill "$pid" 2>/dev/null || true
      sleep 2
      kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$REDIS_PID_FILE"
  fi
}

# When START_REDIS=1: use only project Redis. If system Redis is on 6379, stop it so project Redis can bind.
if [ "$START_REDIS" = "1" ] && _probe_ping_no_auth; then
  echo "Redis on $REDIS_HOST:$REDIS_PORT responds without password (likely system Redis)."
  echo "Stopping it so project Redis (with password) can use port $REDIS_PORT..."
  sudo systemctl stop redis-server 2>/dev/null || true
  _stop_project_redis
  sleep 2
  if _probe_ping_no_auth; then
    echo "❌ Redis still responding without password. Stop system Redis and re-run, e.g.:"
    echo "   sudo systemctl stop redis-server"
    echo "   START_REDIS=1 $0"
    exit 1
  fi
fi

if ! check_redis_any; then
  echo "Redis not responding at $REDIS_HOST:$REDIS_PORT."
  if [ "$START_REDIS" = "1" ] && [ -f "$REDIS_CONF" ]; then
    _stop_project_redis
    echo "Starting project Redis (logs: $LOG_DIR/redis.log)..."
    redis-server "$REDIS_CONF" &
    sleep 3
    if check_redis_any; then
      echo "✅ Project Redis started (PID file: $REDIS_PID_FILE)"
    fi
  fi
  if ! check_redis_any; then
    echo "❌ Redis is not running. Start manually: redis-server \"$REDIS_CONF\""
    echo "   With START_REDIS=1, ensure REDIS_PASSWORD in env.local matches redis.conf. Celery will fail without Redis. Continuing..."
  fi
else
  echo "✅ Redis is running"
fi

########################################
# Probe Redis: set Celery URLs from actual Redis (no-auth vs password)
# _probe_ping_* already defined above.
########################################
if _probe_ping_no_auth; then
  # Redis has NO password - do not send AUTH (causes "AUTH without password configured")
  REDIS_PASSWORD=""
  unset REDIS_PASSWORD
  export CELERY_BROKER_URL="redis://${REDIS_HOST}:${REDIS_PORT}/1"
  export CELERY_RESULT_BACKEND="redis://${REDIS_HOST}:${REDIS_PORT}/2"
  echo "Redis auth: none (no password)"
elif _probe_ping_with_auth; then
  # Redis requires password - use REDIS_PASSWORD from env.local
  REDIS_PASSWORD="$REDIS_PASSWORD_RAW"
  export REDIS_PASSWORD
  export CELERY_BROKER_URL="redis://:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}/1"
  export CELERY_RESULT_BACKEND="redis://:${REDIS_PASSWORD}@${REDIS_HOST}:${REDIS_PORT}/2"
  echo "Redis auth: password (from env.local)"
else
  echo "❌ Redis is running but neither no-auth nor env.local password works."
  echo "   Fix: ensure REDIS_PASSWORD in env.local matches Redis requirepass, or use Redis without requirepass."
  exit 1
fi

# Detect the *actual* Redis configuration we are talking to (systemd Redis vs project Redis)
_redis_cli() {
  if [ -n "$REDIS_PASSWORD" ]; then
    redis-cli -a "$REDIS_PASSWORD" -h "$REDIS_HOST" -p "$REDIS_PORT" "$@"
  else
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" "$@"
  fi
}
REDIS_INFO="$(_redis_cli INFO server 2>/dev/null || true)"
REDIS_PID="$(printf "%s\n" "$REDIS_INFO" | awk -F: '/^process_id:/{print $2}' | tr -d '\r')"
REDIS_CONFIG_FILE="$(printf "%s\n" "$REDIS_INFO" | awk -F: '/^config_file:/{print $2}' | tr -d '\r')"
REDIS_LOGFILE="$(_redis_cli CONFIG GET logfile 2>/dev/null | awk 'NR==2{print $0}' | tr -d '\r' || true)"
REDIS_PIDFILE="$(_redis_cli CONFIG GET pidfile 2>/dev/null | awk 'NR==2{print $0}' | tr -d '\r' || true)"

if [ -n "$REDIS_PID" ]; then
  echo "Redis server PID: ${REDIS_PID}"
fi
if [ -n "$REDIS_CONFIG_FILE" ]; then
  echo "Redis config file: ${REDIS_CONFIG_FILE}"
fi
if [ -n "$REDIS_PIDFILE" ]; then
  echo "Redis pidfile: ${REDIS_PIDFILE}"
fi
if [ -n "$REDIS_LOGFILE" ]; then
  echo "Redis logfile: ${REDIS_LOGFILE}"
fi

# Note: Celery URLs are already set above based on REDIS_PASSWORD.
# Here we only surface Redis runtime info for debugging; we do not
# modify auth or broker URLs based on CONFIG GET output.

# Optional: hint if we're not using the project-managed Redis config/logs
if [ "$REDIS_LOGFILE" != "$LOG_DIR/redis.log" ] && [ -n "$REDIS_LOGFILE" ]; then
  echo "ℹ️ Redis is not using $LOG_DIR/redis.log. To use project Redis and logs:"
  echo "   STOP_REDIS=1 scripts/rest_api/stop_servers_celery.sh   # stop project Redis if used"
  echo "   sudo systemctl stop redis-server                      # stop system Redis"
  echo "   START_REDIS=1 scripts/rest_api/launch_servers_celery.sh"
fi

# check_redis uses probed auth (for Celery start)
check_redis() {
  _redis_cli ping 2>/dev/null | grep -q PONG
}

########################################
# 3) Start orchestrator (FastAPI)
########################################
# Daily log file: new file each day, append within the day (each session/restart appends)
ORCH_LOG="$LOG_DIR/orchestrator_rest_api_$(date +%Y-%m-%d).log"
ORCH_PID_FILE="$LOG_DIR/orchestrator_rest_api.pid"
ORCH_PORT=8000

echo
echo "[3/6] Starting orchestrator FastAPI on port $ORCH_PORT..."

stop_if_running() {
  local pid_file="$1"
  if [ -f "$pid_file" ]; then
    OLD_PID=$(cat "$pid_file" 2>/dev/null || true)
    if [ -n "$OLD_PID" ] && ps -p "$OLD_PID" > /dev/null 2>&1; then
      echo "Stopping existing process (PID: $OLD_PID)..."
      kill "$OLD_PID" 2>/dev/null || true
      sleep 1
    fi
  fi
}

stop_if_running "$ORCH_PID_FILE"
# Export so orchestrator form_loop uses real Celery classification (orchestrator also loads env.local)
export ENABLE_CELERY_CLASSIFICATION="${ENABLE_CELERY_CLASSIFICATION:-1}"
# ORCHESTRATOR_LOG_LEVEL: DEBUG (default), INFO, WARNING. botocore/boto3 are always WARNING.
echo "" >> "$ORCH_LOG"
echo "=== Restart $LAUNCH_TIME ===" >> "$ORCH_LOG"
PYTHONPATH="$BASE_DIR" nohup python3 -m uvicorn backend.orchestrator.main:app --host 0.0.0.0 --port "$ORCH_PORT" >> "$ORCH_LOG" 2>&1 &
echo $! > "$ORCH_PID_FILE"
sleep 2

if ps -p "$(cat "$ORCH_PID_FILE")" > /dev/null 2>&1; then
  echo "✅ Orchestrator started (PID: $(cat "$ORCH_PID_FILE")), log: $ORCH_LOG"
else
  echo "❌ Failed to start orchestrator. Check log: $ORCH_LOG"
fi

########################################
# 4) Start backend/file server (FastAPI)
########################################
# Daily log file: new file each day, append within the day
BACKEND_LOG="$LOG_DIR/backend_rest_api_$(date +%Y-%m-%d).log"
BACKEND_PID_FILE="$LOG_DIR/backend_rest_api.pid"
BACKEND_PORT=5001

echo
echo "[4/6] Starting backend/file server (FastAPI) on port $BACKEND_PORT..."

stop_if_running "$BACKEND_PID_FILE"
echo "" >> "$BACKEND_LOG"
echo "=== Restart $LAUNCH_TIME ===" >> "$BACKEND_LOG"
PYTHONPATH="$BASE_DIR" nohup python3 -m uvicorn backend.api.fastapi_app:app --host 0.0.0.0 --port "$BACKEND_PORT" >> "$BACKEND_LOG" 2>&1 &
echo $! > "$BACKEND_PID_FILE"
sleep 2

if ps -p "$(cat "$BACKEND_PID_FILE")" > /dev/null 2>&1; then
  echo "✅ Backend started (PID: $(cat "$BACKEND_PID_FILE")), log: $BACKEND_LOG"
else
  echo "❌ Failed to start backend. Check log: $BACKEND_LOG"
fi

########################################
# 5) Celery workers
########################################
CELERY_CMD="celery"
if [ -f "$VENV_DIR/bin/celery" ]; then
  CELERY_CMD="$VENV_DIR/bin/celery"
fi

cleanup_celery_worker() {
  local queue_name="$1"
  local pid_file="$LOG_DIR/celery_${queue_name}.pid"
  local log_file="$LOG_DIR/celery_${queue_name}.log"
  if [ -f "$pid_file" ]; then
    local pid=$(cat "$pid_file")
    if ps -p "$pid" > /dev/null 2>&1; then
      echo "Stopping existing celery_$queue_name (PID: $pid)..."
      kill "$pid" 2>/dev/null || true
      sleep 2
    fi
    rm -f "$pid_file"
  fi
  rm -f "$log_file"
  pkill -f "celery.*worker.*$queue_name" 2>/dev/null || true
  sleep 1
}

start_celery_worker() {
  local queue_name="$1"
  local concurrency="$2"
  local log_file="$LOG_DIR/celery_${queue_name}.log"
  local pid_file="$LOG_DIR/celery_${queue_name}.pid"

  if ! check_redis; then
    echo "❌ Cannot start Celery $queue_name without Redis"
    return 1
  fi

  cleanup_celery_worker "$queue_name"
  sleep 1

  echo "Starting Celery worker for $queue_name (concurrency=$concurrency)..."
  cd "$BASE_DIR" && PYTHONPATH="$BASE_DIR" \
    $CELERY_CMD -A backend.task_queue.celery_app worker -Q "$queue_name" \
    --concurrency="$concurrency" \
    --logfile="$log_file" \
    --pidfile="$pid_file" \
    --loglevel=INFO \
    --max-tasks-per-child=1000 \
    --without-gossip --without-mingle --without-heartbeat \
    -n "celery@${queue_name}.%h" \
    --detach

  sleep 2

  if grep -q "celery@.*ready" "$log_file" 2>/dev/null; then
    echo "✅ celery_$queue_name started (log: $log_file)"
    return 0
  else
    echo "⚠️ celery_$queue_name may still be starting; check $log_file"
    return 0
  fi
}

echo
echo "[5/6] Starting Celery workers..."

if start_celery_worker "default" 2; then
  :
else
  echo "⚠️ Celery default worker failed to start"
fi

if start_celery_worker "llm_queue" 6; then
  :
else
  echo "⚠️ Celery llm_queue worker failed to start (required for grievance classification)"
fi

########################################
# 6) Summary
########################################
echo
echo "[6/6] === REST API + Celery stack launched at: $LAUNCH_TIME ==="
echo
echo "Assuming nginx is running with webchat_rest.conf on port 8083:"
echo "  • Bridge (Socket.IO webchat):  http://localhost:8083/"
echo "  • REST webchat client:         http://localhost:8083/rest-webchat/"
echo
echo "APIs:"
echo "  • Orchestrator REST API:       http://localhost:${ORCH_PORT}/message"
echo "  • Orchestrator health:         http://localhost:${ORCH_PORT}/health"
echo "  • Backend/file server:         http://localhost:${BACKEND_PORT}/"
echo
echo "Celery workers: logs/celery_default.log, logs/celery_llm_queue.log"
echo "Set ENABLE_CELERY_CLASSIFICATION=1 before starting orchestrator to use real LLM classification."
echo
echo "Redis: START_REDIS=0 to skip starting project Redis; stop with STOP_REDIS=1 stop_servers_celery.sh"
echo "To stop: scripts/rest_api/stop_servers_celery.sh"
