# Voice Notes + UX Consolidation Brief

## Purpose

**Implementation specs (June5 sprint):** [`docs/sprints/June5/README.md`](June5/README.md)

Feature-level ticket candidates for:

- **Chatbot** — REST webchat + intake flow
- **Ticketing / portal** — officer views, attachments, reporting

Each ticket includes **locked decisions** where product has already chosen a direction.

**Priority** is shown on each ticket: **P1** (next build) · **P2** (follow-on) · **—** (backlog).

---

## Priorities (locked)

### P1 — Chatbot

| ID | Title |
|----|--------|
| CB-03 | Close / exit consolidation |
| CB-04 | File another grievance |
| CB-05 | Attachment step copy rewrite |
| CB-07 | Post-submit success messages + filed banner |

### P1 — Ticketing / portal

| ID | Title |
|----|--------|
| TP-01 | Voice note **playback** (inline audio player) |
| TP-09 | Read full grievance before acknowledge |
| TP-10 | Complainant call report |
| TP-05 | Report links, PDF, library |
| TP-07 | Export all data to Excel |
| TP-08 | Quarterly dashboard clarity |
| TP-11 | Simplify commands (field report, site photo gate, escalation) |
| TP-12 | Assign vs ask for reassignment |
| TP-13 | Officer-friendly validation messages (no API jargon) |
| TP-14 | Grievance summary + categories sync and officer validation |

### P2 — Ticketing / portal

| ID | Title |
|----|--------|
| TP-02 | Voice note **transcription** (force retry + manual fallback) |

### Backlog (not P1) — Chatbot

| ID | Title |
|----|--------|
| CB-01 | Hybrid grievance input (text or voice note) |
| CB-06 | Location by map pin + fallback |
| CB-08 | Photo metadata (location + time) |
| CB-09 | Dust complaint fast path |

---

## Scope notes

- Transcript extract was de-duplicated; removed items stay out unless merged from a later batch (see §E).
- Training and partner-session work is tracked under **§C**, not as product tickets.

---

## A) Chatbot — ticket candidates

### CB-01 — Hybrid grievance input (text or voice note) · **—** backlog

**Feature goal**  
Complainants submit grievance details by typed text, voice note, or both during capture.

**Why**  
Supports low-literacy users and mobile usage in the field.

**In scope**

- Prompt: *"Type your grievance or record a voice note"*.
- Dedicated **Record voice note** button on the grievance description step (not text-only UX).
- Valid submission when text is empty but at least one voice note is attached.
- Voice note stored as grievance attachment and visible downstream (ticketing / grievance API).
- Transcription: reuse the accessible-channel pipeline (`backend/services/accessible/`*), invoked **via API** (not a duplicate implementation in the webchat bundle).

**Out of scope**

- Real-time speech recognition / live caption tuning.

**Locked decisions**


| Topic                                 | Decision                                                                                                                                                                                                                             |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Audio capture (rural / low bandwidth) | Prefer **medium sample rate** and **small chunks** suitable for patchy networks. If the web client **cannot** chunk on device, cap each recording at **60–90 seconds**; user may attach **multiple** voice notes for a longer story. |
| Transcription                         | Server-side via existing accessible voice service API; async after upload is acceptable.                                                                                                                                             |
| Pairing                               | Same audio limits and attachment model apply on portal side → **TP-01** / **TP-02**.                                                                                                                                                 |


---

### CB-03 — Close / exit action consolidation · **P1**

**Feature goal**  
Remove redundant close/hide patterns while keeping compliance-appropriate exits.

**Why**  
Today users see **Close browser** and **Close session** together on paths where only one behavior is needed.

**In scope**

- **Standard grievance flow:** show **Close session** only (same behavior as today’s Close session — reset state, new session id).
- **SEAH flow:** show **Close browser** only (same behavior as today’s Close browser — attempt tab close / safety exit).
- Remove the unused close control from each path; do not add new close semantics.

**Locked decisions**


