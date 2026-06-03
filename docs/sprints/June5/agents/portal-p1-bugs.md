# Agent prompt — Portal P1 bugs / UX polish (June5)

You are fixing **post–Portal P1 UX gaps** in the GRM ticketing UI. Primary ticket: **TP-13** (officer-friendly validation messages).

---

## Read first

1. `docs/sprints/June5/03-portal-p1-spec.md` — § **TP-13** (full tasks + acceptance criteria)
2. `docs/sprints/voice-notes-and-ux-feature-brief.md` — TP-13 locked decisions
3. `docs/sprints/June5/PROGRESS.md` — **Agent: Portal P1 bugs** section

**Context:** Portal P1 (TP-01 … TP-12) is largely **done**. This agent does **not** re-implement those features — it replaces rough error handling and closes desktop/mobile parity gaps left after TP-11.

---

## Mission (1 ticket)

| Order | ID | Summary |
|-------|-----|---------|
| 1 | **TP-13** | In-app validation notices; no `alert()`; no API jargon; desktop Escalate → `EscalationFormCard` + image gate |

---

## Primary paths

**Frontend only** (`channels/ticketing-ui/`):

| File | Work |
|------|------|
| `lib/user-messages.ts` | **Create** — `formatUserFacingError`, `parseApiErrorBody`, known-case map |
| `components/ActionNotice.tsx` | **Create** — amber validation / red failure banner |
| `lib/api.ts` | Optional `ApiError` with `userMessage` from `apiFetch` |
| `lib/field-visit.ts` | Delegate `fieldVisitSaveErrorMessage` to shared formatter |
| `lib/attachments.ts` | Reuse `hasImageAttachment()` for desktop gates |
| `components/thread/EscalationFormCard.tsx` | Wire on **desktop** ticket page |
| `app/tickets/[id]/page.tsx` | Remove `alert(String(e))`; escalation flow; `ActionNotice` |
| `app/m/tickets/[id]/page.tsx` | Same notice pattern; remove action `alert()`s |

**Backend:** read-only unless `detail` strings are still technical (`ticketing/api/routers/tickets.py` perform_action 422s). Prefer UI mapping over API changes.

---

## Do not edit

- `channels/REST_webchat/`, `backend/orchestrator/`, `rasa_chatbot/`
- `backend/actions/`
- Unrelated Portal P1 features (reports, audio player) unless a shared `alert()` is in scope

---

## TP-13 critical rules

1. **Never** show users: `API 422`, `/api/v1/`, `{"detail":...}`, or browser-native `alert()` for ticket actions.
2. **Amber** = expected validation (missing photo, notes, wrong role for assign).
3. **Red** = unexpected failure (generic retry message).
4. Desktop **Escalate** and `#escalate` must match mobile: image check → `EscalationFormCard` → `performAction(ESCALATE)` with payload.
5. Image gate copy (locked): *"Add at least one photo before escalating. Upload a site photo or ask the complainant to send photos via WhatsApp."* (resolve variant: “before resolving”).

Reference implementation patterns:

- Mobile gate: `openEscalationFlow` in `app/m/tickets/[id]/page.tsx`
- Error stripping (partial): `fieldVisitSaveErrorMessage` in `lib/field-visit.ts`
- Modal chrome: `components/ResolutionSheet.tsx`

---

## Progress protocol

Update `docs/sprints/June5/PROGRESS.md` → **Agent: Portal P1 bugs**:

| Ticket | Status | Owner / date | Notes |
|--------|--------|--------------|-------|
| TP-13 Officer-friendly validation messages | `todo` / `in_progress` / `done` | | |

Log deviations if desktop scope expands (e.g. settings page alerts).

---

## Definition of done

- [ ] TP-13 `done` in PROGRESS.md
- [ ] Desktop Escalate without image → amber `ActionNotice`, no browser dialog
- [ ] Desktop Escalate with image → escalation form → success path unchanged
- [ ] Mobile action errors use `ActionNotice` (no `alert` on catch paths in ticket page)
- [ ] `grep -r "alert(String(e))" channels/ticketing-ui/app/tickets channels/ticketing-ui/app/m/tickets` → empty
- [ ] `npx tsc --noEmit` in `channels/ticketing-ui/` passes

---

## Report back

1. Files added/changed
2. Before/after screenshot or steps for Escalate without image (desktop)
3. List of `alert()` removals (file + handler name)
4. Any backend `detail` strings you had to map because they were not user-friendly

Do not commit unless the user asks.
