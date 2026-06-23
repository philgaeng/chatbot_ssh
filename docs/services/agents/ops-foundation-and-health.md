# Agent: Ops foundation & health monitoring

**Copy this entire file into a new Cursor agent session. Build in phase order — A0 first (everything else depends on it).**

## Mission

Stand up the **platform monitoring layer** for the self-hosted Nepal GRM stack, exactly as specified in [`../11_health_and_monitoring_service.md`](../11_health_and_monitoring_service.md):

- a dedicated **`ops/` module** in its own **`ops` container** running a **broker-independent APScheduler** (not Celery),
- a dedicated **`ops` schema** + scoped **`ops_app`** DB role (third Alembic stream),
- **L1** container healthchecks, **L0** host watchdog, **L2** data-plane health checks, **L3** external dead-man's switch,
- self-hosted **backups + restore drill + maintenance**, and the **daily ops report**.

**Deployment reality:** single Ubuntu host, **2 vCPU / 8 GiB RAM**, Docker Compose, self-hosted Postgres 15 + Redis 7. No Supabase. Keep everything lightweight and memory-capped.

**Track progress in [`PROGRESS.md`](PROGRESS.md) (Runbook A).** Flip each item's status as you go; don't mark `done` until its acceptance check passes.

---

## Guardrails

- Per root `CLAUDE.md` (updated): `backend/*`, `channels/*`, `rasa_chatbot/`, `deployment/`, `docker-compose.yml` are **stable shared services** — touch them only where this runbook explicitly says so, with care + tests.
- This runbook's two sanctioned edits outside new code:
  1. Adding compose-level `healthcheck:`/`logging:` keys to existing services (allowed — no source change).
  2. Adding a tiny `health.heartbeat` task to the **GRM** Celery beat (`ticketing/tasks/`) — that's editable.
- All new platform code lives under **`ops/`**. New deps go in **`requirements.grm.txt`**.
- The `ops` container must **never** mount `/var/run/docker.sock` and must keep `mem_limit: 256m`.
- Do **not** commit unless the user asks. Do **not** commit secrets.

---

## Read first (in order)

| File | Why |
|------|-----|
| [`../11_health_and_monitoring_service.md`](../11_health_and_monitoring_service.md) | The spec — build to it |
| [`../12_security_monitoring_service.md`](../12_security_monitoring_service.md) §3 item 9, §3.13 | `ops_app` least-privilege + no-docker-socket constraints |
| [`../../deployment/07_migrations_policy.md`](../../deployment/07_migrations_policy.md) | Three-stream migration model (add the `ops` stream) |
| [`../05_messaging_service.md`](../05_messaging_service.md) | `POST /api/messaging/send-email` contract for alerts + report |
| `ticketing/tasks/celery_app.py` | GRM beat schedule (add `health.heartbeat`) |
| `ticketing/migrations/alembic.ini`, `ticketing/migrations/env.py` | Pattern to clone for `ops/migrations/` |
| `ticketing/config/settings.py` | pydantic-settings pattern to clone for `ops/config` |
| `docker-compose.yml`, `docker-compose.grm.yml` | Where the `ops` service + healthchecks go |
| `scripts/ops/install_tls_renew_cron.sh`, `scripts/ops/test_smtp.py` | Cron-installer + SMTP-probe patterns to reuse |

---

## Implementation — Phase A0: foundation (do first)

1. **`ops/` package skeleton** — create modules with clear function stubs + docstrings:
   `ops/__init__.py`, `ops/config.py` (pydantic-settings: PG, `MESSAGING_API_URL`, thresholds, `HEALTHCHECKS_PING_URL`, `OPS_STATUS_FILE`), `ops/db.py` (SQLAlchemy engine using `OPS_DB_USER`/`OPS_DB_PASSWORD`), `ops/scheduler.py` (APScheduler `BlockingScheduler`, registers all jobs, writes `ops:scheduler:last_tick` + status file every minute), `ops/checks.py`, `ops/maintenance.py`, `ops/reports.py`, `ops/security.py` (stub for Runbook B), `ops/alerts.py` (dedup + Messaging API), `ops/selfcheck.py` (exit 0 if last tick fresh). **(PROGRESS A0.1)**
2. **`requirements.grm.txt`**: add `apscheduler>=3.10`, `pip-audit` (used by Runbook B). **(A0.2)**
3. **`ops/migrations/`** — clone the ticketing Alembic project: `alembic.ini`, `env.py` with `version_table="alembic_version_ops"`, `version_table_schema="ops"`, and `include_object` returning `True` only for `object.schema == "ops"`. **(A0.3)**
4. **Revision 1** (`ops/migrations/versions/ops001_init.py`), header:
   ```python
   # Safe to run: only creates/modifies ops.* objects
   # Does NOT touch: grievances, complainants, public.* or ticketing.* tables
   ```
   - `CREATE SCHEMA IF NOT EXISTS ops`
   - `ops.system_health_checks` (id uuid pk, check_name, status, value_json jsonb, message, checked_at) + index on `(check_name, checked_at DESC)`
   - create role `ops_app` if not exists; grants per spec §5.2 (r/w on `ops.*`, `USAGE`+`SELECT` on the reporting tables in `public.*`/`ticketing.*` the daily report needs). Make grants idempotent. **(A0.4)**
