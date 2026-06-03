# Agent prompt — Chatbot P2 (June5)

You are implementing **Chatbot P2**: voice intake, map pin, photo EXIF, and dust fast path.

---

## Read first

1. `docs/sprints/June5/02-chatbot-p2-spec.md`
2. `docs/sprints/voice-notes-and-ux-feature-brief.md` — CB-01, CB-06, CB-08, CB-09
3. `docs/services/03_voice_grievance_service.md`
4. Confirm **Chatbot P1** is `done` in `docs/sprints/June5/PROGRESS.md` (or user waived)

---

## Mission

| ID | Order | Summary |
|----|-------|---------|
| **CB-01** | 1 | Record voice note button; submit without text if audio attached; 60–90s clips if no chunking; transcription via accessible API (async) |
| **CB-06** | 2 | Map pin location; fallback to existing ask-location form |
| **CB-08** | 3 | Consent + EXIF location/time on image upload |
| **CB-09** | 4 | DUST category short path (pin → file → photos → optional contact) |

---

## You may edit

- `channels/REST_webchat/` — record UI, upload, permissions
- `backend/orchestrator/state_machine.py`, `form_loop.py`
- `backend/actions/generic_actions.py`, `action_submit_grievance.py`
- `backend/api/routers/files.py` — audio MIME + metadata fields
- `backend/services/accessible/*`, `backend/task_queue/registered_tasks.py` (integration only)
- `backend/shared_functions/location_mapping.py` — pin → `location_code`
- `docs/rest_chatbot/`, `docs/services/03_voice_grievance_service.md`

---

## Do not edit

- `channels/ticketing-ui/`, `ticketing/` (except reading grievance file shapes)
- Duplicate transcription in frontend — call backend

---

## Locked decisions

- Medium sample rate; chunk if web allows; else **60–90s** per file, multiple files OK
- Transcription: `transcribe_audio_file_task` / accessible orchestration — not live browser STT
- CB-09 needs CB-06 + CB-08 for full flow

---

## Coordination with portal

- Officers play audio via **TP-01** (should be done before or in parallel)
- Full transcription UI is **TP-02**, not this sprint

---

## Progress protocol

Update `docs/sprints/June5/PROGRESS.md` → **Agent: Chatbot P2** after each ticket.

---

## Definition of done

- [ ] CB-01: voice-only submit creates grievance + attachment
- [ ] CB-06: pin + fallback both work on mobile
- [ ] CB-08: permission + stored metadata (or documented waiver)
- [ ] CB-09: DUST e2e to ticketing dispatch
- [ ] Test matrix noted: Android Chrome + iOS Safari
- [ ] PROGRESS.md all four `done`

---

## Report back

1. Audio formats and size limits implemented
2. API endpoints used for transcription
3. Dust flow state names in orchestrator
4. Open product questions (map provider, dust text skip policy)

Do not commit unless the user asks.