| Topic            | Decision                                                                                                      |
| ---------------- | ------------------------------------------------------------------------------------------------------------- |
| Behavior change  | **No** change to what each button does — only **which** button appears per workflow.                          |
| SEAH vs standard | Close session = regular; Close browser = SEAH (and equivalent sensitive paths if product confirms same rule). |


---

### CB-04 — Post-submission restart ("File another grievance") · **P1**

**Feature goal**  
Let users start a new grievance without managing browser tabs.

**Why**  
End-of-flow copy that tells users to close tabs is a common drop-off point.

**In scope**

- CTA after completion/review: **File another grievance**.
- Deterministic restart via intro / new-grievance path (aligned with `/introduce` reset rules).
- Session safety preserved (clear prior grievance context before new intake).

---

### CB-05 — Attachment step copy (rewrite) · **P1**

**Feature goal**  
Clearer, encouraging language when users reach the file-attachment step.

**Why**  
Current “no file attached” messaging is abrupt; users may not know handwritten complaints and photos are welcome.

**In scope**

- Replace copy equivalent to *"you have not attached any file"* with user-friendly wording (exact EN/NE strings in spec).
- When attachment is offered, use messaging along the lines of:  
*"You can now attach pictures or other documents related to your grievance. These will be reviewed by our officer. You may also attach a photo of a handwritten complaint."*  
(Localize via existing utterance / i18n pattern.)

**Open for spec**

- Whether “no file yet” appears only on skip vs always before first upload.

---

### CB-06 — Location by map pin (with fallback) · **—** backlog

**Feature goal**  
Capture grievance location via map pin when possible; otherwise fall back to the existing location questions.

**Why**  
Pin placement is faster and more accurate on mobile for road-adjacent complaints.

**In scope**

- **Primary:** “Get location by pin” (map picker or drop pin on map in webchat).
- **Fallback:** if pin unavailable, denied, or user opts out → existing **ask location** flow (province / district / municipality / ward, etc., per current form).
- Persist chosen coordinates and/or resolved admin location codes on grievance record as today’s schema allows.

**Open for spec**

- Map provider and offline behavior on low connectivity.
- Whether pin overrides manual location or pre-fills fields for confirmation.

---

### CB-07 — Post-submit success messaging + filed banner · **P1**

**Feature goal**  
After grievance is filed, users see a clear three-part confirmation and a persistent “filed” indicator with reference number.

**Why**  
Users confuse “still in chat” with “not yet submitted”; follow-up questions should not sound like filing failed.

**In scope**

- **Message 1:** explicit **success** (grievance filed).
- **Message 2:** **grievance number** (reference id) prominently shown.
- **Message 3:** clarify that **follow-up questions may continue** but the grievance is **already filed** (attachments, contact, categorization review, etc.).
- **UI banner** at top of chat while in post-filed phase: status *Grievance filed* + grievance number (visible from **submit** through `grievance_review` and `done`, until session reset or file another — not only at `done`).
- **Two chat phases (standard):** (A) three bubbles right after submit/OTP — not one combined recap in chat; (B) same pattern after review outro. SMS may keep full recap text.

**Implementation detail:** see [`01-chatbot-p1-spec.md`](June5/01-chatbot-p1-spec.md) CB-07.

**Related**

- Works with **CB-04** (file another grievance) and attachment steps that happen after submit.

---

### CB-08 — Photo attachment metadata (location + time) · **—** backlog

**Feature goal**  
When users attach photos, optionally use EXIF (or equivalent) metadata to enrich location and timestamp— with explicit consent.

**Why**  
Photos from the field often carry GPS and time useful for dust/road complaints; must be permission-based.

**In scope**

- On attachment upload, **ask permission** to read image metadata (**location** and **time**).
- If granted: extract coordinates/time where present; store on file/grievance metadata for officer review (not shown to complainant as raw EXIF dump).
- If denied or missing: no blocking; user can still complete flow (pin / manual location from **CB-06**).
- Applies to standard attachment step and **CB-09** dust path.

**Out of scope (initial ticket)**

- Computer vision to infer location from image content without GPS.

