# Ticket resolution record and resolved case summary

**Status:** Implemented baseline (June 2026); Summary enhancements and complainant closure page/PDF tracked in this spec.  
**Related:** [04_ticketing_schema.md](04_ticketing_schema.md) (`ticket_events`), [03_ticketing_api_integration.md](03_ticketing_api_integration.md), [CLAUDE.md](../../CLAUDE.md) (PII rules)

This document defines:

1. **Resolution record** — a new officer note type in the case thread (same storage pattern as field reports).
2. **Resolved case summary** — a structured document generated when a ticket is resolved, for supervisors, GRC, ADB, and quarterly reporting.

---

## 1. Background

### 1.1 Where exchanges live today

All thread items (notes, field reports, status pills, tasks, replies) are stored in `**ticketing.ticket_events`** (append-only). There is no separate “messages” table.


| UI item             | `event_type`          | `note`                            | `payload` flags                             |
| ------------------- | --------------------- | --------------------------------- | ------------------------------------------- |
| Internal note       | `NOTE_ADDED`          | text                              | `{ internal: true }`                        |
| Field report        | `NOTE_ADDED`          | formatted visit text              | `{ internal: true, is_field_report: true }` |
| Resolve (today)     | `RESOLVED`            | optional, **not shown in thread** | —                                           |
| Complainant message | `COMPLAINANT_MESSAGE` | text                              | `{ intent, … }`                             |


Field reports use action `FIELD_REPORT` but persist as `**NOTE_ADDED`** so the UI can render a distinct bubble. Resolution should follow the same pattern.

### 1.2 Existing AI findings (different purpose)

On `RESOLVE`, Celery task `**generate_findings**` already runs:

- Input: **PII-clean** `ticket_context_cache.context_json` (from `context_builder.py`).
- Output: `findings_json` + `tickets.ai_summary_en` (short English digest for senior roles).

That output is **not** a formal closure document and **excludes** complainant name/address and project/package context. The **resolved case summary** in §3 is a separate artifact with a fixed section layout and controlled PII inclusion.

### 1.3 LLM service (locked)

The **findings narrative** inside the resolved case summary (`findings_summary.*`) is **always produced by the ticketing LLM service** — the same stack as today:


| Piece         | Location                                                                      |
| ------------- | ----------------------------------------------------------------------------- |
| OpenAI client | `ticketing/clients/llm_client.py` (`_get_client()`, `OPENAI_API_KEY`)         |
| Celery worker | `ticketing/tasks/llm.py`                                                      |
| Async trigger | Queued from `POST …/actions` `RESOLVE` (and manual `POST …/resolved-summary`) |


**New function:** `generate_resolved_case_summary_llm(input: dict, is_seah: bool) -> dict` in `llm_client.py` — structured JSON output via `response_format={"type": "json_object"}`, same model rules as `generate_case_findings`:

- Standard tickets: `gpt-4o-mini`
- SEAH tickets: `gpt-4o`
- `temperature=0`

**Not template-generated:** Project, complainant, complaint, resolution, and workflow blocks are **assembled in Python** (`resolved_summary_builder.py`). Only the **investigation / findings text** is LLM-written. If the LLM call fails after retries, the row is stored with `generation_status: "llm_failed"` and empty digests — officers can retry via `POST …/resolved-summary`; no silent concatenation fallback posing as a summary.

---

## 2. Resolution record (thread note type)

### 2.1 Product rules

- **Who may resolve (Q1-b):** assigned officer, **admin**, or officer whose role matches the current step’s **`supervisor_role`** (even if not assignee).
- Resolve is **blocked** while ticket is `ESCALATED` until the new-level officer **acknowledges** (unchanged).
- `**CLOSE` and `GRC_DECIDE` actions are removed** (v1). The only way to end a case is `**RESOLVE`** with a resolution record. GRC chairs at L3 use **Convene GRC** (`GRC_CONVENE`) then **Resolve** (or **Escalate** to legal / next level) like any assigned officer.
- Officer must choose a **resolution category** and enter **resolution text** (what was decided / done). Both are required.
- The resolution appears in the thread as a **dedicated bubble** (like field reports — not only a grey “Case resolved” pill).
- The **resolution record** in the officer thread stays **internal** (full officer wording). A separate **complainant-facing closure document** (§3.9) is derived at resolve time and shared via link + PDF — plain language, no internal notes or officer roster.

### 2.2 Resolution categories

Stored as `resolution_category` (enum string). UI shows a label; saved text is officer-editable from a default template.


