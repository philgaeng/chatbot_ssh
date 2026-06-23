#!/usr/bin/env bash
set -uo pipefail

# Host watchdog (L0) — supervises Docker containers + host resources.
#
# Runs on the HOST (via cron, every 5 min), where it has Docker + host visibility
# the ops container intentionally lacks (no Docker socket inside ops). It:
#   1. Restarts containers that are unhealthy or exited.
#   2. Checks host disk + RAM pressure (the ops monitor only sees its own mounts).
#   3. Verifies the ops scheduler tick (Redis key) is fresh.
#   4. Emails the operator on action/alert (best-effort via local `mail` if present).
#
# Usage:
#   scripts/ops/host_watchdog.sh /home/ubuntu/nepal_chatbot
#
# Env:
#   DISK_CRIT_PCT (85)  MEM_CRIT_PCT (90)  ALERT_EMAIL ("")  COMPOSE_FILES (auto)

REPO_DIR="${1:-$(pwd)}"
DISK_CRIT_PCT="${DISK_CRIT_PCT:-85}"
MEM_CRIT_PCT="${MEM_CRIT_PCT:-90}"
ALERT_EMAIL="${ALERT_EMAIL:-}"
TICK_KEY="ops:scheduler:last_tick"
STATE_DIR="${WATCHDOG_STATE_DIR:-/var/lib/grms-watchdog}"
STORM_MAX="${STORM_MAX:-3}"        # max restarts per container per window
STORM_WINDOW="${STORM_WINDOW:-900}" # seconds (15 min)
mkdir -p "$STATE_DIR" 2>/dev/null || STATE_DIR="/tmp/grms-watchdog" && mkdir -p "$STATE_DIR"

cd "$REPO_DIR" || { echo "repo not found: $REPO_DIR" >&2; exit 1; }

log() { echo "[$(date -u +%FT%TZ)] watchdog: $*"; }

alert() {
  local subject="$1"; shift
  local body="$*"
  log "ALERT: $subject — $body"
  if [[ -n "$ALERT_EMAIL" ]] && command -v mail >/dev/null 2>&1; then
    printf '%s\n' "$body" | mail -s "[GRM watchdog] $subject" "$ALERT_EMAIL" || true
  fi
}

# ── 1. Container supervision ────────────────────────────────────────────────
# Restart any container that is 'unhealthy' or 'exited' (restart policy handles
# crashes; this catches hangs the kernel won't kill).
mapfile -t BAD < <(docker ps -a \
  --filter "health=unhealthy" \
  --format '{{.Names}}' 2>/dev/null)
mapfile -t EXITED < <(docker ps -a \
  --filter "status=exited" \
  --format '{{.Names}}' 2>/dev/null)

# Restart-storm guard: track restart timestamps per container; if a container has
# been restarted >STORM_MAX times within STORM_WINDOW, STOP restarting and alert
# (a crash-loop won't be fixed by more restarts — escalate to a human instead).
restart_allowed() {
  local c="$1" now epoch f kept count
  now="$(date +%s)"
  f="$STATE_DIR/restarts_${c//[^A-Za-z0-9_.-]/_}.log"
  kept=""
  if [[ -f "$f" ]]; then
    while read -r epoch; do
      [[ -n "$epoch" ]] && (( now - epoch < STORM_WINDOW )) && kept+="$epoch"$'\n'
    done < "$f"
  fi
  count="$(printf '%s' "$kept" | grep -c . || true)"
  if (( count >= STORM_MAX )); then
    return 1
  fi
  printf '%s%s\n' "$kept" "$now" > "$f"
  return 0
}

for c in "${BAD[@]}" "${EXITED[@]}"; do
  [[ -z "$c" ]] && continue
  if restart_allowed "$c"; then
    log "restarting container: $c"
    docker restart "$c" >/dev/null 2>&1 && \
      alert "restarted $c" "Container $c was unhealthy/exited; issued docker restart."
  else
    alert "RESTART STORM: $c" "Container $c exceeded $STORM_MAX restarts in ${STORM_WINDOW}s — NOT restarting again. Manual intervention required (crash loop)."
  fi
done

# ── 2. Host disk pressure ───────────────────────────────────────────────────
DISK_PCT="$(df -P / | awk 'NR==2 {gsub("%","",$5); print $5}')"
if [[ -n "$DISK_PCT" && "$DISK_PCT" -ge "$DISK_CRIT_PCT" ]]; then
  alert "host disk ${DISK_PCT}%" "Root filesystem at ${DISK_PCT}% (threshold ${DISK_CRIT_PCT}%). Pruning dangling docker data."
  docker system prune -f --filter "until=168h" >/dev/null 2>&1 || true
fi

# ── 3. Host memory pressure ─────────────────────────────────────────────────
if command -v free >/dev/null 2>&1; then
  MEM_PCT="$(free | awk '/Mem:/ {printf("%d", $3/$2*100)}')"
  if [[ -n "$MEM_PCT" && "$MEM_PCT" -ge "$MEM_CRIT_PCT" ]]; then
    alert "host memory ${MEM_PCT}%" "RAM usage at ${MEM_PCT}% (threshold ${MEM_CRIT_PCT}%)."
  fi
fi

# ── 4. Ops scheduler liveness (independent of the ops container's self-report) ─
REDIS_CID="$(docker ps --filter "name=redis" --format '{{.Names}}' | head -n1)"
if [[ -n "$REDIS_CID" ]]; then
  TICK="$(docker exec "$REDIS_CID" redis-cli get "$TICK_KEY" 2>/dev/null)"
  if [[ -z "$TICK" ]]; then
    alert "ops scheduler silent" "No $TICK_KEY in Redis — ops monitor may be down; restarting ops."
    docker restart ops >/dev/null 2>&1 || true
  fi
fi

log "cycle complete (disk=${DISK_PCT}% mem=${MEM_PCT:-?}%)"
