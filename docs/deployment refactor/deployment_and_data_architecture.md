# Deployment and data architecture (Phase 1 → Phase 2)

**Status:** Draft  
**Last updated:** 2026-04-14  

Progressive ops plan: start with a **single EC2** and **Docker** (including Postgres and Redis), add **S3** and optional **RDS** when scaling. Edge traffic uses **Nginx** only (see [`deployment/nginx/webchat_rest_aws.conf`](../../deployment/nginx/webchat_rest_aws.conf)). Per-environment URLs and paths live in [`../deployment_environment_urls.md`](../deployment_environment_urls.md).

**Related:** [`../OPERATIONS.md`](../OPERATIONS.md), [`../ARCHITECTURE.md`](../ARCHITECTURE.md), [`../internal_dental_system_strategy.md`](../internal_dental_system_strategy.md) (optional product context for Phase 2 crawler-style features). **Agents:** [`AGENT_INSTRUCTIONS.md`](AGENT_INSTRUCTIONS.md).

---

## 1. Phase 1 scope (authoritative)

This document assumes the **current product architecture** documented in [`../BACKEND.md`](../BACKEND.md):

| In scope | Out of scope for deploy |
|----------|-------------------------|
| **REST webchat** ([`channels/REST_webchat/`](../../channels/REST_webchat/)) | **Rasa server** (no `rasa run`, no separate Rasa process in production) |
| **Orchestrator** (FastAPI): `POST /message`, state machine, invokes **Rasa SDK** actions in-process | **Dedicated Rasa Action Server** as a separate long-running service (logic runs via SDK inside the orchestrator) |
| **Backend API** (FastAPI, e.g. port **5001**): files, grievances, Socket.IO, gsheet, etc. | |
| **Celery** workers + **Redis** + **PostgreSQL** | |

**Form validation and dialogue logic** reuse the **Rasa SDK** action code paths; they are **not** dependent on running the full Rasa stack.

**Runtime processes (conceptual):** orchestrator (~8000), FastAPI backend (~5001), Celery workers, Redis, Postgres, Nginx on the host or in Docker (see §3).

---

## 2. Secrets and configuration

**Principle:** No secrets committed to git. Use environment variables or AWS-managed secret stores at runtime.

| Environment | Mechanism |
|-------------|-----------|
| **Local dev (WSL)** | **`env.local`** (or equivalent local-only env files already ignored by git). Developers copy from any checked-in `.env.example` pattern your project uses. |
| **Stage / prod** | **Environment variables** set on the host or container at start. Values sourced from **AWS** where appropriate, e.g. **Systems Manager Parameter Store** (non-secret config, hierarchical names like `/app/prod/DATABASE_URL`) and **Secrets Manager** (DB passwords, API keys, signing keys). IAM roles on EC2 or ECS task roles grant read access—no long-lived keys in the repo. |

**Migration away from committed defaults:** Replace hard-coded credentials in archived Rasa runner files (see `backend/orchestrator/config/source/legacy_rasa_config/endpoints.yml`) with env-driven configuration in the path your runtime actually uses, or document deprecation.

**Operational checklist:**

- [ ] List every secret the app needs (DB, Redis, JWT/session, third-party APIs).
- [ ] Stage and prod: define **one** injection path (systemd `EnvironmentFile`, Docker `--env-file` from S3+decrypt, ECS secrets, etc.).
- [ ] Rotate keys if any ever lived in git history.

---

## 3. Phase 1 — Single machine (all-in-Docker)

### Goals

- Minimal external dependencies (Postgres and Redis on the same host via Docker).
- Simple deploy and low cost.
- Full control on one EC2.

### Architecture

```mermaid
flowchart TB
  subgraph ec2 [EC2]
    subgraph docker [Docker]
      orch [Orchestrator FastAPI]
      api [Backend FastAPI]
      celery [Celery workers]
      redis [Redis]
      pg [PostgreSQL]
    end
    nginx [Nginx]
  end
  users [Clients]
  users --> nginx
  nginx --> orch
  nginx --> api
  orch --> redis
  celery --> redis
  celery --> pg
  api --> pg
  orch --> pg
```

