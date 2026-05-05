# 11 — Messaging service: API-only access, split deploy, pluggable providers

**Status:** **Spec locked** for implementation (rounds 1–3 complete). **Simplest defaults:** no separate `ops` API key; one env name **`MESSAGING_REMOTE_BASE_URL`** for every caller’s notify base URL.

---

## Purpose

Specify how **SMS / email (and future channels)** should behave so that:

1. **Ticketing** and **chatbot** stacks can live on **different servers**, with messaging delivered only via a **stable HTTP API** (not assumed in-process imports from `backend/services/messaging.py`).
2. **Access** to that API is limited to **authorised callers** (ticketing service vs chatbot/orchestrator side), auditable and rotatable.
3. **Providers** (SNS, SES, Twilio, SendGrid, government gateways, etc.) are **configurable** without rewriting call sites.
4. **Ticketing** can later own a **notifications settings** UI (templates, schedules, provider choice, test send) without entangling chatbot env files.

---

## Current state (baseline)

| Piece | Role today |
| ----- | ---------- |
| `backend/services/messaging.py` | Singleton-style facade; SNS SMS + SES email; used directly from Rasa actions (`base_mixins`), Celery tasks, FastAPI grievance router, legacy Flask app. |
| `backend/api/routers/messaging.py` | `POST /api/messaging/send-sms`, `POST /api/messaging/send-email`; auth must enforce keys + `X-Messaging-Source` per **Auth matrix**. |
| `ticketing/clients/messaging_api.py` | HTTP client; **must** use the same JSON field names as FastAPI (`to` / `text`, `to` / `subject` / `html_body`). |

**Target architecture (round 2):** outbound delivery and provider SDKs live in a **small dedicated notify service**; ticketing holds **routing / defaults in DB**; chatbot and ticketing call the notify HTTP API.

---

## Goals (locked wording for implementers)

### G1 — API as the cross-stack contract

- Any **server that is not the notify / messaging API host** must send traffic via **HTTP** to documented endpoints (same paths unless versioned later, e.g. `/api/v1/messaging/...`).
- The **notify service** is the only place that **initialises boto3 / provider SDKs** for outbound delivery (unless a future spec explicitly allows worker-side providers).

### G2 — Caller identity (`X-Messaging-Source`)

- Every **authenticated** request must send header **`X-Messaging-Source`** (case-insensitive per HTTP) with an **allowed literal**. **v1 allowed set:** `ticketing` \| `chatbot`.
- **Operational jobs** (cron on EC2, Celery workers) use the same header model: jobs that are **owned by the ticketing deployment** use **`ticketing`** + the ticketing stack’s API key; jobs on the **chatbot side** use **`chatbot`** + the chatbot key. **Flower** is **read-only** for monitoring — **no requirement** to send SMS/email via Flower unless product later says otherwise.
- **Not v1 (only if needed later):** extra literals such as `ops` / `scheduler` and matching keys — **out of scope** while we keep the **simplest** model (cron on EC2 uses **`ticketing`** + ticketing key when the job is GRM-owned).
- Logs and metrics must record **client source** (not PII).

### G3 — Configurable providers + country routing

- **SMS** and **email** each resolve to a **provider implementation** via config (env on notify host first; **plus** ticketing DB routing — round 2).
- Built-in providers in v1: **`sns`**, **`ses`**, **`noop`**. Next: **local / in-country SMS and email gateways**.

**Country resolver (locked):** separate step before send — normalise E.164 per **`country_code`**, then choose provider / template. Chatbot dialogue stays country-specific; **notify** stays dumb to conversation rules.

**Persistent routing (round 2 — locked):** first **country → provider / template** routing data lives in **`ticketing.*`** (no PII: e.g. `country_code`, provider key enum, template ids, toggles). Notify service **does not** store complainant PII; it may receive **resolved** routing hints in `context` or fetch read-only config via authenticated **ticketing → notify** internal API (see **D2** below).