| Code                  | Label                                      | Suggested default wording (EN)                                                                                                                                       |
| --------------------- | ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CLASSIFIED`          | Grievance classified                       | This grievance has been reviewed and classified. No specific remedial action is required beyond continued monitoring under the project GRM procedure.                |
| `DEMAND_REJECTED`     | Complainant demand rejected                | After investigation, the grievance was found not to be substantiated. The complainant’s request is not accepted. The case is closed with this determination.         |
| `ACCEPTED_MONETARY`   | Grievance accepted — monetary compensation | The grievance is substantiated. Remedial action includes monetary compensation as agreed with the complainant / per contract and GRM procedure.                      |
| `ACCEPTED_RELOCATION` | Grievance accepted — relocation            | The grievance is substantiated. Remedial action includes relocation / resettlement support as applicable under project safeguards.                                   |
| `ACCEPTED_OTHER`      | Grievance accepted — other remedy          | The grievance is substantiated. Remedial action has been agreed (other than monetary compensation or relocation). Details are recorded in the resolution text below. |


Nepali UI labels: add via i18n later; v1 English-only in API enum is acceptable.

### 2.3 Storage model (no new table)

**One atomic `RESOLVE` action** writes **two** `ticket_events` rows (same transaction):


| Order | `event_type` | Purpose                             | `note`                                         | `payload`                                                                             |
| ----- | ------------ | ----------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------- |
| 1     | `NOTE_ADDED` | Thread bubble — “resolution record” | Formatted resolution body (see §2.4)           | `{ "internal": true, "is_resolution_record": true, "resolution_category": "<code>" }` |
| 2     | `RESOLVED`   | Status change + system pill         | Optional short line (e.g. category label only) | `{ "resolution_category": "<code>", "resolution_event_id": "<uuid of row 1>" }`       |


Also:

- `tickets.status_code` → `RESOLVED`
- `tickets.updated_by_user_id` → resolving officer
- Existing side effects: complainant notify task, `generate_findings` (§3.4), optional `update_grievance_status` on backend (integration point).

**Why two events:** Matches field-report pattern (`NOTE_ADDED` = rich bubble; status event = pill). Keeps `RESOLVED` in `SYSTEM_EVENT_TYPES` without overloading pill rendering with long text.

### 2.4 Formatted `note` for resolution record

```text
Resolution — <Category label>
Date: <YYYY-MM-DD UTC>

<Officer resolution text>
```

Example:

```text
Resolution — Grievance accepted — monetary compensation
Date: 2026-05-21