Nginx may run **on the host** (current samples) or in a container with published ports; keep **one** routing layout and sync with [`../deployment_environment_urls.md`](../deployment_environment_urls.md).

### Concrete steps (outline)

1. **`docker-compose.yml`** (future implementation): services for orchestrator image, backend image, Celery (possibly multiple services or one worker with multiple queues—see [`scripts/rest_api/launch_servers_celery.sh`](../../scripts/rest_api/launch_servers_celery.sh)), `redis:7`, `postgres:15`, volumes for Postgres data.
2. **Nginx:** Extend existing repo configs; do not introduce alternate edge proxies.
3. **Deploy flow:** `git push` → on server `docker compose up -d --build` (or CI-driven).
4. **Migrations:** Prefer **Alembic** when schema migrations are introduced; there is **no** `alembic.ini` in the repo today—treat `alembic upgrade head` as a **future** operational step once migrations exist. Until then, follow whatever SQL/process you use today.
5. **Backups (mandatory):** `pg_dump` (compressed), schedule with **cron** or a Celery beat job; in Phase 1 store on disk or sync to S3 when Phase 2 bucket exists.

### Phase 1 limitations

- Database tied to the instance volume; no automatic failover.
- Backups and restores must be tested deliberately.
- Vertical scaling only until you split services or add RDS/S3.

---

## 4. Phase 2 — S3 + optional RDS

### Goals

- Decouple file and snapshot storage (**S3**).
- Improve reliability and optional DB operations (**RDS**).
- Support future **crawler replay** (e.g. HTML in S3, structured rows in DB)—see [`../internal_dental_system_strategy.md`](../internal_dental_system_strategy.md) if applicable.

### Suggested bucket layout

- `crawler/html/` — short TTL (e.g. 30-day lifecycle).
- `crawler/json/` — structured extracts as needed.
- `images/` — long-lived assets.
- `backups/db/` — encrypted DB dumps.

### Crawler flow (when implemented)

Fetch page → store HTML in S3 → parse → structured data in DB. Add something like `CRAWL_MODE=live|replay` (live fetch vs read HTML from S3).

### RDS (optional)

1. Dump current DB → restore to RDS.
2. Point `DATABASE_URL` (or equivalent) to RDS; restart services.
3. Consider separate DBs for staging and production on one instance for cost, with clear naming (`app_staging`, `app_prod`).

### CI/CD (outline)

Push → deploy staging → run migrations (when Alembic exists) → tests → tag → production deploy. Use GitHub Actions or AWS CodePipeline; inject secrets from AWS, not from repo.

### Environment separation

Examples: `DATABASE_URL_STAGING`, `DATABASE_URL_PROD`, `S3_BUCKET`, `AWS_REGION`. No secrets in Git.

---

## 5. Analysis

**Strengths:** Phased decoupling (files to S3 first, DB to RDS later), backups before scale, clear growth path.

**Risks / gaps:**

- **Two HTTP apps** (orchestrator + backend) plus Celery are more moving parts than a single `uvicorn main:app` tutorial—compose and Nginx must match [`../deployment_environment_urls.md`](../deployment_environment_urls.md).
- **Secrets** must leave committed files entirely for stage/prod.
- **Alembic** is not wired yet—document operational expectations before relying on automated migrations in CI.

---

## 6. Open questions

- **Compose layout:** One `docker-compose.yml` vs base + `docker-compose.override.yml` for local vs stage?
- **TLS:** Terminate at **ALB** vs Nginx on instance; cert source (ACM, Let’s Encrypt).
- **Backups:** Local only in Phase 1 vs upload to S3 immediately; encryption at rest; restore drill schedule.
- **RDS:** When to cut over; connection pooling; staging DB on same RDS or separate.
- **Phase 2 crawler:** Data ownership, PII in HTML, retention policy—tie to product/legal.
- **CI/CD:** Branch model, who approves production, where migrations run.

---

## 7. What this spec does not require by itself

This file is **documentation only**. It does **not** add `docker-compose.yml`, Dockerfiles, or automation scripts until you implement them in a separate change.
