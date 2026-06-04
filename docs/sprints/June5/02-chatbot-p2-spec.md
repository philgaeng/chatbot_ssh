# Chatbot P2 — implementation spec

**Sprint:** June5  
**Tickets:** CB-01, CB-06, CB-08, CB-09  
**Brief:** [voice-notes-and-ux-feature-brief.md](../voice-notes-and-ux-feature-brief.md)  
**Depends on:** Chatbot P1 complete recommended; portal **TP-01** for playback of uploaded audio.

---

## Touch map

| Layer | Path | Role |
|-------|------|------|
| Webchat | `channels/REST_webchat/app.js` | Record UI, upload audio, permission prompts |
| Webchat | `channels/REST_webchat/index.html` | Record button markup |
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
| Rural | Medium sample rate; chunk on device if feasible; else **60–90s** per clip, multiple clips allowed |

### Tasks

1. **UI:** MediaRecorder (or platform fallback) in `app.js`; upload via existing `POST /upload-files` with audio MIME (`audio/mp4`, `audio/webm`, `audio/mpeg`, etc. — confirm `files.py` allowlist).
2. **Flow:** Extend `form_grievance` / `story_main` validation in orchestrator to accept voice-only when `files` slot or grievance files exist post-upload.
3. **API:** Reuse `voice_grievance` orchestration pattern — fire `transcribe_audio_file_task` after upload (see accessible channel); expose **HTTP** entry if webchat cannot call Celery directly (prefer same path as `/upload-files` → process task).
4. **Do not** duplicate transcription logic in `channels/` — call backend only.

### Acceptance criteria

- [ ] Record + upload works on latest Chrome Android + Safari iOS (test matrix in PROGRESS).
- [ ] Grievance submits with voice only; `grievance_id` created.
- [ ] Officer sees audio on ticket (**TP-01**).

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
