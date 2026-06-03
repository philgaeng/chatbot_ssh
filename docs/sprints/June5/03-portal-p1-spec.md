# Portal P1 — implementation spec

**Sprint:** June5  
**Tickets:** TP-01, TP-05, TP-07, TP-08, TP-09, TP-10, TP-11, TP-12, **TP-13** (follow-on UX — see [`agents/portal-p1-bugs.md`](agents/portal-p1-bugs.md))  
**Brief:** [voice-notes-and-ux-feature-brief.md](../voice-notes-and-ux-feature-brief.md)

**UI root:** `channels/ticketing-ui/` (Next.js)  
**API root:** `ticketing/`

---

## Shared touch map

| Area | Path |
|------|------|
| API client | `channels/ticketing-ui/lib/api.ts` — `performAction`, reports, files; `apiFetch` throws `Error("API {status} {path}: {body}")` |
| User messages | `channels/ticketing-ui/lib/user-messages.ts` — **TP-13** `formatUserFacingError`, known-case map |
| Action notice UI | `channels/ticketing-ui/components/ActionNotice.tsx` — **TP-13** in-app banner (amber / red) |
| Attachments helper | `channels/ticketing-ui/lib/attachments.ts` — `hasImageAttachment()` (TP-11 gate; TP-13 desktop) |
| Escalation form | `channels/ticketing-ui/components/thread/EscalationFormCard.tsx` — TP-11; **TP-13** wire desktop Escalate |
| Desktop ticket | `channels/ticketing-ui/app/tickets/[id]/page.tsx` |
| Mobile thread | `channels/ticketing-ui/app/m/tickets/[id]/page.tsx` |
| Compose / # commands | `channels/ticketing-ui/components/thread/ComposeBar.tsx` |
| Command defs | `channels/ticketing-ui/lib/mobile-constants.ts` — `HASH_COMMANDS`, `TASK_TYPES` |
| Field report form | `channels/ticketing-ui/lib/field-visit.ts` — `FieldVisitFormData`, `formatFieldVisitNote` |
| Actions API | `ticketing/api/routers/tickets.py` — `perform_action`, `VALID_ACTIONS` |
| Action schema | `ticketing/api/schemas/ticket.py` — `TicketActionRequest` |
| Tasks API | `ticketing/api/routers/tasks.py` — `TicketTask` CRUD |
| Task model | `ticketing/models/ticket_task.py` |
| Files | `ticketing/api/routers/tickets.py` — upload/list; `ticketing/models/ticket_file.py` |
| Grievance files | `ticketing/clients/grievance_api.py` — `GET /api/grievance/{id}` → `files` |
| Reports page | `channels/ticketing-ui/app/reports/page.tsx` |
| Summary tab | `channels/ticketing-ui/components/reports/SummaryTab.tsx` |
| Report services | `ticketing/services/report_rows.py`, `report_summary.py`, `report_export.py` |
| Reports API | `ticketing/api/routers/reports.py` |
| Public closure | `ticketing/api/routers/public_closure.py`, `channels/ticketing-ui/app/closure/[token]/page.tsx` |
| Escalation | `ticketing/engine/escalation.py` — `escalate_ticket` |
| Roles / scope | `ticketing/api/dependencies.py`, `ticketing/constants/grm_role_catalog.py` |
| Docs | `docs/ticketing_system/09_reports_and_report_builder.md`, `08_ticket_resolution_and_case_summary.md` |

---

## TP-01 — Voice note playback (inline player)

### Goal

Listen to audio attachments in ticket detail (desktop + mobile). **No transcription** (TP-02).

### Tasks

1. From ticket detail payload, merge **complainant files** (grievance API) + **officer files** (`ticketing.ticket_files` / list endpoint in `tickets.py`).
2. Filter `content_type` or extension for audio (`audio/*`, `.m4a`, `.webm`, `.mp3`, `.wav`, `.aac`).
3. Add `<audio controls>` (or shared component) in:
   - `app/tickets/[id]/page.tsx` — grievance / attachments section
   - `app/m/tickets/[id]/page.tsx` — thread or detail drawer
4. Secure URLs: use existing file download route (grep `download` / `file_path` in `tickets.py` ~1620+).

### Acceptance criteria

- [ ] Play/pause works on mobile Safari + Chrome Android for at least one sample file per format.
- [ ] No new transcription buttons in P1.

---

## TP-09 — Acknowledge with grievance visible in thread UI

### Goal

Officer sees **grievance details + summary** in the messaging-style UI; **Acknowledge** directly below — no hunting in side panels.

### Locked product note (from brief)

Display grievance details and summary in main thread UI; Acknowledge button below.

### Tasks

