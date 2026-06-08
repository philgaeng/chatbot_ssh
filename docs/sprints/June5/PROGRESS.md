# June5 sprint — agent progress tracker

> Update this file when you **start**, **block**, or **complete** work. One row per ticket per agent run.  
> Specs: see [`README.md`](README.md).

---

## How to use (all agents)

0. Paste the matching prompt from [`agents/`](agents/README.md) into your agent session.
1. Read your spec (`01`–`04`) and the [feature brief](../voice-notes-and-ux-feature-brief.md).
2. Claim a ticket: set status to `in_progress` and add your agent id + date.
3. Implement only paths listed in your spec **Touch map**.
4. When done: set status `done`, add PR/commit hash, note any spec deviation.
5. Do **not** edit another agent’s in-progress row without coordination.

**Status values:** `todo` | `in_progress` | `blocked` | `done` | `skipped`

---

## Agent: Chatbot P1

**Prompt:** [`agents/chatbot-p1.md`](agents/chatbot-p1.md)  
**Spec:** [`01-chatbot-p1-spec.md`](01-chatbot-p1-spec.md)  
**Primary paths:** `channels/REST_webchat/`, `backend/orchestrator/`, `backend/actions/`, `backend/actions/utils/utterance_mapping_rasa.py` (or equivalent utterance sources)

| Ticket | Status | Agent / date | PR / commit | Notes |
|--------|--------|--------------|-------------|-------|
| CB-03 Close / exit consolidation | `done` | Chatbot P1 / 2026-06-03 | | `close_controls_mode` + UI filter; workflow-specific outro buttons |
| CB-04 File another grievance | `done` | Chatbot P1 / 2026-06-03 | | `done` state handles `/new_grievance` and `/seah_intake`; client restart helper |
| CB-05 Attachment copy rewrite | `done` | Chatbot P1 / 2026-06-03 | | `utterances.js` + server outro attachment strings |
| CB-07 Success messages + filed banner | `done` | Chatbot P1 / 2026-06-03 | | Three outro messages + `#grievance-filed-banner` |

**CB-03 verification**

- [x] Standard flow: only **Close session** visible in header + post-upload buttons.
- [x] SEAH flow: only **Close browser** visible (same payloads as today).
- [x] No duplicate close prompts in bot messages for same step.

**CB-04 verification**

- [x] After submit/review, **File another grievance** appears and triggers clean `/new_grievance` or `/seah_intake` path.
- [x] Prior `grievance_id` cleared; new intake works without tab close.

**CB-05 verification**

- [x] No harsh “not attached” copy; new EN/NE strings in `utterances.js`.
- [x] Post-upload encouragement mentions photos, documents, handwritten complaint.

**CB-07 verification**

- [x] Three bot messages after file: success → grievance # → follow-ups OK.
- [x] Top banner shows filed + grievance id until session reset.

**Sprint P1 chatbot complete when:** all four tickets `done` and checkboxes above checked.

---

## Agent: Chatbot P2

**Prompt:** [`agents/chatbot-p2.md`](agents/chatbot-p2.md)  
**Spec:** [`02-chatbot-p2-spec.md`](02-chatbot-p2-spec.md)  

| Ticket | Status | Agent / date | PR / commit | Notes |
|--------|--------|--------------|-------------|-------|
| CB-01 Voice note intake | `done` | Chatbot P2 / 2026-06-03 | | Record button, 45s cap, composer status banner, voice-only submit |
| CB-06 Location by pin | `done` | Chatbot P2 / 2026-06-03 | | Consent → manual/map; coords on `complainants.location_geo` at submit |
| CB-08 Photo EXIF metadata | `done` | Chatbot P2 / 2026-06-03 | | Session consent + exifr; metadata on `file_attachments.client_metadata` |
| CB-09 Dust fast path | `done` | Chatbot P2 / 2026-06-03 | | Menu `/dust_grievance`, preset Air Pollution, photo prompt after pin |

**P2 verification (manual)**

- [ ] Android Chrome + iOS Safari: record voice, map pin, photo upload with EXIF consent
- [ ] Voice-only: record → File as is → grievance filed
- [ ] Dust: fast path → pin → photos → optional contact → ticket dispatch

**P2 test matrix (automated):** `pytest tests/orchestrator/test_chatbot_p2.py`

---

## Agent: Portal P1

**Prompt:** [`agents/portal-p1.md`](agents/portal-p1.md)  
**Spec:** [`03-portal-p1-spec.md`](03-portal-p1-spec.md)  
**Primary paths:** `channels/ticketing-ui/`, `ticketing/api/`, `ticketing/services/`, `ticketing/models/`

