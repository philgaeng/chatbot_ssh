#!/usr/bin/env bash
set -uo pipefail

# Security pre-promotion gate — docs/services/12_security_monitoring_service.md §4.
# Asserts the prod config is hardened. NON-ZERO EXIT on any violation.
#
# Usage:
#   scripts/ops/security-preflight.sh [repo_dir]
#
# Env:
#   ENV_FILE      (default <repo>/env.local)
#   TLS_HOST      (default grm-chatbot.dor.gov.np)   CERT_MIN_DAYS (14)
#   BACKUP_STATUS (/var/backups/grms/last_backup.json)
#   RESTORE_STATUS(/var/backups/grms/last_restore_drill.json)
#   PREFLIGHT_STATUS (/var/backups/grms/last_preflight.json)  — written for the daily report
#   COMPOSE_FILES (space-separated; default the prod set)

REPO_DIR="${1:-$(pwd)}"
cd "$REPO_DIR" || { echo "repo not found: $REPO_DIR" >&2; exit 2; }

ENV_FILE="${ENV_FILE:-$REPO_DIR/env.local}"
TLS_HOST="${TLS_HOST:-grm-chatbot.dor.gov.np}"
CERT_MIN_DAYS="${CERT_MIN_DAYS:-14}"
BACKUP_STATUS="${BACKUP_STATUS:-/var/backups/grms/last_backup.json}"
RESTORE_STATUS="${RESTORE_STATUS:-/var/backups/grms/last_restore_drill.json}"
PREFLIGHT_STATUS="${PREFLIGHT_STATUS:-/var/backups/grms/last_preflight.json}"
COMPOSE_FILES="${COMPOSE_FILES:-docker-compose.yml docker-compose.grm.yml docker-compose.prod.yml}"

FAILS=0
pass() { echo "  PASS: $*"; }
fail() { echo "  FAIL: $*" >&2; FAILS=$((FAILS+1)); }

# Read a KEY=value from the env file (last occurrence wins). Empty if absent.
getenv() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | sed 's/^"//; s/"$//'; }

echo "== Security preflight ($(date -u +%FT%TZ)) =="
[[ -f "$ENV_FILE" ]] || fail "env file not found: $ENV_FILE"

# 1. Bypass-auth must be off; demo profile not active.
BYPASS="$(getenv NEXT_PUBLIC_BYPASS_AUTH)"
[[ "$BYPASS" == "true" ]] && fail "NEXT_PUBLIC_BYPASS_AUTH=true (demo bypass)" || pass "bypass-auth not enabled"
case " ${COMPOSE_PROFILES:-} " in *" demo "*) fail "COMPOSE_PROFILES includes 'demo'";; *) pass "demo profile not active";; esac

# 2. Keycloak issuer set.
[[ -n "$(getenv KEYCLOAK_ISSUER)" ]] && pass "KEYCLOAK_ISSUER set" || fail "KEYCLOAK_ISSUER empty"

# 3. Secrets set & non-default.
for k in REDIS_PASSWORD TICKETING_SECRET_KEY MESSAGING_API_KEY KEYCLOAK_WEBHOOK_SECRET DB_ENCRYPTION_KEY; do
  v="$(getenv "$k")"
  if [[ -z "$v" || "$v" == "changeme" || "$v" == "password" ]]; then
    fail "$k unset or default"
  else
    pass "$k set"
  fi
done

# 4. POSTGRES_PASSWORD != default.
PG="$(getenv POSTGRES_PASSWORD)"
[[ "$PG" == "password" || -z "$PG" ]] && fail "POSTGRES_PASSWORD is default/empty" || pass "POSTGRES_PASSWORD non-default"

# 5. CORS allowlist not '*'.
CORS="$(getenv CORS_ALLOWED_ORIGINS)"
if [[ -z "$CORS" || "$CORS" == "*" ]]; then fail "CORS_ALLOWED_ORIGINS unset or '*'"; else pass "CORS allowlist set"; fi

# 6. TLS cert > CERT_MIN_DAYS.
if command -v openssl >/dev/null 2>&1; then
  END="$(echo | openssl s_client -servername "$TLS_HOST" -connect "$TLS_HOST:443" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
  if [[ -n "$END" ]]; then
    END_EPOCH="$(date -d "$END" +%s 2>/dev/null || echo 0)"
    DAYS=$(( (END_EPOCH - $(date +%s)) / 86400 ))
    (( DAYS >= CERT_MIN_DAYS )) && pass "TLS cert ${DAYS}d remaining" || fail "TLS cert only ${DAYS}d remaining"
  else
    fail "TLS cert unreadable for $TLS_HOST"
  fi
else
  echo "  SKIP: openssl not available for cert check"
fi

# 7. No 6379/5432 published on a host port; 8. no docker.sock mount.
for f in $COMPOSE_FILES; do
  [[ -f "$f" ]] || continue
  if grep -Eq '"[0-9]+:6379"|:6379"[[:space:]]*$|- "6379' "$f"; then fail "$f publishes Redis 6379"; fi
  if grep -Eq '"[0-9]+:5432"|- "5432' "$f"; then fail "$f publishes Postgres 5432"; fi
  if grep -q 'docker.sock' "$f"; then fail "$f mounts docker.sock"; fi
done
pass "port/docker-socket scan complete"

# 9. Latest backup < 26h + restore drill green.
if [[ -f "$BACKUP_STATUS" ]] && command -v python3 >/dev/null 2>&1; then
  AGE_OK="$(python3 - "$BACKUP_STATUS" <<'PY'
import json,sys,datetime as dt
try:
    d=json.load(open(sys.argv[1]))
    ts=dt.datetime.fromisoformat(d["completed_at"].replace("Z","+00:00"))
    age=(dt.datetime.now(dt.timezone.utc)-ts).total_seconds()/3600
    print("ok" if d.get("ok") and age<26 else "bad")
except Exception:
    print("bad")
PY
)"
  [[ "$AGE_OK" == "ok" ]] && pass "DB backup fresh (<26h)" || fail "DB backup stale/missing/failed"
else
  fail "no backup status at $BACKUP_STATUS"
fi
if [[ -f "$RESTORE_STATUS" ]]; then
  grep -q '"ok": true' "$RESTORE_STATUS" && pass "restore drill green" || fail "restore drill not green"
else
  echo "  WARN: no restore-drill status at $RESTORE_STATUS"
fi

# ── verdict + status file for the daily report ───────────────────────────────
OK_JSON=true; [[ $FAILS -gt 0 ]] && OK_JSON=false
mkdir -p "$(dirname "$PREFLIGHT_STATUS")" 2>/dev/null || true
printf '{ "ok": %s, "fails": %d, "ran_at": "%s" }\n' "$OK_JSON" "$FAILS" "$(date -u +%FT%TZ)" > "$PREFLIGHT_STATUS" 2>/dev/null || true

echo "== Preflight: $FAILS violation(s) =="
[[ $FAILS -eq 0 ]] || exit 1