**Open for spec**

- Privacy copy (EN/NE) and retention rules for extracted coordinates.

---

### CB-09 — Dust complaint fast path (category-specific workflow) · **—** backlog

**Feature goal**  
Shorter, guided intake when user selects **DUST** (or equivalent category), optimized for road-dust reports with pin + photo evidence.

**Why**  
Dust is a high-volume, structurally similar complaint type; a dedicated path reduces abandonment.

**Proposed flow (product draft — validate in spec)**


| Step        | Behavior                                                                                                                                                                                  |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Category | User chooses **DUST**.                                                                                                                                                                    |
| 2. Location | **2a.** Map **pin** → automatic location where possible. **2b.** Fallback: nearest **municipality**, then **locality/village**; optional **km on road** or municipality-level descriptor. |
| 3. File     | **File grievance** (minimal narrative or skip if policy allows for dust-only).                                                                                                            |
| 4. Evidence | **Add picture(s)**; run **CB-08** metadata permission + extraction.                                                                                                                       |
| 5. Contact  | **Optional** contact details — UI makes optional nature **more obvious** (e.g. “You can skip — we already have your grievance number”).                                                   |


**In scope**

- New or branched flow state(s) in orchestrator for dust-only path (or category flag on existing form).
- Reuse **CB-06** (pin + fallback) and **CB-08** (photo metadata).
- Ticket still created via existing submit + ticketing dispatch.

**Open for spec**

- Whether dust path skips free-text grievance entirely or uses a one-line default summary.
- Alignment with KL Road package/QR prefill when scanned from site signage.

---

## B) Ticketing / portal — ticket candidates

### TP-01 — Voice note playback (inline player) · **P1**

**Feature goal**  
Officers can **listen** to voice-note attachments on ticket detail (mobile + desktop).

**Why**  
Audio evidence must be reviewable without downloading files; transcription comes in **TP-02**.

**In scope**

- List audio attachments on ticket (complainant + officer uploads; common iOS/Android formats).
- **Inline audio player** on ticket detail and mobile thread.
- Attachment metadata in exports where applicable (no playback in XLSX).

**Out of scope (→ TP-02)**

- Force transcription, retries, manual transcript fallback.

**Locked decisions**

| Topic | Decision |
|-------|----------|
| Audio formats | Align with future **CB-01** contract when voice intake ships; until then support existing grievance file types. |

---

### TP-02 — Voice note transcription · **P2**

**Feature goal**  
Officers can trigger transcription of voice attachments and fall back to manual entry when automation fails.

**Why**  
Playback alone (**TP-01**) is not enough for search, summary, or officers who need text.

**In scope**

- **Force transcription** with retries (accessible service API, same as CB-01).
- On failure: prompt officer to **enter manual transcript/summary**.
- Show transcription on ticket timeline or attachment panel when available.

**Depends on** TP-01 (player + attachment list), CB-01 (intake) when live.

---

### TP-09 — Acknowledge only after full grievance read · **P1**

**Feature goal**  
Officers must view the complete grievance content before **Acknowledge** is enabled.

**Why**  
Prevents perfunctory acknowledgement without reviewing complainant narrative, attachments, and summary.

**In scope**

- Display the grievance details and grievance summary in the main messenging type UI and the button Acknowledge below, this way the user doesnt have to look for the grievance details, it is right here in the chatbot.

**Open for spec**

- Whether “full read” means scroll-to-end, time-on-page threshold, or explicit “I have read” checkbox.

---

### TP-10 — Complainant call log (mirror location report pattern) · **P1**

**Feature goal**  
Officers can record **phone contact with complainant** using the same interaction pattern as the existing **location** report / verification flow.

**Why**  
Call outcomes need to be on the case timeline for accountability and follow-up.

**In scope**

- **Call complainant** action on ticket detail (alongside or near reveal-contact / reply).
- Structured **call report** form aligned with existing location-report UX (fields TBD: date/time, person contacted, notes). Same implementation than field report.
- Persist as ticket event visible in timeline; respect PII rules (phone reveal logging unchanged).

