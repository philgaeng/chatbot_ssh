# Voice Grievance Service Spec

> **RETIRED (CL-02, July 2026).** The accessible voice channel (`channels/accessible/`)
> and its exclusive backend — the `voice_grievance.py` router
> (`/accessible-file-upload`, `/submit-grievance`, `/grievance-status/{id}`) and the
> `backend/services/accessible/` helpers/orchestration — were removed. This spec is kept
> for historical reference only.
>
> **Still live:** the webchat voice-note **upload** path — chunked upload via
> `/upload-voice-chunk` + `/upload-voice-complete` (`backend/api/routers/files.py`) and the
> `grievance_voice_recordings` / `grievance_transcriptions` tables.
>
> ⚠ **Corrected 2026-08-18: the transcription half is NOT live, and this line said it was.**
> `transcribe_audio_file_task` is registered and **nothing enqueues it**. The upload handler stores
> the file and stops there, by decision — `backend/task_queue/registered_tasks.py:157`:
> *"CB-01 proto: store audio only; transcription/classification deferred to officers."*
> So audio reaches the database and an officer, never a model. This is **deferral, not rot**: the
> feature is designed for and the recordings are being kept for it. DPG-14.3's signature fix
> (`language`, not `language_code`) is what makes it correct on the day it is switched back on —
> and until then, "voice transcription is not live" (Q-13.2) is true for a second reason nobody had
> recorded: not just the budget, but that no code path calls it. The
> `/accessible-socket.io` Socket.IO mount is REST_webchat status infra, not part of this
> retired channel.

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

> ⚠ **Transcription reconciled with the code, 2026-08-18 (DPG-14.3).** Step 2 below describes a step
> that **raised `TypeError` on every invocation** until that date: `transcribe_audio_file` passed
> `language_code=…` to the OpenAI SDK, whose parameter is `language` and which accepts no `**kwargs`.
> The failure was logged and re-raised, so it was absorbed by the task layer and looked like an
> ordinary transcription failure. Verified against the pinned `openai==1.70.0` in-container.
>
> The signature is now correct and unit-tested (`tests/backend/test_llm_services.py`). **That is not
> the same as "transcription works":** voice is not live for lack of an LLM budget (Q-13.2), so there
> is no field evidence and no Nepali WER baseline — DPG-22 owns that. Read step 2 as
> `⚠ Not verified end-to-end`.

Typical voice path:

1. save recording metadata
2. transcribe audio task
3. classify/summarize and related LLM tasks
4. persist derived fields
5. emit task completion status

## 3b) REST webchat path (CB-01, June5)

After `POST /upload-files` stores an **audio** attachment for a bot grievance (`*-B` id suffix), `process_file_upload_task` starts the same chain as accessible intake via `process_single_audio_file()` with `field_name: grievance_voice_note`.

- Client: MediaRecorder in `channels/REST_webchat/modules/voiceNote.js` (max 90s per clip).
- Voice-only submit: empty description allowed when ≥1 audio file exists on the grievance.
- Early upload: if the grievance row is not yet in DB, `/upload-files` creates a minimal stub when `complainant_id` is posted with the file.

## 4) Cross-Service Dependencies

- Task queue service (Celery tasks)
- Database service managers
- Accessible Socket.IO emission helper (`emit_status_update_accessible`)

## 5) Error Behavior

Common errors:

- `400` invalid/missing ids or no files
- `404` missing grievance in status endpoint
- `500` processing/storage failures
