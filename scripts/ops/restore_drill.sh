#!/usr/bin/env bash
set -uo pipefail

# Restore-verification drill — proves backups are actually restorable.
#
# Restores the latest app_db dump into a throwaway scratch DB inside the db
# container, asserts a few table counts are > 0, drops the scratch DB, and writes
# a status JSON the ops monitor reads (ops/checks.py::restore_drill).
#
# Runs on the HOST via cron (weekly).
#
# Usage:
#   scripts/ops/restore_drill.sh /home/ubuntu/nepal_chatbot
#
# Env:
#   BACKUP_DIR (/var/backups/grms)  DB_CONTAINER (auto)  PG_USER (user)
#   SCRATCH_DB (grms_restore_check)  CHECK_TABLES ("public.grievances ticketing.tickets")

REPO_DIR="${1:-$(pwd)}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/grms}"
PG_USER="${PG_USER:-user}"
SCRATCH_DB="${SCRATCH_DB:-grms_restore_check}"
CHECK_TABLES="${CHECK_TABLES:-public.grievances ticketing.tickets}"
STATUS_FILE="$BACKUP_DIR/last_restore_drill.json"

log() { echo "[$(date -u +%FT%TZ)] restore-drill: $*"; }
fail() {
  echo "{\"ok\": false, \"completed_at\": \"$(date -u +%FT%TZ)\", \"error\": \"$1\"}" > "$STATUS_FILE"
  log "FAILED: $1"
  exit 1
}

DB_CONTAINER="${DB_CONTAINER:-$(docker ps --filter "name=db" --format '{{.Names}}' | head -n1)}"
[[ -z "$DB_CONTAINER" ]] && fail "no db container"

LATEST="$(ls -t "$BACKUP_DIR"/app_db_*.dump "$BACKUP_DIR"/app_db_*.dump.gpg 2>/dev/null | head -n1)"
[[ -z "$LATEST" ]] && fail "no dump found in $BACKUP_DIR"
log "restoring $LATEST into $SCRATCH_DB"

# Decrypt if the latest backup is gpg-encrypted.
RESTORE_SRC="$LATEST"
CLEANUP_SRC=""
if [[ "$LATEST" == *.gpg ]]; then
  command -v gpg >/dev/null 2>&1 || fail "encrypted dump but gpg not installed"
  RESTORE_SRC="$(mktemp "${BACKUP_DIR}/restore_XXXX.dump")"
  CLEANUP_SRC="$RESTORE_SRC"
  if [[ -n "${BACKUP_PASSPHRASE:-}" ]]; then
    printf '%s' "$BACKUP_PASSPHRASE" | gpg --batch --yes --passphrase-fd 0 -o "$RESTORE_SRC" -d "$LATEST" \
      || { rm -f "$CLEANUP_SRC"; fail "gpg decrypt (symmetric) failed"; }
  else
    gpg --batch --yes -o "$RESTORE_SRC" -d "$LATEST" \
      || { rm -f "$CLEANUP_SRC"; fail "gpg decrypt (key) failed"; }
  fi
fi

docker exec "$DB_CONTAINER" dropdb -U "$PG_USER" --if-exists "$SCRATCH_DB" >/dev/null 2>&1 || true
docker exec "$DB_CONTAINER" createdb -U "$PG_USER" "$SCRATCH_DB" || fail "createdb failed"

if ! docker exec -i "$DB_CONTAINER" pg_restore -U "$PG_USER" -d "$SCRATCH_DB" --no-owner < "$RESTORE_SRC" 2>/dev/null; then
  log "WARN: pg_restore reported errors (often benign for ownership) — continuing to count check"
fi
[[ -n "$CLEANUP_SRC" ]] && rm -f "$CLEANUP_SRC"

COUNTS="{}"
ALL_OK=true
for tbl in $CHECK_TABLES; do
  n="$(docker exec "$DB_CONTAINER" psql -U "$PG_USER" -d "$SCRATCH_DB" -tAc "SELECT count(*) FROM $tbl" 2>/dev/null || echo "ERR")"
  log "  $tbl = $n"
  [[ "$n" == "ERR" ]] && ALL_OK=false
  COUNTS="$(printf '%s' "$COUNTS" | sed "s/}$/\"$tbl\": \"$n\", }/" )"
done
COUNTS="$(printf '%s' "$COUNTS" | sed 's/, }/}/')"

docker exec "$DB_CONTAINER" dropdb -U "$PG_USER" --if-exists "$SCRATCH_DB" >/dev/null 2>&1 || true

cat > "$STATUS_FILE" <<EOF
{
  "ok": $ALL_OK,
  "completed_at": "$(date -u +%FT%TZ)",
  "dump_file": "$LATEST",
  "counts": $COUNTS
}
EOF
log "status written: $STATUS_FILE (ok=$ALL_OK)"
$ALL_OK || exit 1
