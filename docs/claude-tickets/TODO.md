# GRM Ticketing — TODO / Backlog

> This file tracks open gaps, pending tasks, and future features.
> Updated alongside `PROGRESS.md`. Read both before picking up work.
> Last reviewed: 2026-05-05

---

## ✅ WEEK 2 — Frontend (complete as of 2026-04-27)

All screens confirmed built and running on port 3001 (`NEXT_PUBLIC_BYPASS_AUTH=true` for local):
- AppShell (sidebar, nav, badge count, SEAH indicator, Cognito + bypass auth)
- Queue page (tabs, summary tiles, ticket rows, SLA countdown, SEAH red border/badge)
- All Tickets page (list + search), Escalated page (focused list)
- Ticket detail (grievance card, workflow stepper, SLA bar, event timeline, complainant PII + phone reveal)
- File attachments (complainant read + officer upload), assign + reassign-to-teammate panels
- Action panel (ACKNOWLEDGE / ESCALATE / RESOLVE / CLOSE / NOTE / GRC_CONVENE / GRC_DECIDE / REPLY)
- Settings page (full admin panel), Badge + SlaCountdown components

---

## 🔴 WEEK 3 — Must fix before demo (May 10)

### ~~1. Auto-assign officer on escalation~~ ✅ DONE (`d4e2f1a`)
**File:** `ticketing/engine/escalation.py` — `escalate_ticket()`  
**Problem:** After escalation, `assigned_to_user_id` stays as the previous officer.
The next-level officer is never assigned automatically — ticket sits in limbo until a
super-admin manually reassigns via `PATCH /tickets/{id}`.  
**Fix:** Call `auto_assign_officer(ticket, db)` inside `escalate_ticket()` immediately
after advancing `current_step_id`. Set `ticket.assigned_to_user_id` from the result.
Also: the unseen notification event at line 130 of `escalation.py` currently fires
`notify_user_id=ticket.assigned_to_user_id` *before* the reassign — move it after
so the notification goes to the new officer, not the old one.  
**Demo impact:** Pre-seeded tickets have hardcoded `assigned_to` so demo is safe.
New tickets created via live API or chatbot webhook will have no assigned officer.

### ~~2. Automatic complainant notification on RESOLVE / ESCALATE~~ ✅ DONE (`d4e2f1a`)
**File:** `ticketing/api/routers/tickets.py` — `perform_action()`  
**Problem:** Action handler commits and returns — no notification fires automatically.
Demo scenario 1 ends with "complainant notified via chatbot" but that requires the
officer to manually hit `POST /reply`. The plumbing exists; it just isn't wired.  
**Fix:** Add `notify_complainant.delay(ticket.ticket_id)` at the end of the `RESOLVE`
and `ESCALATE` branches (after commit). The task is already scaffolded in
`ticketing/tasks/notifications.py`.  
**Demo impact:** Low — presenter manually clicks Reply during demo. Fix before week 3 integration.

### 3. Test public.grievances integration and PII fetching
**What to verify:**
- `ticketing/tasks/grievance_sync.py` — Celery Beat task polls `public.grievances`
  every 2 min. Column names are hardcoded in a raw SQL query. Must be validated against
  the actual schema after the public Alembic migration is finalised.
- `ticketing/clients/grievance_api.py` — `GET /api/grievance/{grievance_id}` PII fetch
  called from the ticket detail view. Test with a real grievance ID against the running
  backend on port 5001. Verify: name, phone, province/district/municipality/ward fields
  all returned and mapped correctly in the ticket detail response.
- `public.complainants` — confirm column names match what `grievance_sync.py` expects
  (location fields: `province`, `district`, `municipality`, `ward`, `village`).
- End-to-end smoke test: submit a grievance via chatbot → confirm ticket auto-created
  in `ticketing.tickets` within 2 min, with correct `grievance_location`, `priority`,
  `grievance_summary`, `session_id`.
**Dependency:** User is currently rewriting `public.*` tables via Alembic migration.
  Do not test until that migration lands and DB is re-seeded.

