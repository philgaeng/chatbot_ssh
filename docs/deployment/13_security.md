# Security Features — Platform Overview (June 2026)

**Status:** As-built reference for implemented controls and locked policies.  
**Related:** [09_privacy.md](09_privacy.md), [11_llm_pipeline_policy.md](11_llm_pipeline_policy.md), [../ticketing_system/06_messaging_rules_whatsapp_sms.md](../ticketing_system/06_messaging_rules_whatsapp_sms.md), [../services/05_messaging_service.md](../services/05_messaging_service.md), [../ticketing_system/00_ticketing_decisions.md](../ticketing_system/00_ticketing_decisions.md)

This document is the **single index of security features** across chatbot, backend, and GRM ticketing.

---

## 1. Security architecture (high level)

| Layer | Control |
|---|---|
| **Data separation** | `public.*` (grievance vault) and `ticketing.*` (operational metadata) in one DB, isolated by schema |
| **Integration boundary** | No cross-schema FK; service-to-service via HTTP APIs only |
| **PII boundary** | No complainant PII in `ticketing.*`; brokered reads from grievance API |
| **SEAH boundary** | DB-level `is_seah` filtering + role/workflow scope |
| **Auth boundary** | Keycloak OIDC in production; scoped officer access via `OfficerScope` |

---

## 2. Authentication and session security

| Feature | Where | Notes |
|---|---|---|
| **Keycloak OIDC (production)** | Ticketing UI + API auth stack | Officer login and JWT validation (`KEYCLOAK_ISSUER`) |
| **Officer onboarding lifecycle** | `ticketing.officer_onboarding` | `invited` → `active` via Keycloak webhook |
| **Keycloak webhook auth** | `POST /api/v1/webhooks/keycloak` | Header `X-Keycloak-Webhook-Secret` = `KEYCLOAK_WEBHOOK_SECRET` |
| **Service-to-service API keys** | Messaging, ticketing webhook | `x-api-key` / `X-Ticketing-Secret` |
| **Dev-only bypass mode** | Local UI + API (`:3001`/`:5002`) | `AUTH_MODE=bypass`, honoured **only** when `APP_ENV=dev`; production can never bypass |
| **OTP verification (chatbot intake)** | Complainant flow | Phone verification before grievance submission |

### 2.1 Fail-closed guarantees (HR-01)

Authentication fails **closed**: a missing env var can no longer silently disable auth
(previously an unset `KEYCLOAK_ISSUER` authenticated every request as a demo super_admin,
and an unset `TICKETING_SECRET_KEY` disabled the webhook/API-key check with only a log
warning). After CL-03 two canonical flags gate this, both defaulting to the safe value:
`APP_ENV` ∈ `dev`/`staging`/`production` (default **`production`**) and `AUTH_MODE` ∈
`keycloak`/`bypass` (default **`keycloak`**). The bypass is permitted **only** when
`APP_ENV=dev` **and** `AUTH_MODE=bypass`; production can never bypass. These are set solely
in `env.local` — never in the grm/aws/prod overlays (there is no `docker-compose.override.yml`
any more). `APP_ENV` replaces the old `TICKETING_ENV`/`BACKEND_ENV`/`ENVIRONMENT`.

| Condition | dev bypass (`APP_ENV=dev` **and** `AUTH_MODE=bypass`) | staging / production (default) |
|---|---|---|
| `KEYCLOAK_ISSUER` unset (ticketing) | demo super_admin bypass allowed | **App refuses to start** (`RuntimeError` at boot); per-request `503` as defense in depth |
| `TICKETING_SECRET_KEY` unset (ticketing) | API-key check disabled (warns) | **App refuses to start**; `verify_api_key` returns `503` |
| Backend grievance key list empty (`TICKETING_SECRET_KEY` + `MESSAGING_API_KEY`) | API-key check skipped | **Backend refuses to start**; `_ticketing_auth_check` returns `503` |
| `x-internal-user-id` + valid `x-api-key`, no `x-internal-role` | least-privilege identity (**no roles**) — no default super_admin, any env | same |

