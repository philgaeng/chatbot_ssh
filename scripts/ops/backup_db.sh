#!/usr/bin/env bash
set -uo pipefail

# Self-hosted Postgres + uploads backup (we own backups — no managed DB).
#
# Runs on the HOST via cron (daily, off-peak). Dumps app_db, tars the uploads
# volume, prunes old backups, and writes a status JSON the ops monitor reads
# (ops/checks.py::backup_status_check).
#
# Usage:
#   scripts/ops/backup_db.sh /home/ubuntu/nepal_chatbot
#
# Env:
#   BACKUP_DIR (/var/backups/grms)   RETENTION_DAYS (14)
#   DB_CONTAINER (auto: name~db)     PG_USER (user)  PG_DB (app_db)
#   UPLOADS_VOLUME (auto-detect *uploads_data)
#   Encryption (optional, recommended for prod / off-box):
#     BACKUP_GPG_RECIPIENT  — gpg public-key id → asymmetric encrypt (preferred), OR
#     BACKUP_PASSPHRASE     — symmetric AES256 passphrase
#   Off-box copy (optional):
#     BACKUP_REMOTE         — rclone remote:path (needs rclone) or scp target user@host:/path
#   Key reference (does NOT store the key — see docs/deployment/14_key_and_secret_lifecycle.md):
#     DB_ENCRYPTION_KEY     — if set, its sha256 fingerprint is recorded in the status file

REPO_DIR="${1:-$(pwd)}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/grms}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
PG_USER="${PG_USER:-user}"
PG_DB="${PG_DB:-app_db}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
STATUS_FILE="$BACKUP_DIR/last_backup.json"

mkdir -p "$BACKUP_DIR"
log() { echo "[$(date -u +%FT%TZ)] backup: $*"; }

DB_CONTAINER="${DB_CONTAINER:-$(docker ps --filter "name=db" --format '{{.Names}}' | head -n1)}"
if [[ -z "$DB_CONTAINER" ]]; then
  log "ERROR: no db container found"
  echo "{\"ok\": false, \"completed_at\": \"$(date -u +%FT%TZ)\", \"error\": \"no db container\"}" > "$STATUS_FILE"
  exit 1
fi

DUMP_FILE="$BACKUP_DIR/app_db_${STAMP}.dump"
log "dumping $PG_DB from $DB_CONTAINER -> $DUMP_FILE"
if docker exec "$DB_CONTAINER" pg_dump -U "$PG_USER" -Fc "$PG_DB" > "$DUMP_FILE"; then
  DUMP_OK=true
else
  DUMP_OK=false
  log "ERROR: pg_dump failed"
fi

# ── encryption (asymmetric preferred, else symmetric) ───────────────────────
# ⚠ **This section used to be optional, and that was the defect** (D-19/F-4). The contact columns
# stay ciphertext inside the dump, but the grievance narrative, every officer note, and every voice
# recording and photograph in the uploads tar do not — so an unencrypted backup is a complete copy
# of the most sensitive material this system holds, sitting on disk and, with BACKUP_REMOTE set,
# copied off the box. It was produced by default, and only encrypted if an operator happened to set
# one of two variables.
#
# Now: no recipient and no passphrase means **no backup is kept**, unless the operator says in so
# many words that they accept it (BACKUP_ALLOW_UNENCRYPTED=1). Losing a backup is recoverable on the
# next run; an unencrypted copy of a survivor's report is not.
ENCRYPTED=false
if [[ "$DUMP_OK" == true ]]; then
  if [[ -n "${BACKUP_GPG_RECIPIENT:-}" ]] && command -v gpg >/dev/null 2>&1; then
    if gpg --batch --yes --trust-model always -r "$BACKUP_GPG_RECIPIENT" -o "${DUMP_FILE}.gpg" -e "$DUMP_FILE"; then
      rm -f "$DUMP_FILE"; DUMP_FILE="${DUMP_FILE}.gpg"; ENCRYPTED=true
      log "encrypted (gpg recipient $BACKUP_GPG_RECIPIENT)"
    else
      log "ERROR: gpg asymmetric encryption failed"
    fi
  elif [[ -n "${BACKUP_PASSPHRASE:-}" ]] && command -v gpg >/dev/null 2>&1; then
    if printf '%s' "$BACKUP_PASSPHRASE" | gpg --batch --yes --passphrase-fd 0 \
         --cipher-algo AES256 -o "${DUMP_FILE}.gpg" -c "$DUMP_FILE"; then
      rm -f "$DUMP_FILE"; DUMP_FILE="${DUMP_FILE}.gpg"; ENCRYPTED=true
      log "encrypted (symmetric AES256)"
    else
      log "ERROR: gpg symmetric encryption failed"
    fi
  fi

  # ── refuse to keep an unencrypted copy unless it was asked for explicitly ──
  if [[ "$ENCRYPTED" != true ]]; then
    if [[ "${BACKUP_ALLOW_UNENCRYPTED:-0}" == "1" ]]; then
      log "WARN: keeping an UNENCRYPTED dump because BACKUP_ALLOW_UNENCRYPTED=1. It contains the "
      log "WARN: grievance narratives and officer notes in the clear."
    else
      rm -f "$DUMP_FILE"
      DUMP_OK=false
      log "ERROR: no backup kept — the dump could not be encrypted and BACKUP_ALLOW_UNENCRYPTED is not set."
      log "ERROR: set BACKUP_GPG_RECIPIENT (preferred) or BACKUP_PASSPHRASE, or accept the risk explicitly."
    fi
  fi
