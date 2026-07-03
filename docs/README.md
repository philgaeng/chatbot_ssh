# Documentation Index

Top-level guide to the spec tree. Every folder has its own index; this page is the map.

> Reviews of spec completeness and codebase quality live in [`reviews/`](reviews/).

## Structure

```
docs/
├── PROGRESS.md          Operational build log (updated every commit)
├── TODO.md              Open gaps, next features, tech debt
├── ARCHIVING_AND_RETENTION.md   Cross-cutting retention + archive policy
├── deployment/          Architecture, setup, operations, security, auth, DOCKER runbook
├── services/            Shared backend service contracts (chatbot + ticketing + ops)
├── ticketing_system/    GRM ticketing product and implementation specs (+ ui/)
├── rest_chatbot/        Chatbot architecture, flow, frontend, operations
├── seah/                SEAH intake flow + privacy/vault/reveal specs
├── reviews/             Devil's-advocate reviews (specs, codebase)
└── sprints/             One summary per sprint; full originals in sprints/archive/
```

---

## Operational logs (`docs/` root)

| Document | Description |
|---|---|
| [`PROGRESS.md`](PROGRESS.md) | Current build state, demo DB, deviations, commit log |
| [`TODO.md`](TODO.md) | Open gaps, post-demo backlog, tech debt |
| [`ARCHIVING_AND_RETENTION.md`](ARCHIVING_AND_RETENTION.md) | Resolved-case archiving schedule, `archiving_policy` settings, attachment tiering |

---

## Deployment & Operations (`docs/deployment`)

| Document | Description |
|---|---|
| [`01_architecture.md`](deployment/01_architecture.md) | As-built system map: compose services/ports, request/data flows, schemas & migration streams |
| [`02_setup.md`](deployment/02_setup.md) | Docker-era setup: env files, bring-up, migrations, seeding |
| [`03_operations.md`](deployment/03_operations.md) | Startup runbook, migration run order, monitoring, backups, logs |
| [`04_backend.md`](deployment/04_backend.md) | Orchestrator + backend API + Celery queues |
| [`06_integrations.md`](deployment/06_integrations.md) | Chatbot→ticketing, SMS/SMTP, gsheet, dormant legacy GRM sync |
| [`07_migrations_policy.md`](deployment/07_migrations_policy.md) | Three-stream Alembic ownership (ticketing/public/ops) |
| [`08_commit_strategy.md`](deployment/08_commit_strategy.md) | Branch/commit workflow, staging deploys, QR scan flow |
| [`09_privacy.md`](deployment/09_privacy.md) | PII architecture: vault vs metadata vs derived summaries |
| [`10_production_server_spec.md`](deployment/10_production_server_spec.md) | Production infra/server spec |
| [`11_llm_pipeline_policy.md`](deployment/11_llm_pipeline_policy.md) | LLM task pipeline policy (translation, findings, PII boundary) |
| [`12_environment_urls.md`](deployment/12_environment_urls.md) | Environment URL registry (incl. `grm-chatbot.dor.gov.np` prod) |
| [`13_security.md`](deployment/13_security.md) | Security controls index (Keycloak, scopes, PII, QR, preflight) |
| [`14_key_and_secret_lifecycle.md`](deployment/14_key_and_secret_lifecycle.md) | Secret inventory, rotation, `DB_ENCRYPTION_KEY` backup |
| [`15_host_hardening.md`](deployment/15_host_hardening.md) | Host-OS hardening runbook (ufw, sshd, fail2ban, watchdog cron) |
| [`16_auth_keycloak.md`](deployment/16_auth_keycloak.md) | Keycloak as-built: realm, clients, invites, SMTP, webhook, themes |
| [`DOCKER.md`](deployment/DOCKER.md) | Build, start, migrate, seed, test, debug the container stack |

Legacy pre-Docker docs preserved in [`deployment/archive/`](deployment/archive/).

---

## Shared Services (`docs/services`)

Start at [`00_services_index.md`](services/00_services_index.md); endpoint matrix in [`01_api_contracts.md`](services/01_api_contracts.md).

