# Operations — Docker-era guide

**Status:** As-built, July 2026 — rewritten from legacy doc, original in [`archive/03_operations.md`](archive/03_operations.md). All legacy systemd/Rasa procedures removed; the stack is Docker Compose only.

## 1. Daily driving

```bash
docker compose ps                                   # health of all services (healthchecks are built in)
docker compose logs -f backend orchestrator         # tail chatbot services
docker compose -f docker-compose.yml -f docker-compose.grm.yml logs -f ticketing_api grm_celery ops
docker compose restart <service>                    # bounce one service
curl http://localhost:5001/health ; curl http://localhost:8000/health ; curl http://localhost:5002/health
```

Container build/run/debug recipes (rebuild-one-service, exec, psql, seed, pytest): [`DOCKER.md`](DOCKER.md).

## 2. Startup Runbook (Dev/SSH)

Use this sequence when bringing up a dev/integration host from a fresh DB or after major schema merges.

```bash
cd /home/ubuntu/nepal_chatbot

# 1) Sync code and ensure latest migration files are in the backend image
git fetch origin
git checkout main
git pull --ff-only origin main
docker compose build backend

# 2) db_init = migrate-before-start: applies the public Alembic stream, THEN
#    seeds reference/lookup data. The app no longer creates public.* tables at
#    startup — the Alembic baseline (migrations/public) owns all public.* DDL (CL-01).
docker compose --profile init run --rm db_init || true

# 3) Apply migration streams (public is idempotent here — db_init already ran it;
#    ticketing + ops are separate streams). Always migrate before starting the app.
docker compose run --rm --no-deps backend python -m alembic -c migrations/public/alembic.ini upgrade head
docker compose run --rm --no-deps backend python -m alembic -c ticketing/migrations/alembic.ini upgrade head
docker compose run --rm --no-deps backend python -m alembic -c ops/migrations/alembic.ini upgrade head

# 4) Seed locations/workflows/tickets (JSON source)
docker compose run --rm --no-deps backend python -m ticketing.seed.import_locations_json \
  --country NP \
  --en backend/dev-resources/location_dataset/en_cleaned.json \
  --ne backend/dev-resources/location_dataset/ne_cleaned.json \
  --max-level 3
docker compose run --rm --no-deps backend python -m ticketing.seed.mock_tickets --reset

# 5) Restart full stack
docker compose -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml ps
```

Post-start verification:

```bash
# Core chatbot/public runtime tables
docker compose run --rm --no-deps backend python - <<'PY'
import os
from sqlalchemy import create_engine, text
e = create_engine(os.environ["DATABASE_URL"])
with e.connect() as c:
    for t in ("public.complainants", "public.grievances", "public.file_attachments"):
        print(t, "=>", c.execute(text(f"select to_regclass('{t}')")).scalar())
PY
```

Expected:
- All three `public.*` tables resolve (not `None`).
- `mock_tickets --reset` logs `location OK` for KL Road location codes.
- `ticketing_api` becomes healthy after startup.

## 3. Migration run order

Standard order (what `make migrate_all` does): **ticketing → public → ops**.

### Public + ticketing migration run order (May5 SEAH tranche)

```bash
# 1) ticketing schema changes first
python -m alembic -c ticketing/migrations/alembic.ini upgrade head

# 2) public schema changes second
python -m alembic -c migrations/public/alembic.ini upgrade head
```

Rollback notes:

- Ticketing rollback uses ticketing revision IDs only.
- The public stream is a **single squashed baseline** (`pub000_public_core_baseline`, CL-01). `downgrade base` drops every public.* table; there are no intermediate public revisions to roll back to. To rebuild an existing (non-prod, 0-record) DB onto the baseline, use `make reset_public_dev` (drops+recreates the public schema — including the `alembic_version_public` row — then re-migrates).

Full stream-ownership policy: [`07_migrations_policy.md`](07_migrations_policy.md).

## 4. Monitoring — the `ops` container + host watchdog

Monitoring is layered and already built (spec + as-built detail: [`../services/11_health_and_monitoring_service.md`](../services/11_health_and_monitoring_service.md)):

| Layer | What | Where |
|---|---|---|
| L1 | Compose `healthcheck` on every service, `restart: unless-stopped` | compose files |
| L0 | Host watchdog cron: restarts unhealthy/exited containers, restart-storm guard, host disk/RAM checks | `scripts/ops/host_watchdog.sh` (+ `install_watchdog_cron.sh`, every 5 min) |
| L2 | `ops` container (APScheduler, broker-independent): DB/Redis/queue-depth/beat-liveness/cert/SMTP checks → `ops.system_health_checks`; deduped email alerts; daily ops report | `ops/` module, `make wsl-ops` / `aws-deploy-ops` / `prod-deploy-ops` |
| L3 | External dead-man's switch: healthchecks.io ping (`HEARTBEAT_URL`) | `ops/` (green-only ping) |
| Security | Daily dependency/CVE scan → `ops.dependency_findings`; pre-promotion gate `make security-preflight` | [`../services/12_security_monitoring_service.md`](../services/12_security_monitoring_service.md) |

## 5. Backups & recovery

| Script | Purpose |
|---|---|
| `scripts/ops/backup_db.sh` | Daily `pg_dump` (custom format) from the `db` container, gzip, off-box copy, prune |
| `scripts/ops/restore_drill.sh` | Periodic restore verification into a scratch DB — proves backups are usable |
| `scripts/ops/aws_to_prod_db_sync.sh` | Replace prod DB + uploads from AWS staging (`make prod-sync-db-from-aws CONFIRM=1`, destructive, VPN) |

Notes:
- `DB_ENCRYPTION_KEY` must be backed up **separately** from DB dumps (dumps contain pgcrypto ciphertext only) — see [`14_key_and_secret_lifecycle.md`](14_key_and_secret_lifecycle.md).
- Uploads live in the `uploads_data` volume; backups in the `backups_data` volume (mounted into `ops` at `/var/backups/grms`).
- Manual one-off: `docker compose exec -T db pg_dump -U user -d app_db -F c > backup.dump`.

## 6. Logs

| What | Where |
|---|---|
| All containers | `docker compose logs [-f] <service>` — json-file driver, bounded 10 MB × 5 files per container |
| Host watchdog | `logs/watchdog.log` (structured; rotated via `deployment/logrotate/grms.conf`) |
| Nginx access/error | inside the `nginx` container → `docker compose logs nginx` |
| Ops check history | Postgres: `ops.system_health_checks` (queryable), plus daily ops email |
| Keycloak | `docker compose --profile auth logs keycloak` |

## 7. Common procedures

```bash
# Deploy update (staging/prod: prefer make aws-deploy / prod-deploy — they wrap this)
git pull --ff-only origin main
make migrate_all
docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d --build

# Recreate nginx after editing deployment/nginx/*.conf
make wsl-nginx

# Reset DB (DEV ONLY — destroys data)
docker compose down -v          # wipes volumes
make wsl-chatbot && docker compose --profile init run --rm db_init && make migrate_all

# Flush Redis (dev; clears sessions/results)
docker compose exec redis redis-cli FLUSHALL
```

## 8. Security operations

Implemented-controls index: [`13_security.md`](13_security.md). Key/secret rotation: [`14_key_and_secret_lifecycle.md`](14_key_and_secret_lifecycle.md). Host hardening: [`15_host_hardening.md`](15_host_hardening.md). Pre-promotion gate: `make security-preflight` (non-zero exit blocks promotion).