### ~~4. Wire OfficerScope seed rows so auto-assign works for live API tickets~~ ✅ DONE
`seed_mock_officer_scopes()` in `mock_tickets.py` — already seeded 9 rows, auto-assign works.

### 5. Visual test + polish pass
**What to do:** Open `http://localhost:3001`, click through every screen, verify:
- All 6 demo tickets show in queue with correct status/priority/SLA colours
- Ticket detail for each demo ticket loads correctly
- ACKNOWLEDGE → ESCALATE → RESOLVE flow works end-to-end
- GRC CONVENE → DECIDE flow works (use GRV-2025-001)
- SEAH ticket (GRV-2025-SEAH-001) shows 🔒 badge and red border
- Reports page — currently a stub, decide if a placeholder is enough for demo

### 6. Staging deploy to grm.stage.facets-ai.com
**What:** Docker deploy to staging EC2, Nginx config, SSL.  
**How:** Same EC2 as chatbot, add a new Nginx `location` block for port 3001 (UI)
and 5002 (API). Run `docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d`
on the EC2 after pulling the branch.  
**NEXT_PUBLIC_API_URL** must be set to the public staging URL (not localhost) for the
UI to talk to the API from the browser.  
**Dependency:** Visual test (above) should pass first.

---

## 🟡 POST-DEMO FEATURES (prioritised)

### ~~7. LLM: Multilingual notes + "Findings" summary~~ ✅ DONE (`edfa942`) ⭐ BIG FEATURE
**Rationale:** Field officers (L1/L2, DOR) write notes in Nepali or mixed Nepali-English.
Supervisors and observers (GRC chair, ADB roles) read only English. Without translation
the case timeline is opaque to half the audience. The "Findings" panel gives supervisors
a one-glance digest of a case without reading every raw note.

#### 7a — Per-note translation
- When a `NOTE_ADDED` event is created, fire a Celery task `translate_note.delay(event_id)`.
- Task calls LLM: *"Translate the following to English. If already in English, return as-is.
  Preserve technical/legal terms. Output only the translated text."*
- Store result in `TicketEvent.payload["translation_en"]`.
- In the ticket detail timeline, if `translation_en` exists show it below the original
  with a small `🌐 Translated` chip. Original is always preserved and visible.
- Non-English users see only the original (toggle if needed post-demo).

#### 7b — "Findings" summary panel
- A dedicated **Findings** card on the ticket detail (right column, below complainant card).
- Content: one LLM call over all `NOTE_ADDED` events + key status events (ESCALATED,
  GRC_CONVENED, GRC_DECIDED, RESOLVED) for the ticket.
- Prompt: *"You are a grievance officer. Summarise the following case notes into a brief
  Findings report: key facts, actions taken, outstanding issues, and recommended next step.
  Write in formal English. Max 150 words."*
