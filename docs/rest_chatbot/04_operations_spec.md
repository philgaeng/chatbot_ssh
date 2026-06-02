# REST Chatbot Operations Spec

## 1) Runtime Services

Minimum services for full REST chatbot behavior:

- Orchestrator API (`backend/orchestrator/main.py`)
- Backend FastAPI (`backend/api/fastapi_app.py`)
- Redis (for socket/celery messaging)
- Celery workers (`backend/task_queue/celery_app.py`)
- Database services used by grievance/file/task operations

## 2) Startup Commands (Reference)

Orchestrator:

`uvicorn backend.orchestrator.main:app --host 0.0.0.0 --port 8000`

Backend API:

`uvicorn backend.api.fastapi_app:app --host 0.0.0.0 --port 5001`

Socket mode note:

- Orchestrator also exposes a combined ASGI app (`asgi`) if running HTTP + socket bridge together is desired.

## 3) Reverse Proxy Expectations

Frontend expects same-origin paths:

- `/message` -> orchestrator
- `/upload-files` -> backend api
- `/file-status/*` -> backend api
- `/accessible-socket.io` -> backend socket ASGI mount

Without reverse proxy path wiring, webchat startup and uploads will fail.

## 4) Environment Variables Used by Chatbot Runtime

Core behavior toggles:

- `ENABLE_CELERY_CLASSIFICATION`
- `ENABLE_SEAH_DEDICATED_FLOW`
- `ORCHESTRATOR_LOG_LEVEL`

API/task infrastructure:

- `UPLOAD_FOLDER`
- `SOCKETIO_REDIS_URL`
- database connection environment consumed by DB managers

Messaging and integration auth:

- `MESSAGING_API_KEY`
- `TICKETING_SECRET_KEY`
- ticketing dispatch endpoint settings in `ticketing_dispatch.py` (`TICKETING_API_URL`)

## 5) Observability and Debugging

Recommended checks:

- `GET /health` on orchestrator and backend API
- verify `/upload-files` accepts test payload
- verify `/file-status/{id}` transitions from `STARTED` -> terminal status
- verify socket connection and room join in browser logs

Failure hotspots:

- missing proxy routing
- missing Redis/Celery worker when async pipeline is expected
- invalid/missing env vars for DB/messaging integrations

## 6) Production Behavior Guarantees

Chatbot submission path:

- grievance submit should not block on ticketing dispatch failure
- file upload pipeline reports status incrementally and provides user fallback messages
- session reset via `/introduce` and close/clear actions is deterministic

## 7) Ownership Boundaries

`docs/rest_chatbot` should contain only chatbot-specific behavior.

Shared service contracts used by chatbot but also used elsewhere are documented in:

- `docs/services/*`

Current shared service specs:

- `docs/services/05_messaging_service.md`
- `docs/services/02_grievance_service.md`
- `docs/services/04_file_processing_service.md`
- `docs/services/08_gsheet_monitoring_service.md`
- `docs/services/03_voice_grievance_service.md`
- `docs/services/06_llm_service.md`
- `docs/services/07_task_queue_service.md`
- `docs/services/10_database_service.md`
- `docs/services/09_grm_integration_service.md`
