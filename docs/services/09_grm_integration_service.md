# GRM Integration Service Spec

## 1) Scope

External/system integration orchestration layer for syncing chatbot grievance data with GRM systems.

Implementation:

- `backend/services/integration/grm_integration_service.py`

## 2) Components

### `GRMDataMapper`

Maps between chatbot grievance schema and GRM schema:

- chatbot -> GRM field mapping
- GRM -> chatbot reverse mapping
- status mapping translation

### `GRMSyncManager`

Core sync manager:

- initializes remote connection (including SSH tunnel path if configured)
- syncs single or batch grievances
- fetches GRM status
- updates GRM-side status
- tracks sync history and metrics

### `GRMIntegrationOrchestrator`

High-level orchestration facade:

- initialize/cleanup lifecycle
- process single/batch payloads
- integration status reporting

## 3) Dependencies

- MySQL and GRM service wrappers from `database_services/mysql_services.py`
- SSH tunnel utilities
- GRM config and field/status mapping constants (`backend/config/grm_config.py`)

## 4) Runtime Model

- Feature-gated by integration config (`enabled` flag).
- Maintains in-memory sync history and statistics in process.
- Designed as optional integration path (not a hard dependency for core chatbot runtime).

## 5) Operational Considerations

- Initialization must succeed before sync operations are considered available.
- Failures return structured sync result objects with status/message/error.
- Cleanup should close tunnel/resources on shutdown.
