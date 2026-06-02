# Ticketing System – As-Built Status (June 2026)

> This document replaces the original v1 implementation plan. It records what has actually been built.
> For open/planned work → `docs/sprints/claude-tickets/TODO.md`.
> For full build log → `docs/sprints/claude-tickets/PROGRESS.md`.

---

## Phase 1 – Schema and migrations ✅ Complete

- `ticketing.*` schema with ~25 tables (see `04_ticketing_schema.md`)
- Alembic migration chain: ~30 revisions, scoped to `ticketing.*` only
- `include_object` guard prevents touching `public.*` tables

## Phase 2 – Core ticketing API ✅ Complete

- FastAPI service (`ticketing/api/main.py`) on port 5002
- Full CRUD for tickets, workflows, organizations, locations, projects, packages
- Ticket action engine (`POST /tickets/{id}/actions`): ACKNOWLEDGE, ESCALATE, RESOLVE, CLOSE, NOTE_ADDED, FIELD_REPORT, GRC_CONVENE, GRC_DECIDE, ASSIGN
- Role-based access control via `OfficerScope` on all list endpoints
- SEAH filtering at DB query level (`is_seah` flag)

## Phase 3 – Workflow engine and escalation ✅ Complete

- `ticketing/engine/workflow_engine.py` — step lookup, workflow assignment
- `ticketing/engine/escalation.py` — auto-assign on escalation, SLA check
- Celery SLA watchdog (every 15 min) in `ticketing/tasks/escalation.py`
- Auto-assign officer (`auto_assign_officer()`) on escalation using `OfficerScope`
- Automatic complainant notification on RESOLVE and ESCALATE: orchestrator `POST /message` → SMS fallback

## Phase 4 – Integration with chatbot ✅ Complete

- Chatbot webhook: `backend/actions/utils/ticketing_dispatch.py` (fire-and-forget)
- Wired into standard and SEAH grievance submission paths
- QR token scan: `GET /api/v1/scan/{token}` public endpoint; chatbot `ActionIntroduce` reads `t` URL param and pre-fills 7 slots
- PII fetch on-demand: `ticketing/clients/grievance_api.py`

## Phase 5 – Officer UI ✅ Complete

Built in `channels/ticketing-ui/` (Next.js 16, TypeScript, Tailwind v4).

- AppShell: sidebar, role-gated nav, badge count, SEAH indicator
- Queue page: tabs (My Queue / Watching / Escalated / Resolved), summary tiles, ticket rows with SLA countdown and SEAH badge
- All Tickets page (filterable list), Escalated page
- Ticket detail: grievance card, workflow stepper, SLA bar, event timeline, complainant PII + phone reveal (logged)
- Action panel: all action types
- File attachments: complainant read + officer upload
- Assign / reassign panels
- Settings page: full admin panel (workflows, users, orgs, locations, projects, packages, QR tokens)
- Reports page: Overview / Pivot / Quarterly email tabs
- Badge + SlaCountdown components

## Phase 6 – Extended features ✅ Complete

| Feature | Status | Notes |
|---|---|---|
| 4-tier permission model (Actor/Supervisor/Informed/Observer) | ✅ | `ticket_viewers.tier`; ViewersBar in UI |
| LLM per-note translation (EN) | ✅ | Celery task, GPT-4; `note_en` on ticket_events |
| LLM findings digest (`ai_summary_en`) | ✅ | `POST /tickets/{id}/findings`; role-gated |
| QR token intake | ✅ | `ticketing.qr_tokens`; QrCodeModal in Settings |
| Resolved case summary | ✅ | `ticket_resolved_summaries`; LLM generation |
| Overdue episodes | ✅ | `ticket_overdue_episodes`; `current_overdue_episode_id` on tickets |
| Reports: Overview + Pivot + Quarterly email | ✅ | `09_reports_and_report_builder.md` §2–§11 |
| Keycloak webhook → officer onboarding | ✅ | `POST /api/v1/webhooks/keycloak` |
| Roles catalog (9 GRM roles) | ✅ | `ticketing.roles`; Settings role editor |
| Bypass auth + demo roster | ✅ | `NEXT_PUBLIC_BYPASS_AUTH=true`; `grm_bypass_user` cookie |
| Admin audit log | ✅ | `ticketing.admin_audit_log` |

## Phase 7 – Remaining / Planned

| Item | Priority | Notes |
|---|---|---|
| Reports Summary tab (§12) | 🔲 Medium | ADB Project Director quarterly matrix + charts. Specified in `09_reports_and_report_builder.md`. |
| Staging deploy (`grm.stage.facets-ai.com`) | 🔲 High | Docker + Nginx + SSL on EC2. See `docs/sprints/claude-tickets/DOCKER.md`. |
| `public.grievances` sync smoke test | 🔲 High | Validate `grievance_sync.py` column names against live public schema. |
| Async large report export | 🔲 Low | Currently synchronous; large exports may timeout. |
| File storage → S3 | 🔲 Low | Currently local filesystem. |
| Server-Sent Events (SSE) notifications | 🔲 Low | Post-proto upgrade from badge polling. |
