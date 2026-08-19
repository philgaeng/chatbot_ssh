# Documentation Index

Top-level guide to the spec tree. Every folder has its own index; this page is the map.

> **`docs/<domain>/` says _what_ we build. [`engineering/`](engineering/) says _how_.** Start there before writing code.
> Reviews of spec completeness and codebase quality live in [`reviews/`](reviews/).

## Structure

```
docs/
├── PROGRESS.md          Operational build log (updated every commit)
├── TODO.md              Open gaps, next features, tech debt
├── ARCHIVING_AND_RETENTION.md   Cross-cutting retention + archive policy
├── engineering/         HOW we build: DB, services, API, tests, frontend, doc lifecycle
├── _starter_kit/        Portable skeleton of the above, for reuse on a new project
├── deployment/          Architecture, setup, operations, security, auth, DOCKER runbook
├── services/            Shared backend service contracts (chatbot + ticketing + ops)
├── ticketing_system/    GRM ticketing product and implementation specs (+ ui/)
├── rest_chatbot/        Chatbot architecture, flow, frontend, operations
├── seah/                SEAH intake flow + privacy/vault/reveal specs
├── dpg/                Digital Public Good qualification: compliance status + evidence pack
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
| [`models/01_seah_detection_benchmark.md`](models/01_seah_detection_benchmark.md) | **How a model change on the SEAH path is tested** — where the examples come from (authored by the Nepal team, never real cases), how many are needed, and why the set screens rather than ranks. ⚠ The dataset itself is deliberately **not** in this repository |

---

## Engineering standards (`docs/engineering`) — read before writing code

Start at [`00_engineering_index.md`](engineering/00_engineering_index.md) — it carries the ten rules and the shared definition of done.

| Document | Read before you touch |
|---|---|
| [`01_database.md`](engineering/01_database.md) | any model, migration, or SQL — Postgres, Alembic, three streams, naming, transactions, seeds |
| [`02_python_services.md`](engineering/02_python_services.md) | any service/engine/task — thin entrypoint over a fat service layer, function contracts, errors |
| [`03_api_layer.md`](engineering/03_api_layer.md) | any FastAPI router or schema — authz as a dependency, error mapping, pagination |
| [`04_testing.md`](engineering/04_testing.md) | any test — the pyramid, the integration-marker contract, pinning tests, CI |
| [`05_frontend.md`](engineering/05_frontend.md) | any `channels/ticketing-ui/` code — App Router, data access, errors, a11y, i18n |
| [`06_documentation_lifecycle.md`](engineering/06_documentation_lifecycle.md) | any doc — the four tiers, **when a sprint spec is promoted to a live spec**, honesty markers |

Visual and copy standards live with the UI specs: [`ui/02_design_system.md`](ticketing_system/ui/02_design_system.md) and [`ui/05_ui_copy_style.md`](ticketing_system/ui/05_ui_copy_style.md).

**Reusing this on another project:** [`_starter_kit/`](_starter_kit/) is a portable, project-agnostic skeleton of the standards above — engineering set, design system, and copy/tone guide, stripped of anything specific to this codebase. Copy it into a new repo and fill the `‹…›` placeholders and **FILL:** decision callouts. Start at [`_starter_kit/README.md`](_starter_kit/README.md).

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
| [`17_manual_browser_sweep.md`](deployment/17_manual_browser_sweep.md) | **Manual browser sweep** — the one session that clears the browser-only debt carried since Tier 1 (D-17/24/33/49/56 + HR-07, H2-02/06/08). Ordered so filing a grievance in Part A produces the ticket Part C checks; **read its warning first** — seeded tickets have no PII, so testing the card on one cannot tell "fixed" from "broken" |
| [`DOCKER.md`](deployment/DOCKER.md) | Build, start, migrate, seed, test, debug the container stack |

Legacy pre-Docker docs preserved in [`deployment/archive/`](deployment/archive/).

---

## Shared Services (`docs/services`)

Start at [`00_services_index.md`](services/00_services_index.md); endpoint matrix in [`01_api_contracts.md`](services/01_api_contracts.md).

| Document | Service |
|---|---|
| [`02_grievance_service.md`](services/02_grievance_service.md) | Grievance API (statuses, detail, PII broker) |
| [`03_voice_grievance_service.md`](services/03_voice_grievance_service.md) | Voice intake — webchat voice notes (accessible channel retired, CL-02) |
| [`04_file_processing_service.md`](services/04_file_processing_service.md) | Uploads, image compression policy, archived attachments |
| [`05_messaging_service.md`](services/05_messaging_service.md) | SMS (DOIT/SNS) + email contract |
| [`06_llm_service.md`](services/06_llm_service.md) | Backend LLM utilities (Whisper, classification, detection) |
| [`07_task_queue_service.md`](services/07_task_queue_service.md) | Chatbot Celery app and task registry |
| [`08_gsheet_monitoring_service.md`](services/08_gsheet_monitoring_service.md) | Google Sheet monitoring feed (RETIRED, CL-02) |
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
- **Officer UI**: [`ui/01_ui_spec.md`](ticketing_system/ui/01_ui_spec.md) + [`ui/02_design_system.md`](ticketing_system/ui/02_design_system.md) + [`ui/05_ui_copy_style.md`](ticketing_system/ui/05_ui_copy_style.md) (plain-language / on-screen wording — the copy source of truth)

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

## Digital Public Good (`docs/dpg`)

Qualification of the platform as a [Digital Public Good](https://www.digitalpublicgoods.net/standard), and the evidence pack that supports it.

| Document | Description |
|---|---|
| [`00_compliance_status.md`](dpg/00_compliance_status.md) | **The full assessment.** Indicator by indicator with file-and-line evidence: what complies, what does not, the LLM platform-independence question, and the questions for ADB's DPG consultant |
| [`dependency-licenses.md`](dpg/dependency-licenses.md) | **The generated licence audit** (DPG-02) — 153 packages across four dependency sets, scanned in-container from the resolved trees, with a disposition for every entry carrying conditions. Supersedes the hand-written inventories |
| [`privacy-assessment.md`](dpg/privacy-assessment.md) | **The privacy assessment and data-flow inventory** (DPG-04) — indicators 7, 9 and 9a. Thirteen data-flow legs verified against the code, assessed against Nepal's Individual Privacy Act 2018, with a 17-item findings register. ⚠ Drafted by an AI agent, **no legal review** — see its §0.1 |
| [`open-model-configuration.md`](dpg/open-model-configuration.md) | **How to run this system on open models** (DPG-16) — the two committed configurations, what the registry declares, the per-model structured-output measurements, the T1/T2/T3 ladder, and an explicit *what is not yet true* section (the open model ids are placeholders until DPG-23 measures them) |
| [`01_consultant_briefing.md`](dpg/01_consultant_briefing.md) | **The shareable summary** — what to send the consultant ahead of the meeting. The scorecard, what the sprint closes, the fourteen questions, and the full dependency inventory, in ~320 lines |

The engineering that closes the gaps is specced in [`sprints/2026-08-llm/`](sprints/2026-08-llm/README.md).

**Open-source project hygiene** (indicator 8) lives at the repository root, not under `docs/`:
[`SECURITY.md`](../SECURITY.md) (private disclosure — this platform holds SEAH reports),
[`CONTRIBUTING.md`](../CONTRIBUTING.md), [`CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md), and the
issue/PR templates under `.github/`. A governance model and a release/versioning policy are
deliberately deferred — [`sprints/2026-08-llm/followups/governance-and-versioning-policy.md`](sprints/2026-08-llm/followups/governance-and-versioning-policy.md).

---

## Sprints (`docs/sprints`)

One summary per sprint — see [`sprints/README.md`](sprints/README.md). Original sprint specs, agent prompts, and handoffs are read-only under [`sprints/archive/`](sprints/archive/).
