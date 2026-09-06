# Architecture — Nepal Chatbot + GRM Ticketing

**Status:** As-built, July 2026 — rewritten from legacy doc, original in [`archive/01_architecture.md`](archive/01_architecture.md).
**Last updated:** 2026-09-06 — §1: the image model (eleven services, two images), the UI's two variants per commit, and why staging pulls while production still builds.

The whole stack is **Docker Compose only** — no systemd services, no standalone Rasa server, no Flask. One repo, one image for all Python services, plus a Next.js image for the officer UI and stock images for Postgres/Redis/nginx/Keycloak.

## 1. Service map

### Base stack — `docker-compose.yml` (chatbot)

| Service | Image / command | Port (container) | Role |
|---|---|---|---|
| `orchestrator` | `uvicorn backend.orchestrator.main:app` | 8000 | Conversation state machine; runs intake actions from `backend/actions/` in-process. `POST /message`, `GET /health` |
| `backend` | `uvicorn backend.api.fastapi_app:app` | 5001 | Grievance/file/messaging/voice/gsheet APIs (FastAPI). See [`04_backend.md`](04_backend.md) |
| `celery_llm` | Celery `-Q llm_queue` (concurrency 6) | — | LLM classification/summarization tasks |
| `celery_default` | Celery `-Q default` (concurrency 2) | — | General background tasks |
| `celery_file` | Celery `-Q file_queue` (concurrency 1) | — | File processing (image compression, voice) |
| `redis` | `redis:7` | 6379 | Broker (db1) + result backend (db2) + Socket.IO bus (db0); `requirepass` when `REDIS_PASSWORD` set |
| `db` | `postgres:15` | 5432 (host `5433` via GRM overlay) | `app_db` — schemas `public`, `ticketing`, `ops`, `keycloak` |
| `nginx` | `nginx:stable` | 80 (host `8080` on WSL; `80/443` via AWS/prod overlays) | Edge: serves `channels/REST_webchat/` static + proxies APIs |
| `db_init` | one-shot, `--profile init` | — | Creates baseline chatbot tables in an empty volume |

All Celery workers share one app: `backend.task_queue.celery_app`.

### GRM overlay — `docker-compose.grm.yml`

| Service | Port (host) | Role |
|---|---|---|
| `ticketing_api` | 5002 | Ticketing FastAPI (`ticketing.api.main:app`) — the **single** consolidated API; auth behaviour set by `AUTH_MODE` (`keycloak` default / `bypass` only when `APP_ENV=dev`) |
| `grm_ui` | 3001 | Officer UI (Next.js) — the **single** consolidated UI; auth mode baked from `AUTH_MODE`/`KEYCLOAK_ISSUER` at build time; proxies to `ticketing_api:5002` |
| `grm_celery` | — | GRM Celery worker, queues `grm_ticketing,grm_geocode` (SLA watchdog, escalation, grievance sync, notifications, archiving) |
| `grm_celery_beat` | — | GRM periodic scheduler (SLA watchdog, sync, heartbeat, archiving) |
| `ops` | — | Platform monitor (`python -m ops.scheduler`, APScheduler, broker-independent). Spec: [`../services/11_health_and_monitoring_service.md`](../services/11_health_and_monitoring_service.md) |
| `keycloak` *(profile `auth`)* | 18080 (`KEYCLOAK_HOST_PORT`) | Keycloak 26 OIDC provider (the only profile-gated service); state in `keycloak` schema of `app_db`. See [`16_auth_keycloak.md`](16_auth_keycloak.md) |

The old demo-vs-auth split (`ticketing_api_auth`:5003 / `grm_ui_auth`:3002) is **gone** (CL-03): one `ticketing_api` (:5002) and one `grm_ui` (:3001), their auth behaviour driven by `AUTH_MODE` + `KEYCLOAK_ISSUER`.

GRM Celery app: `ticketing.tasks.celery_app.celery_app` — separate from the chatbot Celery app, same Redis broker.

### Environment overlays

| File | Adds |
|---|---|
| `docker-compose.aws.yml` | nginx on host `80/443`, TLS conf `deployment/nginx/webchat_rest_compose_aws.conf` (`nepal-gms-chatbot.facets-ai.com` + `grm-auth.` subdomain), certbot mounts |
| `docker-compose.prod.yml` | Nepal DOR prod (`grm-chatbot.dor.gov.np`): TLS conf `webchat_rest_compose_prod.tls.conf`, single-host Keycloak at `/keycloak` path, IPv4-preferred SMTP for Keycloak |

There is no `docker-compose.override.yml` any more (CL-03): dev-ness comes from `env.local` (`APP_ENV=dev AUTH_MODE=bypass`), not an override file. The compose set is `docker-compose.yml` (base) + `docker-compose.grm.yml` (single GRM stack) + `docker-compose.aws.yml` / `docker-compose.prod.yml` (deploy overlays). Deploys bring Keycloak up with `--profile auth`.

### Images — eleven services, two images

Ten services build the **root `Dockerfile`** and share one image; `grm_ui` builds its own. They
are named by variable so the same compose files serve a developer's machine, a CI runner and a
deploy host:

| Image | Services | Reference |
|---|---|---|
| `app` | `orchestrator`, `backend`, `db_init`, `celery_file`, `celery_default`, `celery_llm`, `ticketing_api`, `grm_celery`, `grm_celery_beat`, `ops` | `${IMAGE_REGISTRY}/app:${IMAGE_TAG:-local}` |
| `ui` | `grm_ui` | `${IMAGE_REGISTRY}/ui:${UI_IMAGE_TAG:-${IMAGE_TAG:-local}}` |

