# Health, Security & Monitoring — Build Progress

**Single source of truth for the ops/monitoring build.** Every agent working from a runbook in this folder **must update this file** as it completes work items (flip status, add a one-line note + commit/PR ref). Do not mark `done` without the acceptance check passing.

**Specs:** [`../11_health_and_monitoring_service.md`](../11_health_and_monitoring_service.md) · [`../12_security_monitoring_service.md`](../12_security_monitoring_service.md)
**Runbooks:** [`ops-foundation-and-health.md`](ops-foundation-and-health.md) · [`security-monitoring-and-hardening.md`](security-monitoring-and-hardening.md)

**Status legend:** ☐ todo · ◐ in progress · ☑ done · ⊘ skipped/won't-do (note why)

---

## Runbook A — Ops foundation & health (spec 11)

### A0. Ops module + container + Alembic stream
| # | Item | Spec | Status | Notes |
|---|------|------|--------|-------|
| A0.1 | `ops/` package skeleton (`scheduler.py`, `checks.py`, `maintenance.py`, `reports.py`, `alerts.py`, `security.py`, `selfcheck.py`, `config.py`, `db.py`, `models.py`) | 11 §2, §13 | ☑ | built; py_compile clean |
| A0.2 | Add `apscheduler` (+ `pip-audit`) to `requirements.grm.txt` | 11 §13 | ☑ | |
| A0.3 | New `ops` Alembic stream (`ops/migrations/`, `alembic_version_ops`, `include_object` → `schema=='ops'`) | 11 §5.2 | ☑ | env runs migrations as admin role |
| A0.4 | Revision 1 (`ops001_init`): `CREATE SCHEMA ops` + `ops.system_health_checks` + `ops_app` role/grants (read-only on reporting tables, guarded) | 11 §5.2 | ☑ | password via `OPS_DB_PASSWORD` |
| A0.5 | `ops` service in compose (same image, `python -m ops.scheduler`, `mem_limit 192m`, **no docker.sock**, no published port, depends on `db`) | 11 §4.6 | ☑ | in `docker-compose.grm.yml` |
| A0.6 | `make migrate_all` includes the ops stream (`migrate_ops`); `07_migrations_policy.md` updated | 11 §13 | ☑ | |
| A0.7 | Env: `MESSAGING_API_URL`, `OPS_STATUS_FILE`, `OPS_DB_USER`, `OPS_DB_PASSWORD`, `HEALTH_ALERT_EMAIL`, `DAILY_REPORT_EMAIL`, `HEALTHCHECKS_PING_URL` | 11 §12 | ◐ | wired in compose; still add to env.local example |

### A1. L1 — container healthchecks
| # | Item | Spec | Status | Notes |
|---|------|------|--------|-------|
| A1.1 | `healthcheck` on orchestrator, backend | 11 §4.1 | ☑ | urllib → /health |
| A1.2 | `healthcheck` on redis | 11 §4.2 | ☑ | `redis-cli ping` |
| A1.3 | `healthcheck` on celery_file/default/llm, grm_celery | 11 §4.3 | ☑ | all 4 workers via `inspect ping` |
| A1.4 | `healthcheck` on grm_celery_beat, grm_ui(_auth), nginx | 11 §4.4 | ☑ | beat=schedule mtime; UIs=node http; nginx=pgrep |
| A1.5 | `healthcheck` on `ops` container (`ops.selfcheck`) | 11 §4.6 | ☑ | tick file < 180s |
| A1.6 | Upgrade Redis dependents to `condition: service_healthy` | 11 §4.5 | ☑ | base + grm overlays |

### A2. L0 — host watchdog
| # | Item | Spec | Status | Notes |
|---|------|------|--------|-------|
| A2.1 | `scripts/ops/host_watchdog.sh` (container supervision + restart) | 11 §6.1 | ☑ | restarts unhealthy/exited |
| A2.2 | Restart-storm guard (state file, >3/15min → stop + alert) | 11 §6.1 | ☑ | per-container state in `$WATCHDOG_STATE_DIR` |
| A2.3 | Host disk/RAM checks (L0 owns `disk_check`/`memory_check`) | 11 §5.1, §6.1 | ☑ | df + free, prune on disk crit |
| A2.4 | Reads stale `ops:scheduler:last_tick` (ops); restarts ops if silent | 11 §6 | ☑ | beat-key read deferred to A3.4/ops |
| A2.5 | Cron installer (`install_watchdog_cron.sh`, mirrors TLS one) | 11 §6.1 | ☑ | every 5 min |