5. **`ops` service** in compose (prefer `docker-compose.grm.yml` so the base stack stays clean) per spec §4.6: same `Dockerfile`, `command: python -m ops.scheduler`, scoped `ops_app` creds, `mem_limit: 256m`, **no** ports, **no** docker socket, `depends_on: db (service_healthy)`, `restart: unless-stopped`, healthcheck `python -m ops.selfcheck`. **(A0.5, A1.5)**
6. **Makefile / migrations:** ensure `make migrate_all` runs the ops stream too. **(A0.6 — policy doc already done)**
7. **Env:** add the §12 vars to `env.local` (and document in the spec's env block if missing). **(A0.7)**

**A0 acceptance:** `alembic -c ops/migrations/alembic.ini upgrade head` creates `ops` schema + table + role; `docker compose ... up -d ops` starts and goes healthy; `ops_app` write to `ticketing.*`/`public.*` is denied while `ops.*` write succeeds.

## Phase A1 — container healthchecks (L1)

8. Add `healthcheck` blocks per spec §4.1–§4.4 to: orchestrator, backend, redis, celery_file/default/llm, grm_celery, grm_celery_beat, grm_ui(_auth), nginx. Keep probes cheap. **(A1.1–A1.4)**
9. Upgrade Redis dependents from `service_started` → `service_healthy`. **(A1.6)**

**A1 acceptance:** `docker compose ps` shows `healthy`; killing a worker/redis/api → auto-restart within one interval.

## Phase A2 — host watchdog (L0)

10. `scripts/ops/grm-watchdog.sh` per spec §6.1: supervise + restart unhealthy/exited containers (incl. `ops`), check Redis, check both heartbeats (`health:beat:last_run`, `ops:scheduler:last_tick`), worker `inspect ping`, **host disk/RAM** (L0 owns `disk_check`/`memory_check`), restart-storm guard, structured log to `logs/watchdog.log`. **(A2.1–A2.4)**
11. Cron installer mirroring `install_tls_renew_cron.sh` (every 2–5 min). **(A2.5)**

**A2 acceptance:** stop `ops` → watchdog restarts it on stale tick; storm guard halts after >3 restarts/15min + alerts.

## Phase A3 — ops checks (L2)

12. Implement `ops/checks.py` data-plane checks (§5.1): `db_connectivity_check`, `redis_check`, `queue_depth_check`, `stale_job_check`, `endpoint_check`, `cert_check`, `smtp_check`, `grm_beat_liveness_check`. Each writes an `ops.system_health_checks` row and, on warn/critical, calls `ops/alerts.py`. **(A3.1–A3.4, A3.6, A3.7)**
13. Register all in `ops/scheduler.py` at the §5.1 cadences.
14. **GRM beat heartbeat:** add a tiny `health.heartbeat` task to `ticketing/tasks/` and a `beat_schedule` entry (every 60s) that sets `health:beat:last_run` (EX 180). The ops monitor only reads it. **(A3.5)**
15. GRM Celery `task_failure` signal handler → deduped immediate alert for non-retryable escalation/report/sync failures. **(A3.8)**

**A3 acceptance:** **stop Redis** → ops still records check rows to Postgres + sends the critical alert email (proves broker-independence).

## Phase A4 — external heartbeat (L3)

16. `external_heartbeat` job: `curl HEALTHCHECKS_PING_URL` only when latest checks are green; never raises. **(A4.1)** Provider config is ops/manual. **(A4.2)**

## Phase A5 — backups & maintenance

17. `scripts/ops/pg-backup.sh` (host cron, daily 02:00 Asia/Kathmandu): `docker compose exec -T db pg_dump -F c | gzip`, **encrypt** (gpg/age), **off-box** copy, prune (7d/4w/3-6m). **(A5.1)** Document `DB_ENCRYPTION_KEY` separate backup. **(A5.2)**
18. Uploads backup job (tar + encrypt + off-box, weekly). **(A5.3)**
19. `ops.checks.backup_status_check` (daily) + `ops.checks.restore_drill` (weekly: restore latest dump into scratch DB, assert table counts). **(A5.4)**
20. `ops/maintenance.py`: prune_logs, prune_health_checks (>90d), prune_uploads_orphans, vacuum_analyze, os_update_check (report-only). **(A5.5)**

## Phase A6 — daily ops report

21. `ops.reports.daily_ops_report` (§11): APScheduler cron 07:00 Asia/Kathmandu, tz-aware, **always sends** via Messaging API, pings external heartbeat on success. **(A6.1, A6.5)**
22. Activity section (grievances/tickets/SLA/files/messaging) read directly from Postgres; officer logins from Keycloak events API. Health + backup + dependency summary from `ops.system_health_checks` / `ops.dependency_findings` / watchdog log. Optional XLSX via `openpyxl`. **(A6.2–A6.4)**

**A6 acceptance:** report arrives at 07:00 Asia/Kathmandu with non-empty activity + health sections, even with Celery degraded.

---

## Definition of done

- All Runbook A items in [`PROGRESS.md`](PROGRESS.md) are `☑` with acceptance notes.
- Spec §14 acceptance criteria all pass (esp. the broker-independence + no-docker-socket checks).
- `ops/migrations` heads = 1; `make migrate_all` green on a fresh DB.
- Update [`PROGRESS.md`](PROGRESS.md) deviations log for any departure from spec.
- Hand off to [`security-monitoring-and-hardening.md`](security-monitoring-and-hardening.md) (Runbook B) — it reuses the `ops` module + Alembic stream you built here.