Contractor will pay NRs 15,000 for crop damage. Payment scheduled within 14 days. Complainant informed by phone.
```

### 2.5 API contract

**Extend** `TicketActionRequest` (`ticketing/api/schemas/ticket.py`):

```python
resolution_category: Optional[str] = None  # required when action_type == RESOLVE
# note: required when action_type == RESOLVE (min length 12 chars after strip)
```

**Validation on `RESOLVE`:**

- `resolution_category` ∈ enum above.
- `note` length ≥ **12** after strip.
- Reject if ticket already `RESOLVED` or `CLOSED` (no re-resolve — Q2).
- Auto-acknowledge if assignee resolves while `OPEN`/`ESCALATED` (Q4).
- On success: `update_grievance_status` with resolution excerpt (Q6).

**Response:** unchanged `TicketActionResponse`; `event_id` = `RESOLVED` event id (client may refetch ticket for both events).

### 2.6 UI contract

**Desktop** (`/tickets/[id]`): Replace one-click Resolve with **Resolution sheet / modal**:

- Category `<select>` (5 options; changing selection pre-fills textarea with default wording; officer may edit).
- Resolution text `<textarea>` (required).
- Confirm → `performAction({ action_type: "RESOLVE", resolution_category, note })`.

**Mobile** (`/m/tickets/[id]`): Same fields in bottom sheet from ⋮ menu or green resolve CTA.

**Thread rendering** (`NoteBubble`):

- New helper `isResolutionRecordEvent(event)` — `NOTE_ADDED` + `payload.is_resolution_record`.
- Style: distinct from field report (e.g. **green** left border — “Resolution record”) to align with resolved status.
- System pill still shows “Case resolved” from `RESOLVED` event.

**Info menu (mobile):** Optional “Resolution” row when resolved (read-only view of resolution record).

### 2.7 Audit and LLM pipeline

- Resolution record is included in `**context_builder`** timeline like field reports:
  - `payload.is_resolution_record = true`
  - `payload.resolution_category` for LLM context
- `**translate_note`:** run on resolution `NOTE_ADDED` if non-English (same as other notes).
- `**generate_findings`:** unchanged trigger on resolve; findings remain PII-clean supervisor digest.

---

## 3. Resolved case summary (post-resolve document)

### 3.1 Purpose

When a ticket becomes **resolved**, generate a **single structured summary** for:

- Officer / supervisor case file
- GRC / ADB oversight
- Quarterly XLSX export enrichment (future)
- Print/PDF export (future)

This is **not** the same as `ai_summary_en` (2–4 sentences, no PII). It is a **full closure report** with explicit sections.

### 3.2 When it runs


| Trigger   | Behaviour                                                                                                                                         |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Automatic | Celery task `**generate_resolved_case_summary(ticket_id)`** queued immediately after successful `RESOLVE` commit (alongside `generate_findings`). |
| Manual    | `POST /api/v1/tickets/{ticket_id}/resolved-summary` — same roles as findings regeneration (§3.7).                                                 |


Idempotent: if `ticket_resolved_summaries` row exists and `source_resolution_event_id` matches latest resolution record, skip unless `force=true`.

### 3.3 Output storage (PII exception)

**New table** `ticketing.ticket_resolved_summaries` (one row per ticket; created on first successful resolve):

```sql
CREATE TABLE ticketing.ticket_resolved_summaries (
    ticket_id                   VARCHAR(36) PRIMARY KEY
        REFERENCES ticketing.tickets(ticket_id) ON DELETE CASCADE,
    grievance_id                VARCHAR(64) NOT NULL,
    resolved_at                 TIMESTAMPTZ NOT NULL,
    resolved_by_user_id         VARCHAR(128),
    source_resolution_event_id  VARCHAR(36) NOT NULL,  -- NOTE_ADDED is_resolution_record
    summary_json                JSONB NOT NULL,         -- schema §3.5
    summary_text_en             TEXT,                   -- optional flat narrative for export
    generated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    generation_model            VARCHAR(64) NOT NULL,   -- e.g. gpt-4o-mini | gpt-4o
    generation_status           VARCHAR(32) NOT NULL DEFAULT 'pending',
        -- pending | complete | llm_failed
    token_estimate              INTEGER,
    -- Complainant-facing (§3.9)
    summary_public_json         JSONB,              -- sanitized closure view for static page + PDF
    summary_text_primary        TEXT,               -- flat narrative in grievance language (ne | en)
    closure_public_token        VARCHAR(64) UNIQUE, -- opaque token for unauthenticated page/PDF
    closure_public_url          TEXT                -- cached full URL sent to complainant (optional)
);
```

**PII rationale (CLAUDE.md):** Complainant name, phone, and full address **must not** live in `ticket_events` or `tickets` cached fields. They **may** appear in this **officer-only** closure table, populated once at resolve from `**GET /api/grievance/{id}`** via existing broker (`get_grievance_detail` / reveal flow). Access: same roles as reveal + supervisors (`grc_chair`, `adb_*`, `super_admin`, `local_admin`, assigned officer).

### 3.4 Section layout (`summary_json` schema)

```json
{
  "version": 1,
  "generated_at": "ISO-8601",
  "project": {
    "project_id": "uuid",
    "project_code": "KL_ROAD",
    "project_name": "Kakarbhitta–Laukahi Road",
    "package_id": "uuid | null",
    "package_code": "SHEP/OCB/KL/01 | null",
    "package_name": "Lot 1 … | null",
    "organization_id": "DOR",
    "location_code": "P1_MOR",
    "location_display": "Province 1 — Morang (display chain)"
  },
  "officers_involved": [
    {
      "user_id": "email-or-sub",
      "display_name": "Officer Name",
      "role_key": "site_safeguards_focal_person",
      "participation": "assigned | acknowledged | noted | escalated | resolved | informed | observer"
    }
  ],
  "complainant": {
    "complainant_id": "string",
    "name": "full name",
    "phone": "string | null",
    "email": "string | null",
    "address_line": "street / tole",
    "village": "string | null",
    "ward": "string | null",
    "municipality": "string | null",
    "district": "string | null",
    "province": "string | null",
    "address_full": "single formatted line for reports"
  },
  "complaint": {
    "filed_at": "ISO-8601 (ticket.created_at or grievance created)",
    "grievance_id": "GRV-…",
    "categories": "cached categories string",
    "original_complaint": "grievance_description (decrypted from backend)",
    "original_summary": "tickets.grievance_summary (non-PII cache)"
  },
  "resolution": {
    "resolved_at": "ISO-8601",
    "resolved_by_user_id": "string",
    "resolved_by_display_name": "string",
    "category": "ACCEPTED_MONETARY",
    "category_label": "Grievance accepted — monetary compensation",
    "text": "officer resolution text (from resolution record note)"
  },
  "findings_summary": {
    "field_reports_count": 3,
    "field_reports_digest_en": "<LLM — summary of all is_field_report notes>",
    "other_notes_digest_en": "<LLM — summary of other internal NOTE_ADDED>",
    "combined_digest_en": "<LLM — 2–6 paragraph impartial findings narrative>",
    "ai_summary_en": "copy of tickets.ai_summary_en if generate_findings finished first; else null"
  },
  "llm": {
    "model": "gpt-4o-mini",
    "generated_at": "ISO-8601",
    "input_token_estimate": 1200
  },
  "workflow": {
    "final_status": "RESOLVED",
    "levels_reached": ["L1 Site", "L2 PD/PIU"],
    "sla_breached": false,
    "is_seah": false
  }
}
```

### 3.5 Data sources per section


| Section                                | Source                                                                                                                                                                                                                        |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Project**                            | `ticketing.tickets` + join `ticketing.projects`, `ticketing.project_packages` on `package_id`; location labels from `ticketing.locations` or `LOCATION_CODES` resolver                                                        |
| **Package**                            | `tickets.package_id` → `project_packages`                                                                                                                                                                                     |
| **Officers involved**                  | Distinct `created_by_user_id` + `actor_role` from `ticket_events`; plus current/former `assigned_to_user_id`; `ticket_viewers`; map `user_id` → display name from `ticketing.user_roles` / roster API                         |
| **Complainant**                        | **Backend** `GET /api/grievance/{grievance_id}` at generation time (decrypted fields: name, phone, email, address, village, ward, municipality, district, province). Build `address_full` as comma-separated non-empty parts. |
| **Complaint — date**                   | `tickets.created_at` (or grievance `created_at` if exposed by API)                                                                                                                                                            |
| **Complaint — original**               | `grievance_description` from backend (PII); fallback `grievance_summary` cache only if backend down                                                                                                                           |
| **Resolution**                         | Latest `NOTE_ADDED` where `is_resolution_record`; category from `payload.resolution_category`                                                                                                                                 |
| **Findings summary**                   | **LLM only** — see §3.6; input = field reports + other notes + resolution text + original complaint excerpt                                                                                                                   |
| **Project / complainant / resolution** | Python assembly — **not** passed to LLM for invention; LLM receives them as read-only context                                                                                                                                 |


### 3.6 Generation pipeline (LLM service)

```
RESOLVE committed
    ├─► generate_findings(ticket_id)                    [existing — PII-clean, llm_client.generate_case_findings]
    └─► generate_resolved_case_summary(ticket_id)       [new — ticketing/tasks/llm.py]