### A3. L2 — ops checks (data plane)
| # | Item | Spec | Status | Notes |
|---|------|------|--------|-------|
| A3.1 | `db_connectivity_check`, `redis_check`, `queue_depth_check` | 11 §5.1 | ☑ | |
| A3.2 | `stale_job_check`, `endpoint_check` | 11 §5.1 | ☑ | stale_job best-effort (grant-gated) |
| A3.3 | `cert_check`, `smtp_check` | 11 §5.1 | ☑ | smtp reads `SMTP_*` env |
| A3.4 | `grm_beat_liveness_check` (reads heartbeat key) | 11 §5.1 | ☑ | reads `health:beat:last_run` (db0) |
| A3.5 | `beat_heartbeat` task added to **GRM** beat (sets `health:beat:last_run`) | 11 §5.1, §6 | ☑ | `ticketing/tasks/ops_heartbeat.py`, every 60s |
| A3.6 | Results persisted to `ops.system_health_checks` via `ops_app` | 11 §5.2 | ☑ | `ops/db.py::record_check` |
| A3.7 | Inline dedup alerting (`ops/alerts.py`, max 1/signature/hour) | 11 §5.3, §8 | ☑ | in-process dedup |
| A3.8 | GRM Celery `task_failure` signal → immediate alert (business tasks) | 11 §5.3 | ☑ | `@task_failure.connect` in celery_app; heartbeat excluded |

### A4. L3 — external dead-man's switch
| # | Item | Spec | Status | Notes |
|---|------|------|--------|-------|
| A4.1 | `external_heartbeat` ping (green-only) → `HEALTHCHECKS_PING_URL` | 11 §7 | ☑ | every 10 min + after daily report |
| A4.2 | Provider configured (healthchecks.io / UptimeRobot) | 11 §7 | ☐ | ops/manual — set `HEALTHCHECKS_PING_URL` |

### A5. Backups & maintenance (self-hosted)
| # | Item | Spec | Status | Notes |
|---|------|------|--------|-------|
| A5.1 | `scripts/ops/backup_db.sh` (pg_dump + uploads tar + prune + GPG encrypt + off-box) | 11 §9.1 | ☑ | `BACKUP_GPG_RECIPIENT`/`BACKUP_PASSPHRASE`/`BACKUP_REMOTE` |
| A5.2 | `DB_ENCRYPTION_KEY` backed up separately + documented | 11 §9.1 | ☑ | `docs/deployment/14_key_and_secret_lifecycle.md`; fp recorded in status |
| A5.3 | Uploads backup job (encrypt + off-box, weekly) | 11 §9.3 | ◐ | in `backup_db.sh`; uploads tar still plain (dump encrypted) |
| A5.4 | `ops.checks.backup_status_check` + weekly `restore_drill` (`scripts/ops/restore_drill.sh`) | 11 §9.2 | ☑ | checks read status JSONs |
| A5.5 | `ops/maintenance.py`: prune_logs / prune_health_checks / prune_uploads_orphans / vacuum_analyze / os_update_check | 11 §9.4 | ◐ | prune_health_checks/vacuum real; others report-only |

### A6. Daily ops report
| # | Item | Spec | Status | Notes |
|---|------|------|--------|-------|
| A6.1 | `ops.reports.daily_ops_report` @ 07:00 Asia/Kathmandu (tz-aware) | 11 §11 | ☑ | CronTrigger tz-aware |
| A6.2 | Activity section (grievances/tickets/SLA/files/messaging) | 11 §11.2 | ◐ | added SLA episodes + files + logins; messaging-volume omitted |
| A6.3 | Officer login count from Keycloak events API | 11 §11.2 | ☑ | `keycloak.event_entity` LOGIN (best-effort) |
| A6.4 | Health + backup + dependency summary section | 11 §11.2 | ☑ | health table (incl. backup_status check) + security signals |
| A6.5 | Always-sends + pings external heartbeat on success | 11 §11.1 | ☑ | |

---

## Runbook B — Security monitoring & hardening (spec 12)

### B1. Dependency / CVE monitoring
| # | Item | Spec | Status | Notes |
|---|------|------|--------|-------|
| B1.1 | `ops.dependency_findings` table (ops Alembic stream, `ops002_depfindings`) | 12 §2.2 | ☑ | dedupe unique constraint |
| B1.2 | `ops/security.py` → `dependency_scan` (pip-audit primary) | 12 §2.1 | ☑ | upsert + auto-resolve, report-only |
| B1.3 | npm audit (ticketing-ui) + optional Dependabot/Trivy | 12 §2.1 | ◐ | `scripts/ops/npm_audit.sh` + ingest in `dependency_scan`; Dependabot/Trivy still optional |
| B1.4 | `ops.security.pg_security_check` (Advisors substitute) | 12 §3 item 8 | ☑ | superuser/idle-txn/long-query checks |