- Cached in `ticketing.tickets.ai_summary_en` (new column, Alembic migration needed).
- Regenerate button visible to admin/supervisor roles — fires `generate_findings.delay(ticket_id)`.
- Shown to: `grc_chair`, `adb_hq_safeguards`, `adb_hq_exec`, `adb_national_project_director`,
  `super_admin`. Hidden from L1/L2 field officers (they write the notes, don't need the digest).

#### Implementation plan
- **LLM provider confirmed: OpenAI** (`gpt-4` for translation, `gpt-3.5-turbo` for
  classification). Client lives in `backend/services/LLM_services.py`.
  `translate_grievance_to_english_LLM()` already exists — we reuse the same pattern.
  Init: `OpenAI(api_key=os.getenv("OPENAI_API_KEY"))`. Key is already in `env.local`.
- **New file `ticketing/tasks/llm.py`** with two Celery tasks on `grm_ticketing` queue:
  - `translate_note(event_id)` — fetches event note, calls OpenAI `gpt-4`, stores
    result in `TicketEvent.payload["translation_en"]`
  - `generate_findings(ticket_id)` — fetches all NOTE_ADDED + key status events,
    calls OpenAI `gpt-4`, stores result in `Ticket.ai_summary_en`
- **New file `ticketing/clients/llm_client.py`** — thin wrapper around `OpenAI` client
  (same init pattern as `LLM_services.py`). Keeps ticketing independent of backend/
  (DO NOT import from `backend/services/` — reuse the pattern, not the code).
- **DB migration:** Add `ai_summary_en TEXT` + `ai_summary_updated_at TIMESTAMPTZ`
  to `ticketing.tickets`. (`translation_en` goes into existing JSONB payload — no migration.)
- **API:** Add `POST /api/v1/tickets/{id}/findings` (trigger regenerate, admin only).
  `GET /api/v1/tickets/{id}` already returns `ai_summary_en` once added to `TicketDetail`.
- **Frontend:** `FindingsCard` component in ticket detail right column. Translated note
  shown inline in `EventTimeline` when `payload.translation_en` present.

#### 7c — Hook: fire translation automatically on NOTE_ADDED
- In `tickets.py` `perform_action()`, after commit for `NOTE` action:
  `translate_note.delay(event.event_id)`
- Same pattern as `notify_complainant.delay()` already wired for RESOLVE/ESCALATE.

**Dependencies:** `OPENAI_API_KEY` already in `env.local` (used by chatbot). No new
credentials needed.

### 8. User language preference (per organisation)  *(depends on #7)*
**Rationale:** Required to correctly present translated content and future
UI localisation. Officers from DOR likely prefer Nepali; ADB officers prefer English.  
**Scope:**
- Add `preferred_language` column to `ticketing.user_roles` (or a new
  `ticketing.user_preferences` table). Default: `"ne"` for DOR org, `"en"` for ADB.
- Organisation-level default in `ticketing.organizations.default_language` (new column).
  Individual officer preference overrides org default.
- Expose `GET /api/v1/users/me/preferences` and `PATCH` endpoint.
- Frontend: Settings → My Profile → Language (dropdown: English / नेपाली).
- Used by: LLM translation feature (above), future UI i18n.
**Alembic:** One migration — add column to `ticketing.organizations` + new
  `ticketing.user_preferences` table.

### 9. Mobile-first ticket management UI (officer field app)
**Rationale:** Field officers (L1 site focal persons, contractor officers) work primarily
on phones. The full Next.js settings-heavy UI is not suitable for mobile field use.  
**Scope — what's IN:**
- View assigned tickets + SLA countdown
- Acknowledge / add note / escalate / resolve actions
- View case timeline (events + notes)
- Reply to complainant
- Photo/file upload (camera roll)
- SEAH badge (read-only visual, same access control)
- Push notification support (post-proto: Firebase or PWA push)
**Scope — what's OUT (explicitly):**
- No Settings tab (no workflow editor, no user management, no org/location config)
- No Reports tab
- No All Tickets view (officers see only their queue)
- No GRC convene/decide (desktop-only action for GRC chair)
**Stack options (decide before building):**
  - Option A: PWA skin of the existing Next.js app — same repo, responsive breakpoints,
    hide Settings/Reports nav on mobile viewport. Lowest effort.
  - Option B: Separate React Native / Expo app — true native push, camera API, offline.
    Higher effort, separate repo.
  - Option C: Separate Next.js route group `/mobile/*` with a stripped layout.
    Middle ground — same API, different shell.
**Recommendation:** Start with Option A (PWA) — add `mobile:` Tailwind breakpoint
overrides to the existing ticketing-ui, hide desktop-only nav items, add a
`manifest.json` for PWA install. Revisit native if offline or camera is needed.
**Dependencies:** Week 2 desktop UI complete ✅. Consider adding note translation (#7a) to the mobile UI once that feature lands.

---

## 🟠 CHATBOT-SIDE INTEGRATION NOTE — PII scrubbing in grievance intake

> **For whoever works on `backend/actions/` or `rasa_chatbot/` intake flow.**
> This is a ticketing-system dependency — the findings pipeline reads `grievance_summary`
> and officer notes, and those go to OpenAI. We need PII stripped before storage.

### Problem
When a complainant submits a grievance, the free-text narrative often contains PII
(full name, phone number, neighbours' names, contractor names, home address details).
The chatbot LLM call already summarises + categorises the grievance — we need to add
PII scrubbing to that same call so the stored `grievance_summary` is clean.

`ticketing.tickets.grievance_summary` is cached at ticket creation from this field
and flows directly into the AI findings pipeline (OpenAI call). If the summary
contains PII, it leaves the system.

### Fix — extend the existing summarisation prompt
In the LLM call that generates `grievance_summary` (wherever the chatbot assembles
the grievance summary before storing it), add the following instruction:

```
Replace any personal identifiers with role descriptors:
- Person names → "the complainant", "a neighbour", "the contractor", "the officer"
- Phone numbers → [phone redacted]
- Email addresses → [email redacted]
- Specific street addresses → [address redacted]  (keep district/municipality level)
- ID card / passport numbers → [ID redacted]
Keep: location at district/municipality level, dates, nature of the grievance,
project name, road name.
```

### Storage convention (two fields)
- `grievance_summary` (existing) — **scrubbed** summary → safe for AI pipeline, ticketing
- `original_statement` or `raw_narrative` (vault, existing) — original unredacted text
  → only accessible via the reveal session (`POST /tickets/{id}/reveal`)

If the chatbot currently stores only one field, the scrubbed version should replace it
and the raw text should be kept in an encrypted/restricted column.

### Why this boundary matters
The ticketing `context_builder.py` (see `ticketing/engine/context_builder.py`) only
reads `ticket.grievance_summary` — if that field is clean, the entire AI pipeline
downstream is structurally PII-free. Officer notes may also contain incidental PII
(e.g. officer writes "called Ram at 9841…") — the translation + findings prompts
should also include the redaction instruction as a safety net (already done in
`ticketing/clients/llm_client.py` `_FINDINGS_SYSTEM` prompt).

### Officer notes
Officer notes (`NOTE_ADDED` events) can also contain incidental PII. The findings
prompt in `ticketing/clients/llm_client.py` already instructs the LLM never to
include names/phones/addresses in output — this is a safety net, not a substitute
for source-level scrubbing.

---

## 🟡 LLM: Structured context cache + findings pipeline (Layer 1 + 2)

**Implemented:** `ticketing/engine/context_builder.py`, `ticketing/models/ticket_context_cache.py`,
migration `i6j8l0n2p4`, updated `ticketing/clients/llm_client.py` + `ticketing/tasks/llm.py`.

**Layer 1 — `ticketing.ticket_context_cache`**
One row per ticket. Rebuilt whenever an event with `summary_regen_required=True` is committed.
`context_builder.build_and_store()` is the single, auditable place that assembles events into
a PII-clean JSON document. Never includes `created_by_user_id` — only `actor_role`.
`findings_json` stores the structured LLM output alongside the input context.

**Layer 2 — Structured JSON output from LLM**
`llm_client.generate_case_findings(context, is_seah)` now:
- Takes the pre-assembled context dict (not raw text)
- Uses `gpt-4o-mini` for standard tickets, `gpt-4o` for SEAH
- `temperature=0.0` for consistency
- Returns structured JSON: `{summary_en, key_findings[], recommended_action, urgency, languages_detected[]}`
- `Ticket.ai_summary_en` still populated from `summary_en` (frontend backward compat)
- Full structured output stored in `ticket_context_cache.findings_json`
- System prompt explicitly instructs: never include names/phones/addresses in output

---

## 🔵 TECH DEBT (low urgency)

| Item | File | Notes |
|------|------|-------|
| Seed log message still says `PROVINCE_1` | `kl_road_standard.py:319` | Cosmetic — actual stored value is `NP_P1` |
| `_scope_candidates` calls `_location_and_ancestors` twice (branches B + C) | `workflow_engine.py` | Minor perf — combine into one call |
| `OfficerScope` seed creates `UserRole` rows but no `OfficerScope` rows | `mock_tickets.py` | Auto-assign returns `None` for API-created tickets; pre-seeded demo unaffected |
| Cognito user pool not created | `env.local` | `COGNITO_GRM_USER_POOL_ID` empty; all auth stubs until post-proto |
| `grievance_sync.py` hardcoded column list | `tasks/grievance_sync.py` | Will break if public schema column names change — add integration test |

---

*Updated by Claude Code. Stage this file with every relevant commit.*
