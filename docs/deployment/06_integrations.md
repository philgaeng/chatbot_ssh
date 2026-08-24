# Integrations

**Status:** As-built, July 2026 — rewritten from legacy doc, original in [`archive/06_integrations.md`](archive/06_integrations.md). Twilio/WhatsApp and OAuth sample code removed (never in the current stack).

## 1. Chatbot → GRM ticketing (the primary integration)

- **Ticket creation:** on submit, `backend/actions/utils/ticketing_dispatch.py` POSTs to the ticketing API (`POST /api/v1/tickets`).
- **Reconciliation:** `ticketing.tasks.grievance_sync.sync_grievances` (GRM Celery Beat) sweeps `public.grievances` → `ticketing.tickets` for missed webhooks.
- **Data-boundary rules** (no PII in `ticketing.*`, PII fetched via `GET /api/grievance/{id}`): `CLAUDE.md` + [`../ticketing_system/03_ticketing_api_integration.md`](../ticketing_system/03_ticketing_api_integration.md).
- Dev bring-up + seed baseline for validating this flow: [`03_operations.md`](03_operations.md) §2 (Startup Runbook).

## 2. Messaging — SMS (DOIT gateway, in Nepal) + email (SMTP)

Canonical spec: [`../services/05_messaging_service.md`](../services/05_messaging_service.md). Summary:

| Channel | Provider | Notes |
|---|---|---|
| SMS | **DOIT government gateway** (`SMS_PROVIDER=doit`, `DOIT_SMS_BEARER_TOKEN`) | Production Nepal |
| SMS | ~~**AWS SNS**~~ | ✅ **Removed 2026-08-24** — no cross-border SMS fallback exists. `SMS_PROVIDER` unset with no token ⇒ `disabled` |
| SMS | `disabled` | No outbound SMS |
| Email | SMTP relay (`SMTP_*` in `env.local`) | Shared by Messaging API, quarterly reports, and Keycloak invite mail |

All callers go through the Messaging API (`POST /api/messaging/send-sms|send-email`, `x-api-key`) — see [`04_backend.md`](04_backend.md) §3. There is **no Twilio** integration.

## 3. Google Sheets monitoring — RETIRED (CL-02, July 2026)

The read-only Apps Script monitoring dashboard (`channels/monitoring-gsheet/`) and its backend feed (`GET /gsheet-get-grievances`, `GSHEET_BEARER_TOKEN`) were removed. The endpoint was already dead (no `db_manager.gsheet.get_grievances_for_gsheet` implementation). Monitoring is now served by the ticketing UI. Historical spec: [`../services/08_gsheet_monitoring_service.md`](../services/08_gsheet_monitoring_service.md).

## 4. Legacy MySQL GRM sync (dormant)

Code for syncing grievances into the legacy PHP/MySQL GRM system still exists but is **not active** in any environment:

- `backend/services/integration/grm_integration_service.py` (+ MySQL/SSH-tunnel services, `GRM_MYSQL_*` / `GRM_SSH_*` / `GRM_INTEGRATION_ENABLED` env vars)
- Spec: [`../services/09_grm_integration_service.md`](../services/09_grm_integration_service.md)

The GRM function is now served by the in-repo ticketing system (`ticketing/` + `channels/ticketing-ui/`). Leave the legacy path disabled unless a bidirectional sync with the old system is explicitly required; the archived doc retains the full configuration reference.

## 5. Identity — Keycloak

Officer authentication (OIDC), invite flow, and the Keycloak→ticketing webhook are covered in [`16_auth_keycloak.md`](16_auth_keycloak.md).