`IMAGE_TAG` defaults to `local`, so a plain `docker compose build` on a dev box needs no
registry and no credentials. CI publishes the commit's short sha.

⚠ **The officer UI has two images per commit, and only one of them has a login.**
`NEXT_PUBLIC_AUTH_MODE` is inlined by the Next compiler, so the auth mode is a property of the
**image**, not of the runtime — `ui:<sha>` is the Keycloak build and `ui:<sha>-bypass` reads an
identity from a cookie for the end-to-end suite. That is why `grm_ui` has its own tag variable:
one shared `IMAGE_TAG` could not name a bypass UI beside a normal `app`.
`scripts/ci/check_no_bypass_image.sh` refuses a `-bypass` reference in any compose file
describing a real environment; the runtime also fails closed (HR-01).

### Where images are built — and why the two hosts differ

**Staging pulls; production still builds on the box.** One switch, `DEPLOY_BUILD`, chosen per
target: the `aws-*` deploy targets set `0` (pull), everything else defaults to `1` (build).

⚠ **The asymmetry is deliberate, not drift.** Building on the deploy host is what took staging
off the network for 41 minutes on 2026-09-04 — a Next.js build exhausted a 3825 MB instance with
no swap. Pulling removes that class of failure. Production has **not** been converted because
nobody has yet confirmed the VPN-only DOR host can reach the registry at all, and an untested
deploy path discovered during a maintenance window is worse than a slow one. The switch is
ready for the day that is answered.

Deploys print the resolved image digest per service after `up -d`, because a pulling deploy that
was not given a new tag succeeds while changing nothing.

## 2. Request / data flows

### Complainant webchat (active channel: `channels/REST_webchat/`)

```
Browser ── /rest-webchat/ (static) ──► nginx
   │                                    │ /message
   └── chat turn ───────────────────────┼──► orchestrator:8000  (state machine + backend/actions/)
   └── file upload /upload-files ───────┴──► backend:5001       (files router → celery file_queue)
```

`channels/webchat/` (Socket.IO webchat) is **legacy and unmounted** — do not build against it.

### Chatbot → ticketing

- On grievance submit, `backend/actions/utils/ticketing_dispatch.py` POSTs to the ticketing API (`POST /api/v1/tickets`) to create the ticket.
- Safety net: `ticketing.tasks.grievance_sync.sync_grievances` (GRM Celery Beat) periodically reconciles `public.grievances` → `ticketing.tickets` for anything the webhook missed.
- Ticketing reads grievance detail/PII fresh via `GET /api/grievance/{id}` on the backend — never by joining `public.*`.

### Officer UI → ticketing API → Keycloak

```
Browser ──► grm_ui :3001 (Next.js; server-side proxy via rewrites)
                 │                     ▲ OIDC login (browser → Keycloak issuer URL, when AUTH_MODE=keycloak)
                 └──► ticketing_api :5002 ──► JWT validated against Keycloak JWKS
                            │
                            ├──► GET /api/grievance/{id}   (backend:5001 — PII on demand)
                            ├──► POST /message             (orchestrator:8000 — officer reply to complainant)
                            └──► POST /api/messaging/send-sms|send-email (backend:5001 — SMS fallback, reports)
```

### Notifications

Complainant: chatbot-first (`POST /message` with stored `session_id`), SMS fallback via Messaging API (DOIT gateway in Nepal prod, AWS SNS dev/international — see [`../services/05_messaging_service.md`](../services/05_messaging_service.md)). Officers: in-app badge.

## 3. Database — one Postgres, four schemas, three Alembic streams

`app_db` in the `db` container:

| Schema | Owner / migration stream | Contents |
|---|---|---|
| `public` | `migrations/public/alembic.ini` (version table `alembic_version_public`) | Chatbot canonical data: grievances, complainants (pgcrypto-encrypted PII), files, SEAH intake, vault/reveal audit |
| `ticketing` | `ticketing/migrations/alembic.ini` (version table in `ticketing` schema) | Tickets, workflows, roles, settings, events — **no PII**, string refs to `grievance_id` only, no cross-schema FKs/joins |
| `ops` | `ops/migrations/alembic.ini` (version table `alembic_version_ops`) | `system_health_checks`, `dependency_findings`; scoped `ops_app` role |
| `keycloak` | Keycloak manages its own DDL | Keycloak 26 internal state |

Rules (locked): the three Alembic streams never share a table; run all of them with `make migrate_all`. Full policy: [`07_migrations_policy.md`](07_migrations_policy.md).

## 4. Deeper specs

| Topic | Where |
|---|---|
| Per-service specs (grievance, files, messaging, LLM, task queue, DB, health, security monitoring) | [`../services/00_services_index.md`](../services/00_services_index.md) |
| Ticketing product/schema/API/workflow specs | `../ticketing_system/` (start: `04_ticketing_schema.md`) |
| Chatbot conversation flow, forms, frontend | `../rest_chatbot/` (flows: `02_flow_spec.md`) |
| SEAH sensitive intake | `../seah/` (written in parallel; see `../seah/README.md`) |
| Auth (Keycloak) as-built | [`16_auth_keycloak.md`](16_auth_keycloak.md) |
| Build/run/debug containers | [`DOCKER.md`](DOCKER.md) |
| Setup runbook | [`02_setup.md`](02_setup.md) · Operations: [`03_operations.md`](03_operations.md) |
| Privacy/security | [`09_privacy.md`](09_privacy.md) · [`13_security.md`](13_security.md) |

> Numbering note: `05_rasa.md` was retired to [`archive/05_rasa.md`](archive/05_rasa.md) — the Rasa runtime no longer exists; the number is intentionally unused.