generate_resolved_case_summary (Celery):
  1. resolved_summary_builder.assemble(ticket_id, db) → dict
       - Non-LLM sections: project, package, officers, complainant (grievance API),
         complaint, resolution, workflow
       - LLM input bundle: field_report_notes[], other_notes[], resolution_text,
         original_complaint, optional findings_json from ticket_context_cache
  2. llm_client.generate_resolved_case_summary_llm(bundle, is_seah=ticket.is_seah)
       → { field_reports_digest_en, other_notes_digest_en, combined_digest_en }
  3. Merge LLM output into summary_json.findings_summary + summary_json.llm
  4. UPSERT ticketing.ticket_resolved_summaries
       generation_status = complete | llm_failed
       generation_model = model id used
  5. summary_text_en = optional Jinja/plain template of full summary_json (export only;
       not a substitute for LLM digests)
```

#### 3.6.1 LLM input bundle (user message JSON)

Sent as compact JSON to OpenAI (same pattern as `generate_case_findings`):

```json
{
  "case_ref": { "grievance_id": "…", "is_seah": false },
  "original_complaint": "…",
  "resolution": { "category": "ACCEPTED_MONETARY", "text": "…" },
  "field_reports": [{ "at": "…", "by_role": "…", "text": "…" }],
  "other_officer_notes": [{ "at": "…", "by_role": "…", "text": "…" }],
  "prior_ai_findings": { "summary_en": "…", "key_findings": [] }
}
```

`prior_ai_findings` is included when `generate_findings` has already written `ticket_context_cache.findings_json` (task may run in parallel — summary task may briefly wait or regenerate without it).

#### 3.6.2 LLM output schema (system prompt)

`generate_resolved_case_summary_llm` returns **only**:

```json
{
  "field_reports_digest_en": "<1–3 paragraphs>",
  "other_notes_digest_en": "<1–2 paragraphs>",
  "combined_digest_en": "<2–6 paragraphs — full findings narrative for closure report>"
}
```

**System prompt rules (locked):**

- Write in plain English, past tense, impartial GRM analyst tone (ADB Nepal road projects).
- Base every sentence on `field_reports`, `other_officer_notes`, `original_complaint`, and `resolution` — **never invent** visits, payments, or outcomes not in the input.
- `combined_digest_en` must synthesise investigation chronology and evidence; it must **not** repeat the resolution decision verbatim (that lives in `resolution.text`).
- May reference the complainant as “the complainant”; may use municipality/district from input — do not add phone/email.
- If field reports conflict with earlier notes, state the discrepancy.
- If input is empty, return short factual sentence: insufficient officer documentation to summarise findings.

**Implementation:** `response_format={"type": "json_object"}`, `max_tokens` ≈ 1200, `temperature=0`, retries via Celery (`max_retries=3`).

#### 3.6.3 Failure behaviour


| Condition                               | Behaviour                                                                                                     |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `OPENAI_API_KEY` missing / client error | `generation_status=llm_failed`; `findings_summary` digests null; UI shows “Summary generation failed — Retry” |
| Invalid JSON from model                 | Retry task; then `llm_failed`                                                                                 |
| Grievance API down                      | Non-LLM sections partial; LLM still runs on notes; complainant block flagged `_backend_unavailable`           |


Officers always see **structured sections** (project, complaint, resolution) even when LLM fails; only findings paragraphs are missing until retry succeeds.

### 3.7 API and UI — officer read path


| Method | Path                                           | Description                                                                                                                                                                            |
| ------ | ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/api/v1/tickets/{ticket_id}/resolved-summary` | Full `summary_json` + metadata. Officer JWT. PII masked per Q7/Q8.                                                                                                                      |
| `POST` | `/api/v1/tickets/{ticket_id}/resolved-summary` | Queue regeneration (202). Supervisor roles.                                                                                                                                            |


