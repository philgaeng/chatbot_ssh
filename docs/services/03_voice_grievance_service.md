# Voice Grievance Service Spec

**Status:** live specification (tier 1) — authoritative for what the system does today.
**Last updated:** 2026-08-20 · ⚠ backfilled from git 2026-09-04; not re-verified against the code

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
> So audio reaches the database and an officer, never a model. This is **deferral, not rot** — and
> it is bigger than transcription alone (Q-22, 2026-08-18): **four LLM paths are parked together as
> this one flow** — ASR, contact extraction ×2 (which consume a *transcription of spoken contact
> details*, not typed input), and grievance translation. `backend/task_queue/test_tasks.py` still
> holds the chains. ⚠ **This spec is therefore the best surviving description of a parked feature,
> and whoever unparks it will start here.** What it costs to unpark: a transcription budget (Q-19)
> and DPG-22's Nepali WER baseline, which does not exist yet. DPG-14.3's signature fix
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
>
> ### ⚠ DPG-22, 2026-08-20 — three things measured, and none of them is a WER
>
> **1. There is no chosen model and no WER, and the reason is not only budget.** The benchmark set
> has **no audio** — six voice-origin items, all of them *transcript-shaped text*, which is what
> classification consumes and not what transcription consumes. Nothing in this repository can author
> a recording, and TTS would not close the gap: synthetic speech is cleaner than a person on a rural
> mobile connection, so a WER measured on it would flatter every candidate.
> [Follow-up](../sprints/2026-08-llm/followups/no-audio-subset-for-asr-benchmark.md).
>
> **2. ⚠ The open configuration's ASR endpoint returns 404.** `.env.open` ships
> `ASR_BASE_URL=https://router.huggingface.co/v1`, and that router **does not expose**
> `/v1/audio/transcriptions` — verified for `whisper-large-v3`, its turbo variant, and a
> provider-pinned form. Not auth and not billing: the same route *without* a token returns 401, chat
> and `/v1/models` both return 200 with it, and the router's catalogue holds 132 models, **none of
> them audio**. **So whoever unparks this flow must first choose an ASR provider that does serve the
> OpenAI-compatible audio surface** — the registry already keeps `ASR_BASE_URL` and `ASR_API_KEY`
> separate from the chat endpoint precisely so that is a two-line change.
> [Follow-up](../sprints/2026-08-llm/followups/the-open-config-has-no-working-asr-endpoint.md).
>
> **3. Licences verified from the model cards, at probe time** — this is the part that *is* settled:
>
> | Candidate | Licence (read 2026-08-20) | Verdict |
> |---|---|---|
> | `openai/whisper-large-v3` | **apache-2.0** | ✅ permissive |
> | `openai/whisper-large-v3-turbo` | **MIT** | ✅ permissive — ⚠ the sprint spec's table says Apache-2.0. **It is MIT.** Both pass the filter, so no decision changes, but the table was wrong |
> | `ai4bharat/indicwav2vec_v1_nepali` | **MIT** | ✅ permissive, and it is the **Nepali-specific** model — far smaller, CTC decoder, much faster |
> | `facebook/mms-1b-all` | **cc-by-nc-4.0** | ❌ **cannot ship** — non-commercial. Excluded on licence, not on quality, exactly as the spec predicted |
> | Meta *Omnilingual ASR* | ⚠ **could not be verified** — the repository ids tried do not resolve publicly; only community re-exports are findable | ⚠ The spec asserts Apache-2.0; **that is unverified**, and it should not be repeated until someone resolves the real repo |
>
> **And the framing that must travel with any future number.** Voice has never been live, so there
> is **no incumbent to beat**. The honest sentence is *"we shipped a working ASR path where there
> was none"* — never *"we matched the incumbent"*. Both are fine; conflating them is not, and the
> baseline column in [`model-benchmarks.md`](../dpg/model-benchmarks.md) says "never live" rather
> than sitting blank for that reason.

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