**Open for spec**

W edont make anything mandatory so that users may just write down everything they need directly as notes - we let managers enforce using structured reports like field report or calls.

---

### TP-11 — Simplify officer commands (field report, site photo, escalation) · **P1**

**Feature goal**  
Reduce command clutter on ticket detail / mobile compose (`#` palette); align actions with field practice.

**Why**  
Overlapping commands (field report, site photo task, escalation review) confuse officers.

**In scope — command list**

| Change | Decision |
|--------|----------|
| **Field report** | **One** path: **assign a field report** to someone; assignee opens the task and **enters details** (structured form). Remove duplicate “write field report” shortcuts. |
| **Site photo required** | **Remove** as standalone command / task (`DOCUMENT_PHOTO`, `#photo`). |
| **Site photo gate** | Before **Close** or **Escalate**, require ≥1 **image** in ticket attachments (officer or complainant files). Block with clear message if none. |
| **Photos from complainant** | **No** portal re-login for complainants; extra photos via **WhatsApp**; officer uploads if needed. |
| **Escalation + escalation review** | **Merge**: escalation review is a **step inside Escalate**, not a separate command. |

**Escalation step (same shape as field report)**

| Field | Default / behavior |
|-------|-------------------|
| Date | Today (editable) |
| Person(s) involved | Current user + **Add** others |
| Notes | Required — why escalation is requested |

**Implementation note**  
`channels/ticketing-ui/lib/mobile-constants.ts` — `HASH_COMMANDS` / `TASK_TYPES` today include `#report`, `#photo`, `#review`, `#escalate`.

---

### TP-12 — Assign vs reassignment (supervisor vs L1) · **P1**

**Feature goal**  
**Assign** is supervisor-only; L1 officers **acknowledge** or **ask for reassignment** with mandatory reason codes.

**Why**  
Package-scoped L1 must not assign across the team; routing up the chain needs audit trail.

**In scope**

| Role | Capabilities |
|------|----------------|
| **Supervisor** | **Assign** to any officer on their team. |
| **L1 / package actor** | **Acknowledge** (with **TP-09**) or **Ask for reassignment** — not assign. |

**Ask for reassignment**

1. L1 selects **Ask for reassignment** when ticket is out of scope.
2. Ticket goes to **immediate superior** (package supervisor).
3. Superior may reassign in team or **ask upward** to **project-level** officer when beyond package.

**Reassignment reason (required)**

| Code | Label |
|------|--------|
| `OUT_OF_PACKAGE_SCOPE` | Out of package scope |
| `OUT_OF_LOCATION` | Out of location of responsibility |
| `OTHER` | Other (+ **notes** required) |

Store on timeline event (`REASSIGNMENT_REQUESTED` / assign payload).

**Related** TP-09, TP-11 (assign-to-officer picker may share UI).

---

### TP-13 — Officer-friendly validation messages · **P1**

**Feature goal**  
When an officer action cannot proceed (missing photo, required notes, permission denied, etc.), show a clear message **inside the GRM UI** — never a browser `alert()` with API paths, status codes, or JSON.

**Why**  
After **TP-11** (image gate, escalation form), desktop **Escalate** still calls the API directly in some paths; failures surface as `Error: API 422 /api/v1/tickets/.../actions: {"detail":"..."}` — confusing and off-brand.

**In scope**

- **Central error formatter** in ticketing UI: parse `apiFetch` errors, extract FastAPI `detail` (string or object), strip `API \d+ /path` prefix.
- **Known-case mapping** for ticket actions (image required before escalate/resolve, escalation notes required, reassignment notes for OTHER, supervisor-only assign, acknowledge-before-action on escalated ticket, final escalation level, etc.) — use backend `detail` text where already user-friendly; rewrite technical field names (`escalation_notes is required`) to plain language.
- **In-app notice** component (banner or modal in app chrome): amber for **expected validation**; red for unexpected failures; dismissible; no mention of HTTP, endpoints, or JSON.
- **Replace `alert(String(e))`** on desktop and mobile ticket detail for: acknowledge, escalate, resolve, assign, reassignment, uploads, task complete, field report save (align with `fieldVisitSaveErrorMessage` pattern).
- **Client-side gates (desktop parity):** before opening escalation form or resolve sheet, run `hasImageAttachment()` — same copy as server when blocked (avoids round-trip).
- **Desktop escalate flow:** wire **Escalate** button and `#escalate` to **EscalationFormCard** (date, persons, notes) — not bare `performAction(ESCALATE)` without form.

