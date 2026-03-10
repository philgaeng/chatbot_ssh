#!/usr/bin/env bash

set -euo pipefail

# Simple helper script to add the complainant_phone_verified column
# to the complainants table, if it does not already exist.
#
# This script reuses the same DB config as other database utilities
# in scripts/database/config.sh, so it will point at the same host,
# port, user and database as the rest of the project.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Load DB configuration (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, …)
source "$PROJECT_ROOT/scripts/database/config.sh"

SQL="
ALTER TABLE complainants
ADD COLUMN IF NOT EXISTS complainant_phone_verified BOOLEAN DEFAULT FALSE;
"

echo "Running migration to add complainant_phone_verified column to complainants…"
PGPASSWORD="$DB_PASSWORD" psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -c "$SQL"
echo "Migration completed."


