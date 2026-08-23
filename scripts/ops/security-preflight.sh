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

# 1. Auth must be keycloak and env non-dev (dev bypass is honoured only when
#    APP_ENV=dev AND AUTH_MODE=bypass — production can never bypass).
APP_ENV_V="$(getenv APP_ENV)"
AUTH_MODE_V="$(getenv AUTH_MODE)"
[[ "$AUTH_MODE_V" == "bypass" ]] && fail "AUTH_MODE=bypass (demo bypass)" || pass "AUTH_MODE not bypass"
[[ "$APP_ENV_V" == "dev" ]] && fail "APP_ENV=dev (not a deployed environment)" || pass "APP_ENV not dev"

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

# 4. POSTGRES_PASSWORD: non-default in the env file, AND actually reaching the containers.
#
# ⚠ The second half is the point. This check read only $ENV_FILE for months and passed
# the whole time, while eleven compose services set POSTGRES_PASSWORD in their own
# `environment:` blocks — which override `env_file:` — so the value it was asserting on
# was read by nobody and every deployed database ran as `user`/`password`. A gate that
# reports green on a variable nothing consumes is worse than no gate, because it is
# quoted as evidence. Checking the env file alone cannot detect that; checking the
# compose files for a literal is what detects it, and needs no running stack.
PG="$(getenv POSTGRES_PASSWORD)"
[[ "$PG" == "password" || -z "$PG" ]] && fail "POSTGRES_PASSWORD is default/empty in $ENV_FILE" || pass "POSTGRES_PASSWORD non-default in $ENV_FILE"

# 4b. No compose file may pin the DB credentials to a literal — that makes $ENV_FILE inert.
#     A value is acceptable only if it interpolates (`${VAR...}`); anything else is a literal.
CRED_KEYS='POSTGRES_PASSWORD|POSTGRES_USER|POSTGRES_DB|KC_DB_PASSWORD|KC_DB_USERNAME'
hardcoded=0
for f in $COMPOSE_FILES; do
  [[ -f "$f" ]] || continue
  while IFS= read -r hit; do
    [[ -n "$hit" ]] || continue
    fail "$f hardcodes a DB credential (overrides env_file, making $ENV_FILE inert): ${hit%%:*}"
    hardcoded=1
  done < <(grep -nE "^[[:space:]]+($CRED_KEYS):[[:space:]]*[^\$[:space:]]" "$f" || true)
  # DATABASE_URL with inline credentials is the same defect wearing a URL.
  while IFS= read -r hit; do
    [[ -n "$hit" ]] || continue
    fail "$f embeds credentials in DATABASE_URL: ${hit%%:*}"
    hardcoded=1
  done < <(grep -nE "^[[:space:]]+DATABASE_URL:[[:space:]]*[a-z+]+://[^$]*:[^$@]*@" "$f" || true)
done
(( hardcoded == 0 )) && pass "no compose file hardcodes DB credentials"

# 4c. Best effort, and only when a stack is up: what a container holds must match $ENV_FILE.
#     Hashes are compared so no secret is ever printed or logged.
if command -v docker >/dev/null 2>&1 && [[ -n "$PG" ]]; then
  cf=""; for f in $COMPOSE_FILES; do [[ -f "$f" ]] && cf="$cf -f $f"; done
  live="$(docker compose --env-file "$ENV_FILE" $cf exec -T backend printenv POSTGRES_PASSWORD 2>/dev/null | tr -d '\r\n' || true)"
  if [[ -z "$live" ]]; then
    echo "  SKIP: container check (no running backend) — 4b still covers the literal case"
  elif [[ "$(printf %s "$live" | sha256sum)" == "$(printf %s "$PG" | sha256sum)" ]]; then
    pass "the running backend holds $ENV_FILE's POSTGRES_PASSWORD"
  else
    fail "the running backend's POSTGRES_PASSWORD differs from $ENV_FILE — $ENV_FILE is inert"
  fi
fi

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