**Out of scope**

- Changing backend validation rules (only optional polish of `detail` strings if still technical).
- Toast library / SSE — single notice state per page is enough for P1.
- Reports/settings pages (unless same `alert` pattern found during pass).

**Locked decisions**


| Topic | Decision |
| ----- | -------- |
| Browser `alert()` | **Do not use** for ticket action errors on `app/tickets/[id]` and `app/m/tickets/[id]`. |
| User-visible text | **Never** show status codes, URL paths, `API`, or raw `{"detail":...}` JSON. |
| Validation vs failure | **Amber** = expected “complete this first”; **red** = could not save / try again. |
| Image gate copy | *"Add at least one photo before escalating. Upload a site photo or ask the complainant to send photos via WhatsApp."* (align mobile + desktop + server). |
| Implementation | `lib/user-messages.ts` + `components/ActionNotice.tsx` (or equivalent); optional `ApiError` from `apiFetch` with `.userMessage` only. |

**Related** TP-11 (image gate, escalation form), TP-12 (supervisor assign messages).

**June5 spec:** [`docs/sprints/June5/03-portal-p1-spec.md`](June5/03-portal-p1-spec.md) § TP-13 · Agent: [`docs/sprints/June5/agents/portal-p1-bugs.md`](agents/portal-p1-bugs.md)

---

### TP-14 — Grievance summary, categories, and officer validation · **P1**

**Feature goal**  
Officers always see **AI summary**, **categories**, and **complainant narrative** on the ticket (including cases filed “as is” before classification finishes). When the complainant did not confirm classification in chatbot, an officer with access to the case **reviews/edits and confirms** categories (and summary per spec) in the portal **before Acknowledge**.

**Why**  
Observed on AWS (`B-GR-20260602-KOJH-5491`): `public.grievances` had summary + categories ~1 minute after `ticketing.tickets` was created with empty cache — portal showed “No summary”. `grievance_sync` only creates tickets and filters `is_temporary = false`, so late LLM results never reach the UI.

**In scope**

- **Data:** Ticket detail and list must show summary/categories even when cache on `ticketing.tickets` is empty — source of truth includes **`public.grievances`** (read via grievance API), **without** requiring `is_temporary = false` for **read** paths.
- **Sync:** Keep ticket cache updated when classification completes (backfill job + forward path on LLM completion / periodic sync).
- **UI — ORIGINAL GRIEVANCE / TP-09 card:** Two distinct panels in one card (not one blended narrative block):
  1. **Original grievance** — read-only box with raw `grievance_description` only.
  2. **Summary** — separate bordered box with LLM/officer summary text, **its own validation badge** (complainant / officer / review required / pending), and an **editable textarea** so officers can fix LLM errors; **Categories** below as a third labeled block (comma-separated edit when required).
- **UI — Officer validation:** When status is `LLM_generated`, `LLM_failed`, or `LLM_skipped`, amber summary badge + **Confirm summary & categories** → `officer_confirmed`. **Blocks Acknowledge** until then. `complainant_confirmed` skips the gate but summary/categories remain **editable** with **Save changes** (same PATCH; sets `officer_confirmed` if officer edits).
- **Submit path (chatbot):** Ensure `dispatch_ticket` sends summary/categories when available at submit (read from DB if session slots empty).
- **Read path:** Grievance fetch for display **must not** filter on `is_temporary` (AWS shows submitted rows can still be `is_temporary = true`).

**Out of scope (initial)**

