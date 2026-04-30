# Scripts Directory (Docker-Only)

This repository now uses a Docker-first operational model.

## Current Script Areas

- `scripts/docker/`
  - `init_db.sh`: container entrypoint used by `db_init` profile.
- `scripts/database/`
  - `init.py`, `config.sh`: DB bootstrap path used by `scripts/docker/init_db.sh`.
  - `migrate_seah_demo_catalog.py`, `import_seah_demo_seed_csv.py`, `seeds/`: optional SEAH demo seed flow.
- `scripts/ops/`
  - Operational helper scripts (for example TLS renewal cron install).

## Removed Legacy Areas

The following were removed as part of Docker-only cleanup:

- `scripts/local/`
- `scripts/rest_api/`
- `scripts/servers/`
- `scripts/rasa/`
- `scripts/task_queue/`
- `scripts/db/`

These previously managed host processes directly (manual Redis/Rasa/Uvicorn/Celery orchestration, remote SSH wrappers, and local ngrok helpers).

## Migration Policy

- Ticketing schema changes must go through Alembic:
  - `ticketing/migrations/alembic.ini`
- Avoid adding one-off schema mutation scripts under `scripts/database/`.
- If a new schema change is needed, add a migration (or explicit seed script if data-only and environment-safe).