**Officer UI:**

- Link to full closure view (same layout as public page but includes officer-only sections when authenticated).
- Mobile ⋮: **Resolution** (thread) + **Case summary** (closure page).
- Loading state while Celery runs.

### 3.9 Complainant-facing static page + PDF (locked)

**Purpose:** After resolve, the complainant gets a **simple static web page** (no login) to read the outcome and **download a PDF** — same content, print-ready.

This is the primary deliverable for Q11 (not officer-only).

#### 3.9.1 What the complainant sees

`summary_public_json` — subset of officer summary, **no internal data**:


| Section | Included | Excluded |
| ------- | -------- | -------- |
| Header | Project name, package/road label, grievance reference, resolved date | Internal org codes |
| Complainant | Their own name + address (already theirs) | Other people’s PII |
| Complaint | Filed date, original complaint text (their language) | AI `ai_summary_en`, internal categories jargon |
| Outcome | Resolution category label (plain language), **resolution text for complainant** | Officer roster, field-report digests, internal notes |
| Findings (optional) | Short **public findings** paragraph in grievance language (LLM) — high-level only | `field_reports_digest`, officer names, legal speculation |

**SEAH tickets:** Public page is still issued to the complainant (they filed it) but **public findings** must be minimal and non-identifying (no third-party names, no investigation tactics). Officer full summary remains restricted.

#### 3.9.2 LLM: complainant narrative

Extend `generate_resolved_case_summary_llm` output with:

```json
{
  "field_reports_digest_en": "...",
  "other_notes_digest_en": "...",
  "combined_digest_en": "...",
  "resolution_text_public": "<plain-language outcome for complainant, grievance language>",
  "findings_summary_public": "<1–2 paragraphs max, grievance language, no officer names>"
}
```

`resolution_text_public` may start from officer `resolution.text` but LLM rewrites for clarity if needed. Store language code on row: `primary_language` (`ne` | `en`).

#### 3.9.3 Access — token URL (no Cognito)