1. **Mobile** (`app/m/tickets/[id]/page.tsx`): Add pinned card or first thread block with `grievance_summary`, categories, location, truncated narrative; **Acknowledge** CTA when `expected_actions` includes `ACKNOWLEDGE`.
2. **Desktop** (`app/tickets/[id]/page.tsx`): Mirror or enhance existing grievance card — same information hierarchy.
3. Gate: optional scroll/end detection (open in spec) — minimum: button only enabled after card expanded/viewed once.
4. API unchanged unless adding `GRIEVANCE_REVIEWED` event — optional in `perform_action` for ACKNOWLEDGE.

### Acceptance criteria

- [ ] L1 actor sees summary + ack on one screen (mobile priority).
- [ ] Works with **TP-12** (L1 cannot assign, can ack).

---

## TP-10 — Complainant call report

### Goal

Structured **call log** like field report / location report — **not mandatory** (managers enforce usage).

### Tasks

1. Reuse `FieldVisitFormData` pattern in `lib/field-visit.ts` — new `CallReportFormData` or extend with `kind: "call"`.
2. Add `#call` / task flow in `ComposeBar.tsx` — mirror `submitFieldReportForm` (~814 in mobile page).
3. Persist via `performAction` with `NOTE` + payload `{ is_call_report: true }` **or** new action type if backend extended (prefer NOTE + flag like `is_field_report` in `tickets.py` FIELD_REPORT branch).
4. Fields: date/time (default now), person contacted, notes.

### Acceptance criteria

- [ ] Call report appears as distinct timeline bubble.
- [ ] PII: phone reveal rules unchanged (`demo_reveal` / reveal contact).

---

## TP-05 — Report links (internal + public), library

### Goal

Web-first reports; **two link types**; officer-facing web includes richer ticket fields; PDF optional; library retained.

### Locked decisions (from brief)

- Web before PDF; align columns web ↔ PDF where possible.
- **Internal link** — officers (auth).
- **Public link** — complainant-facing (SMS); less detail.
- Officer web report adds: grievance category, escalated Y/N, level at resolution, etc. (from `report_rows` fields).

### Tasks

1. **Internal:** Signed or tokenized URL from reports export/summary (extend `reports.py` + `report_export.py`).
2. **Public:** Reuse/extend `public_closure.py` pattern or new `public_report` router — no officer PII.
3. **SMS:** `ticketing/clients/messaging_api.py` — send public URL (integration point).
4. UI: `app/reports/page.tsx` — “Copy internal link”, “Copy public link” per generated report; library in `quarterly_library.py` / existing library UI.
5. Map fields from `ticketing/services/report_rows.py` §4 column keys.

### Acceptance criteria

- [ ] Internal link opens authenticated or one-time officer view with extended columns.
- [ ] Public link shows safe subset only.
- [ ] Library lists past reports with both link types where applicable.

---

## TP-07 — Export all data to Excel

### Goal

Single **Export all data** → XLSX, analysis-ready, **OfficerScope**-filtered.

### Tasks

1. Add endpoint e.g. `GET /api/v1/reports/export-all` or extend `report_export.py` with full row set from `report_rows.py` (all tickets in scope, not only quarterly template).
2. UI: button on `app/reports/page.tsx` toolbar.
3. Enforce scope in query layer (same as `GET /tickets` / `reports/query` — `dependencies.py` + workflow engine filters).
4. Cap: respect `report_limits` in `ticketing/services/report_limits.py` (default row cap — document if hit).

### Acceptance criteria

- [ ] XLSX opens in Excel with stable headers and no broken encoding (UTF-8).
- [ ] User A cannot see user B’s out-of-scope tickets in export.

---

## TP-08 — Quarterly dashboard clarity

### Goal

Fix confusing Summary matrix labels; tooltips; level vs package toggle.

### Locked label direction (from brief)

Clarify first two columns — example rename:


| Was (confusing) | Suggested |
|-----------------|-----------|
| Open end 2026-Q2 | **Open at end of 2026-Q2** (snapshot) |
| Open 2026-Q2 | **Open during 2026-Q2** (pipeline) |

(Product final strings in implementation.)

### Tasks

1. `channels/ticketing-ui/components/reports/SummaryTab.tsx` — column headers, tooltips on L1–L4, agency, package.
2. `ticketing/services/report_summary.py` — expose header metadata if generated server-side.
3. View toggle: **Level detail** vs **Total per package** — filter matrix columns client-side or via API param on `GET /api/v1/reports/summary`.
4. Hover labels on L1/L2/L3/L4 cells (chart + matrix).

### Acceptance criteria

- [ ] Tooltips on all L-level and package headers.
- [ ] Toggle switches matrix aggregation without breaking export.

---

## TP-11 — Simplify commands + site photo gate + merged escalation

### Goal

Fewer `#` commands; photo gate before close/escalate; escalation includes review fields.

### Locked decisions

