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
| CB-03 Close / exit consolidation | `todo` | | | |
| CB-04 File another grievance | `todo` | | | |
| CB-05 Attachment copy rewrite | `todo` | | | |
| CB-07 Success messages + filed banner | `todo` | | | |

---

## Agent: Chatbot P2

**Prompt:** [`agents/chatbot-p2.md`](agents/chatbot-p2.md)  
**Spec:** [`02-chatbot-p2-spec.md`](02-chatbot-p2-spec.md)  

| Ticket | Status | Agent / date | PR / commit | Notes |
|--------|--------|--------------|-------------|-------|
| CB-01 Voice note intake | `todo` | | | |
| CB-06 Location by pin | `todo` | | | |
| CB-08 Photo EXIF metadata | `todo` | | | |
| CB-09 Dust fast path | `todo` | | | |

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
| 2026-06-03 | Portal P1 | Officer upload + grievance file download now serve audio/* MIME types for inline playback |
| | | SMS public report URL: integration point left in `POST /reports/share` (messaging_api not wired) |
| | | Voice intake (CB-01) + TP-02 share accessible transcription API |

---

## Deviations from spec (append-only)

| Ticket | Deviation | Approved by |
|--------|-----------|-------------|
| TP-05 | Report shares stored in `ticketing.settings` JSON (`report_share_links`) — no new Alembic table | — |
| TP-05 | SMS dispatch not wired; `# INTEGRATION POINT` in reports router | — |
| TP-08 | Second matrix column relabeled “Overdue open at end of Q*” (matches existing metric keys, not new pipeline column) | — |

---

## Open blockers

| Ticket | Blocker | Owner |
|--------|---------|-------|
| TP-05 | SMS wiring requires `MESSAGING_API_KEY` + product copy for public URL | Integration |
