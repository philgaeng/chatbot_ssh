# Agent: Security monitoring & hardening

**Copy this entire file into a new Cursor agent session.** Prereq: **Runbook A** (`ops` module + `ops` Alembic stream + container) must already exist — this runbook adds to it.

## Mission

Implement the security monitoring + hardening backlog in [`../12_security_monitoring_service.md`](../12_security_monitoring_service.md):

- daily, report-only **dependency/CVE scanning** on the `ops` scheduler,
- a self-hosted **pg security check** (Supabase-Advisors substitute),
- the **hardening backlog** (Redis auth, CORS allowlist, non-default creds, rate limiting, log rotation, security headers, least-privilege roles, key lifecycle),
- a **`security-preflight.sh`** gate that blocks promotion on insecure config.

**Deployment reality:** single Ubuntu host, 2 vCPU / 8 GiB, Docker Compose, self-hosted Postgres + Redis. Report-first posture (no auto-upgrade, no auto-block) for proto.

**Track progress in [`PROGRESS.md`](PROGRESS.md) (Runbook B).** Flip statuses as you go.

---

## Guardrails

- Several hardening items **deliberately** touch stable shared services (`backend/api/`, `ticketing/api/`, `deployment/nginx/`, `docker-compose.yml`, `env.local`). Per the updated `CLAUDE.md` these are **care boundaries**, not off-limits — but change them **deliberately, with tests**, and keep each item in its own commit so it's easy to revert.
- 🔴 items can break the running stack (Redis auth, CORS). Apply + verify locally before prod; coordinate env changes.
- New scanning/monitoring code lives under **`ops/`**; new tables use the **`ops` Alembic stream**.
- Report-only: scans must **never** auto-modify dependencies or block deploys (except the explicit preflight gate, which is opt-in at promotion time).
- Don't commit unless asked. Don't commit secrets.

---

## Read first (in order)

| File | Why |
|------|-----|
| [`../12_security_monitoring_service.md`](../12_security_monitoring_service.md) | The spec — build to it |
| [`../11_health_and_monitoring_service.md`](../11_health_and_monitoring_service.md) §2, §4.6, §5.2 | `ops` module/container/schema you extend |
| [`../../deployment/13_security.md`](../../deployment/13_security.md) | As-built controls + §14 preflight checklist to automate |
| `backend/api/fastapi_app.py`, `ticketing/api/main.py` | CORS allowlist fix (item 2) — both have `allow_origins=["*"]` |
| `docker-compose.yml`, `docker-compose.grm.yml`, `docker-compose.prod.yml` | Redis auth, log rotation, healthchecks |
| `deployment/nginx/webchat_rest_compose_prod.tls.conf` | Rate limiting + security headers + `server_tokens off` |
| `requirements.txt`, `requirements.grm.txt`, `channels/ticketing-ui/package.json` | Scan targets |

---

## Implementation — Phase B1: dependency / CVE monitoring

1. **`ops.dependency_findings`** table — new revision in the **ops** Alembic stream (`ops/migrations/versions/ops00X_dependency_findings.py`), header `# only ops.*`, schema per spec §2.2 (unique on `(source, package, advisory_id)`). **(PROGRESS B1.1)**
2. **`ops/security.py` → `dependency_scan`** job (registered on `ops/scheduler.py`, daily off-peak): run `pip-audit` against the installed env (primary), parse JSON, upsert into `ops.dependency_findings` (bump `last_seen`, set `resolved_at` when gone). Report-only. **(B1.2)**
3. Add `npm audit --json` for `channels/ticketing-ui` (run in CI or against the UI image) and optional Dependabot alerts API (`GET /repos/philgaeng/chatbot_ssh/dependabot/alerts` with `GITHUB_TOKEN`) + optional Trivy image scan. Dedupe by source. **(B1.3)**
4. **`ops.checks.pg_security_check`** (§3 item 8): report-only pg checks — over-privileged roles, missing expected grants/RLS, long-running/idle-in-transaction, connection saturation, missing-index hot queries (`pg_stat_statements` if enabled). Writes `ops.system_health_checks`. **(B1.4)**

**B1 acceptance:** `dependency_scan` populates `ops.dependency_findings`; daily report (A6.4) shows new/open critical counts.

## Phase B2 — hardening backlog (one commit per item)

> Order: 🔴 first (correctness/breakage risk), then 🟠, 🟡, 🟢.

