# Setup — Docker-era runbook

**Status:** As-built, July 2026 — rewritten from legacy doc, original in [`archive/02_setup.md`](archive/02_setup.md). The legacy systemd / virtualenv / `rasa train` path is gone; everything runs via Docker Compose (see [`01_architecture.md`](01_architecture.md) for the service map, [`DOCKER.md`](DOCKER.md) for day-to-day container commands).
**Last updated:** 2026-09-07 — host ports are defaults and `make ephemeral-up` runs an isolated second stack (QA-03). Earlier: §4 gains the additive repair path for a drifted dev database (`ensure_officer_coverage`), so recovering staffing no longer means `--reset` taking the projects and organizations with it. Earlier: 2026-09-04 · ⚠ backfilled from git 2026-09-04; not re-verified against the code

## 1. Prerequisites

- Docker Engine + Compose v2 (on Windows: Docker Desktop with WSL2 backend — always run compose **from WSL**, never Git Bash/PowerShell)
- `make`, `git`
- No host Python/Postgres/Redis required — they run in containers. (Optional: conda env + `make dev-grm-deps` for host-side pytest.)

## 2. Environment files

Compose reads **`env.local`** at the repo root (`env_file:` on every service; gitignored — never commit secrets). Minimum keys to check/fill:

```env
# LLM
OPENAI_API_KEY=...

# PII encryption (public.* pgcrypto)
DB_ENCRYPTION_KEY=...          # python -c "import secrets; print(secrets.token_urlsafe(32))"

# Redis (empty = dev, no password; set in staging/prod)
REDIS_PASSWORD=

# Messaging (see docs/services/05_messaging_service.md)
SMTP_SERVER=... SMTP_PORT=587 SMTP_USERNAME=... SMTP_PASSWORD=... SMTP_FROM=...
SMS_PROVIDER=doit|disabled
DOIT_SMS_BEARER_TOKEN=...      # Nepal prod SMS

# Ticketing / GRM
TICKETING_PORT=5002
TICKETING_SECRET_KEY=...

# Keycloak (auth profile — see 16_auth_keycloak.md)
KEYCLOAK_ADMIN_PASSWORD=...
KEYCLOAK_WEBHOOK_SECRET=...
KC_HOSTNAME_URL=http://localhost:18080          # prod: https://grm-chatbot.dor.gov.np/keycloak
KEYCLOAK_ISSUER=http://localhost:18080/realms/grm

# Ops monitor
OPS_DB_PASSWORD=...
HEALTH_ALERT_EMAIL=... DAILY_REPORT_EMAIL=... HEARTBEAT_URL=...
```

Postgres credentials are fixed inside compose (`user`/`password`/`app_db` on service `db`) — dev only; overlays/env govern staging/prod. URLs/hosts per environment: [`12_environment_urls.md`](12_environment_urls.md).

## 3. First bring-up (fresh clone / empty DB)

```bash
cd /home/philg/projects/nepal_chatbot     # repo root, inside WSL

# 1) Chatbot base stack (db, redis, backend, orchestrator, celery x3, nginx)
make wsl-chatbot                          # = docker compose -f docker-compose.yml up -d --build

# 2) One-shot: baseline chatbot tables in the empty Postgres volume
docker compose --profile init run --rm db_init

# 3) All three Alembic migration streams (ticketing.* + public.* + ops.*)
make migrate_all                          # = migrate_ticketing + migrate_public + migrate_ops

# 4) Seed reference + demo data
docker compose run --rm --no-deps backend python -m ticketing.seed.import_locations_json \
  --country NP \
  --en backend/dev-resources/location_dataset/en_cleaned.json \
  --ne backend/dev-resources/location_dataset/ne_cleaned.json \
  --max-level 3
make seed_seah_providers                  # SEAH support centres (public.seah_service_providers)
```

## 4. Compose up flows (GRM overlay + auth profile)

| Command | What comes up |
|---|---|
| `make wsl-chatbot` | Chatbot only — webchat at http://localhost:8080/ |
| `make wsl-demo-bypass` (alias `wsl-ticketing`) | GRM single stack, dev bypass: UI :3001 → `ticketing_api` :5002, **no Keycloak** (mock super-admin) |
| `make wsl-up` | Everything: chatbot + GRM single stack (dev bypass) |
| `make wsl-auth` | Add Keycloak :18080 (`--profile auth`); for real OIDC set `AUTH_MODE=keycloak` + `KEYCLOAK_ISSUER` in `env.local` and rebuild — same UI :3001 / `ticketing_api` :5002 |
| `make wsl-down` | Stop all (base + GRM + auth profile) |

⚠ **The host ports below are defaults.** Since QA-03 each is `${VAR:-<number>}`, so an unset
variable gives exactly the port shown — and `make ephemeral-up` runs a second, fully isolated,
seeded stack beside your own (ui :13001, api :15002, webchat :18081) without touching it.
`make ephemeral-down` takes its volumes with it. See [`03_operations.md`](03_operations.md) §6b.

