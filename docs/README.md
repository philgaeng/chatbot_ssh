# Documentation Index

This is the top-level guide for production and historical docs.

## Structure

```
docs/
├── deployment/          Ops and deployment runbooks
├── services/            Shared backend service contracts (cross-project)
├── ticketing_system/    GRM ticketing product and implementation specs
├── rest_chatbot/        Chatbot-specific architecture, flow, frontend, operations
└── sprints/             Historical notes and refactor specs (read-only)
```

---

## Deployment & Operations (`docs/deployment`)

| Document | Description |
|---|---|
| [`deployment/01_architecture.md`](deployment/01_architecture.md) | System components, service map, request/data flow |
| [`deployment/02_setup.md`](deployment/02_setup.md) | Setup, Docker, runtime configuration |
| [`deployment/03_operations.md`](deployment/03_operations.md) | Monitoring, troubleshooting, maintenance tasks |
| [`deployment/04_backend.md`](deployment/04_backend.md) | Backend service architecture and runtime notes |
| [`deployment/05_rasa.md`](deployment/05_rasa.md) | Rasa and NLU operational references |
| [`deployment/06_integrations.md`](deployment/06_integrations.md) | External integrations and boundaries |
| [`deployment/07_migrations_policy.md`](deployment/07_migrations_policy.md) | Migration ownership/policy across schemas |
| [`deployment/08_commit_strategy.md`](deployment/08_commit_strategy.md) | Branch and commit workflow |
| [`deployment/09_privacy.md`](deployment/09_privacy.md) | PII handling and privacy controls |
| [`deployment/13_security.md`](deployment/13_security.md) | Security features index (auth, PII, audit, SEAH, messaging) |
| [`deployment/10_production_server_spec.md`](deployment/10_production_server_spec.md) | Production infra/server spec |
| [`deployment/11_llm_pipeline_policy.md`](deployment/11_llm_pipeline_policy.md) | LLM task pipeline policy |
| [`deployment/12_environment_urls.md`](deployment/12_environment_urls.md) | Environment URL registry |

---

## Shared Services (`docs/services`)

Primary entry points:

- [`services/00_services_index.md`](services/00_services_index.md)
- [`services/01_api_contracts.md`](services/01_api_contracts.md)

Service specs:

- [`services/02_grievance_service.md`](services/02_grievance_service.md)
- [`services/03_voice_grievance_service.md`](services/03_voice_grievance_service.md)
- [`services/04_file_processing_service.md`](services/04_file_processing_service.md)
- [`services/05_messaging_service.md`](services/05_messaging_service.md)
- [`services/06_llm_service.md`](services/06_llm_service.md)
- [`services/07_task_queue_service.md`](services/07_task_queue_service.md)
- [`services/08_gsheet_monitoring_service.md`](services/08_gsheet_monitoring_service.md)
- [`services/09_grm_integration_service.md`](services/09_grm_integration_service.md)
- [`services/10_database_service.md`](services/10_database_service.md)

---

## GRM Ticketing System (`docs/ticketing_system`)

Primary index:

- [`ticketing_system/README.md`](ticketing_system/README.md)

Core specs:

- [`ticketing_system/00_ticketing_decisions.md`](ticketing_system/00_ticketing_decisions.md)
- [`ticketing_system/00_ticketing_overview_and_questions.md`](ticketing_system/00_ticketing_overview_and_questions.md)
- [`ticketing_system/01_ticketing_scope_and_stack.md`](ticketing_system/01_ticketing_scope_and_stack.md)
- [`ticketing_system/02_ticketing_domain_and_settings.md`](ticketing_system/02_ticketing_domain_and_settings.md)
- [`ticketing_system/03_ticketing_api_integration.md`](ticketing_system/03_ticketing_api_integration.md)
- [`ticketing_system/04_ticketing_schema.md`](ticketing_system/04_ticketing_schema.md)
- [`ticketing_system/05_ticketing_impl_plan.md`](ticketing_system/05_ticketing_impl_plan.md)
- [`ticketing_system/06_messaging_rules_whatsapp_sms.md`](ticketing_system/06_messaging_rules_whatsapp_sms.md)
- [`ticketing_system/07_officer_management_and_assignment.md`](ticketing_system/07_officer_management_and_assignment.md)
- [`ticketing_system/08_ticket_resolution_and_case_summary.md`](ticketing_system/08_ticket_resolution_and_case_summary.md)
- [`ticketing_system/09_reports_and_report_builder.md`](ticketing_system/09_reports_and_report_builder.md)
- [`ticketing_system/Escalation_rules.md`](ticketing_system/Escalation_rules.md)
- [`ticketing_system/LOCATION_CODES.md`](ticketing_system/LOCATION_CODES.md)

Feature specs:

- [`ticketing_system/features/projects_catalog_admin_layers_and_settings.md`](ticketing_system/features/projects_catalog_admin_layers_and_settings.md)
- [`ticketing_system/features/settings/settings_tab_projects_and_seah_contact_centers.md`](ticketing_system/features/settings/settings_tab_projects_and_seah_contact_centers.md)

---

## REST Chatbot (`docs/rest_chatbot`)

Primary index:

- [`rest_chatbot/00_rest_chatbot_index.md`](rest_chatbot/00_rest_chatbot_index.md)

Production specs:

- [`rest_chatbot/01_backend_spec.md`](rest_chatbot/01_backend_spec.md)
- [`rest_chatbot/02_flow_spec.md`](rest_chatbot/02_flow_spec.md)
- [`rest_chatbot/03_frontend_spec.md`](rest_chatbot/03_frontend_spec.md)
- [`rest_chatbot/04_operations_spec.md`](rest_chatbot/04_operations_spec.md)

Workflow map assets:

- [`rest_chatbot/workflow_maps/seah_intake_turn_map.json`](rest_chatbot/workflow_maps/seah_intake_turn_map.json)
- [`rest_chatbot/workflow_maps/turn_map.schema.json`](rest_chatbot/workflow_maps/turn_map.schema.json)

---

## Sprints (Historical, Read-Only) (`docs/sprints`)

| Folder | Contents |
|---|---|
| [`sprints/claude-tickets/`](sprints/claude-tickets/) | Claude session outputs, handoffs, UI notes |
| [`sprints/Refactor specs/`](sprints/Refactor specs/) | Past refactor specification sets |
| [`sprints/deployment refactor/`](sprints/deployment refactor/) | Deployment refactor notes |
