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
| **Demo-only bypass mode** | Local UI (`:3001`) | `NEXT_PUBLIC_BYPASS_AUTH=true`; must be disabled in production |
| **OTP verification (chatbot intake)** | Complainant flow | Phone verification before grievance submission |

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
| **Field-level DB encryption** | Backend grievance/complainant data | `DB_ENCRYPTION_KEY` + pgcrypto model |
| **Envelope/key split by sensitivity** | Vault architecture | Separate handling for standard vs SEAH-sensitive content (policy) |
| **Secrets via environment** | All services | No credentials in repo; `.env` / deployment env vars |
| **Webhook/API shared secrets** | Ticketing + messaging + Keycloak | `TICKETING_SECRET_KEY`, `MESSAGING_API_KEY`, `KEYCLOAK_WEBHOOK_SECRET` |

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
| **Separate auth stack in production** | `docker-compose.grm.yml` | `grm_ui_auth` + `ticketing_api_auth` |
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

- [ ] `NEXT_PUBLIC_BYPASS_AUTH` is **false** in production UI builds
- [ ] `KEYCLOAK_ISSUER` and auth containers enabled
- [ ] `TICKETING_SECRET_KEY`, `MESSAGING_API_KEY`, `KEYCLOAK_WEBHOOK_SECRET` set and rotated
- [ ] `DB_ENCRYPTION_KEY` set and backed up securely
- [ ] TLS certificates valid on public domains
- [ ] SEAH role visibility tested (standard roles cannot access SEAH tickets)
- [ ] Reveal-contact audit events verified in logs/DB
- [ ] Messaging test confirms no PII in staff notification payloads

---

## 15. Related specifications

| Topic | Document |
|---|---|
| Privacy architecture and reveal policy | [09_privacy.md](09_privacy.md) |
| LLM safety and processing policy | [11_llm_pipeline_policy.md](11_llm_pipeline_policy.md) |
| Ticketing security decisions | [../ticketing_system/00_ticketing_decisions.md](../ticketing_system/00_ticketing_decisions.md) |
| Ticketing API auth/integration | [../ticketing_system/03_ticketing_api_integration.md](../ticketing_system/03_ticketing_api_integration.md) |
| Staff messaging policy | [../ticketing_system/06_messaging_rules_whatsapp_sms.md](../ticketing_system/06_messaging_rules_whatsapp_sms.md) |
| Messaging service contract | [../services/05_messaging_service.md](../services/05_messaging_service.md) |
| Health, monitoring & self-hosted backups | [../services/11_health_and_monitoring_service.md](../services/11_health_and_monitoring_service.md) |
| Security monitoring & hardening backlog | [../services/12_security_monitoring_service.md](../services/12_security_monitoring_service.md) |