5. **🔴 Redis auth** (item 1): set `requirepass` via `REDIS_PASSWORD`; update `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`/`SOCKETIO_REDIS_URL` to `redis://:<pw>@redis:6379/...` across all compose files + the `ops` redis probe; update Redis healthcheck to `redis-cli -a "$REDIS_PASSWORD" ping`. Verify Celery + sockets + ops `redis_check` still work. **(B2.1)**
6. **🔴 CORS allowlist** (item 2): replace `allow_origins=["*"]` in `backend/api/fastapi_app.py` and `ticketing/api/main.py` with an env-driven allowlist (`CORS_ALLOWED_ORIGINS`); drop blanket `Access-Control-Allow-Origin *` for authenticated nginx routes. **(B2.2)**
7. **🔴 Non-default DB creds** (item 3): ensure prod sources `POSTGRES_*`/`DATABASE_URL` from env (not compose `user`/`password` defaults); add the assert to the preflight script (B3). **(B2.3)**
8. **🟠 Container healthchecks** (item 4) — already delivered by Runbook A §A1; just verify + tick. **(B2.4)**
9. **🟠 Bypass-auth prod assert** (item 5): preflight asserts served UI build has `NEXT_PUBLIC_BYPASS_AUTH=false` and `demo` profile not active. **(B2.5)**
10. **🟠 nginx rate limiting** (item 6): `limit_req_zone`/`limit_conn_zone` for public `/message`, upload, QR `scan/{token}`, public-closure routes; stricter caps on token + upload. **(B2.6)**
11. **🟠 Docker log rotation** (item 7): per-service `logging: { driver: json-file, options: { max-size: "10m", max-file: "5" } }` (or daemon-global); wire `ops.maintenance.prune_logs` + logrotate for `logs/*.log`. **(B2.7)**
12. **🟡 Least-privilege DB roles** (item 9): `ops_app` already shipped in Runbook A — extend with scoped chatbot/ticketing/keycloak roles where feasible. **(B2.8)**
13. **🟡 Key lifecycle** (item 10): document rotation cadence; ensure `DB_ENCRYPTION_KEY` separate secure backup (ties to A5.2). **(B2.9)**
14. **🟡 nginx security headers** (item 11): HSTS, `X-Content-Type-Options: nosniff`, frame-ancestors/CSP, `server_tokens off`. **(B2.10)**
15. **🟢 Host hardening runbook** (item 12): document ufw/fail2ban/unattended-upgrades; surface failed-login counts in daily report. **(B2.11)**
16. **🟢 ops least-privilege preserved** (item 13): assert no app/monitor container mounts `/var/run/docker.sock`; `ops` keeps `mem_limit`. **(B2.12)**

## Phase B3 — preflight gate

17. **`scripts/ops/security-preflight.sh`** (§4): assert all of — bypass-auth false; Keycloak issuer + auth containers; `REDIS_PASSWORD`/`TICKETING_SECRET_KEY`/`MESSAGING_API_KEY`/`KEYCLOAK_WEBHOOK_SECRET`/`DB_ENCRYPTION_KEY` set & non-default; `POSTGRES_PASSWORD != password`; CORS not `*` for credentialed APIs; TLS cert > 14 days; no `:6379`/`:5432` published publicly; no `docker.sock` in app/monitor containers; latest DB backup < 26h + restore drill green. **Non-zero exit on any violation.** **(B3.1)**
18. Wire into deploy / Makefile target. **(B3.2)**
19. Fold the security signals into the daily ops report (§5): new/open critical findings, failed logins, fail2ban bans, contact-reveal volume, webhook auth rejections, preflight last-run status. **(B3.3, builds on A6.4)**

**B3 acceptance:** `security-preflight.sh` exits non-zero when any default secret / bypass / stale-cert / open-port / docker-socket condition is present; exits 0 on a clean prod config.

---

## Definition of done

- All Runbook B items in [`PROGRESS.md`](PROGRESS.md) are `☑` with acceptance notes.
- Spec §8 acceptance criteria pass (Redis rejects unauth; prod APIs reject disallowed Origin; preflight fails on insecure config; logs no longer unbounded).
- Each hardening item is a separate, revertable commit.
- Update [`PROGRESS.md`](PROGRESS.md) deviations log for anything skipped (note why, esp. 🟢/ops-manual items).
