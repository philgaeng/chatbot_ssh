# Task Queue Service Spec

## 1) Scope

Shared async execution infrastructure for file, LLM, messaging, and DB tasks.

Primary implementation:

- task definitions: `backend/task_queue/registered_tasks.py`
- task orchestration/utilities: `backend/task_queue/task_manager.py`
- Celery app: `backend/task_queue/celery_app.py`

## 2) Task Type Model

Central task categories:

- `LLM`
- `FileUpload`
- `Messaging`
- `Database`
- `Default`

Each category maps to:

- service label
- queue/priority settings
- retry policy

Configuration source:

- `TASK_CONFIG` in `task_manager.py`

## 3) Registration Pattern

Tasks use:

- `@TaskManager.register_task(task_type=...)`

Decorator behavior:

- binds Celery task
- applies queue/retry metadata
- auto-injects service context via task type mapping
- records task metadata in internal registry

## 4) Status and Monitoring

Task manager responsibilities:

- start/complete/fail event logging
- retry decisioning/backoff
- status emission to backend `/task-status` API

Websocket status flow:

1. task manager posts status to backend endpoint
2. backend router emits to socket rooms/channels
3. frontend receives status events

## 5) Database Operation Bridge

`DatabaseTaskManager` handles persistence-aware operations:

- prepares result payloads for DB managers
- creates/updates entity records
- creates/updates task records tied to entities

This supports retry-safe task lifecycle tracking.

## 6) Major Registered Tasks

- file processing:
  - `process_file_upload_task`
  - `process_batch_files_task`
- messaging:
  - `send_sms_task`
  - `send_email_task`
- LLM:
  - `transcribe_audio_file_task`
  - `classify_and_summarize_grievance_task`
  - `extract_contact_info_task`
  - `translate_grievance_to_english_task`
  - `detect_sensitive_content_task`
- db write-through:
  - `store_result_to_db_task`
