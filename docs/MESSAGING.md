# Messaging — architecture, API, routing, and operations

This document is the **single operational summary** for outbound **SMS and email** (complainant fallback, grievance status updates, ticketing reports, OTP flows, etc.). Product decisions and stakeholder Q&A live in [`docs/Refactor specs/May5_seah/11-messaging-api-split-deploy-and-providers.md`](Refactor%20specs/May5_seah/11-messaging-api-split-deploy-and-providers.md).

---

## Goals

1. **Stable HTTP contract** — Ticketing, chatbot workers, and cron jobs call **`POST /api/messaging/send-sms`** and **`POST /api/messaging/send-email`** on the backend / notify host (paths unchanged unless versioned later).
2. **Authenticated callers only** — Intended stacks identify themselves with **`x-api-key`** + **`X-Messaging-Source`** (`ticketing` | `chatbot`).
3. **Configurable providers** — SNS, SES, noop today; more adapters keyed off **`ticketing.notification_routes`** per country/project (non-PII policy rows).
4. **Split deploy ready** — Chatbot-side code can use **`MESSAGING_USE_REMOTE_API`** so nothing assumes boto3 runs inside Rasa actions.

Secrets (AWS keys, SES sender, SMS gateways) stay on the **messaging / notify** runtime — **not** in `ticketing.*` rows.

---

## HTTP API (backend FastAPI)

| Method | Path | Body (JSON) |
|--------|------|----------------|
| POST | `/api/messaging/send-sms` | `to`, `text`, optional `context` |
| POST | `/api/messaging/send-email` | `to` (array), `subject`, `html_body`, optional `context` |

**Response envelope** (additive only): `status` (`SUCCESS` | `FAILED`), optional `error_code`, `error`, `message`, `message_id`.

### `context` object (recommended fields)

| Field | Purpose |
|-------|---------|
| `source_system` | e.g. `ticketing`, `chatbot` |
| `purpose` | e.g. `grievance_status_update`, `sms_fallback` |
| `grievance_id` / `ticket_id` | Correlation for logs (non-PII where possible) |
| **`country_code`** | **ISO 3166-1 alpha-2** (e.g. `NP`) — required for **DB-backed routing** |
| **`project_id`** | **ticketing.projects.project_id** — optional override row |
| `extra` | Arbitrary bag (e.g. `template_id` legacy hints) |

If **`country_code`** is omitted, delivery uses **environment defaults** only (`MESSAGING_SMS_PROVIDER` / `MESSAGING_EMAIL_PROVIDER`).

**Implementation:** [`backend/api/routers/messaging.py`](../backend/api/routers/messaging.py)

---

## Authentication

### Headers

- **`x-api-key`** — Shared or per-stack secret.
- **`X-Messaging-Source`** — Literal **`ticketing`** or **`chatbot`** (audit + key binding).

### Environment (server hosting `/api/messaging`)

| Variable | Role |
|----------|------|
| `MESSAGING_API_KEY_TICKETING` | Secret for `X-Messaging-Source: ticketing` |
| `MESSAGING_API_KEY_CHATBOT` | Secret for `X-Messaging-Source: chatbot` |
| `MESSAGING_API_KEY` | Legacy single secret (still requires source header when any key is set) |
| `MESSAGING_API_AUTH_DISABLED=true` | **Local dev only** — disables checks (never in production images) |

If **no** `MESSAGING_API_KEY*` is set and auth is not disabled, the API **accepts all requests** and logs a one-time warning (legacy dev behaviour).

**Implementation:** [`backend/api/deps/messaging_auth.py`](../backend/api/deps/messaging_auth.py)

**Ticketing service** should set `messaging_api_key` in its settings to the same value the messaging host expects for **ticketing** (see [`ticketing/config/settings.py`](../ticketing/config/settings.py)).

---

## Per-request provider selection (long-term D2)

### Database: `ticketing.notification_routes`

Policy table (no PII): **country** default and optional **per-project** override for `sms` / `email` — `provider_key`, `template_id`, `options_json`, etc.

- **Model / resolver:** [`ticketing/models/notification_route.py`](../ticketing/models/notification_route.py)  
- **Migration:** `ticketing/migrations/versions/n7h9j1k3m5p7_notification_routing_tables.py`  
- **Apply:** `python -m alembic -c ticketing/migrations/alembic.ini upgrade head`

### Runtime (messaging host)

`backend/services/notification_routing_runtime.py` resolves the effective row when `context.country_code` is present:

- **`NOTIFICATION_ROUTING_SOURCE=db`** (default) — SQLAlchemy session to the same Postgres as ticketing (`ticketing.*`).
- **`NOTIFICATION_ROUTING_SOURCE=http`** — **GET** from the ticketing service (no DB on notify host) — see below.

| Variable | Role |
|----------|------|
| `NOTIFICATION_ROUTING_ENABLED` | Default `true`; `false` → always use env providers only |
| `NOTIFICATION_ROUTING_SOURCE` | `db` or `http` |
| `NOTIFICATION_ROUTING_HTTP_BASE_URL` | e.g. `http://ticketing:5002` when `SOURCE=http` |
| `NOTIFICATION_ROUTING_HTTP_API_KEY` | Optional; falls back to `MESSAGING_API_KEY_TICKETING` |