| Item | Spec |
| ---- | ---- |
| Token | `closure_public_token` — UUID4, stored on `ticket_resolved_summaries`, regenerated if summary regenerated |
| Public URL | `{PUBLIC_BASE_URL}/closure/{token}` e.g. `https://nepal-gms-chatbot.facets-ai.com/closure/a1b2c3…` |
| Env | `TICKETING_PUBLIC_BASE_URL` or reuse chatbot public URL from project settings |
| Auth | **None** — possession of URL = access (same pattern as opaque download links). Optional future: grievance ref + last-4 phone OTP |
| Expiry | No expiry v1 (token valid while case closed). Optional `expires_at` post-v1 |

**Distribution:**

1. **Chatbot / orchestrator** — include link in resolved message (`POST /message` body).
2. **SMS fallback** — short message + URL when session expired (Messaging API).
3. Officer can copy link from ticket UI (“Complainant closure link”).

Update Q5: generic notify text **includes closure URL** once summary generation completes (async — send follow-up message if summary finishes after first notify, or delay notify until summary ready ≤60s).

#### 3.9.4 Static web page (Next.js)

| Route | Audience | Auth |
| ----- | -------- | ---- |
| `/closure/[token]` | Complainant (and anyone with link) | Public — outside `AppShell` / Cognito |
| `/tickets/[id]/closure` | Officer preview | JWT |
| `/m/tickets/[id]/closure` | Officer mobile preview | JWT |

**Page UX:**

- Mobile-first, large type, Nepali + English UI chrome based on `primary_language`.
- Sections: reference number, project, your complaint, outcome, findings summary.
- Prominent **“Download PDF”** button (primary CTA).
- Secondary: “Print” (`window.print()` with `@media print` CSS).
- Footer: GRM / project branding, generation date.
- `noindex` robots — not for SEO; link-only discovery.

#### 3.9.5 PDF download

| Approach | v1 choice |
| -------- | --------- |
| **Server PDF** | **Yes** — `GET /api/v1/public/closure/{token}/pdf` returns `application/pdf` attachment `GRM-closure-{grievance_id}.pdf` |
| Generator | Python **`reportlab`** or **`weasyprint`** (HTML → PDF) in ticketing API — add to `requirements.grm.txt` |
| Content | Same data as `summary_public_json` + `summary_text_primary` — single layout template shared with static page |
| Client fallback | If PDF generation fails, page shows “Download unavailable — use Print to save as PDF” |

Officer authenticated route: `GET /api/v1/tickets/{ticket_id}/closure.pdf` (full or public version — default **public** version for consistency with what complainant receives).

#### 3.9.6 Public API


| Method | Path | Auth | Description |
| ------ | ---- | ---- | ----------- |
| `GET` | `/api/v1/public/closure/{token}` | None | Returns `summary_public_json`, `primary_language`, `generated_at`, `grievance_id` (reference only). 404 if invalid token or summary not ready. |
| `GET` | `/api/v1/public/closure/{token}/pdf` | None | PDF bytes. 503 if `generation_status != complete`. |

Rate-limit by IP (proto: nginx or middleware) — post-v1.

#### 3.9.7 Security

- Token is unguessable (128-bit+ UUID).
- Public JSON must **never** include: officer `user_id`s, internal notes, full field reports, `findings_summary.other_notes_digest_en`, SEAH-sensitive third-party details.
- Do not expose `ticket_id` in public URL (use token only).
- Audit log optional: `CLOSURE_PAGE_VIEWED` — post-v1.

### 3.8 Relationship to quarterly reports

[Reports spec in CLAUDE.md](00_ticketing_decisions.md) lists XLSX columns. Add optional columns (future):

- `Resolution category`
- `Resolution text` (excerpt)
- `Findings summary` (excerpt from `combined_digest_en`)

Implementation can read from `ticket_resolved_summaries` without re-calling LLM.

---

## 4. Implementation scope (single release)

Ship **in one go** (owner note: not phased A→D):

- Resolution form + API (dual events, categories, min **12** chars)
- `ticket_resolved_summaries` + LLM summary (30s wait for `generate_findings`)
- **Complainant static closure page** `/closure/{token}` + **Download PDF** (§3.9)
- Officer preview routes + mobile ⋮ links + quarterly XLSX columns
- Narrative in **grievance language** when Nepali (see §5.2)
- `reportlab` or `weasyprint` in `requirements.grm.txt` for PDF


---

## 5. Architecture (locked)

