# Health & Monitoring Service Spec

**Status:** Proposed (build target). Adapts the Stratcon `CELERY_REDIS_TASK_QUEUE_SPEC §16/§18` health + daily-report model to the **self-hosted Nepal GRM stack**.
**Deployment reality:** single Ubuntu host, **2 vCPU / 8 GiB RAM**, Docker Compose, self-hosted **Postgres 15** and **Redis 7** in containers. **No Supabase, no managed DB, no managed backups** — we own backups, restore drills, and DB health.
**Architecture decision:** monitoring/health/backup/security/reporting is a **cross-cutting platform concern**, so it lives in its own **`ops/` module** running in a dedicated, lightweight **`ops` container** with a **broker-independent scheduler (APScheduler)** — *not* on Celery. This is deliberate: a monitor must not share fate with the things it watches. Celery-based health tasks depend on Redis (broker + result backend) and would go blind exactly when Redis/a worker is down. The `ops` scheduler instead writes results **directly to Postgres** and alerts via the **Messaging API over HTTP**, so it keeps working through a broker outage. GRM *business* tasks (SLA watchdog, escalation, grievance-sync, quarterly report) stay on GRM Celery where they belong.
**Related:** [`13_security.md`](../deployment/13_security.md) · [`12_security_monitoring_service.md`](12_security_monitoring_service.md) · [`07_task_queue_service.md`](07_task_queue_service.md) · [`05_messaging_service.md`](05_messaging_service.md) · [`03_operations.md`](../deployment/03_operations.md) · [`10_production_server_spec.md`](../deployment/10_production_server_spec.md)

---

## 1. Goals & non-goals

**Goals**

1. Detect and auto-recover from container crash/hang (chatbot + GRM + infra).
2. Surface degradation *before* it becomes an outage: disk, RAM, DB connectivity, queue backlog, beat liveness, cert expiry, SMTP reachability, stale jobs.
3. One **daily ops email** to the operator summarizing activity + system health.
4. An **external dead-man's switch** so a fully-down host (where internal alerting can't fire) is still noticed.
5. Self-hosted **DB + uploads backup** with periodic **restore verification**.

**Non-goals (proto / 8 GiB constraint)**

- No heavyweight observability stack (Prometheus + Grafana + Loki) by default — it would consume a meaningful slice of 8 GiB. A lightweight optional path is noted in §10.
- No paid APM.
- No real-time push alerting beyond email + external heartbeat (SSE/officer push is post-proto, per `CLAUDE.md`).

---

## 2. Stack inventory (what we are monitoring)

From `docker-compose.yml` + `docker-compose.grm.yml` + `docker-compose.prod.yml`:

| Container | Role | Port | Existing `healthcheck`? | Existing `restart`? |
|---|---|---|---|---|
| `orchestrator` | FastAPI state machine | 8000 | ❌ none | `unless-stopped` |
| `backend` | Flask/FastAPI grievance + files + messaging | 5001 | ❌ none | `unless-stopped` |
| `celery_file` | chatbot worker `file_queue` | — | ❌ none | `unless-stopped` |
| `celery_default` | chatbot worker `default` | — | ❌ none | `unless-stopped` |
| `celery_llm` | chatbot worker `llm_queue` | — | ❌ none | `unless-stopped` |
| `redis` | broker + result backend + socket bus | 6379 | ❌ none | `unless-stopped` |
| `db` | Postgres 15 (`app_db`) | 5432 | ✅ `pg_isready` | `unless-stopped` |
| `nginx` | reverse proxy / TLS | 80/443 | ❌ none | `unless-stopped` |
| `ticketing_api` | GRM API (demo) | 5002 | ✅ `/health` | `unless-stopped` |
| `ticketing_api_auth` | GRM API (Keycloak) | 5003 | ✅ `/health` | `unless-stopped` |
| `grm_celery` | GRM worker `grm_ticketing,grm_geocode` | — | ❌ none | `unless-stopped` |
| `grm_celery_beat` | GRM scheduler | — | ❌ none | `unless-stopped` |
| `grm_ui` / `grm_ui_auth` | Next.js officer UI | 3001/3002 | ❌ none | `unless-stopped` |
| `keycloak` | OIDC IdP | 18080 | ✅ `/health/ready` | `unless-stopped` |
| `ops` 🆕 | **Platform monitor** — APScheduler running health / backup-status / security-scan / daily-report / external-heartbeat | — | self (§4.6) | `unless-stopped` |