Auth mode is a config flag (`AUTH_MODE`), not a duplicate service — dev bypass and real Keycloak use the **same** `grm_ui` (:3001) + `ticketing_api` (:5002). Raw compose equivalents (what the Makefile wraps):

```bash
docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml up -d                  # chatbot + GRM (dev bypass)
docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml --profile auth up -d   # + Keycloak
```

### Keycloak realm bootstrap (once, after `wsl-auth` and Keycloak is healthy)

```bash
make keycloak-setup
# = docker compose ... exec -T ticketing_api python -m ticketing.auth.keycloak_setup
```

Idempotent: creates the `grm` realm, clients, mappers, realm SMTP, demo officers. Details: [`16_auth_keycloak.md`](16_auth_keycloak.md).

### GRM demo tickets

```bash
make wsl-seed        # ticketing.seed.mock_tickets --reset (idempotent)
```

### Repairing a drifted database WITHOUT resetting it

⚠ **`--reset` is not idempotent in the sense that matters here: it wipes and re-seeds**, taking the
projects, organizations and officers with it. On a development database carrying local setup you want
to keep, that is too high a price for a green test run.

```bash
docker exec nepal_chatbot-backend-1 python -m ticketing.seed.ensure_officer_coverage          # report
docker exec nepal_chatbot-backend-1 python -m ticketing.seed.ensure_officer_coverage --apply  # write
```

Fills **officer-staffing gaps only**, by inserting `ticketing.officer_scopes` rows and nothing else —
no updates, no deletes, no Keycloak calls, and no invented officers (identity lives in Keycloak; a
user created here is one nobody can log in as). Dry-run by default, idempotent, and it **asks the
go-live checks whether a gap exists** rather than carrying its own copy of the rule.

*The symptom it fixes:* `Ticket intake blocked: Add a Level 1 officer (wf:…:LEVEL_1_SITE:actor) for
these packages: 01, 02, …` — and, downstream of it, every `tests/ticketing` integration test failing
at once. **The cause is usually a level that declares `staff_per_package`**: a project-wide officer
scope deliberately does *not* satisfy it ([`../ticketing_system/`](../ticketing_system/) · `project_go_live.py` C1), so
each active package needs its own row. Measured 2026-09-06 on a drifted dev DB: 20 test failures, all
from five missing rows.
## 5. Migration make targets (reference)

| Target | Runs |
|---|---|
| `make migrate_ticketing` | `alembic -c ticketing/migrations/alembic.ini upgrade head` |
| `make migrate_public` | `alembic -c migrations/public/alembic.ini upgrade head` |
| `make migrate_ops` | `alembic -c ops/migrations/alembic.ini upgrade head` |
| `make migrate_all` | all three, in that order |
| `make reset_public_dev` | **dev only** — drop + recreate `public` schema, re-migrate, restart |

All run inside the `backend` container image (`docker compose run --rm --no-deps backend ...`) so they use the compose DB. Policy + run-order rules: [`07_migrations_policy.md`](07_migrations_policy.md).

## 6. Verify

```bash
docker compose ps                                   # all healthy
curl http://localhost:5001/health                   # backend
curl http://localhost:8000/health                   # orchestrator
curl http://localhost:5002/health                   # ticketing_api (with GRM overlay)
# Webchat: http://localhost:8080/   Officer UI: http://localhost:3001
# Keycloak admin: http://localhost:18080 (auth profile)
make check_grm_ports                                # asserts grm_ui :3001 + ticketing_api :5002
make test-ticketing                                 # pytest inside ticketing_api container
```

## 7. Staging / production deploys

Remote deploys are Makefile-driven (pull `main`, migrate, rebuild selected services):

| Env | Targets |
|---|---|
| AWS staging (`nepal-gms-chatbot.facets-ai.com`, key SSH) | `make aws-up` (on host) · `make aws-deploy` / `aws-deploy-light` / `aws-deploy-full` / `aws-deploy-ops` · `make ssh-running` |
| Nepal DOR prod (`grm-chatbot.dor.gov.np`, Sophos VPN + password SSH) | `make prod-deploy` / `prod-deploy-light` / `prod-deploy-full` / `prod-deploy-ops` · `make ssh-prod` · `make prod-sync-db-from-aws CONFIRM=1` |

Prod compose stack:

```bash
docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  -f docker-compose.prod.yml --profile auth up -d
```

Before promotion run `make security-preflight` (gate defined in [`../services/12_security_monitoring_service.md`](../services/12_security_monitoring_service.md) §4). TLS via certbot (`deployment/certbot/`, renew cron: `scripts/ops/install_tls_renew_cron.sh`). Server spec: [`10_production_server_spec.md`](10_production_server_spec.md); hardening: [`15_host_hardening.md`](15_host_hardening.md).
