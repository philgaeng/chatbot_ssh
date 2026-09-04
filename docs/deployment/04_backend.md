# Backend services — Orchestrator + Backend API

**Status:** As-built, July 2026 — rewritten from legacy doc, original in [`archive/04_backend.md`](archive/04_backend.md). Flask and the Django Helpdesk option are gone; both entry points are FastAPI.
**Last updated:** 2026-08-24 · ⚠ backfilled from git 2026-09-04; not re-verified against the code

## 1. Two entry points

| Service | Module | Port | Role |
|---|---|---|---|
| **Orchestrator** | `backend.orchestrator.main:app` | 8000 | Conversation: `POST /message` runs the state machine and invokes intake actions from `backend/actions/` in-process (no Rasa server). Optional Socket.IO bridge for legacy clients. |
| **Backend API** | `backend.api.fastapi_app:app` | 5001 | Data plane: files, grievance CRUD/status, messaging, voice, gsheet monitoring. |

Both are started by Docker Compose (`uvicorn ... --host 0.0.0.0`). The actions call shared code in `backend/services/` (messaging, LLM, database managers, file server core, image compression).

## 2. Orchestrator

- `POST /message` — request `{ user_id, message_id?, text, payload?, channel? }` → response `{ messages, next_state, expected_input_type }`.
- `GET /health`.
- Callers: REST webchat (`channels/REST_webchat/`), ticketing officer-reply (`ticketing/clients/orchestrator.py`, `channel: "ticketing"`).
- Conversation flow spec: [`../rest_chatbot/02_flow_spec.md`](../rest_chatbot/02_flow_spec.md).

## 3. Backend API — routers (as mounted in `backend/api/fastapi_app.py`)

All routers are included without a prefix; paths below are the real URL paths. Socket.IO ASGI app mounted at `/accessible-socket.io`.

### `backend/api/routers/grievance.py`

| Endpoint | Purpose |
|---|---|
| `GET /api/grievance/{grievance_id}` | Grievance detail incl. decrypted PII (primary source for ticketing) |
| `POST /api/grievance/{grievance_id}/status` | Update status (triggers complainant notifications) |
| `GET /api/grievance/statuses` | List available statuses |

### `backend/api/routers/files.py`

| Endpoint | Purpose |
|---|---|
| `POST /upload-files` | Multi-file upload for a grievance (queues `file_queue` processing, incl. image compression) |
| `POST /upload-voice-chunk` · `POST /upload-voice-complete` | Chunked voice-recording upload |
| `GET /files/{item}` · `GET /download/{file_id}` · `GET /file-status/{file_id}` | List / download / processing status |
| `GET|POST /grievance-review/{grievance_id}` | Review-form data used by the webchat |
| `POST /generate-ids` | Generate grievance/session identifiers |
| `POST /task-status` | Celery → API task-status callback |
| `GET /` · `GET /test-db` · `POST /test-upload` | Health/diagnostics |

### `backend/api/routers/messaging.py` — the Messaging API

| Endpoint | Purpose |
|---|---|
| `POST /api/messaging/send-sms` | SMS via provider selected by `SMS_PROVIDER` (DOIT gateway / disabled) |
| `POST /api/messaging/send-email` | Email via shared SMTP relay |

Auth: `x-api-key` header. Callers: ticketing (SMS fallback, quarterly reports), Celery tasks, chatbot actions via `backend/clients/messaging_api.py`. Spec: [`../services/05_messaging_service.md`](../services/05_messaging_service.md). **No Twilio anywhere.**

> The accessible-voice router (`voice_grievance.py` — `/accessible-file-upload` · `/submit-grievance` · `/grievance-status/{id}`) and the gsheet feed (`gsheet.py` — `/gsheet-get-grievances`) were removed with the legacy channels (CL-02, July 2026). Webchat voice notes still upload through the file server router (`/upload-voice-chunk`, `/upload-voice-complete`).

Plus app-level `GET /health`.

## 4. Celery (chatbot task queue)

One app — `backend.task_queue.celery_app` — Redis broker (db1) / result backend (db2), three workers by queue:

| Worker (compose service) | Queue | Concurrency | Typical tasks |
|---|---|---|---|
| `celery_llm` | `llm_queue` | 6 | classification, summarization, translation, follow-up questions |
| `celery_default` | `default` | 2 | notifications, general background jobs |
| `celery_file` | `file_queue` | 1 | file processing, image compression, voice transcription |

Tasks are registered in `backend/task_queue/registered_tasks.py`; workers report completion to the API via `POST /task-status`. The GRM ticketing Celery app (`ticketing.tasks.celery_app`, queues `grm_ticketing`/`grm_geocode`) is **separate** — see [`../services/07_task_queue_service.md`](../services/07_task_queue_service.md).

## 5. Database services

`backend/services/database_services/` provides the managers (complainants, grievances, files) over `public.*`, with pgcrypto field-level encryption for PII (`DB_ENCRYPTION_KEY`). Details: [`../services/10_database_service.md`](../services/10_database_service.md) and [`../services/02_grievance_service.md`](../services/02_grievance_service.md). Uploads are stored in the `uploads_data` volume (`/app/uploads`), officer ticketing uploads under `uploads/ticketing/{ticket_id}/`.

## 6. Contract summary for external callers (e.g. ticketing)

- Grievance data + PII: `GET /api/grievance/{id}` — never query `public.*` directly.
- Status updates: `POST /api/grievance/{id}/status`.
- Conversation turn (officer reply): Orchestrator `POST /message`.
- SMS/email: `POST /api/messaging/send-*` with `x-api-key`.
- File upload: `POST /upload-files`.