| Ticket | Status | Agent / date | PR / commit | Notes |
|--------|--------|--------------|-------------|-------|
| TP-01 Audio player | `done` | Portal P1 / 2026-06-03 | | `AudioPlayer` + `AttachmentListSection`; audio MIME on download |
| TP-09 Acknowledge + grievance in thread | `done` | Portal P1 / 2026-06-03 | | `GrievanceThreadCard` pinned on mobile OPEN tickets |
| TP-10 Call complainant report | `done` | Portal P1 / 2026-06-03 | | `#call` + `CallReportComposeCard`; NOTE + `is_call_report` |
| TP-05 Report links (internal + public) | `done` | Portal P1 / 2026-06-03 | | `POST /reports/share`; `/reports/view/{token}`, `/reports/public/{token}` |
| TP-07 Export all data Excel | `done` | Portal P1 / 2026-06-03 | | `GET /reports/export-all` flat sheet with `ALL_DATA_EXPORT_COLUMNS` |
| TP-08 Quarterly dashboard clarity | `done` | Portal P1 / 2026-06-03 | | Renamed matrix labels, tooltips, level vs package toggle |
| TP-11 Simplify commands + gates | `done` | Portal P1 / 2026-06-03 | | Removed `#photo`/`#review`; image gate; escalation form |
| TP-12 Assign vs reassignment | `done` | Portal P1 / 2026-06-03 | | `REASSIGNMENT_REQUESTED`; supervisor-only assign |

---

## Agent: Portal P1 bugs

**Prompt:** [`agents/portal-p1-bugs.md`](agents/portal-p1-bugs.md)  
**Spec:** [`03-portal-p1-spec.md`](03-portal-p1-spec.md) § TP-13  
**Primary paths:** `channels/ticketing-ui/lib/user-messages.ts`, `components/ActionNotice.tsx`, `app/tickets/[id]/page.tsx`, `app/m/tickets/[id]/page.tsx`

| Ticket | Status | Agent / date | PR / commit | Notes |
|--------|--------|--------------|-------------|-------|
| TP-13 Officer-friendly validation messages | `done` | Portal P1 bugs / 2026-06-03 | | `user-messages.ts`, `ActionNotice`; desktop escalation form parity |

**TP-13 verification**

- [x] Desktop Escalate without image → amber in-app notice (no browser dialog)
- [x] Desktop Escalate with image → `EscalationFormCard` → submit succeeds
- [x] Mobile action errors use in-app notice (no `alert` on ticket action catches)
- [x] Error text never contains `API`, `/api/v1/`, or JSON `detail` wrapper

---

## Agent: Portal P2

**Prompt:** [`agents/portal-p2.md`](agents/portal-p2.md)  
**Spec:** [`04-portal-p2-spec.md`](04-portal-p2-spec.md)  

| Ticket | Status | Agent / date | PR / commit | Notes |
|--------|--------|--------------|-------------|-------|
| TP-02 Voice transcription + manual fallback | `todo` | | | |

---

## Cross-team integration log

