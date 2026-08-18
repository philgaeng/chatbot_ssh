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

LLM provider, models and deadlines (DPG-16/DPG-17):

- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TIMEOUT`, `LLM_MAX_RETRIES`, `LLM_STRUCTURED_OUTPUT`
- `ASR_BASE_URL`, `ASR_API_KEY`, `ASR_TIMEOUT` — transcription runs on its own endpoint and its own
  (much longer) deadline
- `MODEL_CLASSIFY`, `MODEL_EXTRACT`, `MODEL_TRANSLATE`, `MODEL_DETECT`, `MODEL_ASR`
- `TIMEOUT_CLASSIFY`, and the per-task `STRUCTURED_*` capability flags
- deprecated but honoured, with one warning each: `OPENAI_API_KEY`, `OPENAI_CLASSIFICATION_TIMEOUT`

> **All of them are declared in one place** — [`backend/config/llm_config.py`](../../backend/config/llm_config.py),
> which the ticketing surface reads too. This list is a pointer for the operator, not a second
> source: `.env.example` is generated from that registry and pinned against it in CI, so a variable
> added to the code and not documented there fails the build. The two ready-made configurations are
> `.env.openai` and `.env.open`; how to switch is
> [`docs/dpg/open-model-configuration.md`](../dpg/open-model-configuration.md).
>
> ⚠ An empty `LLM_API_KEY` means **no client is built at all**. That is deliberate: every call site
> then takes its own documented fallback (raise, sentinel dict, or fail-open on the SEAH path)
> instead of a client that 401s on every request, which on a Celery worker reads as an outage.

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
