# Security Monitoring & Hardening Spec

**Status:** Proposed (build target). Companion to [`11_health_and_monitoring_service.md`](11_health_and_monitoring_service.md). Adapts Stratcon `CELERY_REDIS_TASK_QUEUE_SPEC §17/§19` (dependency monitoring) to the **self-hosted** Nepal GRM stack and adds hardening items found by screening the codebase.
**Deployment reality:** single Ubuntu host, 2 vCPU / 8 GiB, Docker Compose, self-hosted Postgres + Redis. **No Supabase Advisors** — its DB-advisor checks from the source spec do not apply; we substitute self-hosted equivalents.
**Authoritative index of *implemented* controls:** [`../deployment/13_security.md`](../deployment/13_security.md). This document covers **monitoring of** security posture + **gaps to close**; it does not restate what `13_security.md` already documents as built.

---

## 1. Scope

1. **Continuous security monitoring** — dependency/CVE scanning, secret-exposure checks, auth-failure surfacing.
2. **Hardening backlog** — concrete fixes for weaknesses found in the current codebase (§3), prioritized.
3. **Reporting** — fold security signals into the daily ops report (`11_…§11`).

Everything here is **report-first** (no auto-upgrade, no auto-block) for proto, matching the source spec's posture.

---

## 2. Dependency & CVE monitoring (spec §17 adaptation)

New ops job **`ops.security.dependency_scan`** (daily, off-peak), scheduled by the broker-independent `ops` scheduler (see [`11_…§2`](11_health_and_monitoring_service.md)), report-only, results deduped into a new table.

### 2.1 Sources

| Source | Covers | How |
|---|---|---|
| **`pip-audit`** (primary) | Python deps in the running image (`requirements.txt`, `requirements.grm.txt`) | Run against the installed env — reflects what's actually deployed, not just the pin file. |
| **`npm audit --json`** | `channels/ticketing-ui` (Next.js 16) frontend deps | Run in the UI image / CI. The chatbot stack is Python; the officer UI is the npm surface. |
| **GitHub Dependabot alerts API** (optional) | Repo-wide, incl. transitive | `GET /repos/philgaeng/chatbot_ssh/dependabot/alerts` with existing `GITHUB_TOKEN`, if the repo has alerts enabled. |
| **Trivy image scan** (optional) | OS packages in `python:*`, `postgres:15`, `redis:7`, `nginx`, `keycloak`, `node` base images | Base-image OS CVEs (a real surface on a long-lived single host). Run in CI or weekly. |

> ❌ **Not applicable:** the source spec's `health.supabase_advisors` and Supabase-managed backup checks. We are self-hosted — substitute `pg`-side checks (§3 item 8) and our own backup verification (`11_…§9`).

### 2.2 `ops.dependency_findings` table

Lives in the dedicated **`ops` schema** (its own Alembic stream — see [`11_…§5.2`](11_health_and_monitoring_service.md) and [`../deployment/07_migrations_policy.md`](../deployment/07_migrations_policy.md)).

```sql
-- Safe to run: only creates/modifies ops.* objects
-- Does NOT touch: grievances, complainants, public.* or ticketing.* tables
CREATE TABLE ops.dependency_findings (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source        text NOT NULL,           -- 'pip-audit' | 'npm' | 'dependabot' | 'trivy'
    package       text NOT NULL,
    installed_ver text,
    advisory_id   text,                    -- CVE / GHSA
    severity      text,                    -- 'low'|'moderate'|'high'|'critical'
    fixed_in      text,
    first_seen    timestamptz NOT NULL DEFAULT now(),
    last_seen     timestamptz NOT NULL DEFAULT now(),
    resolved_at   timestamptz,
    UNIQUE (source, package, advisory_id)
);
```

Dedupe by `(source, package, advisory_id)`; bump `last_seen` on re-detection; set `resolved_at` when no longer reported. Daily report shows **new** + **open critical/high** counts.

---

## 3. Hardening backlog — findings from codebase screening