| Date | Who | What |
|------|-----|------|
| 2026-06-03 | Portal P1 bugs | TP-13: `formatUserFacingError`, `ActionNotice`, desktop/mobile ticket pages |
| 2026-06-03 | Docs | TP-13 spec + `portal-p1-bugs` agent prompt (friendly validation UX) |
| 2026-06-03 | Portal P1 | Officer upload + grievance file download now serve audio/* MIME types for inline playback |
| | | SMS public report URL: integration point left in `POST /reports/share` (messaging_api not wired) |
| | | Voice intake (CB-01) + TP-02 share accessible transcription API |

---

## Deviations from spec (append-only)

| Ticket | Deviation | Approved by |
|--------|-----------|-------------|
| CB-03 | `channels/webchat/` not mirrored; REST_webchat is canonical for this worktree | — |
| TP-05 | Report shares stored in `ticketing.settings` JSON (`report_share_links`) — no new Alembic table | — |
| TP-05 | SMS dispatch not wired; `# INTEGRATION POINT` in reports router | — |
| TP-08 | Second matrix column relabeled “Overdue open at end of Q*” (matches existing metric keys, not new pipeline column) | — |

---

## Agent: Image compression

**Prompt:** [`agents/image-compression.md`](agents/image-compression.md)  
**Spec:** [`docs/services/04_file_processing_service.md`](../../services/04_file_processing_service.md) §6

| Item | Status | Agent / date | PR / commit | Notes |
|------|--------|--------------|-------------|-------|
| Dockerfile libheif gate | `done` | Image compression / 2026-06-08 | | `vips -l foreign` HEIF check in Dockerfile |
| `image_compression.py` | `done` | Image compression / 2026-06-08 | | pyvips thumbnail → JPEG q80, EXIF strip |
| `file_server_core` hook | `done` | Image compression / 2026-06-08 | | Image branch before `store_file_attachment` |
| `file_queue` worker (concurrency 1) | `done` | Image compression / 2026-06-08 | | `celery_file` service in docker-compose |
| Tests | `done` | Image compression / 2026-06-08 | | `tests/backend/test_image_compression.py` |
| Prod smoke (HEIC + JPEG) | `todo` | | | Manual after deploy |

---

## Open blockers

| Ticket | Blocker | Owner |
|--------|---------|-------|
| TP-05 | SMS wiring requires `MESSAGING_API_KEY` + product copy for public URL | Integration |

---

## Agent: Archiving and retention

**Prompt:** [`agents/archiving-retention.md`](agents/archiving-retention.md)  
**Spec:** [`docs/ARCHIVING_AND_RETENTION.md`](../../ARCHIVING_AND_RETENTION.md)

| Item | Status | Agent / date | PR / commit | Notes |
|------|--------|--------------|-------------|-------|
| Settings `archiving_policy` | `done` | Archiving agent / 2026-06-08 | | super_admin JSON + seed default |
| Ticketing migration | `done` | Archiving agent / 2026-06-08 | | `z1a3b5c7` — `is_archived`, `archived_at` |
| Public migration | `done` | Archiving agent / 2026-06-08 | | `pub008` — grievances + file_attachments + `archived` status |
| `archiving.py` + Celery task | `done` | Archiving agent / 2026-06-08 | | Daily 03:00 Kathmandu; `ARCHIVING_DRY_RUN` env |
| Queue/upload guards | `done` | Archiving agent / 2026-06-08 | | Default queue filter; 409 upload; admin file access |
| Settings UI JSON | `done` | Archiving agent / 2026-06-08 | | System config tab section |
| Tests | `done` | Archiving agent / 2026-06-08 | | `tests/ticketing/test_archiving.py` |
| Prod dry-run | `todo` | | | Set `ARCHIVING_DRY_RUN=true` on first prod run |

**Implementation notes**

- `attachment_tier_on_archive` default **`none`** in seed (local DB); **`cold`** copies to `uploads/archive/{grievance_id}/` when enabled.
- S3 Glacier tier documented only; no boto3 move until `S3_BUCKET` is wired.
- Reopen (L2): `clear_archive_on_reopen` on ticket action when status leaves `RESOLVED`/`CLOSED`.

---

## Agent: Roles & permissions

**Prompt:** [`agents/roles-permissions.md`](agents/roles-permissions.md)  
**Product spec:** [`docs/ticketing_system/11_roles_and_permissions.md`](../../ticketing_system/11_roles_and_permissions.md)  
**Implementation spec:** [`05-roles-permissions-spec.md`](05-roles-permissions-spec.md)  
**Primary paths:** `ticketing/`, `channels/ticketing-ui/app/settings/`, `AuthProvider.tsx`

| Ticket | Status | Agent / date | PR / commit | Notes |
|--------|--------|--------------|-------------|-------|
| RP-01 Data model (`admin_scopes`, `role_kind`, `role_origin`) | `done` | Cursor / 2026-06-08 | | Migration `a2b4c6d8` |
| RP-02 Auth core (`admin_access.py`, `CurrentUser`) | `done` | Cursor / 2026-06-08 | | `get_authenticated_user` loads scopes |
| RP-03 Roles API (CRUD, archetypes, usage counts) | `done` | Cursor / 2026-06-08 | | |
| RP-04 Admin assignment API | `done` | Cursor / 2026-06-08 | | `/api/v1/admin-scopes` |
| RP-05 Route guards (matrix on routers) | `done` | Cursor / 2026-06-08 | | workflows, locations create, settings |
| RP-06 Settings UI tab access matrix | `done` | Cursor / 2026-06-08 | | AuthProvider + `page.tsx` |
| RP-07 Roles tab (operational only, create wizard) | `done` | Cursor / 2026-06-08 | | |
| RP-08 Workflows-first (step dropdown, inline create) | `done` | Cursor / 2026-06-08 | | |
| RP-09 Admin access platform sub-tab | `done` | Cursor / 2026-06-08 | | |
| RP-10 Seed & `local_admin` migration | `done` | Cursor / 2026-06-08 | | Demo officers + 3 `admin_scopes` rows |
| RP-11 Tests | `done` | Cursor / 2026-06-08 | | 11 passed in `ticketing_api` container |

**Verification (manual)**

- [ ] `super_admin`: all Settings tabs + Admin access
- [ ] `country_admin` NP + `standard`: create project; cannot see SEAH-only officer invite
- [ ] `country_admin` NP + `seah`: SEAH workflows/officers; cannot create project
- [ ] `project_admin` KL_ROAD + `standard`: staffing + orgs; cannot create roles
- [ ] Custom role created → bound on workflow step → officer invited → auto-assign eligible
- [ ] Inline **+ Create role** from workflow step works

**Sprint complete when:** RP-01 … RP-11 `done` and `11_roles_and_permissions.md` §8 updated.