| Topic | Decision |
| ----- | -------- |
| End-of-case actions | **`RESOLVE` only** — `CLOSE` and `GRC_DECIDE` removed |
| GRC L3 | **Convene** then **Resolve** or **Escalate** (legal = L4 via Escalate) |
| Resolution storage | `NOTE_ADDED` + `is_resolution_record`, then `RESOLVED` pill |
| Findings in closure doc | **LLM** (`generate_resolved_case_summary_llm`) |

---

## 5.2 Product decisions (answered)

Implementation follows this table. Original Q&A kept below for audit.

| # | Answer | Implementation |
|---|--------|----------------|
| Q1 | **b** | Assignee + admin + user with current step **`supervisor_role`** may `RESOLVE` |
| Q2 | **no** | Block second `RESOLVE`; resolution immutable |
| Q3 | **12** | Min chars on resolution `note` |
| Q4 | **yes** | Auto-acknowledge before resolve |
| Q5 | **a** + link | Generic resolved message **includes closure page URL** when summary is ready (see §3.9.3) |
| Q6 | **a** | `POST /api/grievance/{id}/status` + resolution excerpt |
| Q7 | **a** | Full PII in summary for assignee + supervisor/reveal roles; masked for others |
| Q8 | **yes** | Informed + `informed_pii_access` → full summary PII |
| Q9 | **30s** | Summary Celery waits up to 30s for `findings_json` |
| Q10 | **a** | One release (all features) |
| Q11 | **Complainant static page + PDF** | Public `/closure/{token}` (no login) + **Download PDF**; officer preview at `/tickets/[id]/closure`; link in SMS/chatbot on resolve |
| Q12 | **ok** | Mobile ⋮ **Resolution** row when resolved |
| Q13–14 | **Grievance language** | Flat export text in Nepali when grievance is Nepali; EN findings digests + `summary_text_en`; add `summary_text_ne` or `summary_text_primary` as needed |
| Q15 | **All at once** | Quarterly XLSX: resolution category, text excerpt, findings excerpt |
| Q16 | **Category on pill** | “Case resolved — {category label}” |
| Q17 | **ok** | Green resolution bubble |
| Q18 | **ok** | Legal via **Escalate** only |

**Owner note:** everything in one go — not 4 phases.

---

## 5.3 Open questions — answers (archive)


| #       | Topic                    | Question                                                                                                                                                                                                                                                                                                       | Answer                                 |
| ------- | ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| **Q1**  | Who may resolve          | Who can perform `RESOLVE`? **(a)** Assigned officer + admin only (current). **(b)** Also supervisor roles at the ticket’s level without being assignee. **(c)** Any officer whose role matches the current workflow step (from step config).                                                                   | b                                      |
| **Q2**  | Re-resolve               | After a ticket is `RESOLVED`, can officers submit a **second** resolution (supersede), or is resolution **immutable** (changes only via new internal notes / future “reopen” workflow)?                                                                                                                        | no                                     |
| **Q3**  | Minimum text             | Minimum length for resolution `note` after strip? (Spec draft: **20** characters.)                                                                                                                                                                                                                             | 12                                     |
| **Q4**  | Auto-acknowledge         | On resolve, should the assigned officer be **auto-acknowledged** if still `OPEN`/`ESCALATED` (same as field report / note)?                                                                                                                                                                                    | yes                                    |
| **Q5**  | Complainant notification | On resolve, complainant message: **(a)** keep today’s generic chatbot/SMS text for all categories. **(b)** Per-category templates (which categories get which text?). **(c)** No outbound message in v1.                                                                                                       | a                                      |
| **Q6**  | Grievance backend sync   | On resolve, call `**POST /api/grievance/{id}/status`** on the chatbot backend with status + resolution excerpt? **(a)** Yes, v1. **(b)** Defer. **(c)** Yes, but status only (no resolution text).                                                                                                             | a                                      |
| **Q7**  | PII in closure summary   | Who may see **full** complainant block in `GET …/resolved-summary` (name, phone, full address)? **(a)** Assigned officer + same roles as PII reveal / supervisors (`grc_chair`, `adb_*`, `super_admin`, `local_admin`). **(b)** Assigned only. **(c)** Everyone with ticket access (masked phone like `/pii`). | a                                      |
| **Q8**  | Informed tier            | May **Informed** viewers (not Observer) read the resolved summary if `informed_pii_access` is true on the workflow step?                                                                                                                                                                                       | yes                                    |
| **Q9**  | LLM task order           | `generate_findings` and `generate_resolved_case_summary` run in parallel. Should summary task **wait** (e.g. 30s) for `findings_json` to include `prior_ai_findings`? **(a)** Wait up to N seconds. **(b)** Never wait; optional field may be null.                                                            | a - 30s                                |
| **Q10** | Implementation batch     | Ship in one release: **(a)** A+B+C (resolution form + DB + LLM summary + read UI). **(b)** A first, then B+C. **(c)** A+B only (no read UI until later).                                                                                                                                                       | a                                      |
| **Q11** | Resolved summary UI (v1) | Where should officers read the closure document first? **(a)** Desktop sidebar panel. **(b)** Mobile/desktop info menu only. **(c)** Both. **(d)** API only until PDF phase.                                                                                                                                   | we can generate a static web page?     |
| **Q12** | Mobile info menu         | Show read-only **“Resolution”** row in ⋮ menu when ticket is resolved (links to resolution bubble / text)?                                                                                                                                                                                                     | ok                                     |
| **Q13** | `summary_text_en`        | Generate a single flat `**summary_text_en`** narrative from `summary_json` in v1 (for copy/export), or JSON-only until phase D (PDF)?                                                                                                                                                                          | language depends of grievance language |
| **Q14** | Nepali                   | Need `**summary_text_ne`** or Nepali UI for resolution categories in v1?                                                                                                                                                                                                                                       | needed if nepali is the language       |
| **Q15** | Quarterly XLSX           | Include resolution category + findings excerpt in quarterly export in **same release** as B, or phase D only?                                                                                                                                                                                                  | we will do all at once                 |
| **Q16** | System pill label        | Should the `RESOLVED` system pill show **category** (e.g. “Case resolved — monetary compensation”) or stay generic **“Case resolved”**?                                                                                                                                                                        | Case resolved + category               |
| **Q17** | Bubble colour            | Resolution thread bubble: **green** border (spec draft) vs another colour to distinguish from complainant (emerald) and field report (amber)?                                                                                                                                                                  | ok                                     |
| **Q18** | Legal escalation         | GRC / L3 “escalate to legal” is now only `**ESCALATE`** (no `GRC_DECIDE`). Confirm workflow has a legal step and officers know to use Escalate after convening?                                                                                                                                                | ok                                     |


