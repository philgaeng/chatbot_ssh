# File Processing Service Spec

## 1) Scope

Shared file upload, storage, processing-status, and task-status bridge for webchat and related channels.

Primary implementation:

- API router: `backend/api/routers/files.py`
- core logic: `backend/services/file_server_core.py`
- async workers: `backend/task_queue/registered_tasks.py`

## 2) API Endpoints

### `POST /upload-files`

Multipart upload endpoint.

Inputs:

- `grievance_id` (required)
- `files[]` (required)
- optional metadata: `rasa_session_id`, `flask_session_id`, `client_type`

Behavior:

- Validates extension and max-size rules
- Stores files in grievance directory
- Enqueues `process_file_upload_task`
- Returns `202` with `task_id` and `files` (file ids) on accepted batch

### `GET /file-status/{file_id}`

Returns file processing state:

- `STARTED`
- `SUCCESS`
- `FAILURE`

Failure statuses are cached from failed task-status pushes.

### `GET /files/{item}`

Dual behavior:

- if `item` matches grievance-id pattern -> list file metadata for grievance
- else -> serve file by filename from upload folder

### `GET /download/{file_id}`

Resolves file metadata by id and returns attachment stream.

### `POST /task-status`

Internal bridge endpoint for async workers to publish status.

Behavior:

- Accepts task status payload
- routes events based on source mode:
  - accessible source (`A`) emits accessible status updates
  - bot/webchat source (`B`) emits room events (`task_status` / `file_status_update`)

## 3) Core Validation Rules

In `FileServerCore`:

- extension allow-list
- MIME allow-list checks
- per-file max sizes by file type

Audio uploads can include metadata extraction (duration/format where available).

## 4) Async Pipeline

File tasks:

- `process_file_upload_task`
- `process_batch_files_task`
- `aggregate_batch_results`

Status tracking:

- task manager emits status updates to backend `/task-status`
- frontend polling via `/file-status/{file_id}` remains authoritative UX fallback

## 5) Operational Notes

- Requires valid grievance id context to persist attachment records.
- Upload path defaults to `UPLOAD_FOLDER`/`uploads`.
- Endpoint includes compatibility behavior with legacy Flask service contracts.