Startup guards live in `ticketing/api/main.py` (`_assert_auth_configured`) and
`backend/api/fastapi_app.py` (`_assert_backend_auth_configured`); the per-request
defenses live in `ticketing/api/dependencies.py` (`verify_api_key`,
`_resolve_user_identity`) and `backend/api/routers/grievance.py` (`_ticketing_auth_check`).

---

## 3. Authorization and access control

| Feature | Where | Notes |
|---|---|---|
| **GRM role catalog** | `ticketing.roles` | Role codes with `workflow_scope` (`standard` / `seah` / `both`) |
| **OfficerScope jurisdiction** | `ticketing.officer_scopes` | Org + project + package + location scope for ticket visibility/actions |
| **4-tier ticket participation** | `ticketing.ticket_viewers` | Actor / Supervisor / Informed / Observer |
| **Action-level permissions** | Ticket action API | Step role + assignee/supervisor rules for RESOLVE, ESCALATE, GRC actions |
| **SEAH invisibility** | Ticket list/detail queries | Non-SEAH roles cannot read SEAH tickets (`is_seah=true`) |
| **Workflow scope separation** | Standard vs SEAH workflows | One ticket uses one workflow only |
| **Admin-only settings** | Settings UI/API | Workflows, users, orgs, locations, report limits restricted by role |
| **Report access scope** | Reports API/UI | Same `OfficerScope` model as queue |

---

## 4. PII and sensitive data protection

| Feature | Where | Notes |
|---|---|---|
| **No PII in ticketing tables** | `ticketing.*` | Name/phone/email/address never stored in ticketing schema |
| **Non-PII cache only on tickets** | `ticketing.tickets` | Summary, categories, location text cached at creation |
| **Brokered PII fetch** | `GET /api/v1/tickets/{id}/pii` | On-demand read from grievance API; access logged |
| **Reveal session controls** | `POST .../reveal-contact/begin` + `.../close` | Time-bounded reveal with audit trail |
| **Vault domain model** | `public.*` grievance store | Original narrative + identifiers treated as restricted content |
| **Summary-first officer UX** | Ticket detail + LLM summaries | Operational view defaults to redacted/safe content |
| **Resolved summary PII exception** | `ticketing.ticket_resolved_summaries` | Officer-only closure artifact; controlled access roles |
| **Public closure sanitization** | `summary_public_json` | Complainant-facing closure excludes internal notes/officer roster |

Detailed policy: [09_privacy.md](09_privacy.md).

---

## 5. Encryption and secrets

| Feature | Where | Notes |
|---|---|---|
| **Field-level DB encryption** | Backend grievance/complainant data | `DB_ENCRYPTION_KEY` + pgcrypto model. **`backend` is the sole holder** — it decrypts server-side in `get_grievance_by_id`, so `GET /api/grievance/{id}` serves plaintext and ticketing needs no key (T3-04). Ticketing has no accessor for it and must not regain one; pinned by `tests/ticketing/test_pii_boundary.py`. |
| **Envelope/key split by sensitivity** | Vault architecture | Separate handling for standard vs SEAH-sensitive content (policy) |
| **Secrets via environment** | All services | No credentials in repo; `.env` / deployment env vars |
| **Webhook/API shared secrets** | Ticketing + messaging + Keycloak | `TICKETING_SECRET_KEY`, `MESSAGING_API_KEY`, `KEYCLOAK_WEBHOOK_SECRET` |


### 5.1 Where each secret lives — the "lives in" inventory

> **Added 2026-08-20.** §5 above says *"no credentials in repo; `.env` / deployment env vars"*, which
> is true and answers the wrong question. It does not say **where the canonical copy is** or **what
> else holds a copy** — and that is precisely what nobody reconstructs from memory when a key has to
> be rotated in a hurry.
>
> ⚠ **The vault paths below are a PROPOSED convention, not a record of what exists.** Confirm the
> real Proton Pass vault/item names and replace them. A plausible-looking path that resolves to
> nothing is worse than a blank.

