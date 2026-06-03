# API Contracts Matrix

Production API contract reference across shared backend services.

## Endpoints

| Endpoint | Method | Service Spec | Auth | Primary Consumers | Source |
|---|---|---|---|---|---|
| `/api/grievance/statuses` | GET | `docs/services/02_grievance_service.md` | None | chatbot, office tools | `backend/api/routers/grievance.py` |
| `/api/grievance/{grievance_id}` | GET | `docs/services/02_grievance_service.md` | None | chatbot, ticketing, monitoring | `backend/api/routers/grievance.py` |
| `/api/grievance/{grievance_id}/status` | POST | `docs/services/02_grievance_service.md` | None | office workflows, integrations | `backend/api/routers/grievance.py` |
| `/api/complainant/{complainant_id}` | PATCH | `docs/services/02_grievance_service.md` | `x-api-key` (`TICKETING_SECRET_KEY` when configured) | ticketing integration | `backend/api/routers/grievance.py` |
| `/upload-files` | POST | `docs/services/04_file_processing_service.md` | None | REST webchat, channel upload flows | `backend/api/routers/files.py` |
| `/file-status/{file_id}` | GET | `docs/services/04_file_processing_service.md` | None | REST webchat polling | `backend/api/routers/files.py` |
| `/files/{item}` | GET | `docs/services/04_file_processing_service.md` | None | chat UI, admin tooling | `backend/api/routers/files.py` |
| `/download/{file_id}` | GET | `docs/services/04_file_processing_service.md` | None | chat UI, admin tooling | `backend/api/routers/files.py` |
| `/task-status` | POST | `docs/services/04_file_processing_service.md` | None (internal caller path) | task workers -> websocket bridge | `backend/api/routers/files.py` |
| `/grievance-review/{grievance_id}` | GET | `docs/services/04_file_processing_service.md` | None | grievance review flows | `backend/api/routers/files.py` |
| `/grievance-review/{grievance_id}` | POST | `docs/services/04_file_processing_service.md` | None | grievance review flows | `backend/api/routers/files.py` |
| `/api/messaging/send-sms` | POST | `docs/services/05_messaging_service.md` | `x-api-key` (`MESSAGING_API_KEY`/`TICKETING_SECRET_KEY` fallback) | chatbot, ticketing, tasks | `backend/api/routers/messaging.py` |
| `/api/messaging/send-email` | POST | `docs/services/05_messaging_service.md` | `x-api-key` (`MESSAGING_API_KEY`/`TICKETING_SECRET_KEY` fallback) | chatbot, ticketing, tasks | `backend/api/routers/messaging.py` |
| `/gsheet-get-grievances` | GET | `docs/services/08_gsheet_monitoring_service.md` | `Authorization: Bearer ...` | Google Sheets monitoring | `backend/api/routers/gsheet.py` |
| `/accessible-file-upload` | POST | `docs/services/03_voice_grievance_service.md` | None | accessible channel | `backend/api/routers/voice_grievance.py` |
| `/grievance-status/{grievance_id}` | GET | `docs/services/03_voice_grievance_service.md` | None | accessible channel | `backend/api/routers/voice_grievance.py` |
| `/submit-grievance` | POST | `docs/services/03_voice_grievance_service.md` | None | accessible channel | `backend/api/routers/voice_grievance.py` |

## Realtime Contract

| Channel | Transport | Event(s) | Producer | Consumer |
|---|---|---|---|---|
| `/accessible-socket.io` room = grievance/session | Socket.IO | `status_update*` | backend task-status bridge | accessible clients |
| `/accessible-socket.io` room = `flask_session_id` | Socket.IO | `task_status`, `file_status_update` | backend task-status bridge | REST webchat |

## Ownership and Change Rules

- API behavior changes must be updated in the corresponding service spec in `docs/services/*`.
- Consumer-specific flow/UI behavior belongs in `docs/rest_chatbot/*`, not here.
- For new endpoints, add:
  1. service spec entry,
  2. matrix row in this file,
  3. source file reference.

## Versioning and Deprecation Policy

### Compatibility Levels

- **Non-breaking changes**: additive fields, new optional params, internal behavior improvements with same contract.
- **Breaking changes**: removing/renaming fields, changing required auth, changing status codes/response shape in existing paths.

### Non-breaking Change Policy

- Allowed without endpoint version bump.
- Must be reflected in the service spec and this matrix in the same change set.
- Existing required fields and semantics must remain stable.

### Breaking Change Policy

- Introduce a new endpoint version or parallel route (for example `/api/v2/...`) instead of in-place replacement.
- Keep prior version active during migration window until all known consumers are updated.
- Explicitly document:
  - impacted consumers (chatbot, ticketing, monitoring, accessible),
  - migration steps,
  - deprecation target date.

### Deprecation Stages

1. **Announce**: mark endpoint/field as deprecated in service spec and matrix notes.
2. **Dual-run**: support old and new contracts in parallel.
3. **Migrate**: update all consumers and verify runtime behavior.
4. **Remove**: delete old contract only after migration confirmation.

### Consumer Update Requirement

- Any breaking or deprecation change must include consumer-facing doc updates in:
  - `docs/rest_chatbot/*` (if chatbot behavior is affected),
  - relevant product/integration docs for other consumers.

### Auth and Security Changes

- Treat auth requirement changes as breaking by default.
- Roll out with parallel support where feasible to avoid service interruption.

### Error Contract Stability

- Existing error response keys should remain stable (`status`, `error_code`, `error` patterns) unless versioned.
- New error fields may be added if backward compatible.
