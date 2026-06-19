# Scripts Directory (Docker-Only)

This repository now uses a Docker-first operational model.

## Current Script Areas

- `scripts/docker/`
  - `init_db.sh`: container entrypoint used by `db_init` profile.
- `scripts/database/`
  - `init.py`, `config.sh`: DB bootstrap path used by `scripts/docker/init_db.sh`.
  - `import_seah_service_providers_xlsx.py`, `seeds/seah_service_providers_kl_road.csv`: SEAH support-centre directory for chatbot outro (`public.seah_service_providers`). Makefile: `make seed_seah_providers` (CSV upsert), `make seed_seah_providers_xlsx` (refresh CSV from Excel).
  - `migrate_seah_demo_catalog.py`, `import_seah_demo_seed_csv.py`, `seeds/`: legacy SEAH demo catalog (`seah_contact_points`). Makefile: `make compose_seed_seah_catalog`.
- `scripts/ops/`
  - Operational helper scripts (for example TLS renewal cron install).
  - `test-smtp.sh` / `test_smtp.py`: verify SMTP env, TCP reachability, and optional test send (runs in `backend` container).
  - `aws_to_prod_db_sync.sh` / `prod_sync_remove_mock_data.sql`: replace prod DB from AWS staging (`make prod-sync-db-from-aws CONFIRM=1`).

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