- Rebuilding the full chatbot complainant-review form inside the portal (use a focused officer review panel, not every chatbot button/slot).

**Locked decisions (2026-06-03)** — full model: [`docs/sprints/June5/04-classification-status-spec.md`](June5/04-classification-status-spec.md)

| Topic | Decision |
| ----- | -------- |
| Field | `public.grievances.grievance_classification_status` (Option B). **Not** `grievance_status` workflow history. |
| Default | `pending` |
| Active codes | `pending`, `LLM_generated`, `LLM_failed`, `LLM_skipped`, `complainant_confirmed`, `officer_confirmed` |
| Skip LLM | `LLM_skipped` replaces `slot_skipped`; **officer must classify** |
| No retry status in DB | Do not store `LLM_error` while Celery retries; final failure → `LLM_failed` |
| Complainant validated | `complainant_confirmed` — green badge; no officer gate |
| Officer required | When `LLM_generated`, `LLM_failed`, or `LLM_skipped` (e.g. on assign / before Acknowledge) → edit + confirm → `officer_confirmed` |
| `is_temporary` | Retired (no read/sync filter) |
| Read model | **Hybrid** detail merge + list cache + forward sync |
| Officer UX | Edit **categories + summary**, then confirm; layout = original (read-only) + summary (editable + status badge) + categories |
| Backfill | One-time AWS SQL for empty ticket cache |

**Related** TP-09, `dispatch_ticket`, `grievance_sync`.

**June5 spec:** [`docs/sprints/June5/03-portal-p1-spec.md`](June5/03-portal-p1-spec.md) § TP-14

---

### TP-15 — Complainant PII: standard visible, SEAH masked, mobile `tel:` · **P1**

**Feature goal**  
Standard GRM officers read complainant **name, phone, email, and address** in the portal without a vault step. SEAH cases **keep** masked contact + audited reveal. On **mobile**, phone is a **`tel:`** link for one-tap calling.

**In scope**

- `GET /api/v1/tickets/{id}/pii`: return decrypted contact for `is_seah = false`; omit contact fields when `is_seah = true` (`pii_masked: true`).
- Desktop **Complainant** card and mobile **Complainant Info** sheet share `ComplainantContactFields`.
- SEAH: amber notice + **Reveal original statement** (mobile sheet closes then opens reveal modal).

**Out of scope**

- Changing vault TTL or reveal reason codes.
- Complainant self-service portal.

**June5 spec:** [`docs/sprints/June5/03-portal-p1-spec.md`](June5/03-portal-p1-spec.md) § TP-15

---

### TP-05 — Report delivery: links first, PDF optional, library · **P1**

**Feature goal**  
Recipients open reports via link; PDF and history remain available.

**Why**  
Links are easier than attachments for many stakeholders.

**In scope**

- Link-first sharing for generated reports.  
Align all the fields between PDF and web - the web comes first  
We should have two different links: one internal displayed to officer and another one for public use and sent by SMS to the complainant.  
Add more details on the report available to officers like Grievance Category, Escalated, Level of resolution (all the info available on the ticket)
- PDF export remains optional.
- Report **library / history** retains past outputs for re-access.

---

### TP-07 — Export all data to Excel (analysis-ready) · **P1**

**Feature goal**  
One reliable full export for offline analysis in Excel.

**Why**  
Users routinely reformat and pivot outside the portal.

**In scope**

- **Export all data to Excel** entry point on reports (or agreed surface).
- Consistent column set, clean values, enough fields for analysis without reconstructing from multiple screens.

**Locked decisions**


| Topic      | Decision                                                                                           |
| ---------- | -------------------------------------------------------------------------------------------------- |
| Data scope | Export respects **current user’s OfficerScope** only (no cross-org “super export” in this ticket). |


---

### TP-08 — Quarterly dashboard clarity · **P1**

**Feature goal**  
Quarterly overview is readable without institutional knowledge.

**Why**  
Labels (e.g. “total base”), colors, and L1–L4 jargon cause misreads.

**In scope**