### G4 — Notifications settings (ticketing UI)

- **Super_admin only for v1** for editing notification defaults (`local_super_admin` **deferred** until multi-country org model needs it).
- **v1 of the page includes test send** (SMS to a designated number, email to self).
- **No email attachments** through this API in v1.

---

## Non-goals

- Replacing **orchestrator `POST /message`** with messaging API.
- Storing **complainant PII** in `ticketing.*` notification config.
- **OTP** product redesign in this spec.

---

## Deployment topologies (reference)

| Topology | Chatbot / ticketing workers | Notify / messaging API |
| -------- | ---------------------------- | ------------------------ |
| **A — Monolith (legacy)** | Same host as old backend | May temporarily co-host routes; **migrate toward B**. |
| **B — Split** | Call `https://<notify-host>/api/messaging/*` | **Dedicated notify service** (round 2); holds provider credentials. |
| **C — Ticketing consumer** | Ticketing Celery / API | Same notify endpoints + `X-Messaging-Source: ticketing`. |

**Physical ownership (round 2 — locked):** **`/api/messaging` lives on a small dedicated notify service** so **providers per country** can change **without** redeploying chatbot or full ticketing app. **Logical** ownership of “what to send when” remains **ticketing** (DB + UI).

---

## HTTP API contract (v1) — locked

Paths (until versioned):

- `POST /api/messaging/send-sms`
- `POST /api/messaging/send-email`

**SMS:** `to`, `text`, optional `context`.

**Email:** `to` (array), `subject`, `html_body`, optional `context`.

**Response envelope:** `{ "status": "SUCCESS" | "FAILED", "error_code"?, "error"?, "message"?, "message_id"? }` — extend additively only.

**Attachments:** out of scope v1.

---

## Auth matrix — locked (includes round 2 Q1)

| Rule | Decision |
| ---- | -------- |
| Keys | **Per-stack keys (final):** `MESSAGING_API_KEY_TICKETING` and `MESSAGING_API_KEY_CHATBOT`. Optional legacy **`MESSAGING_API_KEY`** only if you later need a single secret for both (not default). |
| `X-Messaging-Source` | **Mandatory** whenever any `MESSAGING_API_KEY*` is configured. Allowed literals **v1:** `ticketing` \| `chatbot`. Key must match the declared source (per-stack table in implementation). |
| Header name | **`X-Messaging-Source`** (HTTP spelling); clients and docs should use this consistently. |
| Local dev | **`MESSAGING_API_AUTH_DISABLED=true`** on dev machines only; never default in production images. |
| Ticketing `messaging_api_key` | **Equals** the secret notify expects for **`X-Messaging-Source: ticketing`** (same value as `MESSAGING_API_KEY_TICKETING` on notify host, modulo secret distribution tooling). |

---

## Grievance status notifications — locked

Grievance flows must call **`POST /api/messaging/*`** on the notify service (same JSON + headers as external clients). **No** in-process bypass on any host that is not the notify implementation itself.

---

## Celery / workers — locked

When **`MESSAGING_USE_REMOTE_API=true`**, workers **always** use **HTTP** to the notify base URL, **even** if colocated (uniform path).

---

## Provider configuration

### Notify service host (env)

| Variable | Meaning |
| -------- | ------- |
| `MESSAGING_SMS_PROVIDER` | `sns` \| `noop` \| future adapters |
| `MESSAGING_EMAIL_PROVIDER` | `ses` \| `noop` \| future adapters |

**Secrets:** only on **notify** (env, Parameter Store, etc.).

### Ticketing DB (round 2 — locked)

- **Country → provider / template** (and non-secret toggles) persist in **`ticketing.*`** **from the first migration that introduces the table**, not “wait for UI”. UI reads/writes the same tables later.

### Long-term: how settings reach notify (round 2 Q6 — locked with reco)