---

## 6. Files to touch (implementation checklist)


| Area             | Files                                                                    |
| ---------------- | ------------------------------------------------------------------------ |
| Spec             | this document                                                            |
| Schema migration | `ticketing/migrations/versions/…_ticket_resolved_summaries.py`           |
| Models           | `ticketing/models/ticket_resolved_summary.py`                            |
| Actions          | `ticketing/api/routers/tickets.py` (`RESOLVE` branch)                    |
| Schemas          | `ticketing/api/schemas/ticket.py`                                        |
| Summary builder  | `ticketing/services/resolved_summary_builder.py`                         |
| Tasks            | `ticketing/tasks/llm.py` (`generate_resolved_case_summary` Celery task)  |
| LLM              | `ticketing/clients/llm_client.py` (`generate_resolved_case_summary_llm`) |
| Context          | `ticketing/engine/context_builder.py` (flag resolution notes)            |
| UI lib           | `channels/ticketing-ui/lib/resolution.ts`                                |
| UI thread        | `NoteBubble.tsx`, ticket pages desktop + mobile                          |
| Public closure   | `app/closure/[token]/page.tsx` (no auth)                                 |
| Officer closure  | `app/tickets/[id]/closure/page.tsx`, `app/m/tickets/[id]/closure/page.tsx` |
| Public API       | `ticketing/api/routers/public_closure.py`                                |
| PDF service      | `ticketing/services/closure_pdf.py`                                      |
| Reports          | `ticketing/api/routers/reports.py`                                       |
| Deps             | `requirements.grm.txt` — `reportlab` or `weasyprint`                       |
| API client       | `channels/ticketing-ui/lib/api.ts`                                       |


---

## 7. References

- Field report pattern: `FIELD_REPORT` → `NOTE_ADDED` + `is_field_report` — `ticketing/api/routers/tickets.py`
- Event model: `ticketing/models/ticket.py` (`TicketEvent`)
- PII broker: `GET /api/v1/tickets/{id}/pii` — `ticketing/api/routers/tickets.py`
- Existing findings: `generate_findings` / `generate_case_findings` — `ticketing/tasks/llm.py`, `ticketing/clients/llm_client.py`
- LLM config: `OPENAI_API_KEY` in `env.local` / `ticketing/config/settings.py`