fi

# ── uploads volume tar (best-effort) ────────────────────────────────────────
UPLOADS_TAR=""
UPLOADS_VOLUME="${UPLOADS_VOLUME:-$(docker volume ls --format '{{.Name}}' | grep -E 'uploads_data$' | head -n1)}"
if [[ -n "$UPLOADS_VOLUME" ]]; then
  UPLOADS_TAR="$BACKUP_DIR/uploads_${STAMP}.tar.gz"
  log "archiving uploads volume $UPLOADS_VOLUME -> $UPLOADS_TAR"
  docker run --rm -v "$UPLOADS_VOLUME":/data:ro -v "$BACKUP_DIR":/backup alpine \
    tar czf "/backup/uploads_${STAMP}.tar.gz" -C /data . || log "WARN: uploads tar failed"

  # ⚠ The uploads tar holds the voice recordings and photographs attached to grievances — the most
  # directly identifying material in the system, and none of it is encrypted at rest. Same rule as
  # the dump (D-19/F-4).
  if [[ -f "$UPLOADS_TAR" ]]; then
    if [[ -n "${BACKUP_GPG_RECIPIENT:-}" ]] && command -v gpg >/dev/null 2>&1; then
      if gpg --batch --yes --trust-model always -r "$BACKUP_GPG_RECIPIENT" \
           -o "${UPLOADS_TAR}.gpg" -e "$UPLOADS_TAR"; then
        rm -f "$UPLOADS_TAR"; UPLOADS_TAR="${UPLOADS_TAR}.gpg"
        log "uploads archive encrypted (gpg recipient $BACKUP_GPG_RECIPIENT)"
      fi
    elif [[ -n "${BACKUP_PASSPHRASE:-}" ]] && command -v gpg >/dev/null 2>&1; then
      if printf '%s' "$BACKUP_PASSPHRASE" | gpg --batch --yes --passphrase-fd 0 \
           --cipher-algo AES256 -o "${UPLOADS_TAR}.gpg" -c "$UPLOADS_TAR"; then
        rm -f "$UPLOADS_TAR"; UPLOADS_TAR="${UPLOADS_TAR}.gpg"
        log "uploads archive encrypted (symmetric AES256)"
      fi
    fi
    if [[ "$UPLOADS_TAR" != *.gpg && "${BACKUP_ALLOW_UNENCRYPTED:-0}" != "1" ]]; then
      rm -f "$UPLOADS_TAR"; UPLOADS_TAR=""
      log "ERROR: uploads archive discarded — it could not be encrypted and "
      log "ERROR: BACKUP_ALLOW_UNENCRYPTED is not set. It contains voice notes and photographs."
    fi
  fi
fi

# ── prune old backups ───────────────────────────────────────────────────────
find "$BACKUP_DIR" -name 'app_db_*.dump' -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
find "$BACKUP_DIR" -name 'app_db_*.dump.gpg' -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
find "$BACKUP_DIR" -name 'uploads_*.tar.gz*' -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true

# ── optional off-box copy (disaster recovery) ────────────────────────────────
OFFBOX=false
if [[ "$DUMP_OK" == true && -n "${BACKUP_REMOTE:-}" ]]; then
  if command -v rclone >/dev/null 2>&1 && [[ "$BACKUP_REMOTE" == *:* && "$BACKUP_REMOTE" != *@* ]]; then
    rclone copy "$DUMP_FILE" "$BACKUP_REMOTE" && OFFBOX=true || log "WARN: rclone off-box copy failed"
  elif command -v scp >/dev/null 2>&1; then
    scp -q "$DUMP_FILE" "$BACKUP_REMOTE" && OFFBOX=true || log "WARN: scp off-box copy failed"
  else
    log "WARN: BACKUP_REMOTE set but neither rclone nor scp available"
  fi
fi

# Key fingerprint (reference only — never store the key itself).
KEY_FP="null"
if [[ -n "${DB_ENCRYPTION_KEY:-}" ]] && command -v sha256sum >/dev/null 2>&1; then
  KEY_FP="\"$(printf '%s' "$DB_ENCRYPTION_KEY" | sha256sum | cut -c1-16)\""
fi

DUMP_SIZE=$(stat -c%s "$DUMP_FILE" 2>/dev/null || echo 0)
cat > "$STATUS_FILE" <<EOF
{
  "ok": $DUMP_OK,
  "completed_at": "$(date -u +%FT%TZ)",
  "dump_file": "$DUMP_FILE",
  "dump_size_bytes": $DUMP_SIZE,
  "encrypted": $ENCRYPTED,
  "offbox_copied": $OFFBOX,
  "uploads_tar": "$UPLOADS_TAR",
  "retention_days": $RETENTION_DAYS,
  "encryption_key_fp": $KEY_FP
}
EOF
log "status written: $STATUS_FILE (dump_ok=$DUMP_OK, size=$DUMP_SIZE, enc=$ENCRYPTED, offbox=$OFFBOX)"
$DUMP_OK || exit 1