**Source of truth: Proton Pass.** Everything else is a derived copy. `pass-cli` can resolve
`pass://vault/item/field` references, so the vault column is intended to be machine-usable rather
than prose.

| Variable | Protects | Source of truth | Derived copies |
|---|---|---|---|
| `DB_ENCRYPTION_KEY` | ⭐ **Complainant PII at rest.** `backend` is the sole holder (T3-04) — ticketing has no accessor and must not regain one | `pass://GRM/Postgres/db_encryption_key` | local · AWS staging · DOR prod |
| `SEARCH_TOKEN_PEPPER` | ⭐ HMAC pepper for phone/email/name lookup tokens (D-19/F-3). ⚠ **Rotating it invalidates every stored token** — `scripts/database/rehash_search_tokens.py` must run on the same box | `pass://GRM/Postgres/search_token_pepper` | local · AWS staging · DOR prod |
| `POSTGRES_PASSWORD` | Database superuser | `pass://GRM/Postgres/password` | local · AWS staging · DOR prod |
| `OPS_DB_PASSWORD` | Scoped `ops_app` role | `pass://GRM/Postgres/ops_password` | local · AWS staging · DOR prod |
| `REDIS_PASSWORD` | Broker + result backend | `pass://GRM/Redis/password` | local · AWS staging · DOR prod |
| `TICKETING_SECRET_KEY` | Ticketing ↔ chatbot webhook | `pass://GRM/Ticketing/secret_key` | local · AWS staging · DOR prod |
| `MESSAGING_API_KEY` | Messaging API (`x-api-key`) — also guards `GET /api/grievance/{id}`, which serves **plaintext PII** | `pass://GRM/Messaging/api_key` | local · AWS staging · DOR prod |
| `KEYCLOAK_CLIENT_SECRET` | OIDC client | `pass://GRM/Keycloak/client_secret` | local · AWS staging · DOR prod |
| `KEYCLOAK_ADMIN_PASSWORD` | ⭐ Realm admin — **can mint officer accounts** | `pass://GRM/Keycloak/admin_password` | local · AWS staging · DOR prod |
| `KEYCLOAK_WEBHOOK_SECRET` | Onboarding webhook | `pass://GRM/Keycloak/webhook_secret` | local · AWS staging · DOR prod |
| `SMTP_PASSWORD` | Officer-invite mail relay | `pass://GRM/SMTP/password` | local · AWS staging · DOR prod |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | SNS (complainant SMS) | `pass://GRM/AWS/*` | local · AWS staging · DOR prod |
| `LLM_API_KEY` / `ASR_API_KEY` | Model provider. ⚠ **Grievance text is sent to whoever this authenticates against** | `pass://GRM/LLM/hf_token` | local · **GitHub secret `HF_TOKEN`** · staging/prod when the open config ships |

### 5.2 ⚠ CI holds exactly one secret, and it must stay that way

`HF_TOKEN` is the **only** GitHub Actions secret in this repository, and the reason is a rule worth
stating rather than rediscovering:

> **Anyone with repository write access can print a GitHub Actions secret** by editing a workflow.
> So a secret in CI is exposed to the union of everyone who can push — which is a wider set than
> everyone who can reach the production box.

That is an acceptable trade for `HF_TOKEN` specifically: it is **scoped** (inference only),
**capped** (extra usage is pre-paid, so the loaded balance is the ceiling), and **cheap to rotate**
(revoke, mint, re-paste; nothing stored depends on it). It is not an acceptable trade for anything
in the rows above it.

⚠ **Which is also why CI must not adopt vault injection.** `pass-cli` resolves `pass://` references
by authenticating to Proton — so a runner using it needs a Proton credential, and that credential
would itself have to live in a GitHub secret. The bootstrap does not disappear; it **moves and gets
worse**, because a vault session unlocks `DB_ENCRYPTION_KEY`, the Keycloak admin password and the
SMTP relay, where today CI can reach one rate-limited inference token.

