# Architecture — Nepal Chatbot + GRM Ticketing

**Status:** As-built, July 2026 — rewritten from legacy doc, original in [`archive/01_architecture.md`](archive/01_architecture.md).

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
| `ticketing_api` | 5002 | Ticketing FastAPI (`ticketing.api.main:app`) — demo/bypass instance (no Keycloak JWT) |
| `grm_ui` | 3001 | Officer UI (Next.js), `BYPASS_AUTH=true`, proxies to `ticketing_api:5002` |
| `grm_celery` | — | GRM Celery worker, queues `grm_ticketing,grm_geocode` (SLA watchdog, escalation, grievance sync, notifications, archiving) |
| `grm_celery_beat` | — | GRM periodic scheduler (SLA watchdog, sync, heartbeat, archiving) |
| `ops` | — | Platform monitor (`python -m ops.scheduler`, APScheduler, broker-independent). Spec: [`../services/11_health_and_monitoring_service.md`](../services/11_health_and_monitoring_service.md) |
| `keycloak` *(profile `auth`)* | 18080 (`KEYCLOAK_HOST_PORT`) | Keycloak 26 OIDC provider; state in `keycloak` schema of `app_db`. See [`16_auth_keycloak.md`](16_auth_keycloak.md) |
| `ticketing_api_auth` *(profile `auth`)* | 5003 | Second ticketing API instance with real Keycloak JWT validation |
| `grm_ui_auth` *(profile `auth`)* | 3002 | Officer UI built with real OIDC config (`BYPASS_AUTH=false`) |

GRM Celery app: `ticketing.tasks.celery_app.celery_app` — separate from the chatbot Celery app, same Redis broker.

### Environment overlays

| File | Adds |
|---|---|
| `docker-compose.aws.yml` | nginx on host `80/443`, TLS conf `deployment/nginx/webchat_rest_compose_aws.conf` (`nepal-gms-chatbot.facets-ai.com` + `grm-auth.` subdomain), certbot mounts |
| `docker-compose.prod.yml` | Nepal DOR prod (`grm-chatbot.dor.gov.np`): TLS conf `webchat_rest_compose_prod.tls.conf`, single-host Keycloak at `/keycloak` path, demo `grm_ui` disabled (moved to `demo` profile), IPv4-preferred SMTP for Keycloak |
| `docker-compose.override.yml` | Local dev conveniences |

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
Browser ──► grm_ui(_auth) :3001/:3002 (Next.js; server-side proxy via rewrites)
                 │                          ▲ OIDC login (browser → Keycloak issuer URL)
                 └──► ticketing_api(_auth) :5002/:5003 ──► JWT validated against Keycloak JWKS
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
