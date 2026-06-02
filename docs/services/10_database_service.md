# Database Service Spec

## 1) Scope

Shared database abstraction layer and manager composition used by APIs, tasks, and action code.

Primary modules:

- `backend/services/database_services/postgres_services.py`
- `backend/services/database_services/grievance_manager.py`
- `backend/services/database_services/complainant_manager.py`
- `backend/services/database_services/base_manager.py`
- optional integrations:
  - `mysql_services.py`
  - `ssh_tunnel.py`
  - `setup_encryption.py`

## 2) Primary Access Pattern

Most services import and use:

- `db_manager` from `postgres_services`

`db_manager` exposes manager domains (for example grievance/file/task/gsheet) used by:

- API routers
- task queue managers
- action handlers
- integration services

## 3) Functional Areas

### Grievance domain

- grievance CRUD/status/history
- grievance review data read/write
- status timeline and related lookups

### Complainant domain

- complainant create/update/fetch
- id and association lookups

### Files/recordings/transcriptions/translations

- attachment storage and lookup
- recording entries for voice flow
- transcription/translation persistence

### Task tracking

- task creation/update/status
- retry metadata and history

### Monitoring/reporting helpers

- gsheet monitoring queries

## 4) Security and Data Handling Notes

- Sensitive fields and encryption support exist via dedicated setup/encryption utilities.
- API layers enforce additional field-level controls (for example complainant patch whitelist).
- Cross-service callers should avoid direct SQL and use managers to keep behavior consistent.

## 5) Operational Notes

- Connection and SQL behavior are centralized in manager layer.
- Service consumers should handle DB errors explicitly and map to API-safe responses.