**The rule that generalises:** inject-from-vault pays off where the environment *already* holds many
secrets — a developer laptop, a deploy box — because it removes plaintext at rest without widening
the blast radius. It is a **downgrade** where the environment holds few, because it trades one
scoped credential for vault-wide access. CI holds few. CI keeps its one secret.

### 5.3 Rotation

Rotating any row above means updating **every** derived copy. Copies do not self-update, and nothing
in this repository detects a stale one — the symptom is a service failing to start, or worse, a
lookup silently returning nothing (`SEARCH_TOKEN_PEPPER`).

- **Local** — regenerate from the vault (`pass-cli inject` / `pass-cli run --env-file`)
- **GitHub** — manual re-paste; `gh secret set HF_TOKEN` needs *Secrets: write* on the PAT
- **AWS staging / DOR prod** — per the deployment runbook, then restart the affected services
- ⚠ **`SEARCH_TOKEN_PEPPER` additionally requires** `scripts/database/rehash_search_tokens.py` on
  that box, or phone and email lookup return nothing and no error is raised

⚠ **`pass-cli` is beta and gated to paid Proton tiers.** Prove it on the developer machine before it
goes anywhere near a deploy path — a vault-resolution failure on the DOR box during an incident is a
much worse day than a hand-copied variable.

---

## 6. Messaging security

| Feature | Where | Notes |
|---|---|---|
| **Central Messaging API** | `POST /api/messaging/send-sms`, `send-email` | Single delivery layer with auth + logging |
| **API key enforcement** | Messaging router | `x-api-key` required when key configured |
| **No PII in staff SMS/WhatsApp alerts** | Policy + caller responsibility | Link + reference only |
| **Context metadata for audit** | Messaging request `context` | `source_system`, `purpose`, `grievance_id`, `ticket_id`, etc. |
| **Delivery failure envelope** | Messaging API responses | Structured `FAILED` + `error_code` |

Policy: [../ticketing_system/06_messaging_rules_whatsapp_sms.md](../ticketing_system/06_messaging_rules_whatsapp_sms.md)  
Contract: [../services/05_messaging_service.md](../services/05_messaging_service.md)

---

## 7. Audit logging and traceability

| Feature | Where | Notes |
|---|---|---|
| **Ticket event audit trail** | `ticketing.ticket_events` | Append-only lifecycle and communication events |
| **Admin audit log** | `ticketing.admin_audit_log` | Settings/user/role/org changes |
| **Contact reveal logging** | Reveal endpoints + ticket events | Who accessed PII, when |
| **Messaging send logs** | Messaging service | Destination + truncated content + context + result |
| **SLA/overdue accountability** | `ticketing.ticket_overdue_episodes` | Officer/step context at breach time |
| **Correlation keys** | Cross-service audits | `grievance_id`, `ticket_id`, `request_id`, reveal session id |

---

## 8. LLM and AI safety controls

| Feature | Where | Notes |
|---|---|---|
| **PII-clean context for findings** | `ticketing.ticket_context_cache` | Findings generated from policy-safe context |
| **Role-gated AI outputs** | `ai_summary_en`, findings endpoints | Hidden from L1/L2 where configured |
| **SEAH model tiering** | LLM tasks | Stronger model path for SEAH-sensitive processing |
| **Structured JSON outputs** | LLM client contracts | Validated response format + retry/failure states |
| **No PII in staff notification content** | Notification builders | Chatbot/SMS templates use references/links |

Policy detail: [11_llm_pipeline_policy.md](11_llm_pipeline_policy.md).

### 8.1 ⚠ Self-hosted inference (T2) — the intended posture, **not deployed**