**Gap summary:** `restart: unless-stopped` only restarts on *exit*, not on *hang*. Without a container `healthcheck`, a wedged uvicorn/worker/redis stays "up" forever. **Every long-lived container needs a healthcheck** (§4).

There are **two Celery apps** (intentional, per `CLAUDE.md`):
- `backend.task_queue.celery_app` → `llm_queue`, `default`, `file_queue` — no beat.
- `ticketing.tasks.celery_app` → `grm_ticketing`, `grm_geocode` — has Celery Beat (`grm_celery_beat`), runs the SLA watchdog, grievance-sync, escalation, and quarterly report.

**Neither hosts the new ops tasks.** Ops monitoring lives in a third, purpose-built component:

### `ops/` module + `ops` container (the design choice)

- **A standalone `ops/` Python package** — a platform domain owned by neither chatbot nor ticketing. It survives any future reorg or worktree merge.
- **Broker-independent scheduler.** The `ops` container runs **APScheduler** (in-process), *not* Celery. It needs neither a broker nor a result backend, so a Redis/worker outage does not blind it. Results are written **directly to Postgres**; alerts go out via **HTTP to the Messaging API**.
- **Same image, new command.** Reuses the existing `Dockerfile` with `command: python -m ops.scheduler` (~50–80 MB RAM, hard `mem_limit`). No new build pipeline.
- **External-only probing.** It observes every stack over the network/data plane — HTTP `/health`, Redis `INFO`/list-lengths, Postgres `SELECT`, TLS handshake, SMTP — and never imports chatbot/ticketing internals. This avoids coupling and means it doesn't touch the `backend/task_queue/` worktree (which matters for cross-stream merge hygiene, independent of policy).
- **No Docker socket inside the container.** Container supervision/restart and host-level disk/RAM checks are the job of the **host watchdog** (a host cron process that already has Docker + host visibility — §6). Keeping `/var/run/docker.sock` *out* of the `ops` container avoids handing it root-equivalent power. The two components are complementary: the host watchdog acts (restart), the `ops` monitor observes and reports (data-plane health).
- **Dedicated `ops.*` schema + scoped DB role.** Ops storage matches the runtime boundary: a new **`ops` schema** (its own Alembic stream — §5.2) holds `ops.system_health_checks` and `ops.dependency_findings`. The `ops` container connects as a **scoped role** (`ops_app`) with full rights on `ops.*` and **read-only** on the specific `public.*`/`ticketing.*` tables the daily report aggregates — never write access to business data. This realizes the least-privilege goal in [`12_security_monitoring_service.md`](12_security_monitoring_service.md) §3 item 9.

**Boundary note:** adding compose-level `healthcheck:` keys to chatbot worker services (§4.3) is still fine and does not modify `backend/task_queue/` source.

---

## 3. Health model — three layers

| Layer | Mechanism | Recovers? | Detects |
|---|---|---|---|
| **L0 — host watchdog** | Host cron script (Docker + host visibility) → restart unhealthy/exited containers; check host disk/RAM | ✅ auto-restart | container hang/exit, host disk/RAM pressure, dead beat/worker |
| **L1 — container liveness** | Docker `healthcheck` + `restart: unless-stopped` | ✅ auto-restart | crash, hang, unresponsive port |
| **L2 — ops monitor (data plane)** | `ops` container, APScheduler `ops.checks.*` → persist to Postgres, alert via Messaging API | ⚠️ alert only | DB/redis/cert/SMTP/queue/stale-job/endpoint problems |
| **L3 — external dead-man's switch** | `ops` pings a hosted heartbeat URL; provider alerts on *silence* | ❌ external notify | whole-host down, Docker daemon dead, network cut |