**Ticketing internal read API (for HTTP pull):**

- `GET /api/v1/internal/notification-routes/effective?country_code=NP&channel=sms|email&project_id=...`  
- Auth: **`x-api-key`** = `TICKETING_SECRET_KEY` (same as other inbound ticketing API key).  
- **Router:** [`ticketing/api/routers/notification_routes_internal.py`](../ticketing/api/routers/notification_routes_internal.py)

**Adapters** are built per request: [`build_sms_provider_named` / `build_email_provider_named` in `backend/services/messaging_providers.py`](../backend/services/messaging_providers.py) — keys like `sns`, `ses`, `noop` (extend as you add gateways).

---

## Chatbot / Celery (worker side)

| Variable | Role |
|----------|------|
| `MESSAGING_USE_REMOTE_API` | `true` / `1` / `yes` — use HTTP instead of in-process `Messaging()` |
| `MESSAGING_REMOTE_BASE_URL` | Base URL for `/api/messaging/*` (one name for all callers) |
| `MESSAGING_API_KEY_CHATBOT` | `x-api-key` with `X-Messaging-Source: chatbot` |

**Entry point:** `get_action_messaging()` in [`backend/services/messaging.py`](../backend/services/messaging.py)  
**HTTP client:** [`backend/services/messaging_remote.py`](../backend/services/messaging_remote.py)  
**Rasa actions / mixins:** [`backend/actions/base_classes/base_mixins.py`](../backend/actions/base_classes/base_mixins.py)  
**Celery tasks:** [`backend/task_queue/registered_tasks.py`](../backend/task_queue/registered_tasks.py)

---

## Grievance status notifications (grievance API)

Grievance updates no longer call `Messaging()` directly for status emails/SMS. They go through [`backend/services/messaging_http_dispatch.py`](../backend/services/messaging_http_dispatch.py):

| `MESSAGING_GRIEVANCE_DELIVERY` | Behaviour |
|--------------------------------|------------|
| Unset (default) | **`inprocess`** — direct `Messaging()` (avoids single-worker uvicorn self-HTTP deadlock) |
| `http` | HTTP to `MESSAGING_REMOTE_BASE_URL` with `X-Messaging-Source: ticketing` and ticketing key |

**Router:** [`backend/api/routers/grievance.py`](../backend/api/routers/grievance.py)

For **strict HTTP** in production, set `MESSAGING_GRIEVANCE_DELIVERY=http` and use **multiple workers** or a **separate notify** process if the URL points at the same app.

---

## Ticketing → messaging HTTP client

[`ticketing/clients/messaging_api.py`](../ticketing/clients/messaging_api.py) uses the **canonical** JSON field names and headers. Optional kwargs:

- `send_sms(..., country_code=..., project_id=...)`  
- `send_email(..., country_code=..., project_id=...)`  

Base URL: `messaging_api_base_url` (from `MESSAGING_REMOTE_BASE_URL` or `backend_grievance_base_url` in [`ticketing/config/settings.py`](../ticketing/config/settings.py)).

---

## Default env-based providers (no routing row)

| Variable | Values | Notes |
|----------|--------|--------|
| `MESSAGING_SMS_PROVIDER` | `sns`, `noop` | When no per-request `provider_key` |
| `MESSAGING_EMAIL_PROVIDER` | `ses`, `noop` | Same |
| `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | SES | |
| `SES_VERIFIED_EMAIL` | Sender | |
| `SMS_ENABLED` | `true`/`false` | Plus whitelist in chatbot constants for SNS test behaviour |

---

## File map (quick)

| Area | Path |
|------|------|
| Messaging facade + singleton | `backend/services/messaging.py` |
| Provider implementations | `backend/services/messaging_providers.py` |
| Remote HTTP (split workers) | `backend/services/messaging_remote.py` |
| Routing resolution | `backend/services/notification_routing_runtime.py` |
| Grievance delivery mode | `backend/services/messaging_http_dispatch.py` |
| FastAPI messaging routes | `backend/api/routers/messaging.py` |
| API auth dependency | `backend/api/deps/messaging_auth.py` |
| App registration | `backend/api/fastapi_app.py` |
| Ticketing routing model | `ticketing/models/notification_route.py` |
| Ticketing internal GET (HTTP pull) | `ticketing/api/routers/notification_routes_internal.py` |
| Ticketing HTTP client | `ticketing/clients/messaging_api.py` |

---

## What is *not* covered here

- **Orchestrator `POST /message`** (in-app chat to complainant) — different path; not the messaging API.  
- **Cognito / officer email** for reports — still integration points in ticketing tasks.  
- **Push-based config sync** to notify (optional future); current design is **read on each send** (DB or HTTP pull).  
- **Attachments** on `send-email` — not in v1 API contract.

---

## See also

- [11-messaging-api-split-deploy-and-providers.md](Refactor%20specs/May5_seah/11-messaging-api-split-deploy-and-providers.md) — product spec and locked decisions  
- [`docs/ticketing_system/09_messaging_api_spec.md`](ticketing_system/09_messaging_api_spec.md) — older ticketing-focused notes (may overlap; prefer this file + code for truth)
