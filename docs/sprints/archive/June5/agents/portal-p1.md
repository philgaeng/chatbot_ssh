# Agent prompt — Portal P1 (June5)

You are implementing **Portal P1** for the GRM ticketing UI and `ticketing/` FastAPI backend.

---

## Read first

1. `docs/sprints/June5/03-portal-p1-spec.md` — full spec
2. `docs/sprints/voice-notes-and-ux-feature-brief.md` — TP-* locked decisions
3. `docs/ticketing_system/09_reports_and_report_builder.md` — reports tickets
4. `docs/ticketing_system/08_ticket_resolution_and_case_summary.md` — field report / events pattern

---

## Mission (8 tickets)

Implement in this order unless blocked:

| Order | ID | Summary |
|-------|-----|---------|
| 1 | **TP-01** | Inline **audio player** for attachments (desktop + mobile). No transcription. |
| 2 | **TP-11** | Simplify `#` commands; assign-only field report; **image required** before Escalate/Close; merge escalation review into escalate form (date, persons, notes) |
| 3 | **TP-12** | **Assign** = supervisor only; L1 = Acknowledge or **Ask for reassignment** + 3 reason codes |
| 4 | **TP-09** | Grievance summary in thread UI; Acknowledge below (mobile-first) |
| 5 | **TP-10** | Call complainant report (same pattern as field report; not mandatory) |
| 6 | **TP-08** | Summary tab labels, tooltips, level vs package toggle |
| 7 | **TP-07** | Export all data → XLSX, OfficerScope only |
| 8 | **TP-05** | Internal + public report links; web-first; library; richer officer columns |

---

## Primary paths

**Frontend:** `channels/ticketing-ui/`

- `lib/api.ts`, `lib/mobile-constants.ts`, `lib/field-visit.ts`
- `components/thread/ComposeBar.tsx`
- `app/tickets/[id]/page.tsx`, `app/m/tickets/[id]/page.tsx`
- `app/reports/page.tsx`, `components/reports/SummaryTab.tsx`

**Backend:** `ticketing/`

- `api/routers/tickets.py`, `api/schemas/ticket.py`
- `api/routers/tasks.py`, `api/routers/reports.py`
- `api/routers/public_closure.py`
- `engine/escalation.py`, `services/report_rows.py`, `report_summary.py`, `report_export.py`
- `clients/grievance_api.py`, `clients/messaging_api.py`

---

## Do not edit

- `channels/REST_webchat/`, `backend/orchestrator/`, `rasa_chatbot/`
- `backend/actions/` (chatbot domain)
- Schema outside `ticketing.*` without agreement

New DDL only via `ticketing/migrations/` Alembic.

---

## TP-11 / TP-12 critical rules

- Remove `#photo`, `#review` from `lib/mobile-constants.ts`
- `hasImageAttachment()` before ESCALATE / CLOSE
- Escalation payload: date (default today), persons (me + add), notes required
- Reassignment reasons: `OUT_OF_PACKAGE_SCOPE` | `OUT_OF_LOCATION` | `OTHER` + notes
- Complainant extra photos: **WhatsApp** — no complainant portal login

---

## Progress protocol

Update `docs/sprints/June5/PROGRESS.md` → **Agent: Portal P1** per ticket.

Log cross-team notes in **Cross-team integration log** if chatbot attachment MIME types change.

---

## Definition of done

- [ ] All 8 tickets `done` in PROGRESS.md
- [ ] Mobile `#` palette smoke-tested on `app/m/tickets/[id]`
- [ ] Demo roles: site L1 vs supervisor (`mock-officer-site-l1` vs supervisor roster)
- [ ] TP-01 tested without TP-02 buttons
- [ ] Deviations section updated if any

---

## Report back

1. API changes (new routes, action types, event payloads)
2. Screenshots or steps for TP-11 gate and TP-12 L1 vs supervisor
3. Report link URL shapes (internal vs public)
4. Blockers for TP-05 SMS wiring

Do not commit unless the user asks.