Added by [DPG-25](../sprints/2026-08-llm/03-open-models-spec.md#dpg-25), 2026-08-20. **None of this
is built.** T2 is parked because nobody owns the GPU running costs (Q-05), and this section exists so
that unparking starts from a decided network posture instead of an improvised one. Full document:
[`../dpg/vllm-deployment.md`](../dpg/vllm-deployment.md).

| Control | Requirement | Status |
|---|---|---|
| **Network placement** | Private subnet; reachable **only** from the application security group. Never internet-facing | ⚠ not deployed |
| **Transport** | TLS terminated at a reverse proxy in front of vLLM | ⚠ not deployed |
| **Authentication** | `--api-key` set **even on a private network** — defence in depth | ⚠ not deployed |
| **Recovery** | Instance snapshotted once configured, so a rebuild is minutes | ⚠ not deployed |
| **Ownership** | A named owner for monitoring and restart | ⏸ **the parked item** — Q-05. Not the hardware: the *person* |

⚠ **The API-key row is not boilerplate.** §13 of this document already carries a row about a service
bound to `0.0.0.0` *"because the firewall holds"*. **Do not add a second one.** A private network is
a blast-radius control, not an authentication story, and an inference endpoint holds grievance text
in memory.

⚠ **And note what T1 means for this section while T2 stays parked.** T1 is the **steady state, not a
transition**: grievance text — including SEAH narratives — leaves the country indefinitely, reaches a
provider that is selected per request unless the model id pins one, and is unredacted until
[Sprint 3](../sprints/2026-08-llm/04-pii-redaction-spec.md) lands. That is the trade this parking
decision makes, and it is the reason redaction moved from prudent to necessary
([privacy assessment](../dpg/privacy-assessment.md) F-17).

---

## 9. Public and token-based access controls

| Feature | Where | Notes |
|---|---|---|
| **QR token intake** | `ticketing.qr_tokens`, `GET /api/v1/scan/{token}` | Opaque token, revocable, optional expiry |
| **Public closure token** | `closure_public_token` on resolved summary | Unguessable token URL for complainant closure page |
| **Token rate limiting (planned/enforced at edge)** | Nginx/middleware | Protect public endpoints from abuse |
| **No ticket_id in public URLs** | Public closure routes | Token-only public access surface |

---

## 10. Application and API hardening

| Feature | Where | Notes |
|---|---|---|
| **Schema-scoped migrations** | Alembic (`ticketing` + `public` streams) | Prevents accidental cross-domain DDL |
| **Deny-by-default sensitive reads** | Grievance broker APIs | Explicit reveal flow required for vault content |
| **Webhook-only ticket creation from chatbot** | `POST /api/v1/tickets` | `X-Ticketing-Secret` required |
| **Export rate limits** | `report_limits` settings | Caps synchronous export volume |
| **Quarterly assignment caps** | Reports plan settings | Max reports per role per quarter |
| **Internal-only service endpoints** | Messaging and admin APIs | Not exposed as public internet features |

---

## 11. Infrastructure and deployment security

| Feature | Where | Notes |
|---|---|---|
| **TLS termination** | Nginx / production domains | HTTPS for chatbot + GRM endpoints |
| **Keycloak enforced in production** | `docker-compose.grm.yml` (`--profile auth`) | Single `grm_ui` + `ticketing_api` run with `AUTH_MODE=keycloak` |
| **Environment separation** | staging vs production URLs | Independent deployment targets |
| **Backup encryption (ops requirement)** | Operations runbook | Required in production checklist |
| **Least-privilege DB roles (ops target)** | Deployment/operations | App roles scoped to required schemas |

References: [10_production_server_spec.md](10_production_server_spec.md), [03_operations.md](03_operations.md).

---

## 12. Security feature matrix by component

| Component | Key controls |
|---|---|
| **Chatbot / orchestrator** | OTP intake, session-bound replies, no direct ticketing DB access |
| **Backend grievance API** | Encryption, brokered PII, reveal sessions, status APIs |
| **Messaging service** | API key auth, audit context, delivery policy |
| **Ticketing API** | Role/scope checks, SEAH filter, action authorization, webhooks |
| **Ticketing UI** | OIDC auth, bypass disabled in prod, role-gated screens/actions |
| **Reports** | OfficerScope filtering, export limits, role-gated quarterly admin |

---

## 13. Planned / partial controls (tracked)

| Item | Status | Tracking doc |
|---|---|---|
| Executive Summary report tab hardening | Planned | `../ticketing_system/09_reports_and_report_builder.md` §12 |
| Automated PII pattern blocking in Messaging API | Optional enhancement | `../services/05_messaging_service.md` |
| Public closure OTP (ref + phone last-4) | Post-v1 option | `../ticketing_system/08_ticket_resolution_and_case_summary.md` §3.9 |
| SSE/real-time officer notifications | Post-proto | `../ticketing_system/05_ticketing_impl_plan.md` |
| Health/monitoring (healthchecks, watchdog, daily ops report, self-hosted backups) | Proposed | `../services/11_health_and_monitoring_service.md` |
| Security monitoring + hardening backlog (Redis auth, CORS, dep/CVE scan, rate limiting, log rotation) | Proposed | `../services/12_security_monitoring_service.md` |

---

## 14. Security verification checklist (ops)

Use before staging/production promotion:

- [ ] `APP_ENV=production` (or `staging`) and `AUTH_MODE=keycloak` — never `bypass` in deployed UI/API builds
- [ ] `KEYCLOAK_ISSUER` set and Keycloak brought up with `--profile auth`
- [ ] `TICKETING_SECRET_KEY`, `MESSAGING_API_KEY`, `KEYCLOAK_WEBHOOK_SECRET` set and rotated
- [ ] `DB_ENCRYPTION_KEY` set and backed up securely
- [ ] TLS certificates valid on public domains
- [ ] SEAH role visibility tested (standard roles cannot access SEAH tickets)
- [ ] Reveal-contact audit events verified in logs/DB
- [ ] Messaging test confirms no PII in staff notification payloads

---

## 15. Related specifications

> **Privacy assessment (2026-08-18).** This document inventories the *controls*.
> [`../dpg/privacy-assessment.md`](../dpg/privacy-assessment.md) inventories the **data flows** —
> every leg where personal data crosses a boundary, verified against the code — and assesses them
> against Nepal's Individual Privacy Act 2018. It also carries a findings register (§6) with items
> this document does **not** cover: encryption at rest failing open when the key is unset,
> unsalted search hashes, unencrypted-by-default backups, and the permanent unredacted egress of
> grievance text to a model provider outside Nepal. ⚠ It was drafted by an AI agent and **has had no
> legal review** — read its §0.1 before citing it.

| Topic | Document |
|---|---|
| **Privacy assessment + data-flow inventory (indicators 7, 9, 9a)** | [`../dpg/privacy-assessment.md`](../dpg/privacy-assessment.md) |
| Privacy architecture and reveal policy | [09_privacy.md](09_privacy.md) |
| LLM safety and processing policy | [11_llm_pipeline_policy.md](11_llm_pipeline_policy.md) |
| Ticketing security decisions | [../ticketing_system/00_ticketing_decisions.md](../ticketing_system/00_ticketing_decisions.md) |
| Ticketing API auth/integration | [../ticketing_system/03_ticketing_api_integration.md](../ticketing_system/03_ticketing_api_integration.md) |
| Staff messaging policy | [../ticketing_system/06_messaging_rules_whatsapp_sms.md](../ticketing_system/06_messaging_rules_whatsapp_sms.md) |
| Messaging service contract | [../services/05_messaging_service.md](../services/05_messaging_service.md) |
| Health, monitoring & self-hosted backups | [../services/11_health_and_monitoring_service.md](../services/11_health_and_monitoring_service.md) |
| Security monitoring & hardening backlog | [../services/12_security_monitoring_service.md](../services/12_security_monitoring_service.md) |
