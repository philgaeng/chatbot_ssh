#!/usr/bin/env bash
# CL-01 self-consistency gate: the schema produced by a fresh run of the public
# Alembic stream must equal the committed canonical baseline dump. This prevents
# the public.* schema from silently drifting from its own baseline again (the
# root cause the CL-01 squash fixed).
#
#   generate → (re)write the committed dump from a freshly-migrated DB
#   check    → dump the current DB, normalize, diff against the committed dump
#
# Connection comes from PG* env vars (PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE).
# pg_dump is pinned to major 15 (matches CI's postgres:15 service) so the text is
# stable regardless of the local client version — via a local pg_dump 15 if
# present, otherwise `docker run --rm postgres:15`.
set -euo pipefail

MODE="${1:-check}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXPECTED="$REPO_ROOT/migrations/public/expected_public_schema.sql"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGPASSWORD="${PGPASSWORD:-postgres}"
PGDATABASE="${PGDATABASE:-grievance_db_test}"

# Strip pg_dump preamble/comments/version-specific noise so the diff is stable.
normalize() {
  grep -vE '^(--|SET |SELECT pg_catalog|\\restrict|\\unrestrict)' | grep -vE '^[[:space:]]*$'
}

raw_dump() {
  local args=(--schema-only --schema=public --no-owner --no-privileges
              -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE")
  local localver=""
  if command -v pg_dump >/dev/null 2>&1; then
    localver="$(pg_dump --version | grep -oE '[0-9]+' | head -1)"
  fi
  if [ "$localver" = "15" ]; then
    PGPASSWORD="$PGPASSWORD" pg_dump "${args[@]}"
  else
    docker run --rm --network host -e PGPASSWORD="$PGPASSWORD" postgres:15 \
      pg_dump "${args[@]}"
  fi
}

case "$MODE" in
  generate)
    raw_dump | normalize > "$EXPECTED"
    echo "Wrote $EXPECTED ($(wc -l < "$EXPECTED") lines)"
    ;;
  check)
    tmp="$(mktemp)"
    raw_dump | normalize > "$tmp"
    if diff -u "$EXPECTED" "$tmp"; then
      echo "OK: fresh public-schema migration matches committed baseline."
    else
      echo "ERROR: fresh public-schema migration DRIFTED from migrations/public/expected_public_schema.sql"
      echo "If the change is intentional, run: scripts/ci/check_public_schema_baseline.sh generate"
      rm -f "$tmp"
      exit 1
    fi
    rm -f "$tmp"
    ;;
  *)
    echo "usage: $0 [generate|check]" >&2
    exit 2
    ;;
esac
