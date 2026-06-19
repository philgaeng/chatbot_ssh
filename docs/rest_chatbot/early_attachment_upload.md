# Early attachment upload — spec & progress

**Goal:** Users can attach images, documents, and audio at any point in the REST webchat flow. IDs and DB stubs are created on first upload when needed; existing IDs are reused when a flow starts.

## Locked decisions

| Item | Decision |
|------|----------|
| File types | All (image, document, audio/voice) |
| Attach button | Always enabled (never greyed for “no grievance yet”) |
| Composer P1 | Attach works on button-only turns |
| ID minting | `POST /upload-files` generates IDs when `grievance_id` omitted |
| Flow start | Reuse existing `grievance_id` / `complainant_id` in slots |
| SEAH | Same early-ID pattern as standard / road hazard |
| Pre-flow upload | Orchestrator → `main_menu` when `story_main` unset |
| In-flow upload | Slot sync only; UI “go back to chat” snapshot unchanged |
| Status check | Queue files client-side until case `grievance_id` known |
| DB stub | `source: "bot"`, minimal row via `create_or_update_*` |

## Progress

- [x] **A1** Spec doc (this file)
- [x] **A2** `ensure_intake_records_for_attachment` + `resolve_intake_slot_ids`
- [x] **A3** `POST /upload-files` optional `grievance_id`, return IDs in response
- [x] **A4** Orchestrator `/attachment_ids_sync` + `metadata.attachment_sync`
- [x] **A5** Refactor `action_start_grievance_process` / road hazard to reuse IDs
- [x] **A6** `action_start_seah_intake` + state_machine wiring
- [x] **A7** Frontend: attach always on, drop `grievanceCreatedInDb` gate
- [x] **A8** Frontend: status-check pending queue + flush on `grievance_id`
- [x] **A9** Frontend: post-upload `attachment_ids_sync` call
- [x] **A10** Tests: API auto-ID upload, orchestrator sync + reuse
- [x] **A11** Full `tests/orchestrator/` smoke (run after merge)

## Architecture

```
User attach → (status check, no case id?) → pendingClientFiles[]
           → else POST /upload-files (optional grievance_id)
           → ensure_intake_records_for_attachment
           → POST /message attachment_ids_sync
           → story_main set? slots only : main_menu
```

## Key paths

| Path | Role |
|------|------|
| `backend/actions/grievance_intake/ensure_records.py` | Shared ID + DB stub helpers |
| `backend/api/routers/files.py` | Upload entry, optional ID mint |
| `backend/orchestrator/state_machine.py` | `attachment_ids_sync` handler |
| `backend/actions/forms/form_grievance.py` | Reuse IDs on standard start |
| `backend/actions/forms/form_road_hazard.py` | Reuse IDs on fast path start |
| `backend/actions/forms/form_seah_1.py` | `ActionStartSeahIntake` |
| `channels/REST_webchat/app.js` | Upload + pending queue + sync |
| `channels/REST_webchat/modules/uiActions.js` | Attach always enabled |
