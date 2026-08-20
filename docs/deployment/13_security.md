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
> else holds a copy** — precisely what nobody reconstructs from memory when a key must be rotated in
> a hurry.

**Source of truth: Bitwarden Secrets Manager (`bws`).** Everything else is a derived copy.

⚠ **Two Bitwarden products, two vaults, and the distinction is load-bearing here.** Personal logins
live in the password manager (`bw`). **Machine secrets — everything in this section — live in
Secrets Manager (`bws`) under an organization.** They are separate stores with separate CLIs and
separate access models. Keeping them apart is what makes "lives in" unambiguous: if it is in this
table, it is in `bws`, never in `bw`.

**Convention:** one `bws` **project per environment**, and each secret's **key is the environment
variable name itself**. That is what makes the same name carrying three different values tractable —
the project selects the environment, so nothing has to be renamed per environment.

| Project | Environment | Machine account may read |
|---|---|---|
| `grm-local` | developer machines | everything below |
| `grm-staging` | AWS staging | everything below |
| `grm-prod` | DOR production | everything below |
| `grm-ci` | GitHub Actions | ⚠ **`LLM_API_KEY` / `ASR_API_KEY` only** — see §5.2 |

| Variable | Protects | Traps |
|---|---|---|
| `DB_ENCRYPTION_KEY` | ⭐ **Complainant PII at rest.** `backend` is the sole holder (T3-04); ticketing has no accessor and must not regain one, pinned by `tests/ticketing/test_pii_boundary.py` | Rotating it without re-encrypting orphans every stored value |
| `SEARCH_TOKEN_PEPPER` | ⭐ HMAC pepper for phone/email/name lookup tokens (D-19/F-3) | ⚠ **Rotating invalidates every stored token.** `scripts/database/rehash_search_tokens.py` must run on that box, or lookup silently returns nothing and raises nothing |
| `POSTGRES_PASSWORD` | Database superuser | |
| `OPS_DB_PASSWORD` | Scoped `ops_app` role | |
| `REDIS_PASSWORD` | Broker + result backend | |
| `TICKETING_SECRET_KEY` | Ticketing ↔ chatbot webhook | |
| `MESSAGING_API_KEY` | Messaging API — **also guards `GET /api/grievance/{id}`, which serves plaintext PII** | |
| `KEYCLOAK_CLIENT_SECRET` | OIDC client | |
| `KEYCLOAK_ADMIN_PASSWORD` | ⭐ Realm admin — **can mint officer accounts** | |
| `KEYCLOAK_WEBHOOK_SECRET` | Onboarding webhook | |
| `SMTP_PASSWORD` | Officer-invite mail relay | |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | SNS (complainant SMS) | |
| `LLM_API_KEY` / `ASR_API_KEY` | Model provider. ⚠ **Grievance text is sent to whoever this authenticates against** | Also copied into the GitHub secret `HF_TOKEN` |

### 5.2 ⚠ `env.local` cannot be eliminated — it can only be generated

**Ten compose services declare `env_file: env.local`** (`docker-compose.yml` ×6,
`docker-compose.grm.yml` ×4). Containers read that **file**, not the ambient shell environment, so
`bws run -- docker compose up` would inject variables the containers never see.

⚠ **This rules out the "never write the file" pattern** until those ten service definitions are
converted to `environment:` with `${VAR}` substitution. That is a real refactor with a real
regression risk, and it is **not** currently worth doing — so the shape is *generate the file*, not
*replace the file*:

```bash
# Regenerate env.local from the vault. Same file the stack already reads.
export BWS_ACCESS_TOKEN=…                      # scoped to ONE project
bws secret list "$GRM_BWS_PROJECT" -o env > env.local
chmod 600 env.local
```

**What that buys, stated honestly, because it is less than "the copy disappears":**

| | |
|---|---|
| ✅ **Rotation** | regenerate and ship, instead of SSH-and-edit |
| ✅ **Provenance** | the env is derived from a known vault state, not from whatever someone typed in March |
| ✅ **Drift detection** | regenerate to a temp file and `diff` against what is on the box |
| ❌ **Encryption at rest** | **unchanged.** `env.local` is still plaintext on every machine that has one |

Getting plaintext off the boxes needs a different mechanism entirely (Docker secrets, systemd
credentials, a KMS). Out of scope, and named here so nobody assumes this bought it.

### 5.3 Stage and production — inject on the developer machine, ship the file

`make aws-deploy` and `make prod-deploy` run `git pull && docker compose up` **on the box** and never
touch `env.local`. Each box's copy is hand-maintained over SSH. That is the thing worth changing, and
the safe way is to keep vault resolution **on the developer machine**:

```
bws secret list <project> -o env  →  env.local (0600)  →  scp to box  →  deploy
```

⚠ **Do not run `bws` on the DOR box.** It would add a **runtime dependency on Bitwarden being
reachable from Nepal government infrastructure** for services to start — on a host reached only via
VPN with a password prompt. Resolving on the laptop fails *before* anything ships; resolving on the
box fails at 2am during an incident. The machine-account token also never leaves your machine.

**Keep secret rotation a separate `make` target from deploy.** Shipping code and rotating credentials
are different operations with different blast radii, and coupling them means every deploy rewrites
production's environment.

### 5.4 ⚠ CI: keep the GitHub secret — but the reason is narrower than it looks

`HF_TOKEN` is the **only** GitHub Actions secret in this repository. The standing rule:

> **Anyone with repository *write* access can print a GitHub Actions secret** by editing a workflow.
> So a CI secret is exposed to the union of everyone who can push — a wider set than everyone who can
> reach production.

That is acceptable for `HF_TOKEN`: **scoped** to inference, **capped** (extra usage is pre-paid, so
the loaded balance is the ceiling), **cheap to rotate**, and nothing stored depends on it.

**Why not resolve it from the vault in CI instead?** ⚠ **Not for the reason first written here.** The
original argument was that a vault session unlocks everything — true of a whole-vault credential, and
**not true of `bws`**, whose machine accounts are scoped per project. A `grm-ci` project containing
only the model keys yields a token whose blast radius equals the token it replaces. The blast-radius
objection largely dissolves.

What remains is smaller and still decisive **today**:

- it is **one secret for one secret** — `BWS_ACCESS_TOKEN` instead of `HF_TOKEN`, no net reduction;
- it adds a **dependency on Bitwarden being up** for every CI run;
- and it adds indirection for no present gain.

⭐ **The flip point is worth writing down, because it will arrive:** once CI needs **three or more**
secrets, central rotation beats pasting, and a project-scoped `bws` machine account becomes the
better answer. Revisit then — and until then this is a *no payoff yet* decision, not a *dangerous*
one.

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