Ranked by risk on this single-host deployment. Each item: what was found, why it matters, fix.

### 🔴 1. Redis has no authentication
- **Found:** every compose file sets `REDIS_PASSWORD: ""`; `redis:7` runs with no `requirepass`. Redis is the Celery broker, result backend, **and** Socket.IO bus.
- **Risk:** any process/container that reaches the Docker network can read/write the broker → inject/inspect tasks, read cached results, disrupt sockets. On a shared host this is a real lateral-movement path.
- **Fix:** set `requirepass` (strong secret), populate `REDIS_PASSWORD`, and update `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`/`SOCKETIO_REDIS_URL` to `redis://:<pw>@redis:6379/...`. Update the Redis healthcheck to `redis-cli -a "$REDIS_PASSWORD" ping`. Never expose 6379 on a host port in prod.

### 🔴 2. Permissive CORS (`*` + credentials) on both FastAPI apps
- **Found:** `backend/api/fastapi_app.py` and `ticketing/api/main.py` both use `allow_origins=["*"]`, `allow_credentials=True`, `allow_methods=["*"]`. `ticketing/api/main.py:64` already flags this with an `INTEGRATION POINT` to-do. The prod nginx conf also adds `Access-Control-Allow-Origin *` on every block.
- **Risk:** `*` + credentials is contradictory (browsers reject the combo for credentialed requests, and it signals an over-broad policy). Allows any origin to call APIs with cookies/Authorization in scenarios where it *is* honored.
- **Fix:** restrict `allow_origins` to the known UI/chatbot origins (`https://grm-chatbot.dor.gov.np`) via an env-driven allowlist; drop the blanket `Access-Control-Allow-Origin *` in nginx for authenticated routes.

### 🔴 3. Default DB credentials baked into compose
- **Found:** `POSTGRES_USER: user` / `POSTGRES_PASSWORD: password` / `DATABASE_URL=postgresql://user:password@db:5432/...` hardcoded across `docker-compose.yml` and the GRM overlay.
- **Risk:** trivially guessable creds. Fine for WSL dev; a breach surface if they reach prod unchanged.
- **Fix:** in prod, source all `POSTGRES_*`/`DATABASE_URL` from env (`env.local`, gitignored — confirmed) with strong generated values; never rely on compose defaults. Add a pre-promotion check that asserts non-default creds (§4).

### 🟠 4. No container healthchecks on most services → silent hangs
- **Found:** orchestrator, backend, redis, nginx, and all Celery workers + beat have **no** `healthcheck`. `restart: unless-stopped` only restarts on exit, not hang.
- **Risk:** a wedged worker/api appears "up" indefinitely; security-relevant tasks (SLA watchdog, future health/scan tasks) silently stop.
- **Fix:** see `11_…§4`.

### 🟠 5. `NEXT_PUBLIC_BYPASS_AUTH` demo bypass
- **Found:** `grm_ui` (:3001) ships `NEXT_PUBLIC_BYPASS_AUTH=true` (mock super-admin). Documented as demo-only in `13_security.md`.
- **Risk:** if a bypass build is ever deployed to prod, auth is fully off.
- **Fix:** prod uses `grm_ui_auth` (:3002, bypass false) only; the `demo` profile must not be enabled in prod. Add a pre-promotion assert (§4) that the served UI build has bypass disabled.

### 🟠 6. No rate limiting on public endpoints
- **Found:** prod nginx conf (`webchat_rest_compose_prod.tls.conf`) has no `limit_req`/`limit_conn`. Public surfaces include chatbot `/message`, file upload, QR `GET /api/v1/scan/{token}`, and public closure token pages.
- **Risk:** token brute-force (scan/closure tokens), upload flooding (disk exhaustion on 40 GB), LLM-cost abuse via `/message`.
- **Fix:** add `limit_req_zone`/`limit_conn_zone` for public locations; stricter caps on token + upload routes. `13_security.md §9` already lists token rate-limiting as "planned at edge" — implement it here.

