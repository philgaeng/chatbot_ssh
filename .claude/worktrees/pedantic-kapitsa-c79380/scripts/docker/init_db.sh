#!/usr/bin/env bash
# Run inside the app container after Postgres is healthy.
# Loads scripts/database/config.sh (uses env.local / POSTGRES_*), then creates tables.
set -euo pipefail
cd /app
source scripts/database/config.sh
exec python scripts/database/init.py --enable-encryption "$@"