Rename ambiguous labels - The current naming makes it difficult to understand the differenc between the first two columns


| **Open end 2026-Q2** | **Open 2026-Q2** | **Q2026-Q2 On time** | **Q2026-Q2 Overdue** |
| -------------------- | ---------------- | -------------------- | -------------------- |




- Legends/glossary for L1 / L2 / L3 / L4+, agency, and package. make tooltips available when one hovers over the label
- View toggle: **level detail** vs **total per package** (aggregate packages without level breakdown).

---

## C) Non-product / program (separate tracking)


| ID    | Item                                                                                |
| ----- | ----------------------------------------------------------------------------------- |
| AD-01 | Short user walkthrough videos **after** UI tickets above are stable                 |
| AD-02 | Nepali voice-over: try AI narration; volunteer fallback if quality is poor          |
| AD-03 | Partner feedback session (contractor + consultant); consolidate before wide rollout |


---

## D) Resolved decisions index


| ID            | Decision                                                                                                |
| ------------- | ------------------------------------------------------------------------------------------------------- |
| CB-01 / TP-02 | Medium sample rate; chunk on device if feasible; else **60–90s** per file, multiple voice notes allowed |
| CB-01 / TP-02 | Transcription via **accessible** service API (P2)                                                         |
| TP-01 / TP-02 | P1 = player only; P2 = transcription + manual fallback                                                   |
| TP-11         | Site photo = attachment gate; no `#photo`; complainant photos via WhatsApp only                          |
| TP-12         | Assign = supervisor only; L1 = acknowledge or ask for reassignment + 3 reason codes                      |
| TP-13         | Action errors in-app only; no API jargon; amber validation / red failure                                   |
| CB-03         | **Close session** (standard) vs **Close browser** (SEAH); same actions as today, one button per path    |
| TP-07         | Excel export = **user scope only**                                                                      |


---

## E) Notes for upcoming transcript batches

Merge new extracts as:

- **New ticket candidate**
- **Merge into existing ticket** (update locked decisions if product changes)
- **Discard** (implementation detail or program-only)

---

## F) Cross-ticket dependencies

```text
CB-07 (filed banner) ──► post-submit attachment / CB-04 (both P1)
TP-09 (read before ack) ──► TP-12 (L1 acknowledge path)
TP-10 (call report) ── field-report pattern
TP-11 (photo gate) ──► blocks Close / Escalate
TP-11 (escalate form) ──► replaces #review
TP-12 (reassign reasons) ──► all assign / ask-for-reassignment
TP-13 (friendly errors) ──► TP-11 gates + TP-12 permissions; desktop escalate form parity
TP-01 (player) ──► TP-02 (transcription, P2)
CB-06 / CB-08 / CB-09 ── backlog (dust path chain)
```

---

## Ticket index (active)

| ID | Pri | Title |
|----|-----|--------|
| CB-03 | **P1** | Close / exit consolidation |
| CB-04 | **P1** | File another grievance |
| CB-05 | **P1** | Attachment step copy rewrite |
| CB-07 | **P1** | Post-submit success messages + filed banner |
| CB-01 | — | Hybrid grievance input (text or voice note) |
| CB-06 | — | Location by map pin + fallback |
| CB-08 | — | Photo metadata permission (location + time) |
| CB-09 | — | Dust complaint fast path |
| TP-01 | **P1** | Voice note playback (inline player) |
| TP-02 | **P2** | Voice note transcription + manual fallback |
| TP-05 | **P1** | Report links, PDF, library |
| TP-07 | **P1** | Export all data to Excel |
| TP-08 | **P1** | Quarterly dashboard clarity |
| TP-09 | **P1** | Read full grievance before acknowledge |
| TP-10 | **P1** | Complainant call report |
| TP-11 | **P1** | Simplify commands (field report, site photo gate, escalation) |
| TP-12 | **P1** | Assign vs ask for reassignment |
| TP-13 | **P1** | Officer-friendly validation messages |
| AD-01–03 | — | Training / localization / partner session |