| Model | Use |
| ----- | --- |
| **D2 (long-term default — locked)** | Ticketing remains **source of truth** for non-secret config; **notify** receives updates via **push or pull of config snapshot** (implementation choice: signed POST from ticketing to notify, or notify **pulls** read-only from ticketing internal API with service token). **Secrets never** in `ticketing.*`. |
| **D1** | Optional **cache** on notify (TTL) after D2 push/pull — not the sole long-term store. |
| **D3** | Ticketing-only outbound path — **rejected** for long-term here because chatbot and grievance must still hit the same contract; notify stays the single outbound execution point. |

**Rationale:** D2 keeps **PII and secrets off** ticketing DB while letting ticketing **own** routing and templates; notify stays a thin **execution** layer with **per-country provider** swaps.

---

## Chatbot / worker env (split deploy) — locked

| Variable | Meaning |
| -------- | ------- |
| `MESSAGING_USE_REMOTE_API` | `true` → HTTP client |
| `MESSAGING_REMOTE_BASE_URL` | **Single** base URL of the **notify** service (`/api/messaging/*`) for **all** non-notify callers (chatbot workers, ticketing, scripts) — **no** separate `MESSAGING_NOTIFY_BASE_URL` (simplest). |
| `MESSAGING_API_KEY_CHATBOT` | `x-api-key` with `X-Messaging-Source: chatbot` |

Ticketing uses **`messaging_api_key`** + **`X-Messaging-Source: ticketing`** against the **same** `MESSAGING_REMOTE_BASE_URL` (or its own copy of that URL in env — same semantic, one concept).

---

## Observability and retention — locked

- Log `client_source`, `purpose` / ids from `context`, `message_id` when available; mask phone/email.
- Retention: **align grievance/app policy** if defined; else **90-day** default for messaging access logs until compliance replaces it.

---

## Data residency — locked

No **additional** restriction vs current hosting; future tickets may tighten `context` routing.

---

## Round 3 — locked (simplest)

| Topic | Decision |
| ----- | -------- |
| Cron / EC2 / GRM-owned jobs | **`X-Messaging-Source: ticketing`** + **`MESSAGING_API_KEY_TICKETING`** (same as ticketing app). **No** separate `ops` principal or `MESSAGING_API_KEY_OPS` in v1. |
| Notify base URL env | **Keep `MESSAGING_REMOTE_BASE_URL` only** — one variable for “where is `/api/messaging`”, shared by chatbot, ticketing, grievance, and cron clients. **Do not** add `MESSAGING_NOTIFY_BASE_URL` unless a future refactor explicitly deprecates the old name. |

---

## Implementation checklist (execution order)

1. **Notify service** skeleton + move/enforce **`POST /api/messaging/*`** + **auth matrix**.
2. **Grievance** + **Rasa actions** + **Celery**: HTTP-only to notify when remote; align payloads.
3. **Ticketing** client + **Alembic `ticketing.*`**: routing / template tables (**no PII**); wire read path for notify (D2 shape).
4. **Provider abstraction** on notify: `sns`, `ses`, `noop`; stubs for local gateways; **country resolver** fed from ticketing config or snapshot.
5. **Notifications UI v1**: super_admin, **test send**, no attachments.
6. Cut traffic from legacy backend routes to notify (nginx / gateway or dual-run period — ops doc).

---

## Document history

| Round | What changed |
| ----- | ------------- |
| 1 | Initial spec + inline Q answers. |
| 2 | Answers folded into locked sections; round 2 Q list. |
| 3 | Round 2–3 final: **per-stack keys**, **dedicated notify service**, **routing in `ticketing.*`**, **super_admin v1**, **D2 long-term** + optional D1 cache; G2 caller rules; **simplest** round 3 — cron **`ticketing`** + ticketing key, **only** `MESSAGING_REMOTE_BASE_URL`. Spec **ready for implementation**. |
