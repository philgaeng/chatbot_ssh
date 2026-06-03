# Voice Grievance Service Spec

## 1) Scope

Accessible-channel voice grievance ingestion and processing service.

Primary implementation:

- API router: `backend/api/routers/voice_grievance.py`
- helpers/orchestration:
  - `backend/services/accessible/voice_grievance_helpers.py`
  - `backend/services/accessible/voice_grievance_orchestration.py`
  - `backend/services/accessible/voice_grievance.py`

## 2) API Endpoints

### `POST /accessible-file-upload`

Purpose:

- attachment upload flow for accessible channel.

Inputs:

- `grievance_id`
- `files[]`

Behavior:

- stores files under grievance directory
- enqueues `process_batch_files_task`
- returns processing acknowledgement (`202`)

### `GET /grievance-status/{grievance_id}`

Returns grievance + status + files snapshot for accessible frontend.

### `POST /submit-grievance`

Unified accessible submission endpoint combining:

- form data (complainant/grievance identifiers, location/language)
- audio recordings (multipart)

Behavior:

- validates audio filenames/field mapping
- stores recordings in DB
- triggers voice processing orchestration
- emits accessible websocket status update

## 3) Processing Pipeline

Typical voice path:

1. save recording metadata
2. transcribe audio task
3. classify/summarize and related LLM tasks
4. persist derived fields
5. emit task completion status

## 4) Cross-Service Dependencies

- Task queue service (Celery tasks)
- Database service managers
- Accessible Socket.IO emission helper (`emit_status_update_accessible`)

## 5) Error Behavior

Common errors:

- `400` invalid/missing ids or no files
- `404` missing grievance in status endpoint
- `500` processing/storage failures
