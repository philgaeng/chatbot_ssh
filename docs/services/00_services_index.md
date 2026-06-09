# Shared Service Specifications

This folder contains production specs for backend services used across multiple project areas.

## Service Catalog

- `docs/services/01_api_contracts.md`
- `docs/services/05_messaging_service.md`
- `docs/services/02_grievance_service.md`
- `docs/services/04_file_processing_service.md`
- `docs/services/08_gsheet_monitoring_service.md`
- `docs/services/03_voice_grievance_service.md`
- `docs/services/06_llm_service.md`
- `docs/services/07_task_queue_service.md`
- `docs/services/10_database_service.md`
- `docs/services/09_grm_integration_service.md`

## Cross-cutting policies

- [`docs/ARCHIVING_AND_RETENTION.md`](../ARCHIVING_AND_RETENTION.md) — resolved grievance archiving (touches file processing, task queue, grievance API, ticketing)

## Scope Boundary

- Shared service contracts and responsibilities live in `docs/services`.
- Chatbot-specific orchestration/UI/runtime behavior lives in `docs/rest_chatbot`.