| Item | Decision |
|------|----------|
| Field report | One path: **assign** field report task → assignee fills form |
| `#photo` / DOCUMENT_PHOTO | **Remove** |
| Close / Escalate | Block unless ≥1 **image** in attachments (complainant + officer files) |
| Complainant photos | WhatsApp only — no portal complainant login |
| Escalation review | Merged into **Escalate** step: date (today), persons (me + add), notes (required) |

### Tasks

1. **`mobile-constants.ts`:** Remove `#photo`, `#review`; change `#report` to assign-only; keep `#inspect` assign pattern.
2. **`ComposeBar.tsx` / mobile page:** Escalate opens modal with field-report-shaped form before `performAction(..., ESCALATE)`.
3. **Gate:** Helper `hasImageAttachment(files)` — check grievance files + `ticket_files` mime/extension (`tickets.py` image detection ~1664).
4. **Backend:** Extend `TicketActionRequest` + `escalate_ticket` payload with `escalation_date`, `persons_involved[]`, `escalation_notes` (JSON in event payload).
5. **Tasks API:** Field report = create `TicketTask` type `SYSTEM_NOTE` or dedicated type — assignee completes via `openFieldVisit` pattern (`?openFieldVisit=` in mobile page).
6. Remove standalone `ESCALATION_REVIEW` task creation from UI.

### Acceptance criteria

- [ ] Escalate blocked with clear message when no images.
- [ ] Resolve/Close blocked same way (if product includes CLOSE — check `VALID_ACTIONS`).
- [ ] Single assign-field-report entry point.
- [ ] Escalation timeline event contains notes + persons + date.

---

## TP-12 — Assign vs ask for reassignment

### Goal

Supervisors **assign**; L1 **acknowledge** or **ask for reassignment** with reason codes.

### Locked reason codes

- `OUT_OF_PACKAGE_SCOPE`
- `OUT_OF_LOCATION`
- `OTHER` (+ required notes)

### Tasks

1. **Role check:** Use tier/role from `CurrentUser` in `ticketing/api/dependencies.py` + `grm_role_catalog.py` — Supervisor vs Actor (L1).
2. **UI:** Hide `#assign` / Assign panel for L1; show **Ask for reassignment** with reason modal.
3. **API:** New action or extend `perform_action`:
   - `REASSIGNMENT_REQUESTED` → moves queue to superior, stores reason in `ticket_events.payload`
   - Superior assign uses existing assign endpoint with reason on `ASSIGNED` event
4. **Routing:** Package supervisor vs project-level — use `OfficerScope` (`ticketing/models/officer_scope.py`, `workflow_engine.py` `_scope_candidates`).
5. Integrate with **TP-09** ack path.

### Acceptance criteria

- [ ] L1 cannot assign to arbitrary teammate.
- [ ] Supervisor can assign with reason.
- [ ] Ask for reassignment creates visible event and requeues to superior.
- [ ] Project-level escalation path documented in help text.

---

## TP-13 — Officer-friendly validation messages

**Agent prompt:** [`agents/portal-p1-bugs.md`](agents/portal-p1-bugs.md)  
**Brief:** [voice-notes-and-ux-feature-brief.md](../voice-notes-and-ux-feature-brief.md) § TP-13

### Goal

Expected validation failures (missing photo, required notes, wrong role, etc.) are shown **in the GRM UI** with plain language. Officers never see browser `alert()` text containing `API 422`, `/api/v1/...`, or JSON bodies.

### Problem (observed)

Desktop `app/tickets/[id]/page.tsx` uses `alert(String(e))` in `act()`, `submitResolve()`, and related handlers. `apiFetch` in `lib/api.ts` throws:

```text
Error: API 422 /api/v1/tickets/{id}/actions: {"detail":"At least one image attachment..."}
```

Mobile has client image gate + `EscalationFormCard`, but still uses `alert(String(e))` on several catch paths.

### Locked decisions

| Item | Decision |
|------|----------|
| `window.alert()` | Remove for ticket action errors on desktop + mobile ticket pages |
| Visible copy | No HTTP status, paths, `API`, or `{"detail":...}` |
| Validation | Amber in-app notice — “complete this first” |
| Unexpected | Red in-app notice — “could not save, try again” |
| Image gate (client) | Desktop **Escalate** / **Resolve** / `#escalate` call `hasImageAttachment()` before API (same message as server) |
| Desktop escalate | **Escalate** opens `EscalationFormCard` (not bare `performAction(ESCALATE)`) |

### Tasks

1. **`lib/user-messages.ts`**
   - `parseApiErrorBody(raw: string): string | null` — extract FastAPI `detail` from JSON body after `API \d+ path:` prefix.
   - `formatUserFacingError(e: unknown, context?: ActionErrorContext): { message: string; kind: "validation" | "failure" }`.
   - Map known substrings / codes to officer copy (table below). Fallback: generic “Something went wrong. Please try again.”