### 🟠 7. Docker log growth / no rotation → disk-fill DoS
- **Found:** no `logging:` driver options in compose; `logs/` already large (per directory listing). Default `json-file` driver grows unbounded.
- **Risk:** on a 40–50 GB disk, unbounded container + app logs can fill the disk and take the host down (and destroy `health.disk_check`'s headroom).
- **Fix:** set per-service `logging: { driver: json-file, options: { max-size: "10m", max-file: "5" } }` (or configure the daemon globally) + `maintenance.prune_logs` (`11_…§9.4`) + logrotate for `logs/*.log`.

### 🟡 8. No self-hosted DB security/health checks (Supabase Advisors substitute)
- **Found:** since we don't use Supabase, none of its security/performance advisors exist.
- **Fix:** add lightweight `pg`-side checks (report-only) as `ops.checks.*` jobs: roles with excessive privileges, tables without expected RLS/grants, `pg_stat_activity` long-running/idle-in-transaction, connection saturation, missing-index hot queries (via `pg_stat_statements` if enabled). Surfaces the same class of signal Advisors would.

### 🟡 9. Least-privilege DB roles not enforced
- **Found:** app connects as superuser-ish `user`; `13_security.md` lists least-privilege roles as an "ops target".
- **Risk:** a compromised app component has full DB rights (incl. the PII vault).
- **Fix:** create scoped roles — chatbot/backend role limited to `public.*`, ticketing role limited to `ticketing.*` (+ read paths it needs), Keycloak role limited to its schema, and **`ops_app`** limited to r/w on `ops.*` + read-only on the reporting tables (already specified in [`11_…§5.2`](11_health_and_monitoring_service.md) — implement it as the first scoped role since it ships with the new `ops` schema). Aligns with `CLAUDE.md` schema-ownership rules.

### 🟡 10. Encryption-key & secret lifecycle
- **Found:** `DB_ENCRYPTION_KEY`, `TICKETING_SECRET_KEY`, `MESSAGING_API_KEY`, `KEYCLOAK_WEBHOOK_SECRET` via env (good); no documented rotation or key-backup procedure.
- **Risk:** losing `DB_ENCRYPTION_KEY` = permanent PII loss; leaking shared secrets = forged webhooks/messaging.
- **Fix:** document rotation cadence + secure separate backup of `DB_ENCRYPTION_KEY` (tie to `11_…§9.1`). Consider a host secret store (e.g. `docker secrets`/`age`-encrypted env) over plaintext `env.local` in prod.

### 🟡 11. nginx TLS / security headers
- **Found:** TLS is `TLSv1.2 TLSv1.3` (good). Missing: HSTS, `X-Content-Type-Options`, `X-Frame-Options`/CSP, `server_tokens off`.
- **Fix:** add HSTS (`Strict-Transport-Security`), `X-Content-Type-Options: nosniff`, frame-ancestors/CSP appropriate for the UI, and `server_tokens off`.

### 🟢 12. Host hardening (ops)
- **Fix (runbook):** `ufw` (allow 22/80/443 only), SSH key-only + `fail2ban` on `sshd`, unattended security updates, Docker daemon not exposed on TCP, non-root containers where feasible. Surface `fail2ban`/`auth.log` failed-login counts in the daily report.

### 🟢 13. Keep the new `ops` monitor least-privilege
- **Design (not a gap — a constraint to preserve):** the `ops` container (`11_…§4.6`) is intentionally minimal — **no `/var/run/docker.sock` mount** (Docker socket = root-equivalent), `mem_limit: 256m`, no published port, `depends_on: db` only, reaches everything else over the network. Container restart/host-level actions stay in the **host watchdog** (a host process), not in a container.
- **Risk if violated:** mounting the Docker socket into `ops` to "make checks easier" would turn the monitor into a high-value root-equivalent target. Don't.
- **Fix:** treat "no docker socket in any app/monitor container" as a preflight assertion (§4).

---

## 4. Security verification gate (pre-promotion)

Automate `13_security.md §14` as a script (`scripts/ops/security-preflight.sh`) run before staging/prod promotion. Asserts:

- [ ] `NEXT_PUBLIC_BYPASS_AUTH` is **false** in the served UI build; `demo` profile not active.
- [ ] `KEYCLOAK_ISSUER` set + auth containers up.
- [ ] `REDIS_PASSWORD`, `TICKETING_SECRET_KEY`, `MESSAGING_API_KEY`, `KEYCLOAK_WEBHOOK_SECRET`, `DB_ENCRYPTION_KEY` set and **not** default/empty.
- [ ] `POSTGRES_PASSWORD` ≠ `password` (no compose default).
- [ ] CORS allowlist is not `*` for credentialed APIs in prod.
- [ ] TLS cert valid + > 14 days remaining.
- [ ] No `:6379` / `:5432` published on a public host port.
- [ ] No app/monitor container mounts `/var/run/docker.sock` (item 13).
- [ ] Latest DB backup < 26h old and restore drill green.

Fail the gate (non-zero exit) on any violation.

---

## 5. Security signals in the daily ops report

Fold into `11_…§11.2`:

- New + open **critical/high** dependency findings (count + top items).
- Failed officer logins / Keycloak auth errors in the window.
- Host SSH failed-login + `fail2ban` ban count.
- Contact-reveal events (`13_security.md §7`) — volume + any anomaly.
- Webhook auth rejections (`X-Ticketing-Secret` / `X-Keycloak-Webhook-Secret` failures).
- Preflight gate status (last run pass/fail).

---

## 6. Environment variables (append to env)

```env
# Security monitoring
GITHUB_TOKEN=                     # optional: Dependabot alerts API (reuse existing)
SECURITY_ALERT_EMAIL=philgaeng@pm.me
DEP_SCAN_FAIL_ON=critical         # report-only; informational severity gate for the report

# Hardening (see §3)
REDIS_PASSWORD=                   # item 1 — set strong value
CORS_ALLOWED_ORIGINS=https://grm-chatbot.dor.gov.np   # item 2
```

---

## 7. Implementation checklist

**Monitoring**
- [ ] `ops/security.py` → `dependency_scan` (pip-audit primary; npm/Dependabot/Trivy optional), scheduled by the `ops` scheduler.
- [ ] Migration: `ops.dependency_findings` (new `ops` Alembic stream, header guard).
- [ ] `ops.checks.pg_security_check` (§3 item 8) — Advisors substitute.
- [ ] Security section in daily ops report (§5).

**Hardening (prioritized)**
- [ ] 🔴 Redis auth (`requirepass` + broker URLs + healthcheck).
- [ ] 🔴 CORS allowlist (both FastAPI apps + nginx).
- [ ] 🔴 Non-default DB creds in prod + preflight assert.
- [ ] 🟠 Container healthchecks (`11_…§4`).
- [ ] 🟠 Bypass-auth prod assert.
- [ ] 🟠 nginx rate limiting on public/token routes.
- [ ] 🟠 Docker log rotation + log prune.
- [ ] 🟡 Least-privilege DB roles.
- [ ] 🟡 Key rotation + `DB_ENCRYPTION_KEY` separate backup.
- [ ] 🟡 nginx security headers + `server_tokens off`.
- [ ] 🟢 Host hardening runbook (ufw/fail2ban/unattended-upgrades).
- [ ] 🟢 `ops` monitor kept least-privilege — no Docker socket, mem-capped, db-only (item 13).

**Gate**
- [ ] `scripts/ops/security-preflight.sh` (§4) wired into deploy.

---

## 8. Acceptance

- `dependency_scan` populates `dependency_findings`; daily report shows new/open critical counts.
- Redis rejects unauthenticated clients; Celery + sockets still work with auth.
- Prod APIs reject a disallowed `Origin`.
- `security-preflight.sh` fails when any default secret / bypass / stale-cert / open-port condition is present.
- Disk no longer at risk from unbounded Docker logs (rotation verified).
