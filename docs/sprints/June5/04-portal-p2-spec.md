# Portal P2 — implementation spec

**Sprint:** June5  
**Ticket:** TP-02  
**Brief:** [voice-notes-and-ux-feature-brief.md](../voice-notes-and-ux-feature-brief.md)  
**Depends on:** **TP-01** (audio list + player) complete; **CB-01** when voice intake is live.

---

## Touch map

| Layer | Path | Role |
|-------|------|------|
| Ticket UI desktop | `channels/ticketing-ui/app/tickets/[id]/page.tsx` |
| Ticket UI mobile | `channels/ticketing-ui/app/m/tickets/[id]/page.tsx` |
| API client | `channels/ticketing-ui/lib/api.ts` |
| Grievance client | `ticketing/clients/grievance_api.py` |
| Actions | `ticketing/api/routers/tickets.py` |
| LLM tasks | `ticketing/tasks/llm.py` — pattern for async jobs |
| Accessible transcription | `backend/services/accessible/voice_grievance_orchestration.py` |
| Celery | `backend/task_queue/registered_tasks.py` — `transcribe_audio_file_task` |
| LLM | `backend/services/LLM_services.py` — `transcribe_audio_file` |

**Integration rule:** Portal should **not** import `backend.services` directly in production if boundary forbids — prefer HTTP to grievance/voice API or a thin `ticketing/clients/` wrapper that calls backend with service key (mirror `grievance_api.py`).

---

## TP-02 — Voice note transcription + manual fallback

### Goal

Officers trigger transcription on audio attachments; retry; manual text if automation fails.

### Locked decisions

| Topic | Decision |
|-------|----------|
| API | Same accessible / grievance transcription stack as **CB-01** |
| UI | Per-attachment **Transcribe** + status; show text on file card or timeline |
| Failure | Modal or inline form for **manual transcript** stored on file or as `NOTE_ADDED` with `is_transcript: true` |

### Tasks

1. **Backend (`ticketing/`):**
   - New endpoint e.g. `POST /api/v1/tickets/{id}/files/{file_id}/transcribe` OR `POST .../actions` with `TRANSCRIBE_ATTACHMENT`.
   - Enqueue transcription (Celery `grm_ticketing` queue or call backend task via HTTP).
   - Store result: `ticket_files.metadata` JSON or grievance file record via backend API.
   - Retry: idempotent task with attempt count in metadata.
2. **Manual fallback:** `PATCH` file metadata `manual_transcript` or officer note linked to `file_id`.
3. **Frontend:**
   - On each audio row (from TP-01), buttons: **Transcribe**, **Retry**, **Enter transcript manually**.
   - Loading / error states.
4. **Findings pipeline:** Optional — include transcript in `context_builder.py` if text exists (coordinate with `ticketing/engine/context_builder.py`).

### Acceptance criteria

- [ ] Transcribe succeeds for sample Nepali/English audio (test file in repo or recorded).
- [ ] Retry after failure does not duplicate conflicting text (latest wins or versioned).
- [ ] Manual transcript visible to supervisors; same visibility as field reports (internal).
- [ ] No regression on TP-01 player.

### Out of scope

- Real-time streaming transcription
- Complainant-facing transcript display

---

## Testing

- [ ] Audio attachment on demo ticket `GRV-2025-*` with mock file
- [ ] Permission: only assigned actor / supervisor can transcribe (align with NOTE permissions)

---

## Progress

Update [`PROGRESS.md`](PROGRESS.md) Portal P2 table when starting/finishing TP-02.