| Document | Service |
|---|---|
| [`02_grievance_service.md`](services/02_grievance_service.md) | Grievance API (statuses, detail, PII broker) |
| [`03_voice_grievance_service.md`](services/03_voice_grievance_service.md) | Voice intake (accessible + webchat voice notes) |
| [`04_file_processing_service.md`](services/04_file_processing_service.md) | Uploads, image compression policy, archived attachments |
| [`05_messaging_service.md`](services/05_messaging_service.md) | SMS (DOIT/SNS) + email contract |
| [`06_llm_service.md`](services/06_llm_service.md) | Backend LLM utilities (Whisper, classification, detection) |
| [`07_task_queue_service.md`](services/07_task_queue_service.md) | Chatbot Celery app and task registry |
| [`08_gsheet_monitoring_service.md`](services/08_gsheet_monitoring_service.md) | Google Sheet monitoring feed |
| [`09_grm_integration_service.md`](services/09_grm_integration_service.md) | Legacy MySQL GRM sync (dormant) |
| [`10_database_service.md`](services/10_database_service.md) | `db_manager` abstraction layer |
| [`11_health_and_monitoring_service.md`](services/11_health_and_monitoring_service.md) | `ops/` monitor: health checks, watchdog, backups, daily report |
| [`12_security_monitoring_service.md`](services/12_security_monitoring_service.md) | Dependency/CVE scanning + hardening backlog |

---

## GRM Ticketing System (`docs/ticketing_system`)

Full index: [`ticketing_system/README.md`](ticketing_system/README.md). Highlights:

- Decisions & scope: [`00_ticketing_decisions.md`](ticketing_system/00_ticketing_decisions.md), [`01_ticketing_scope_and_stack.md`](ticketing_system/01_ticketing_scope_and_stack.md)
- Domain, API, schema: [`02`](ticketing_system/02_ticketing_domain_and_settings.md) / [`03`](ticketing_system/03_ticketing_api_integration.md) / [`04`](ticketing_system/04_ticketing_schema.md)
- Officers, resolution, reports, queue: [`07`](ticketing_system/07_officer_management_and_assignment.md) / [`08`](ticketing_system/08_ticket_resolution_and_case_summary.md) / [`09`](ticketing_system/09_reports_and_report_builder.md) / [`15`](ticketing_system/15_ticket_queue_search_and_filters.md)
- Settings & admin: [`10`](ticketing_system/10_settings_overview.md)–[`14`](ticketing_system/14_platform_settings.md), org chart [`16`](ticketing_system/16_org_chart_and_positions.md)
- Data models: classification [`17`](ticketing_system/17_classification_status.md), geography [`18`](ticketing_system/18_geography_and_locations.md), [`LOCATION_CODES.md`](ticketing_system/LOCATION_CODES.md), [`Escalation_rules.md`](ticketing_system/Escalation_rules.md)
- **Officer UI**: [`ui/01_ui_spec.md`](ticketing_system/ui/01_ui_spec.md) + [`ui/02_design_system.md`](ticketing_system/ui/02_design_system.md)

---

## REST Chatbot (`docs/rest_chatbot`)

Start at [`00_rest_chatbot_index.md`](rest_chatbot/00_rest_chatbot_index.md).

| Document | Description |
|---|---|
| [`01_backend_spec.md`](rest_chatbot/01_backend_spec.md) | Orchestrator API, session model, ticketing dispatch |
| [`02_flow_spec.md`](rest_chatbot/02_flow_spec.md) | State machine, forms, SEAH route, road-hazard fast path |
| [`03_frontend_spec.md`](rest_chatbot/03_frontend_spec.md) | REST_webchat client (composer, voice, uploads, i18n) |
| [`04_operations_spec.md`](rest_chatbot/04_operations_spec.md) | Runtime services, startup, env vars |
| [`early_attachment_upload.md`](rest_chatbot/early_attachment_upload.md) | Attach-anytime upload spec |

---

## SEAH (`docs/seah`)

Start at [`seah/README.md`](seah/README.md).

| Document | Description |
|---|---|
| [`01_seah_intake_flow.md`](seah/01_seah_intake_flow.md) | As-built intake: victim/witness/focal routes, slots, outro, close controls |
| [`02_vault_privacy_and_reveal.md`](seah/02_vault_privacy_and_reveal.md) | Canonical model, `grievance_parties`, vault, reveal + audit (with implementation-status table) |
| [`03_seah_decision_log.md`](seah/03_seah_decision_log.md) | Condensed decision log with statuses + open items |

---

## Sprints (`docs/sprints`)

One summary per sprint — see [`sprints/README.md`](sprints/README.md). Original sprint specs, agent prompts, and handoffs are read-only under [`sprints/archive/`](sprints/archive/).