2. **`components/ActionNotice.tsx`**
   - Props: `message`, `kind`, `onDismiss`.
   - Styling: amber border/bg for validation; red for failure; fixed or sticky under ticket header; matches Tailwind patterns from `ResolutionSheet` / mobile cards.

3. **`app/tickets/[id]/page.tsx`**
   - State: `actionNotice: { message, kind } | null`.
   - Replace all `alert(String(e))` in action flows with `setActionNotice(formatUserFacingError(e))`.
   - `openEscalationFlow`: client image check → open `EscalationFormCard`; submit via `submitEscalation` (mirror mobile).
   - Wire **Escalate** button and `#escalate` in `handleHashCommand` to `openEscalationFlow`, not `act("ESCALATE")`.
   - Render `<ActionNotice />` + `<EscalationFormCard />` when needed.

4. **`app/m/tickets/[id]/page.tsx`**
   - Same `formatUserFacingError` + `ActionNotice` (mobile-friendly width).
   - Replace `alert(...)` in escalate, resolve, assign, reassignment, upload, task flows.
   - Keep existing client image gate; use shared message constants.

5. **Optional — `lib/api.ts`**
   - Export `class ApiError extends Error { userMessage: string; kind: ... }` thrown from `apiFetch` so callers need not re-parse. Keep throw shape backward-compatible for grep.

6. **Consolidate** `fieldVisitSaveErrorMessage` to call `formatUserFacingError` (or shared `parseApiErrorBody`) to avoid duplicate strip logic.

### Known backend `detail` strings → officer copy

| Backend signal (substring or exact) | Officer message (use or paraphrase) | Kind |
|-----------------------------------|-------------------------------------|------|
| `At least one image attachment is required before escalating` | Add at least one photo before escalating. Upload a site photo or ask the complainant to send photos via WhatsApp. | validation |
| `At least one image attachment is required before resolving` | Add at least one photo before resolving. Upload a site photo or ask the complainant to send photos via WhatsApp. | validation |
| `escalation_notes is required` | Add escalation notes explaining why this case should move to the next level. | validation |
| `Cannot perform` + `ESCALATED` + `Acknowledge` | Acknowledge the ticket first to take ownership at this level. | validation |
| `No next step available` / `final escalation level` | This case is already at the highest escalation level. | validation |
| `reassignment_notes required when reason is OTHER` | Add a short explanation when you choose “Other” as the reassignment reason. | validation |
| `reassignment_reason_code must be` | Choose a reassignment reason before submitting. | validation |
| `No supervisor configured` | No supervisor is set up for this step. Contact your admin. | failure |
| `Only` + `supervisor` / assign permission (403/422 from patch) | Only a supervisor can assign this ticket. Use **Ask for reassignment** if it is out of your scope. | validation |
| `Ticket is already resolved` | This case is already resolved. | validation |
| `note is required` | Add a note before saving. | validation |
| Session expired handling | Keep existing redirect; no alert. | — |
| Unmatched | Something went wrong. Please try again. | failure |

Product may shorten strings; must not expose API paths or field names.

### Acceptance criteria

- [ ] Desktop: Escalate without image shows **amber in-app notice** (no browser dialog).
- [ ] Desktop: Escalate with image opens **escalation form**; missing notes shows validation notice (not API string).
- [ ] Mobile: same behaviors; no `alert()` on action errors.
- [ ] Screenshot regression: error title is **not** `grm-auth... says` / `API 422`.
- [ ] `grep alert(` in `app/tickets/[id]` and `app/m/tickets/[id]` returns zero for action catch blocks (upload generic message may use notice).
- [ ] TypeScript build passes.

### Testing

- [ ] GRV demo ticket at L2 without attachments → Escalate blocked with friendly copy.
- [ ] Add officer image upload → Escalate form → submit with notes → succeeds.
- [ ] L1 tries `#assign` → supervisor-only message (no API path).
- [ ] Field report save failure still readable (via shared formatter).

---

## Suggested implementation order

```text
TP-01 → TP-11 → TP-12 → TP-09 → TP-10 → TP-08 → TP-07 → TP-05 → TP-13
```

(TP-11 and TP-12 may share compose/modal work. **TP-13** after TP-11/12 or in parallel once gates exist.)

---

## Testing

- [ ] Mobile: `#` palette regression on `app/m/tickets/[id]/page.tsx`
- [ ] Demo officers in `ticketing/seed/mock_tickets.py` — site L1 vs supervisor roles
- [ ] Reports: `tests/` if present for `report_rows` / export

---

## Out of scope (Portal P1)

- Transcription (**TP-02**)
- Chatbot intake changes

**TP-13** is Portal P1 follow-on UX (same sprint folder); tracked separately in PROGRESS under **Portal P1 bugs** agent.
