# Operations — Docker-era guide

**Status:** As-built, July 2026 — rewritten from legacy doc, original in [`archive/03_operations.md`](archive/03_operations.md). All legacy systemd/Rasa procedures removed; the stack is Docker Compose only.
**Last updated:** 2026-09-06 — §6a: deploying a tagged build and rolling back (QA-02); the `tail` warning in §7.

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

## 6a. Deploying a specific build, and rolling back

**Staging pulls images that CI already built; production still builds on the box.** Both go
through the same Makefile macros, and which one happens is `DEPLOY_BUILD` — `0` pulls, `1`
builds. The `aws-*` targets set `0`; everything else defaults to `1`.

```bash
make aws-deploy IMAGE_TAG=<short-sha>        # deploy that commit's images
make aws-deploy IMAGE_TAG=<an-older-sha>     # ⭐ that is the rollback — no rebuild
make aws-deploy DEPLOY_BUILD=1               # registry unreachable: build on the box instead
```

⭐ **The rollback is the capability worth knowing about.** Before images were tagged, going back
a version meant rebuilding an older commit *on the deploy host* — the operation that took
staging off the network for 41 minutes on 2026-09-04. Now it is a pull of an image that already
exists, and it takes as long as the download.

**`IMAGE_TAG` is a 7-character short sha**, the same one the build workflow tags with. Find one
with `git rev-parse --short HEAD` on the commit you want, or read it off the Images run.

⚠ **A deploy with no `IMAGE_TAG` is refused, on purpose.** The default resolves to `local`,
which exists only on a developer's machine, so a pulling deploy without a tag would fail
partway through with a registry 404 that reads like an outage. It stops before starting and
says what to pass instead.

⚠ **Production is deliberately unchanged.** `prod-deploy` still builds on the host, because
nobody has yet run `curl -sI https://ghcr.io/v2/` from the VPN-only DOR box to confirm it can
reach the registry at all. Converting it before that answer would put an untested path in a
maintenance window. When the answer arrives, `make prod-deploy DEPLOY_BUILD=0` is the switch —
and it needs a registry credential on that host first.

**Every deploy prints what is actually running**, per service, after `up -d`:

```
aws-deploy: running images —
  ticketing_api      ghcr.io/philgaeng/chatbot_ssh/app:a1b2c3d   sha256:9f2e1c4a8b...
  grm_ui             ghcr.io/philgaeng/chatbot_ssh/ui:a1b2c3d    sha256:3d7b0e5f2c...
```

⚠ **Read it.** A pulling deploy can succeed while changing nothing: if `IMAGE_TAG` was not
bumped, `up -d` is a no-op and the deploy reports OK having redeployed the previous build. The
digest is the only thing that distinguishes those two outcomes, and *"deployed" is not "has
run"* is a lesson this project has already paid for once.

## 7. Common procedures

```bash
# Deploy update (staging/prod: prefer make aws-deploy / prod-deploy — they wrap this; §6a)
git pull --ff-only origin main
make migrate_all
docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d --build

# ⚠ Never pipe a deploy through `tail`, `head` or `less`.
#   make aws-deploy | tail -20     # DON'T
# Those buffer until the pipe closes, so a deploy that is stalling looks identical to one that
# is working — which is what left the operator blind for 41 minutes on 2026-09-04. Let it print,
# or capture with `tee` (which passes output through as it arrives):
#   make aws-deploy 2>&1 | tee deploy.log

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
