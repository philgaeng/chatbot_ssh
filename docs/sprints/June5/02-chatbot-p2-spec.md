# Chatbot P2 — implementation spec

**Sprint:** June5  
**Tickets:** CB-01, CB-06, CB-08, CB-09  
**Brief:** [voice-notes-and-ux-feature-brief.md](../voice-notes-and-ux-feature-brief.md)  
**Depends on:** Chatbot P1 complete recommended; portal **TP-01** for playback of uploaded audio.

---

## Touch map

| Layer | Path | Role |
|-------|------|------|
| Webchat | `channels/REST_webchat/app.js` | Record UI, upload audio, voice status banner API |
| Webchat | `channels/REST_webchat/index.html` | Composer + `#voice-status-banner` markup |
| Webchat | `channels/REST_webchat/styles.css` | Light-blue voice status banner |
| Webchat | `channels/REST_webchat/modules/voiceNote.js` | MediaRecorder, **45s** cap, timer callback |
| Webchat | `channels/REST_webchat/modules/uiActions.js` | `setVoiceStatusBanner()` replace-in-place |
| Webchat | `channels/REST_webchat/utterances.js` | Voice + EXIF + dust copy |
| Orchestrator | `backend/orchestrator/state_machine.py` | Dust branch, location slots |
| Orchestrator | `backend/orchestrator/form_loop.py` | Slot validation for story / location |
| Forms / actions | `backend/actions/generic_actions.py` | Form asks, file upload status |
| Submit | `backend/actions/action_submit_grievance.py` | Allow empty `story_main` when audio present |
| Upload API | `backend/api/routers/files.py` | Accept audio MIME types; metadata fields |
| Voice service | `backend/api/routers/voice_grievance.py` | Reference contract |
| Voice pipeline | `backend/services/accessible/voice_grievance_helpers.py` | |
| Voice pipeline | `backend/services/accessible/voice_grievance_orchestration.py` | Chain `transcribe_audio_file_task` |
| Transcription | `backend/task_queue/registered_tasks.py` | `transcribe_audio_file_task` |
| LLM | `backend/services/LLM_services.py` | `transcribe_audio_file()` |
| Ticketing hook | `backend/actions/utils/ticketing_dispatch.py` | Unchanged; files on grievance still sync |
| Docs | `docs/services/03_voice_grievance_service.md` | Align spec after build |
| Docs | `docs/rest_chatbot/02_flow_spec.md` | Dust + pin topology |

**Portal (read-only for P2 chatbot):** `ticketing/` — tickets show attachments from grievance API; **TP-02** adds transcription UI.

---

## CB-01 — Hybrid grievance input (text or voice note)

### Goal

Text **or** voice note **or** both at grievance description step.

### Locked decisions

| Topic | Decision |
|-------|----------|
| UX | Dedicated **Record voice note** button; prompt: *Type your grievance or record a voice note* |
| Submit | Valid with empty text if ≥1 voice attachment |
| Transcription | Async via accessible pipeline / API — **not** live STT in browser |
| Clip length | **45 seconds max** per recording (hard stop + auto-upload); multiple clips allowed |
| Status UX | **Light-blue banner** above composer toolbar; each status **replaces** the previous (not chat bubbles) |
| Timer | While recording, banner shows **elapsed time** `M:SS` (e.g. `0:12 / 0:45`) updated ~1s |

### Voice status banner (CB-01 UX — locked 2026-06-03)

**Placement:** Inside `#chat-widget`, **above** the composer toolbar row (attach / mic / send), **below** `#messages` (chat history + quick-reply chips stay in the scroll area).

**Visual:** Same pattern as `#grievance-filed-banner` (full width, `role="status"`, `aria-live="polite"`) but **light blue** background (distinct from green filed banner). Hidden when empty.

**Replace-in-place:** One text line (optional second line only if product asks later). New status overwrites prior — no stacking in `#messages`.

**In banner (not in chat):**

| Phase | Example copy (EN) |
|-------|-------------------|
| Recording | `Recording… 0:12 / 0:45 — tap mic to stop` |
| Max length | `Maximum length (45s) reached. Uploading…` |
| Mic denied | `Microphone access is required to record.` |
| Pre-upload | `Voice recording detected. Uploading…` |
| Upload / task poll | `Voice record uploaded. Processing…` → `Voice record saved.` |
| Upload error | `Could not save voice record: {error}` |

**Stays in chat (bot / user content):**

- Orchestrator prompts and quick replies (e.g. **Add a voice record**, **Next step**).
- Post-upload encouragement paragraphs in `utterances.js` (`file_upload.post_upload_*`).
- User typed messages and normal bot Q&A.

**In banner (photos too):** Photo/document upload uses the same banner (`files_detected`, `files_processing`, `files_saved`, errors).

