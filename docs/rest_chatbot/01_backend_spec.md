# REST Chatbot Backend Spec

## 1) Backend Components in Scope

Chatbot backend runtime is split across:

- `backend/orchestrator/main.py` (conversation API)
- `backend/orchestrator/*` (state machine, form loop, action adapter layer)
- `backend/api/fastapi_app.py` (file/grievance/task-status/messaging APIs)
- `backend/task_queue/registered_tasks.py` (async file + LLM task processing)

Legacy note:

- `backend/api/channels_api.py` is a legacy Flask implementation kept for compatibility/reference.
- Production path is FastAPI via `backend/api/fastapi_app.py`.

Shared service contracts referenced by this spec are documented in:

- `docs/services/02_grievance_service.md`
- `docs/services/04_file_processing_service.md`
- `docs/services/07_task_queue_service.md`
- `docs/services/05_messaging_service.md`
- `docs/services/10_database_service.md`

## 2) Orchestrator API (`backend/orchestrator/main.py`)

### 2.1 Endpoint: `POST /message`

Purpose:

- Single turn execution of chatbot flow state machine.

Request fields:

- `user_id` (required): session identity key
- `text` (optional): free text user input
- `payload` (optional): slash command/button payload
- `message_id` (optional): client tracing id
- `channel` (optional): channel identifier (webchat uses `webchat-rest`)

Response fields:

- `messages`: array of bot messages
- `next_state`: resulting conversation state
- `expected_input_type`: `buttons` or `text`

Behavior:

- Loads existing in-memory session by `user_id`, or creates one.
- Calls `run_flow_turn(...)`.
- Saves session updates.
- Returns normalized bot message list + state metadata.

### 2.2 Endpoint: `GET /health`

Response:

- `{"status":"ok"}`

## 3) Session Model (`backend/orchestrator/session_store.py`)

Storage:

- In-memory dictionary keyed by `user_id`.

Session fields:

- `user_id`
- `state`
- `active_loop`
- `requested_slot`
- `slots`
- `updated_at`

Default slots include (non-exhaustive):

- `language_code`
- `story_main`
- `grievance_id`
- `complainant_id`
- grievance/contact helper slots and skip markers

## 4) Backend API Used by REST Webchat (`backend/api/fastapi_app.py`)

FastAPI app mounts these router groups:

- `backend/api/routers/files.py`
- `backend/api/routers/grievance.py`
- `backend/api/routers/messaging.py`
- voice and gsheet routers

Also mounts ASGI Socket.IO app at:

- `/accessible-socket.io`

### 4.1 File/API Endpoints Used by Webchat

#### `POST /upload-files`

Expected multipart fields:

- `grievance_id`
- `files[]`
- optional: `rasa_session_id`, `flask_session_id`, `client_type`

Behavior:

- Validates file extension + size
- Writes files under upload folder
- Enqueues Celery `process_file_upload_task`
- Returns `202` with task id and file ids

#### `GET /file-status/{file_id}`

Returns status for frontend polling:

- `STARTED`
- `SUCCESS`
- `FAILURE`

Failure statuses are cached in-memory when task-status reports failed processing for a file id.

#### `POST /task-status`

Internal bridge for task updates.

Webchat mode behavior (`source == B`):

- Emits socket events to room `flask_session_id`
- Event names:
  - `task_status`
  - `file_status_update` (for file-named tasks)

### 4.2 Grievance Endpoints

Defined in `backend/api/routers/grievance.py`:

- `GET /api/grievance/statuses`
- `GET /api/grievance/{grievance_id}`
- `POST /api/grievance/{grievance_id}/status`
- `PATCH /api/complainant/{complainant_id}` (auth-gated; whitelisted complainant fields)

These are used by chatbot and integrations that need grievance retrieval/status operations.
Detailed shared contract: `docs/services/02_grievance_service.md`.

## 5) Async Task Processing (`backend/task_queue/registered_tasks.py`)

Chatbot-relevant tasks:

- File pipeline:
  - `process_file_upload_task`
  - `process_batch_files_task`
- LLM pipeline:
  - `transcribe_audio_file_task`
  - `classify_and_summarize_grievance_task`
  - `extract_contact_info_task`
  - `translate_grievance_to_english_task`
  - `detect_sensitive_content_task`

Task outputs feed:

- DB updates through database task managers
- websocket/task-status events for frontend UX feedback

## 6) Submission and Ticketing Dispatch

Submission actions in `backend/actions/action_submit_grievance.py`:

- `ActionSubmitGrievance`
- `ActionSubmitSeah`

Post-submit integration:

- `backend/actions/utils/ticketing_dispatch.py::dispatch_ticket(...)`

Dispatch guarantees:

- Fire-and-forget
- Never blocks chatbot submission path on ticketing failures