L0/L1 keep things running (and don't depend on Redis). L2 catches "up but unhealthy" and **survives a broker outage** because it's not Celery-based. L3 catches "everything is down so nothing internal can warn you". The three acting/observing layers are deliberately decoupled so no single failure (esp. Redis) blinds the monitoring.

---

## 4. L1 — Container healthchecks (compose)

Add a `healthcheck` to every long-lived service. Keep probes cheap (8 GiB host).

### 4.1 HTTP services (orchestrator, backend, UIs)

```yaml
orchestrator:
  healthcheck:
    test: ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=5).status==200 else 1)\""]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 20s
```

`backend` (port 5001, `/health` returns `OK`) uses the same shape. `grm_ui*` can probe `http://localhost:3001/` (Next.js) with a longer `start_period: 40s`.

### 4.2 Redis

```yaml
redis:
  healthcheck:
    # Use -a "$REDIS_PASSWORD" once Redis auth is enabled (see 12_security_monitoring_service.md §3)
    test: ["CMD-SHELL", "redis-cli ping | grep -q PONG"]
    interval: 15s
    timeout: 5s
    retries: 5
```

### 4.3 Celery workers (no port to probe)

Use `celery inspect ping` against the worker's own node. It is heavier than an HTTP probe, so run it less often and give a generous `start_period`.

```yaml
celery_llm:
  healthcheck:
    test: ["CMD-SHELL", "celery -A backend.task_queue.celery_app inspect ping -d celery@$$HOSTNAME --timeout 10 | grep -q pong"]
    interval: 60s
    timeout: 20s
    retries: 3
    start_period: 40s
```

> ⚠️ **DO NOT TOUCH boundary:** §4.3 only adds compose-level `healthcheck:` keys to chatbot worker services — it does **not** modify `backend/task_queue/` source. That is allowed.

`grm_celery` uses the same probe with `-A ticketing.tasks.celery_app.celery_app`.

### 4.4 GRM Celery Beat (no port, no inspect endpoint)

Beat liveness is verified by the `ops` monitor via a **heartbeat key the beat writes** (§6) and checked again by the host watchdog. The container-level check just confirms the process exists:

```yaml
grm_celery_beat:
  healthcheck:
    test: ["CMD-SHELL", "pgrep -f 'celery.*beat' >/dev/null || exit 1"]
    interval: 60s
    timeout: 10s
    retries: 3
    start_period: 30s
```

### 4.5 `depends_on` with `condition: service_healthy`

Once Redis has a healthcheck, upgrade dependents from `condition: service_started` to `service_healthy` so workers/orchestrator don't boot against a not-yet-ready broker.

### 4.6 `ops` monitor container

New service — same image, broker-independent scheduler, minimal privileges (no Docker socket, no published port):

```yaml
ops:
  build: { context: ., dockerfile: Dockerfile }
  command: python -m ops.scheduler
  env_file: [env.local]
  environment:
    POSTGRES_HOST: db
    POSTGRES_PORT: "5432"
    # Scoped least-privilege role: r/w on ops.*, read-only on reporting tables (§5.2).
    POSTGRES_USER: ${OPS_DB_USER:-ops_app}
    POSTGRES_PASSWORD: ${OPS_DB_PASSWORD:?set in env.local}
    POSTGRES_DB: app_db
    # Reaches the data plane over the network — no broker dependency.
    MESSAGING_API_URL: http://backend:5001
  depends_on:
    db:
      condition: service_healthy
  restart: unless-stopped
  mem_limit: 256m          # hard cap on the 8 GiB host
  healthcheck:
    # Scheduler writes ops:scheduler:last_tick to a status file/PG each loop.
    test: ["CMD-SHELL", "python -m ops.selfcheck || exit 1"]
    interval: 60s
    timeout: 10s
    retries: 3
    start_period: 20s
```

It depends only on `db` (and reaches everything else over the network), so it stays up and keeps recording even when Redis or any worker is down.

---

## 5. L2 — Ops monitor checks (data plane)

New module **`ops/checks.py`**, scheduled by **`ops/scheduler.py`** (APScheduler) in the `ops` container. Each check writes a row to `system_health_checks` **directly via SQLAlchemy** (no broker) and, on `warn`/`critical`, emits a deduped alert via the Messaging API (§8). Because it's not Celery, every check still runs and records during a Redis/worker outage.

**Owner split:** the `ops` monitor does **data-plane** checks (reachable over the network/DB). **Host-level** disk/RAM and container restart belong to the host watchdog (L0, §6), which has native host + Docker visibility and avoids mounting the Docker socket into a container.

### 5.1 Checks

| Check (APScheduler job) | Owner | Cadence | Critical threshold (8 GiB host) | Notes |
|---|---|---|---|---|
| `ops.scheduler.tick` | ops | 1 min | — | Writes `ops:scheduler:last_tick` (status file + PG). Self-liveness; read by host watchdog + container healthcheck. |
| `db_connectivity_check` | ops | 5 min | `SELECT 1` fails, or connections > 80% of `max_connections` | Self-hosted PG — we own this. |
| `redis_check` | ops | 5 min | `PING` fails, or `used_memory` > 80% of `maxmemory` | Network probe; broker/result/socket bus. |
| `queue_depth_check` | ops | 5 min | any backlog > N for > 10 min | Reads Redis list lengths for `llm_queue`,`default`,`file_queue`,`grm_ticketing` (read-only). |
| `stale_job_check` | ops | 15 min | task `STARTED` with no terminal status > soft_time_limit×2 | Reads result backend / `task_tracking`; catches wedged LLM/file tasks. |
| `endpoint_check` | ops | 5 min | `/health` non-200 on orchestrator/backend/ticketing/keycloak | Black-box HTTP probe across services. |
| `cert_check` | ops | 1/day | TLS for `grm-chatbot.dor.gov.np` expires < **14 days** | TLS handshake over the network (no cert-file mount needed). Complements TLS-renew cron. |
| `smtp_check` | ops | 1/day | SMTP login/STARTTLS fails | Daily report + Keycloak invites depend on it. Reuse `scripts/ops/test_smtp.py`. |
| `grm_beat_liveness_check` | ops | 5 min | `health:beat:last_run` (written by GRM beat) missing/stale | Detects a dead GRM scheduler → SLA watchdog stops silently. |
| `backup_status_check` | ops | 1/day | last successful DB dump > 26h old, or size anomaly | **Self-hosted** — verifies our own cron (§9) via the status row it writes. |
| `disk_check` | **watchdog (L0)** | 15 min | root FS > **85%** (warn 75%) | Host FS visibility lives on the host; ops only sees its own mounts. |
| `memory_check` | **watchdog (L0)** | 5 min | available RAM < **10%** / heavy swap | Host + per-container RSS; OOM is the #1 risk at 8 GiB. |

> **GRM beat still writes the heartbeat.** Add a tiny `health.heartbeat` task to the *GRM* Celery beat that sets `health:beat:last_run` (EX 180). The ops monitor only *reads* it (`grm_beat_liveness_check`). This is the one heartbeat that intentionally lives on Celery — it's how ops proves the *business* scheduler is alive.

### 5.2 `ops.system_health_checks` table + the `ops` Alembic stream

Ops owns its own schema. A **third Alembic stream** — `ops/migrations/` (version table `alembic_version_ops`, `include_object` scoped to `schema == "ops"`) — manages all `ops.*` DDL, parallel to the existing `ticketing` and `public` streams. See [`../deployment/07_migrations_policy.md`](../deployment/07_migrations_policy.md).

The first revision creates the schema, role, and grants:

```sql
-- Safe to run: only creates/modifies ops.* objects
-- Does NOT touch: grievances, complainants, public.* or ticketing.* tables
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE ops.system_health_checks (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    check_name    text NOT NULL,             -- e.g. 'disk_check'
    status        text NOT NULL,             -- 'ok' | 'warn' | 'critical'
    value_json    jsonb,                     -- measured values (free, util %, counts)
    message       text,
    checked_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_health_checks_name_time
    ON ops.system_health_checks (check_name, checked_at DESC);
```

Scoped role (in the same revision or an ops-managed grants migration):

```sql
-- ops_app: read-only on business data, read/write only within ops.*
GRANT USAGE ON SCHEMA ops TO ops_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ops TO ops_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA ops
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ops_app;
-- Read-only for the daily report aggregation:
GRANT USAGE ON SCHEMA public, ticketing TO ops_app;
GRANT SELECT ON <reporting tables/views in public.* and ticketing.*> TO ops_app;
```

Retention: prune rows > 90 days via `ops.maintenance.prune_health_checks` (§9).

### 5.3 Failure alerting (two paths)

- **GRM business tasks** (escalation / report / grievance-sync): wire a Celery `task_failure` signal handler on the GRM Celery app — a **non-retryable** failure sends a deduped immediate alert (max 1 per signature/hour). These *are* Celery, so a signal is the right hook.
- **Ops checks**: alert **inline** from the `ops` scheduler (try/except around each job), using the same dedupe helper. No Celery signal involved — the monitor owns its own alerting end-to-end.
- **Chatbot workers**: observed externally via `stale_job_check` / `queue_depth_check` / `endpoint_check` (no signal inside `backend/task_queue/`).

---

## 6. Heartbeats & the host watchdog (L0)

Two independent heartbeats, by design:

- **GRM beat heartbeat** — a `health.heartbeat` task on `grm_celery_beat` sets `SET health:beat:last_run <iso8601> EX 180`. Proves the *business* scheduler is alive. Read by `grm_beat_liveness_check` (ops) and the watchdog.
- **Ops scheduler tick** — APScheduler writes `ops:scheduler:last_tick` (status file + PG) every minute. Proves the *monitor* is alive. Read by the `ops` container healthcheck and the watchdog.

### 6.1 `scripts/ops/grm-watchdog.sh` (host cron, every 2–5 min)

The host-side actor — independent of Docker healthchecks and of Redis/Celery, with native Docker + host visibility. Responsibilities:

1. `docker compose ps` → any container `unhealthy`/`exited` → `docker compose restart <svc>` (incl. the `ops` container itself).
2. Redis reachable (`redis-cli ping`); else restart `redis`.
3. **GRM beat** heartbeat (`health:beat:last_run` fresh); else restart `grm_celery_beat`.
4. **Ops scheduler** tick (`ops:scheduler:last_tick` fresh); else restart `ops`. *(The monitor's own guardian — closes the "who watches the watcher" gap.)*
5. Worker liveness (`celery inspect ping`); else restart that worker.
6. **Host disk/RAM** (L0 owners of `disk_check`/`memory_check`, §5.1): read `df`/`free`; on critical, alert + (optional) targeted prune.
7. **Restart-storm guard:** track restarts per service in a state file; if > 3 restarts in 15 min, **stop auto-restarting that service and send a one-time alert** (avoid crash-loop thrash on a small host).
8. Append a structured line to `logs/watchdog.log` (read back into the daily report).

Install via cron (mirror the existing `scripts/ops/install_tls_renew_cron.sh` pattern). The watchdog stays a **host script, not a container**, so it can act even if the Docker Compose project is unhealthy and so it never needs the Docker socket mounted into an app container.

---

## 7. L3 — External monitoring (two free tools, opposite directions)

Internal alerting is useless when the whole box is down. We use **two complementary free SaaS tools** — and they do **opposite** things. The rule of thumb:

> **UptimeRobot = *they* check *you*** (inbound uptime probe). **healthchecks.io = *you* check *in*** (outbound cron dead-man's switch).

Both must be present: an inbound probe catches "the public site is down", and a dead-man's switch catches "the scheduled jobs silently stopped" — neither covers the other.

### 7.1 UptimeRobot — inbound HTTP(s) uptime (they check you)

- **HTTP(s) monitors only.** Point UptimeRobot at the public endpoints — e.g. `https://grm-chatbot.dor.gov.np/health` and the officer UI URL — at a **5-min interval**, with **email on down/recovery**.
- **Do NOT use UptimeRobot Heartbeat/Cron monitors** — those are **paid** on the free plan. UptimeRobot's job here is strictly the inbound HTTP(s) probe.

### 7.2 healthchecks.io — outbound cron dead-man's switch (you check in)

- Sign up → **Add Check** → name the daily/cron job → set the **schedule** (e.g. daily, or a cron expression) **+ 2–4 h grace** → add an **email alert** → copy the **Ping URL** (`https://hc-ping.com/...`).
- The ops scheduler job `external_heartbeat` (every 10 min) and the daily report (§11) do a single **`curl`/GET of the ping URL after the job succeeds**, and **only when the latest local checks are green**. If the job never runs (or the host is down), healthchecks.io alerts the operator on silence past the grace window.
- A failed ping must **never** crash the job — the heartbeat is best-effort.

### 7.3 App/env

Set **`HEARTBEAT_URL`** (canonical) to the healthchecks.io ping URL. The ops config also accepts **`STRATCON_HEARTBEAT_URL`** (shared naming across projects) and the legacy **`HEALTHCHECKS_PING_URL`** as aliases — set **healthchecks.io**, **not** UptimeRobot. Treat the URL as a secret; do not commit it.

---

## 8. Alerting (proto)

| Channel | Trigger | Recipient |
|---|---|---|
| **Email** (immediate) | any `critical` health result; non-retryable task failure | operator (e.g. `philgaeng@pm.me`) |
| **Email** (daily roll-up) | always, 07:00 Asia/Kathmandu | operator |
| **External heartbeat silence** | host fully down | provider → operator |

All email goes through the existing **Messaging API** (`POST /api/messaging/send-email`, SMTP/Infomaniak) — see `05_messaging_service.md`. Immediate alerts are **deduped** (max 1 per signature/hour) so a flapping disk doesn't fill the inbox.

---

## 9. Self-hosted backups & maintenance (we own this)

Because there is **no managed DB**, backup/restore is our responsibility.

### 9.1 DB backup — `scripts/ops/pg-backup.sh` (cron, daily 02:00 Asia/Kathmandu)

```bash
# pg_dump custom format from the db container, gzip, off-box copy, prune
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -F c \
  | gzip > "$BACKUP_DIR/app_db_$(date +%F_%H%M).dump.gz"
```

- **Encrypt at rest** (GPG/age) — `app_db` contains the PII vault (`public.complainants`, encrypted columns + `DB_ENCRYPTION_KEY`). A plaintext dump off-box is a breach surface.
- **Off-box copy** (rsync/rclone to object storage or a second host). A backup on the same 40 GB disk does not survive disk loss.
- **Retention:** daily 7d, weekly 4w, monthly 3–6m. Prune to protect the small disk.
- **Crucial:** the **`DB_ENCRYPTION_KEY` is not in the dump** — back it up separately and securely, or encrypted data is unrecoverable.

### 9.2 Restore drill — `ops.checks.restore_drill` (weekly, ops scheduler)

Periodically `pg_restore` the latest dump into a throwaway scratch DB and assert table counts. An untested backup is not a backup. Records result to `system_health_checks`.

### 9.3 Uploads backup

`uploads_data` volume (`uploads/`, incl. `uploads/ticketing/{ticket_id}/`) holds complainant + officer attachments. Tar + encrypt + off-box, weekly. Production target is object storage (`10_production_server_spec.md`); until then it's on the root disk and must be backed up and disk-monitored.

### 9.4 Maintenance tasks — `ops/maintenance.py` (ops scheduler)

| Task | Cadence | Action |
|---|---|---|
| `ops.maintenance.prune_logs` | daily | Enforce Docker log rotation + prune `logs/*.log` (see `12_…§7`). |
| `ops.maintenance.prune_health_checks` | daily | Delete `system_health_checks` > 90d. |
| `ops.maintenance.prune_uploads_orphans` | weekly | Flag upload files with no DB reference (report-only). |
| `ops.maintenance.vacuum_analyze` | weekly | `VACUUM ANALYZE` on hot tables (off-peak). |
| `ops.maintenance.os_update_check` | weekly | Report available OS security updates (report-only, no auto-apply). |

> `os_update_check` only *reports*. Acting on it (or running `prune_logs` against host-level Docker logs) requires host visibility — where a step needs the host rather than the data plane, implement it in the host watchdog/cron and let the ops scheduler read the result.

---

## 10. Optional lightweight metrics (post-proto)

If richer visibility is needed without the full Prometheus footprint on 8 GiB:

- **cAdvisor + node-exporter + a remote-write** to a hosted Grafana Cloud free tier (no local Grafana/Prometheus storage), **or**
- **Netdata** single container (capped memory), **or**
- **Flower** (`celery flower`) for ad-hoc queue inspection — run on demand, not always-on.

Keep any always-on agent under a hard `mem_limit`.

---

## 11. Daily ops report (spec §18 adaptation)

A new ops job **`ops.reports.daily_ops_report`** — distinct from the existing **quarterly** report (`ticketing.tasks.reports.dispatch_quarterly_report`, which stays on GRM Celery). The daily report is broker-independent: it reads activity straight from Postgres and the watchdog log, and sends via the Messaging API — so it still goes out on a day when Celery is degraded.

### 11.1 Schedule & delivery

- **07:00 Asia/Kathmandu** daily (APScheduler cron trigger, timezone-aware — no UTC conversion needed).
- **Always sends** (even on a quiet day — silence is itself a signal).
- Single recipient (operator); via Messaging API `send-email`.
- On success, pings the external heartbeat (§7).

### 11.2 Content — rolling 24 h window to 07:00

**Activity**
- Grievances submitted (total, by channel, by Standard vs SEAH).
- Tickets created / acknowledged / escalated / resolved.
- SLA breaches in the window + currently-overdue count.
- Officer logins (count + distinct) — *Keycloak-sourced* (`KEYCLOAK_ADMIN_URL` events API), **not** Supabase `auth.audit_log_entries` (that source from the Stratcon spec does not apply here).
- Files uploaded + processing success/failure counts.
- Messaging: SMS/email sent + delivery failures (from messaging logs).

**System health summary**
- Latest status per `ops.checks.*` check (ok/warn/critical) from `system_health_checks`.
- Disk %, RAM %, queue depths, beat last-run age.
- Last successful DB backup time + restore-drill result.
- Dependency/CVE finding counts (from `12_security_monitoring_service.md`).
- Container restart count in the window (from watchdog log).

### 11.3 Format

Plain HTML email body (tables). Optional XLSX attachment via `openpyxl` (already a dep) reusing the quarterly report's attachment path. No pandas.

---

## 12. Environment variables (append to env)

```env
# Health & alerting
HEALTH_ALERT_EMAIL=philgaeng@pm.me
DAILY_REPORT_EMAIL=philgaeng@pm.me
DAILY_REPORT_TZ=Asia/Kathmandu
# L3 dead-man's switch: healthchecks.io ping URL (https://hc-ping.com/...), NOT UptimeRobot (secret).
# HEARTBEAT_URL is canonical; STRATCON_HEARTBEAT_URL / HEALTHCHECKS_PING_URL also accepted.
HEARTBEAT_URL=
# UptimeRobot needs no app env — it probes /health from outside (configure in its dashboard).

# Thresholds (sensible 8 GiB defaults)
HEALTH_DISK_WARN_PCT=75
HEALTH_DISK_CRIT_PCT=85
HEALTH_MEM_CRIT_PCT=90
HEALTH_CERT_WARN_DAYS=14

# Backups (self-hosted)
BACKUP_DIR=/var/backups/grms
BACKUP_GPG_RECIPIENT=             # or age recipient for dump encryption
BACKUP_REMOTE_TARGET=             # rclone/rsync destination (off-box)

# Ops monitor container
MESSAGING_API_URL=http://backend:5001   # ops alerts/reports via Messaging API (HTTP, not broker)
OPS_STATUS_FILE=/tmp/ops_scheduler.tick  # scheduler self-liveness marker (read by healthcheck)
OPS_DB_USER=ops_app                      # scoped least-privilege role (see §5.2)
OPS_DB_PASSWORD=                         # set strong value in env.local
```

(`POSTGRES_*`, `CELERY_BROKER_URL`, `SMTP_*`, `MESSAGING_API_KEY` already exist. The `ops` container deliberately uses HTTP messaging + direct PG and does **not** require the broker.)

---

## 13. Implementation checklist

**`ops` module + container**
- [ ] `ops/` package: `scheduler.py` (APScheduler), `checks.py`, `maintenance.py`, `reports.py`, `alerts.py` (dedupe + Messaging API), `selfcheck.py`.
- [ ] `ops` service in compose (same image, `python -m ops.scheduler`, `mem_limit: 256m`, **no Docker socket**, no published port, depends on `db` only).
- [ ] Add `apscheduler` to `requirements.grm.txt`.

**L0 — host watchdog**
- [ ] `scripts/ops/grm-watchdog.sh` + restart-storm guard + cron installer; supervises all containers incl. `ops`; owns host `disk_check`/`memory_check`.
- [ ] Watchdog reads/restarts on stale `health:beat:last_run` (GRM beat) **and** `ops:scheduler:last_tick` (ops).

**L1 — container healthchecks**
- [ ] Add `healthcheck` to orchestrator, backend, redis, nginx, celery_file/default/llm, grm_celery, grm_celery_beat, grm_ui(_auth), `ops` (§4).
- [ ] Upgrade Redis dependents to `condition: service_healthy`.

**L2 — ops checks**
- [ ] `ops/checks.py` implements the data-plane checks in §5.1 (db/redis/queue/stale-job/endpoint/cert/smtp/grm-beat-liveness/backup-status).
- [ ] New **`ops` Alembic stream** (`ops/migrations/`, `alembic_version_ops`, `include_object` → `schema=='ops'`); update `make migrate_all` + [`07_migrations_policy.md`](../deployment/07_migrations_policy.md).
- [ ] Migration: `CREATE SCHEMA ops` + `ops.system_health_checks` + `ops_app` role/grants (header guard).
- [ ] `health.heartbeat` task added to **GRM** beat (sets `health:beat:last_run`).
- [ ] GRM Celery `task_failure` signal handler → deduped immediate alert (business tasks).
- [ ] Ops inline try/except alerting via `ops/alerts.py`.

**L3 — external (two free tools, §7)**
- [ ] `ops.checks.external_heartbeat` → `HEARTBEAT_URL` (healthchecks.io, green-only); check + email alert + 2–4 h grace configured in healthchecks.io.
- [ ] UptimeRobot HTTP(s) monitors on public `/health` + UI URL (5-min, email on down/recovery). **No** UptimeRobot Heartbeat/Cron (paid).

**Backups / maintenance**
- [ ] `scripts/ops/pg-backup.sh` (encrypt + off-box + prune) + host cron (needs `docker exec`).
- [ ] `DB_ENCRYPTION_KEY` backed up separately and documented.
- [ ] Uploads backup job.
- [ ] `ops.checks.backup_status_check` + weekly `ops.checks.restore_drill`.
- [ ] `ops/maintenance.py` prune/vacuum/os-update-check.

**Daily report**
- [ ] `ops.reports.daily_ops_report` (activity + health) @ 07:00 Asia/Kathmandu (APScheduler cron, tz-aware).
- [ ] Keycloak login-count source wired.
- [ ] External heartbeat ping on success.

---

## 14. Acceptance

- Killing any worker/redis/api container → auto-restarts within one healthcheck interval; watchdog logs it.
- **Stopping Redis** → the `ops` monitor keeps running, still records check results to Postgres, and still emails the critical alert (proves broker-independence).
- Killing the `ops` container → host watchdog restarts it on stale `ops:scheduler:last_tick`.
- Filling disk past `HEALTH_DISK_CRIT_PCT` → `critical` row + immediate alert email.
- Stopping `grm_celery_beat` → watchdog restarts it; `grm_beat_liveness_check` records the gap.
- Daily report arrives at 07:00 Asia/Kathmandu with non-empty activity + health sections, even with Celery degraded.
- External provider alerts when the host is powered off (heartbeat stops).
- A restore drill successfully loads the latest encrypted dump into a scratch DB.
- The `ops` container has **no** `/var/run/docker.sock` mount.
- `ops_app` can write to `ops.*` but a write to any `public.*`/`ticketing.*` table is **denied** (scoped-role check); reads needed for the daily report succeed.
- `alembic -c ops/migrations/alembic.ini heads` returns exactly one head; `alembic_version_ops` exists.
