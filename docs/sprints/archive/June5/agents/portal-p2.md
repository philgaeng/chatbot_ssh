# Agent prompt — Portal P2 (June5)

You are implementing **TP-02 only**: voice note **transcription** and manual fallback on the ticketing portal.

---

## Read first

1. `docs/sprints/June5/04-portal-p2-spec.md`
2. `docs/sprints/voice-notes-and-ux-feature-brief.md` — TP-02, CB-01 pairing
3. Confirm **TP-01** is `done` in `docs/sprints/June5/PROGRESS.md`

---

## Mission

**TP-02:** On each audio attachment (from TP-01 list):

- **Transcribe** button → async job (accessible / `transcribe_audio_file_task` pattern)
- **Retry** on failure
- **Manual transcript** fallback stored and shown to officers
- Do not break inline **audio player**

---

## You may edit

- `channels/ticketing-ui/app/tickets/[id]/page.tsx`
- `channels/ticketing-ui/app/m/tickets/[id]/page.tsx`
- `channels/ticketing-ui/lib/api.ts`
- `ticketing/api/routers/tickets.py` (or new file route under tickets)
- `ticketing/tasks/llm.py` or new `ticketing/tasks/transcription.py`
- `ticketing/clients/` — thin HTTP client to backend transcription if needed
- `ticketing/models/ticket_file.py` — metadata JSON for transcript text

**Reference (read-only):**

- `backend/services/accessible/voice_grievance_orchestration.py`
- `backend/task_queue/registered_tasks.py` — `transcribe_audio_file_task`
- `backend/services/LLM_services.py`

Do **not** import `backend.services` directly from ticketing if repo boundary forbids — use HTTP + API key like `grievance_api.py`.

---

## Do not edit

- TP-11 command palette / TP-12 assign (unless fixing conflict)
- Chatbot `channels/REST_webchat/`

---

## Progress protocol

Update `docs/sprints/June5/PROGRESS.md` → **Agent: Portal P2**.

---

## Definition of done

- [ ] Transcribe + retry + manual path work on demo ticket with audio file
- [ ] Permissions: assigned actor / supervisor only (align with NOTE rules)
- [ ] TP-01 player still works
- [ ] PROGRESS.md TP-02 `done`

---

## Report back

1. Endpoint(s) added
2. Where transcript text is stored
3. How Celery/backend task is invoked
4. Dependency on CB-01 if no audio files in DB yet

Do not commit unless the user asks.
