# Services — agent runbooks (health / security / monitoring)

Self-contained build runbooks for the **platform ops layer** (specs [`11_health_and_monitoring_service.md`](../11_health_and_monitoring_service.md) + [`12_security_monitoring_service.md`](../12_security_monitoring_service.md)).

**How to use:** copy **one** runbook into a fresh agent session and run it in phase order. Build **A before B** (B reuses the `ops` module + Alembic stream from A).

| Runbook | Spec | Scope | Progress |
|---------|------|-------|----------|
| [`ops-foundation-and-health.md`](ops-foundation-and-health.md) | [`11_…`](../11_health_and_monitoring_service.md) | `ops/` module + container + `ops` schema/role, container healthchecks, host watchdog, data-plane health checks, backups + restore drill, daily ops report | [`PROGRESS.md`](PROGRESS.md) → Runbook A |
| [`security-monitoring-and-hardening.md`](security-monitoring-and-hardening.md) | [`12_…`](../12_security_monitoring_service.md) | dependency/CVE scan, pg security check, hardening backlog (Redis auth, CORS, rate limiting, log rotation, headers, least-privilege), preflight gate | [`PROGRESS.md`](PROGRESS.md) → Runbook B |

## Progress tracking (required)

[`PROGRESS.md`](PROGRESS.md) is the **single source of truth** for this build. Every agent **must**:

1. Read it at session start to see what's already done / in progress.
2. Flip an item to ◐ when starting it, ☑ when its acceptance check passes (with a one-line note + commit/PR ref).
3. Record any spec departure in the **Deviations / decisions log**.

Do not mark an item `done` without its acceptance check passing. Keep one commit per hardening item (Runbook B) so changes are easy to revert.

## Key constraints (from the specs)

- The `ops` monitor is **broker-independent** (APScheduler, not Celery) and runs in its **own container** — never mounts `/var/run/docker.sock`, stays `mem_limit: 256m`.
- Ops data lives in a **dedicated `ops.*` schema** (third Alembic stream) with a scoped **`ops_app`** role.
- Host-level supervision (restart, disk/RAM) is the **host watchdog** (L0); the ops container does data-plane checks only.