### B2. Hardening backlog (prioritized)
| # | Item | Pri | Spec | Status | Notes |
|---|------|-----|------|--------|-------|
| B2.1 | Redis auth (`requirepass` + broker URLs + healthcheck `-a`) | 🔴 | 12 §3.1 | ☑ | opt-in via `REDIS_PASSWORD`; backward-compatible empty default |
| B2.2 | CORS allowlist (both FastAPI apps + nginx) | 🔴 | 12 §3.2 | ☑ | env `CORS_ALLOWED_ORIGINS`; nginx `*`→host; `*`+creds bug fixed |
| B2.3 | Non-default DB creds in prod + preflight assert | 🔴 | 12 §3.3 | ☑ | preflight asserts `POSTGRES_PASSWORD != password` |
| B2.4 | Container healthchecks | 🟠 | 12 §3.4 | ☑ | Runbook A §A1 complete |
| B2.5 | Bypass-auth prod assert | 🟠 | 12 §3.5 | ☑ | in `security-preflight.sh` |
| B2.6 | nginx rate limiting (public + token routes) | 🟠 | 12 §3.6 | ☑ | `public`/`uploads` zones on /message, uploads, /api/v1/scan |
| B2.7 | Docker log rotation + log prune | 🟠 | 12 §3.7 | ☑ | `x-logging` anchor (all services) + logrotate conf + prune_logs |
| B2.8 | Least-privilege DB roles (`ops_app` first) | 🟡 | 12 §3.9 | ☑ | `ops_app` shipped; opt-in `create_scoped_roles.sql` for the rest |
| B2.9 | Key rotation + `DB_ENCRYPTION_KEY` separate backup | 🟡 | 12 §3.10 | ☑ | `docs/deployment/14_key_and_secret_lifecycle.md` |
| B2.10 | nginx security headers + `server_tokens off` | 🟡 | 12 §3.11 | ☑ | HSTS, nosniff, frame-options, referrer-policy |
| B2.11 | Host hardening runbook (ufw/fail2ban/unattended-upgrades) | 🟢 | 12 §3.12 | ☑ | `docs/deployment/15_host_hardening.md` |
| B2.12 | `ops` monitor least-privilege preserved (no docker.sock, mem-capped) | 🟢 | 12 §3.13 | ☑ | no socket, `mem_limit 192m`; preflight asserts no docker.sock |

### B3. Preflight gate
| # | Item | Spec | Status | Notes |
|---|------|------|--------|-------|
| B3.1 | `scripts/ops/security-preflight.sh` (all §4 asserts) | 12 §4 | ☑ | bypass/secrets/CORS/cert/ports/socket/backup; writes status JSON |
| B3.2 | Wired into deploy / Makefile | 12 §4 | ☑ | `make security-preflight` |
| B3.3 | Security section folded into daily ops report | 12 §5 | ☑ | deps + failed logins + reveals + preflight status |

---

## Deviations / decisions log

| Date | Item | Decision | By |
|------|------|----------|-----|
| 2026-06-23 | Schema for ops tables | Dedicated `ops.*` schema + `ops_app` role (was `ticketing.*`) | spec authoring |
| 2026-06-23 | Scheduler | Broker-independent APScheduler in own `ops` container (not Celery beat) | spec authoring |
| 2026-06-23 | `ops` mem_limit | `192m` (spec said 256m) — fits 8 GiB headroom; APScheduler footprint is small | build |
| 2026-06-23 | Beat heartbeat store | `health:beat:last_run` written to Redis **db0** (derived from broker host); ops reads `REDIS_URL` db0 | build |
| 2026-06-23 | ops Alembic auth | ops migrations run as admin (`POSTGRES_*`) not `ops_app`, since they create schema/role/grants | build |
| 2026-06-23 | Backups encryption | `backup_db.sh` now GPG-encrypts the dump + optional off-box copy (uploads tar still plain) | build |
| 2026-06-23 | Redis auth | Backward-compatible: `${REDIS_PASSWORD:-}` everywhere → empty=plain (dev), set=`requirepass`+auth URLs (prod). No hard cutover | build |
| 2026-06-23 | CORS | Empty `CORS_ALLOWED_ORIGINS` → `["*"]` with `allow_credentials=False` (fixes invalid `*`+creds); set → allowlist + credentials | build |
| 2026-06-23 | Scoped DB roles | `ops_app` enforced via migration; chatbot/ticketing/keycloak roles ship as opt-in SQL (app still connects as `user` until repointed) | build |
| 2026-06-23 | Verification | Docker unavailable in this env — compose validated via YAML parse only; needs `docker compose config` + live smoke before prod | build |