**Clear banner when:**

- User leaves grievance-details step (`disable_voice_note` or equivalent), or
- Session / chat reset (`/introduce`), or
- After post-upload handoff: banner cleared when quick-reply row is shown (success path).

**Implementation notes:**

- `voiceNote.js`: `MAX_SECONDS = 45`; expose `onTick(elapsedSeconds)` for banner timer.
- `app.js` / `eventHandlers.js`: stop calling `appendMessage()` for rows in the table above; call `uiActions.setVoiceStatusBanner(text | null)`.
- Remove duplicate in-chat lines: `voice_detected`, `voice_uploaded_processing`, per-file `#file-status-*` in `#messages` for **audio-only** uploads (batch status → banner).

### Tasks

1. **UI:** MediaRecorder in `voiceNote.js`; upload via `POST /upload-files` with audio MIME (`files.py` allowlist).
2. **Banner:** Markup + CSS + `setVoiceStatusBanner()`; wire all voice lifecycle statuses to banner.
3. **Flow:** Orchestrator voice-only validation on `form_grievance` (unchanged).
4. **API:** Audio upload → backend processing (transcription optional per proto policy); no duplicate pipeline in `channels/`.
5. **Copy:** EN/NE strings in `utterances.js`; **45s** referenced in recording + max-length strings.

### Acceptance criteria

- [ ] Record + upload works on latest Chrome Android + Safari iOS (test matrix in PROGRESS).
- [ ] Grievance submits with voice only; `grievance_id` created.
- [ ] Officer sees audio on ticket (**TP-01**).
- [x] Recording/processing statuses appear **only** in the light-blue banner (not as left-aligned bot bubbles).
- [x] Photo upload progress uses the same banner.
- [x] Banner shows live timer during recording; auto-stops at **45s**.
- [x] Each new status replaces the previous banner text.

---

## CB-06 — Location by map pin (with fallback)

### Goal

Primary: map pin; fallback: existing location form.

### Tasks

1. Add map picker step (library TBD: Leaflet/OSM or existing Nepal geodata) in webchat — new custom payload or form slot e.g. `geo_lat`, `geo_lng`, `location_code`.
2. Persist on complainant/grievance via existing DB fields (check `public.grievances` / complainant province-district columns via `grievance_manager.py`).
3. On deny/fail: branch to existing location ask actions (province → district → municipality in `state_machine.py` / form definitions in `backend/orchestrator/config/domain.yml` if used).
4. Optional: reverse-geocode pin to `location_code` using `backend/shared_functions/location_mapping.py` (QR flow already resolves codes).

### Acceptance criteria

- [ ] Pin path sets location on grievance.
- [ ] Fallback path unchanged for users who skip map.
- [ ] Works without pin on desktop (fallback only).

---

## CB-08 — Photo metadata (location + time)

### Goal

With consent, read EXIF GPS/time from uploaded images.

### Tasks

1. Client: before/after `POST /upload-files`, show permission dialog (EN/NE in `utterances.js`).
2. Client: extract EXIF (e.g. exifr library or light parser); send as optional multipart fields or JSON metadata per file.
3. Server: `files.py` / `process_file_upload_task` — store metadata on file row or grievance extension (schema: check `grievance` files table via `grievance_manager.py`).
4. Denied/missing EXIF: non-blocking.

### Acceptance criteria

- [ ] Permission prompt shown once per session or per upload (spec choice documented).
- [ ] Coordinates stored for officer view (portal ticket detail / grievance `files` in API).
- [ ] No raw EXIF dump shown to complainant.

---

## CB-09 — Dust complaint fast path

### Goal

Short path when category = **DUST**.

### Flow (locked draft)

1. Choose DUST  
2. Location: pin (**CB-06**) OR municipality → locality/village → optional km on road  
3. File grievance (minimal text policy TBD)  
4. Pictures + **CB-08**  
5. Contact optional (obvious skip)

### Tasks

1. Add menu / category intent `DUST` or slot on `new_grievance` branch in `state_machine.py`.
2. Wire steps above; reuse QR `package_id` / `location_code` from `ActionIntroduce._resolve_qr_token` in `generic_actions.py` when `t` param present.
3. Default summary line for dust-only if no text (LLM or static string — product decision).

### Acceptance criteria

- [ ] End-to-end dust report creates ticket via `ticketing_dispatch.dispatch_ticket`.
- [ ] Contact step skippable with clear copy.
- [ ] Depends on CB-06 + CB-08 for full acceptance; pin-only dust path acceptable as MVP if CB-08 deferred with waiver.

---

## Recommended build order

```text
CB -09, CB 08, CB 06, cb 01
```

---

## Out of scope (P2)

- Portal transcription UI (**TP-02**)
- Real-time captioning in browser
