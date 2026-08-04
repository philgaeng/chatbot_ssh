# GRM Ticketing — TODO / Backlog

> This file tracks open gaps, pending tasks, and future features.
> Updated alongside `PROGRESS.md`. Read both before picking up work.
> Last reviewed: 2026-07-04 — moved from `docs/sprints/claude-tickets/` to `docs/`; obsolete Cognito rows removed (auth is Keycloak as-built). Entry dates below reflect when items were logged.

---

## 🟠 Sensitive workflows — access slice SHIPPED 2026-08-02; rename outstanding (`DECISION-sensitive-workflows.md`)

SEAH stops being a `workflow_type` track and becomes **an ordinary optional workflow with `is_sensitive`**. Specs updated (09/11/12/13, ui/04, ui/06).

**✅ Built (660 passed, 5 skipped):** case access is **cast-only** — `can_see_seah_extended()` lost its
`super_admin`, `adb_hq_exec` and `workflow_track=='seah'` branches; the configure side moved to a new
`can_configure_sensitive_workflows()` so admins still author/bind sensitive workflows while seeing no
case. Both PII disclosure endpoints gate on cast membership — **this closed a real hole**: the reveal
had no policy check at all (`clients/grievance_api.py` is a proto fallback that always returns
`granted: true`; the backend's `POST /api/grievance/{id}/reveal` was never built), so any admin who
could see a sensitive case could reveal its PII. Also: sensitive-as-default rejected (422), go-live A2
deleted, portal takes the server's answer instead of deriving access from role keys. Pinned by
`tests/ticketing/test_sensitive_workflow_access.py`.

**Outstanding** (DECISION §7): the **rename** (`workflow_type`/`is_seah`/`workflow_track` →
`is_sensitive` + a configure capability, with migration), `include_seah` → `include_sensitive` in
reports, `archiving_policy` + `tasks/notifications` track keys, retiring the `SEAH_ROLES` fast-path,
the **Sensitive** checkbox in the workflow editor (mocked in ui/06, not built), the real backend
reveal-policy endpoint, and docs/seah/.

---

## Grievance-workflows screen follow-ups (2026-08-02, `followups/workflow-stream-vocabulary-and-intake-route-labels.md`)

- **[Copy] `INTAKE_ROUTE_CATALOG` labels carry jargon.** "File a grievance (safeguards GRM)" /
  "Report a road hazard (fast path)" surface in the project editor's **Chatbot menu** picker, so
  they are governed by [ui/05](ticketing_system/ui/05_ui_copy_style.md). Rename to plain wording —
  ideally mirroring the chatbot's own `story_main` menu text. (`ticketing/constants/workflow_routing.py`)
- ~~**[Go-live] Delete the "Classification coverage" check.**~~ ✅ **done 2026-08-02** — check and
  `workflow_routing.uncovered_classifications()` removed; the `A4` ID collision with doc 13 §7 is
  gone. Go-live copy de-jargoned in the same pass (no "binding"/"catch-all"/"actors"/`L1`; the
  panel says "Accepting grievances", not "Tickets OK").
- ~~**[Go-live] Binary severity is spec-only.**~~ ✅ **done 2026-08-04** — A1 (default workflow), D1
  (locations), E1 (name + code) and C4 (sensitive staffing) promoted to blockers; everything else is
  `severity="info"` and never blocks. **Behaviour change:** a project with no default workflow or no
  linked locations can no longer be activated. Projects already active stay active until deactivated.

---

## Cast-model follow-ups (2026-07-23, `DESIGN-cast-model-and-package-staffing.md`)

- **[Participants DECISION — DECIDED 2026-07-30: keep (B)] Actor-role catalog is deprecated back-compat, not dropped.**
  New model (`implementing_agency_org_id` + `project_donors` + the staffing go-live gate) is primary; the legacy
  tables/service are kept as a dormant fallback (still seeded on create). **No cleanup planned.** Docs 02/03/04/10/11/13/14
  reflect "deprecated, present". (`sprints/2026-07_org_chart_positions/followups/actor-role-catalog-not-dropped.md`)
- **[Phase 2] Owning-level re-scope has no UI.** Position owner is server-stamped; the modal
  dropped the picker. `PATCH /position-types/{id}` still accepts `owner_organization_id`, so
  re-homing a title is API-only. Add an "advanced" edit affordance if needed.
  (`followups/phase2-positions-followups.md`)
- **[Phase 2] `assign_officer_position` default-role fallback.** Assign requires an explicit
  `role_key` for null-default positions; legacy non-null defaults still pre-fill. Drop the
  `or pt.default_role_key` fallback once the seed drops position defaults (Phase 3/§8).
- **[Phase 3e] Cast matrix screen — BUILT** (`ProjectCastSection`, in Projects & packages).
  Remaining §3.6 *niceties*: Copy-from-package, explicit per-cell Override/revert, inline
  "Add officer" (invite + position) in the picker, contractor-org picker (today org = implementing
  agency). (`followups/phase3-cast-ui-followup.md`)
- **[Phase 3e] Seed refresh (§8) optional.** Demo seeds still use named role keys (coexist with
  synthetic keys, §6) — refreshing to the staffing model is fidelity, not correctness.
- **[Phase 5 remainder] GRC per-step `is_grc` flag** — retire the `grc_committee` archetype;
  gate `GRC_CONVENE` on the flag; derive GRC members from the step cast. Working today via the
  role model; deferred (cross-file test + seed coupling). (`followups/phase5-remainder-followup.md`)
- **[Phase 5 remainder] Remove archetype apparatus + user-facing `/roles` CRUD** — already dead at
  runtime (Phase 1); coupled to invariant `test_authz_matrix_extended` + `test_roles_crud`, so
  remove endpoints **with** those test rewrites. Keep `GET /roles`. Completes "stop writing
  per-role permissions". (`followups/phase5-remainder-followup.md`)
- **[Phase 1] Per-role permission writes retire in Phase 5.** Tier is the source of truth now;
  `create_role`/`update_role` still write `roles.permissions` until the archetype apparatus is
  removed (Phase 5). (`followups/tier-permissions-reconciliation.md`)
- **[Perf §6/§3.6] Supervisor-tab hot path — verified, no work needed.** Supervisor membership is
  already materialized at write-time into `ticket_viewers` (`escalation._apply_step_tier_roles`);
  no MV/tier column. (`followups/phase5-remainder-followup.md`)

---

## ✅ Admin-scope org-staffing (2026-07-25, `followups/admin-scope-org-staffing-gaps-followup.md`)

> Surfaced auditing the Admin-access org-scoping change (org_admin now scoped to an `organization_id`
> node, not a country code). All three audited capabilities (child-org create / add donor officer /
> create contractor) already worked; the two adjacent guard gaps below were **logged as debt
> 2026-07-24, then built 2026-07-25** (migration `h4j6l8n0`; ticketing suite 649 passed / 0 failed).

- **✅ [Gap A] Contractor authorship.** `owner_organization_id` on `ticketing.organizations` (self-FK;
  `parent`/`children` relationships now pin `foreign_keys`). `create_organization` stamps the
  creator's org node on a non-super org_admin's `third_party`; `can_admin_org_or_owned` (super OR
  `owner ∈ caller subtree`) gates `update`/`delete` → maintainable by creator + ancestor-org admins.
- **✅ [Gap B] Project-staffing scope.** `require_org_admin_project_scope` constrains the org_admin
  tier to projects its subtree manages (project IA ∈ subtree; unanchored → open); actor orgs stay
  unconstrained; other tiers unchanged. Wired into `staff_cast_slot`, `add/update/remove_project_organization`,
  `add/remove_package_organization`, and `_require_project_scope` (donors).

---

## ✅ WEEK 2 — Frontend (complete as of 2026-04-27)

All screens confirmed built and running on port 3001 (`NEXT_PUBLIC_BYPASS_AUTH=true` for local):
- AppShell (sidebar, nav, badge count, SEAH indicator, OIDC + bypass auth — Keycloak as-built)
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
- ~~`ticketing/tasks/grievance_sync.py` — Celery Beat task polls `public.grievances`
  every 2 min. Column names are hardcoded in a raw SQL query. Must be validated against
  the actual schema after the public Alembic migration is finalised.~~
  ✅ **Validated automatically since T3-07 (2026-07-15):** the column list is declared in
  `tests/ticketing/test_boundary_policy.py`'s `CONTRACT` and gated against the CL-01
  `public.*` baseline in both directions. No manual verification needed.
- `ticketing/clients/grievance_api.py` — `GET /api/grievance/{grievance_id}` PII fetch
  called from the ticket detail view. Test with a real grievance ID against the running
  backend on port 5001. Verify: name, phone, province/district/municipality/ward fields
  all returned and mapped correctly in the ticket detail response.
- ~~`public.complainants` — confirm column names match what `grievance_sync.py` expects
  (location fields: `province`, `district`, `municipality`, `ward`, `village`).~~
  ⚠️ **This row was factually wrong and is retired (T3-07).** `grievance_sync.py` takes
  **exactly one** column from `public.complainants` — `location_code` — via a `LEFT JOIN`,
  plus `complainant_id` to join on. It reads none of those five fields. The two it does read
  are gated by `tests/ticketing/test_boundary_policy.py`, which **fails if ticketing ever
  selects complainant PII** (CLAUDE.md §Data rules rule 3).
- End-to-end smoke test: submit a grievance via chatbot → confirm ticket auto-created
  in `ticketing.tickets` within 2 min, with correct `grievance_location`, `priority`,
  `grievance_summary`, `session_id`.
**Dependency:** User is currently rewriting `public.*` tables via Alembic migration.
  Do not test until that migration lands and DB is re-seeded.

### ~~4. Wire OfficerScope seed rows so auto-assign works for live API tickets~~ ✅ DONE
`seed_mock_officer_scopes()` in `mock_tickets.py` — already seeded 9 rows, auto-assign works.

### 5. Visual test + polish pass (backend verified 2026-05-06)
**Backend smoke test results (all passing):**
- All 6 demo tickets seeded and visible correctly per role (ACKNOWLEDGE action ✓, GRC_CONVENE+GRC_DECIDE ✓, RESOLVE ✓)
- SEAH access gate: 403 for non-SEAH roles, 200 for seah_national_officer + super_admin ✓
- Badge counts: Site L1=3, PIU L2=2, GRC Chair=1, SEAH National=1, ADB observer=0 ✓
- SLA data: GRV-2025-005 breached (-24h, urgency=overdue), GRV-2025-001 warning (48h) ✓
- XLSX report export: generates valid file ✓
- My Queue counts: Site L1=2, PIU L2=1, GRC Chair=1, SEAH National=1, ADB observer=0 ✓
- Escalated tab: GRV-2025-004 now in ESCALATED status, visible to all in-scope roles ✓

**What remains:** Browser click-through (UI rendering, mobile shell, Settings panel)
- Open http://localhost:3001, switch roles via MockRoleSwitcher, verify each screen
- GRC convene → decide flow visual check (date picker + purple button)
- Mobile shell (/m/ routes) quick pass on narrow viewport
- BUG NOTE (2026-06-02): In mobile chat view (`grm-auth.nepal-gms-chatbot.facets-ai.com`),
  the message textbox intermittently freezes (cannot type/send). Repro and fix in next UI
  polish pass; likely input/focus or resize event handling regression.
- Reports — Overview / **Summary** / Pivot / Quarterly ✅; run `alembic upgrade head` + `python -m ticketing.seed.backfill_overdue_episodes` on existing DBs

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

## 🔴 TP-14 — Classification status + portal sync (P1, spec locked 2026-06-03)

**Specs:** [`docs/sprints/archive/June5/04-classification-status-spec.md`](sprints/archive/June5/04-classification-status-spec.md) · [`03-portal-p1-spec.md`](sprints/archive/June5/03-portal-p1-spec.md) § TP-14

**Classification codes:** `pending` (default) → `LLM_generated` | `LLM_failed` | `LLM_skipped` → `complainant_confirmed` or `officer_confirmed`. Officer gate for `LLM_*` (not complainant confirmed). Retire `is_temporary`, `slot_skipped`, `LLM_error` in DB.

**Implementation checklist:**

- [ ] Chatbot: persist `grievance_classification_status` on review + submit; `LLM_skipped`; LLM task sets `LLM_generated`/`LLM_failed`
- [ ] `ticketing_dispatch.py` — DB fallback for summary/categories at submit
- [ ] `grievance_sync.py` — no `is_temporary` filter; UPDATE existing ticket cache
- [ ] `GET /tickets/{id}` — merge grievance; expose classification status
- [ ] Portal: badges, amber panel, block Ack until `officer_confirmed` when required
- [ ] Officer validate API → `officer_confirmed` + audit event
- [ ] AWS backfill for empty cache rows
- [ ] Seed/migration: `LLM_skipped` in `grievance_classification_statuses`; normalize `slot_skipped`

---

## 🔴 ACTIVE SPRINT — Tier-1 Hardening (July 2026)

HR-01…07 from the adversarial codebase review (fail-closed auth, ticket-access gates, unique ticket index, escalation locking, CI, portal + webchat robustness). Specs, tracker, and agent runbooks: `docs/sprints/2026-07_hardening/` · Source: `docs/reviews/devils_advocate_codebase.md` §3 Tier 1.

## 🟠 QUEUED SPRINT — Tier-2 Quality & Performance (Aug 2026, after Tier-1)

H2-01…08: OIDC refresh-grant, `tickets.py` split + engine extraction, authz/escalation test extensions, grievance-sync watermark, auth-dependency cache, shared `useTicketThread` hook, SEAH form mixin + Nepali copy repair. Specs, tracker, runbooks: `docs/sprints/archive/2026-08_tier2_quality/` · Source: `docs/reviews/devils_advocate_codebase.md` §3 Tier 2.

---

## 🔴 SECURITY — open (active ticket, not deferred)

| Item | File | Notes |
|------|------|-------|
| ~~`run_flow_turn` **handler table** (T3-02 p4)~~ ✅ **DONE 2026-07-15** | `backend/orchestrator/state_machine.py` | Shipped. **run_flow_turn 1,485 → 150 lines (−90%)**; the 20-arm chain replaced by a dict lookup + p1's recovery as the default. **D-53's re-sizing settled by doing it: an M, not the spec's S** — 19 arms / ~1,058 lines had to come out before the "22 one-line entries" existed to write. p2's characterization net passed **unchanged** (214/1 both sides) and the extraction is **proven verbatim** (1,025/1,025 moved lines). The win is per-handler signatures — each declares exactly what its body reads, which the chain could not record — **not** the table itself, and **not** correctness: the table is blind to D-51/D-52/D-59 (a recognized state that dispatches nothing passes the lookup), which is why the postcondition landed first. |
| ~~`status_check_form` **silently** treats an unknown `active_loop` as status form 1~~ ✅ **FIXED 2026-07-15** | `backend/orchestrator/state_machine.py` (postcondition + the form-selection `else`) | Closed with **both** halves, because they fix different things: the **postcondition** catches the symptom and — via `_recover_from_unknown_state` — clears the bogus `active_loop`, which is what **un-wedges** the session (a message alone would have left it to re-silence every later turn); the **point fix** logs the offending loop at error, which is the actionable half since `status_check_form` is a *valid* state and the postcondition's log alone would send an operator to the wrong place. Trap recorded for the next person: `story_route` is the hinge and **D-51/D-52 need opposite values of it** — that made two new tests pass pre-fix for the wrong reason, caught only by red-verification. |
| ~~**`GET /api/grievance/{id}` and `POST /api/grievance/{id}/status` are unauthenticated**~~ | — | ✅ **RESOLVED 2026-07-15 by T3-06** (4 commits: contract → audit → client key → authn). Both now `Depends(_ticketing_auth_check)`; the GET gained a `response_model` (51 fields, `extra="allow"` so no column is silently dropped) and a read audit at INFO carrying the caller principal. Verified red pre-fix: unauthenticated, the GET returned **200 with `grievance_description`**. Dev bypass + HR-01 fail-closed 503 preserved and pinned. **⚠️ The exposure check is now ANSWERED: `:5001` is NOT admitted** — SG `sg-01739221c73ab3eb1` (`chatbot-main`/`chatbot-rest`, `ap-southeast-1`) allows only 80/443/22(restricted)/8000/3000. **Not an incident; Phase 2 confirmed.** Two caveats carried below: DOR prod is on non-AWS infra and remains unverified, and `tcp/8000 0.0.0.0/0` **is** open to an unauthenticated orchestrator. See [`sprints/archive/2026-08_tier3_structural/05-grievance-api-hardening-spec.md`](sprints/archive/2026-08_tier3_structural/05-grievance-api-hardening-spec.md). |
| **DOR prod firewall for `:5001` is UNVERIFIED** | `grm-chatbot.dor.gov.np` | T3-06 cleared `:5001` on the **facets/AWS** staging hosts by reading the live security group. **Production runs on DOR infra, not this AWS account** (CLAUDE.md §Superseded), so its firewall could not be checked from here and **no repo artifact can answer it**. The endpoints are now authenticated either way, so an open port is no longer an anonymous-read hole — but it should still be closed. **Ask whoever operates DOR infra whether inbound `:5001`/`:8000` are admitted.** |
| **Orchestrator `:8000` is open to `0.0.0.0/0` and has no auth** | `backend/orchestrator/main.py:102`, `docker-compose.grm.yml:122` | Surfaced by T3-06's exposure check (out of its scope). `POST /message` has no `Depends`; the port is host-mapped by the overlay the staging deploy composes, and SG `sg-01739221c73ab3eb1` admits `tcp/8000` from anywhere. **Less severe than it reads** — `/message` is the public chatbot entry point, so it discloses nothing the web chat doesn't. What it bypasses is nginx: **no TLS** (plaintext `session_id`) and **no rate limit** (the `public` 30r/m zone is nginx-level) on a path that triggers **LLM spend**. Note the irony worth reading: T3-06 spent 4 commits authenticating a port the firewall already closed, while the open port has no auth at all. Tracked: [`sprints/archive/2026-08_tier3_structural/followups/orchestrator-port-8000-open.md`](sprints/archive/2026-08_tier3_structural/followups/orchestrator-port-8000-open.md) |

---

## 🔵 TECH DEBT (low urgency)

| Item | File | Notes |
|------|------|-------|
| 🟡 **Demo officer switcher one-way door — ROOT FIX LANDED 2026-07-16; C4 unblocked. Optional portal hardening remains.** | `ticketing/api/dependencies.py` (`require_admin_or_bypass`) · `ticketing/api/routers/users.py` (roster routes) | Root cause: `GET /users/roster` was `require_admin`, so switching to a non-admin officer 403'd the roster the switcher needs to switch back. **Fixed:** roster now `require_admin_or_bypass` — admin-only under Keycloak, any authenticated identity in dev bypass. Verified live (officer 403→200), pinned by `tests/ticketing/test_demo_switcher_roster.py`, full suite 607 passed. **Bypass builds only; Keycloak posture unchanged.** Residual (optional, defense-in-depth, now moot for the normal flow): the portal catch branch at `AuthProvider.tsx:264-269` still doesn't clear the cookie on a roster failure, and `fallbackBypassToken` still hardcodes super_admin. Tracked: [`sprints/archive/2026-08_tier3_structural/followups/demo-officer-switcher-one-way-door.md`](sprints/archive/2026-08_tier3_structural/followups/demo-officer-switcher-one-way-door.md) · PROGRESS **D-65** |
| ~~`add_more_info_flow` completes into a **silent turn** when `story_route` is unset~~ ✅ **FIXED 2026-07-15** | `backend/orchestrator/state_machine.py` (turn postcondition) | Closed by the **`run_flow_turn` postcondition** — the general guard both followups recommended over point fixes: *no turn returns zero messages*, logged at error with state/intent/active_loop/next_state, then the user is recovered. **One guard closed four instances: D-08, D-51, D-52 and D-59.** Safe to *recover* rather than merely log because the precondition was **measured, not assumed**: instrumenting all three of `run_flow_turn`'s returns across 208 tests found **3 zero-message turns and all 3 were bugs** — `attachment_ids_sync` and the `/introduce` restart never return empty, so there was no legitimate silence to protect and the blast radius is exactly the already-broken turns. That measurement also **found D-59**, a fourth instance nobody knew about. Owned by `tests/orchestrator/test_no_silent_turns.py` (8 tests, verified red). The characterization pin was deleted on the signal its docstring specified. |
| Seed log message still says `PROVINCE_1` | `kl_road_standard.py:319` | Cosmetic — actual stored value is `NP_P1` |
| `_scope_candidates` calls `_location_and_ancestors` twice (branches B + C) | `workflow_engine.py` | Minor perf — combine into one call |
| `OfficerScope` seed creates `UserRole` rows but no `OfficerScope` rows | `mock_tickets.py` | Auto-assign returns `None` for API-created tickets; pre-seeded demo unaffected |
| ~~Cognito user pool not created~~ | — | ✅ Obsolete — Keycloak shipped instead (see `docs/deployment/16_auth_keycloak.md`) |
| ~~`grievance_sync.py` hardcoded column list~~ | — | ✅ **CLOSED by T3-07 (2026-07-15).** The column list is now declared in `tests/ticketing/test_boundary_policy.py`'s `CONTRACT` and gated in both directions against the CL-01 `public.*` baseline: a renamed/dropped column fails in CI **naming the ticketing code that would break**, instead of at 02:00 in a Celery beat job. Mutation-verified (renaming `grievance_summary` in the baseline goes red). The guard covers **all 5** tables ticketing touches, not just this file. `public.complainants` is gated to `location_code`/`complainant_id` — PII selection fails the suite. |
| Utterance `file_name` derived from module name (~200 sites) — move a class to another file and its copy silently breaks | `backend/actions/base_classes/base_mixins.py:63` | Deferred out of T3-01 (which fixes the 4-site `action_name` introspection). **This is the finding the review's "makes the chatbot refactorable" item was actually aiming at**; M+. Already forced one workaround (`services/contact/utterances.py:6` hardcodes `"form_contact"`). Tracked: [`sprints/archive/2026-08_tier3_structural/followups/utterance-file-name-derivation.md`](sprints/archive/2026-08_tier3_structural/followups/utterance-file-name-derivation.md) |
| ~~Ticketing reads `public.grievances` + `public.file_attachments` **directly via its own DB session** — violates locked data rules #1/#5~~ | — | ✅ **NOT DEBT — the rule was retired 2026-07-15.** Reassessment found the surface is **11 statements / 5 tables / 3 writes** (not 3 reads); the rule protects two goals **both already dead in the code** (ticketing can't move DB — it writes to `public.*`; the chatbot can't survive without ticketing — intake location validation reads `ticketing.locations`); there is **no enforcement** (one DB, one role); and routing the reads via `GET /api/grievance/{id}` would be a **security downgrade** (that endpoint has no authn/authz/audit; the direct read sits behind JWT + a jurisdiction gate). **Decision (project owner):** drop "no joins", keep + pin no-FK and no-PII-columns. Evidence: [`sprints/archive/2026-08_tier3_structural/00-reassessment.md`](sprints/archive/2026-08_tier3_structural/00-reassessment.md) §6 → **T3-07** ([`06-boundary-policy-spec.md`](sprints/archive/2026-08_tier3_structural/06-boundary-policy-spec.md)). **✅ T3-07 LANDED 2026-07-15** — CLAUDE.md §Data rules amended to the as-built contract, both surviving rules pinned by `tests/ticketing/test_boundary_policy.py`, downstream docs realigned. The reads are **legitimized as-built; do not re-open them as debt.** |
| `backend/actions/forms/form_story_main_route_step.py` is **entirely dead code** (79 lines, `ValidateMenuForm` + `ValidateFormStoryStep`, zero importers) | `backend/actions/forms/form_story_main_route_step.py` | Deferred out of T3-01 (spec: dead code = log, don't fix). Proven by 4 legs: no importer, absent from `form_loop.py`'s `_FORMS` registry, no name reference, and **no Rasa action server exists** to auto-discover it. **It looks live only because `orchestrator/config/domain.yml:1054` still declares `validate_form_story_main`** — Rasa-era config the hand-rolled state machine no longer honors. T3-01 gave it an explicit key + mapping entry so the "every call-site key resolves" invariant stays total; **delete the module and that entry together.** Tracked: [`sprints/archive/2026-08_tier3_structural/followups/dead-form-story-main-route-step.md`](sprints/archive/2026-08_tier3_structural/followups/dead-form-story-main-route-step.md) |
| The grievance API has **no rate limiting** — `§6`'s "loggable, authorizable, **rate-limitable** at one place" chokepoint argument is now 2/3 true, not 3/3 | `backend/api/routers/grievance.py` | Deferred out of **T3-06 step 4** (spec: *"only if there is an existing mechanism to reuse… if dropped, log the deferral"*). **Measured: nothing reusable reaches these endpoints.** nginx `limit_req_zone` **does** exist (`webchat_rest_compose_prod.tls.conf:8-10`) but there is **no `location /api/grievance` block**, so `:5001` traffic never passes through nginx; no Python limiter is installed (`slowapi` etc. absent from all requirements). Low priority: the port is firewall-closed and both endpoints are now authenticated. **Anyone citing §6's chokepoint argument in a later sprint must know rate-limiting is still unbuilt.** The one piece network posture does *not* solve: auth failures on `_ticketing_auth_check` are unthrottled ⇒ the key is brute-forceable. Tracked: [`sprints/archive/2026-08_tier3_structural/followups/grievance-api-rate-limiting.md`](sprints/archive/2026-08_tier3_structural/followups/grievance-api-rate-limiting.md) |
| `5001:5001` binds the backend API to **all host interfaces** on deployed hosts — a dev convenience applied verbatim in staging | `docker-compose.grm.yml:112-117` | Deferred out of T3-06 §Exposure (*"consider dropping the `5001:5001` host mapping from the **prod** overlay"*). **The mapping is not in a prod overlay** — it is in `grm.yml`, shared by dev and both deploys, and compose **merges** `ports` by concatenation so `docker-compose.aws.yml` **cannot cleanly override it** (you'd get both binds). Removing it outright breaks the documented host-browser dev loop. Defence-in-depth only: the SG already closes `:5001`, so the firewall is the single control holding. Suggested shape: `"${BACKEND_HOST_BIND:-0.0.0.0}:5001:5001"`. Do it together with the `:8000` and vestigial `:3000` SG items — one compose edit, one SG edit. Tracked: [`sprints/archive/2026-08_tier3_structural/followups/grievance-api-host-port-binding.md`](sprints/archive/2026-08_tier3_structural/followups/grievance-api-host-port-binding.md) |
| ~~Host `pytest tests/ticketing` fails on **stale `env.local` DB credentials**~~ | — | ✅ **CLOSED by T3-08 (2026-07-15, `ac0b9d29`).** Root cause was deeper than this row: env.local's `POSTGRES_*` are dead **by construction** — every compose service hardcodes `POSTGRES_DB`/`USER`/`PASSWORD` in its own `environment:` block, so **no container reads them**. `tests/ticketing/_host_env.py` was the only reader, i.e. the only thing that could disagree with the DB it talks to. It no longer reads DB identity from env.local (an explicit shell override still wins). **Bare `pytest tests/ticketing`: 110 failed / 234 errors (132s) → 567 passed / 0 failed (14s).** The `POSTGRES_USER=... pytest` workaround is retired; pinned by `tests/ticketing/test_host_env.py`. `.env.example` already had the correct values — only env.local drifted. |
| ~~`tests/ticketing` is **not reliably green on a developer machine**~~ | — | ✅ **CLOSED by T3-08 (2026-07-15, `9e74e457`).** **This row's diagnosis was wrong** — `l1-officer-3` is not DB residue, it is a seeded officer (`ticketing/constants/demo_officers.py:22`) in the province-fallback pool since `b8cab274`; the original grep missed `ticketing/constants/`. Real cause: 3 assertions named a hardcoded 2-of-4 officer pair, while `auto_assign_officer` ranks by **active ticket load** — so they pinned an identity decided by live data, and passed on a fresh seed only by luck of the `user_id` tie-break. They now assert the province **pool** from `demo_officers`. Mutation-verified still to catch a broken fallback. **Bare `pytest tests/ticketing` = 567/5/0, stable across runs.** The rot went unnoticed because CI never ran these tests — fixed in the same pass (row below). |
| Voice-chunk upload sessions live in a **process-local dict** (+ local `.part` file) — the chunked protocol is stateful across requests, so every chunk must hit the same process | `backend/services/file_server_core.py:29-31`, `docker-compose.yml:48` | Deferred out of T3-03 (spec scopes out `file_server_core` session lifecycle). **Not a live bug** — the API runs a single uvicorn worker (no `--workers`, verified). But adding workers/replicas **silently** breaks voice notes: chunk 1 404s and the client swallows it (`voiceNote.js:31` matches `"not found"`) ⇒ reads as a flaky feature, not a misconfiguration. **Put this on the checklist for any change to the API's worker/replica count.** Tracked: [`sprints/archive/2026-08_tier3_structural/followups/voice-chunk-session-store-is-process-local.md`](sprints/archive/2026-08_tier3_structural/followups/voice-chunk-session-store-is-process-local.md) |
| Portal ESLint debt: 143 warnings, 0 errors (HR-05 downgraded 5 rule families to `warn` to reserve the CI error channel) | `channels/ticketing-ui/` | Tracked ticket: [`sprints/2026-07_hardening/followups/portal-lint-cleanup.md`](sprints/2026-07_hardening/followups/portal-lint-cleanup.md). Endgame: warn → fixed → re-enable as `error`. Includes the 4 unused `eslint-disable` directives (e.g. `AuthProvider.tsx` getUserPreferences effect). **Measured 141 on `dev/tier3-structural` @ `87fbba86` (this row says 143 — one of the two is stale; T3-05 held the measured number flat at 141 across 7 commits).** |
| Settings tabs have **no render smoke tests** — the portal has no DOM test harness at all | `channels/ticketing-ui/vitest.config.ts`, `package.json` | Deferred out of **T3-05** (spec: *"if skipped for scope, log it as a followup + TODO.md row"*). **Not a skipped test — a missing capability:** no `@testing-library/react`, no `jsdom`, no `@vitejs/plugin-react`; vitest is `environment: "node"` and `include: ["**/*.test.ts"]`, so **`.tsx` is never even collected** — the config header says this is deliberate. Standing it up = 3 dev deps + lockfile + `grm_ui` image rebuild + switching the **shared** config to `jsdom` under all 88 existing tests: a dependency decision, not a verbatim move. **T3-05 did close the coverage-from-zero half of D-12** — 27 mutation-checked unit tests now cover the extracted helpers (`workflowHelpers`, `roleEntry`, `friendlyError`), the first tests under `components/settings/`. The extraction is what makes the tabs individually mountable, so the remaining work is now S/M. Tracked: [`sprints/archive/2026-08_tier3_structural/followups/settings-tab-render-tests.md`](sprints/archive/2026-08_tier3_structural/followups/settings-tab-render-tests.md) |
| `ProjectWorkflowSelect` is **dead code** (zero callers; superseded by `ProjectWorkflowsEditor`) | `channels/ticketing-ui/components/settings/workflows/ProjectWorkflowSelect.tsx` | Found while moving in **T3-05**; not fixed (spec: move verbatim, log don't fix). Already dead **before** the sprint — it is one of the 141 baseline eslint warnings. ⚠️ **The extraction made the signal quieter, not louder:** as an *exported* symbol in its own module, `no-unused-vars` no longer flags it, so the portal count went 141 → 140. **That −1 is a lost signal, not an improvement** — do not read it as lint progress. Deletion is XS; natural home is the `portal-lint-cleanup` sweep. Tracked: [`sprints/archive/2026-08_tier3_structural/followups/dead-project-workflow-select.md`](sprints/archive/2026-08_tier3_structural/followups/dead-project-workflow-select.md) |
| ~~Silent OIDC refresh not applied to 4 non-`apiFetch` fetch sites (2 uploads can lose a file selection on token expiry)~~ | — | ✅ **RESOLVED 2026-07-15.** New shared `authedFetch` (proactive refresh + 401→refresh→retry-once) wraps all 4 blob/multipart sites; multipart bodies rebuilt in the thunk so the retry re-sends them; `isSessionExpiredResponse` retired. Vitest 61 (+3 new) / tsc / eslint / next build green. See [`sprints/archive/2026-08_tier2_quality/followups/apifetch-refresh-non-json-sites.md`](sprints/archive/2026-08_tier2_quality/followups/apifetch-refresh-non-json-sites.md). |
| ~~Pre-existing dead imports/local in `routers/tickets.py` (4 unused imports + unused `rerouted` local)~~ | — | ✅ Resolved in H2-02 Pass 4 (package split rewrote the import block — the 4 dead imports weren't carried across; `rerouted` binding dropped, reroute call preserved). Also dropped 3 dead private helpers (`_lookup_workflow`, `_first_step`, `_is_viewer`). Followup doc closed. |
| ~~Authz gaps surfaced by H2-03: (1) 15 unauthenticated reference/config GET endpoints, (2) `DELETE /roles/{id}` no gate on non-system roles, (3) `PATCH /projects/{id}` metadata no gate~~ | — | ✅ **RESOLVED 2026-07-15.** (2) delete gates on `CREATE_OPERATIONAL_ROLE`; (3) patch gates on `MANAGE_PROJECT` (xfail flipped to passing); (1) 10 project-config GET reads locked to `get_authenticated_user`, geography stays public, sweep allowlist trimmed to 5. Full ticketing suite 545 passed / 0 xfailed. Optional later step: per-project scope-gating (not just authenticate). See [`sprints/archive/2026-08_tier2_quality/followups/authz-gaps-h2-03.md`](sprints/archive/2026-08_tier2_quality/followups/authz-gaps-h2-03.md). |
| `StepCast` greys **wrong-track** roles only; the other two "why-excluded" reasons need a backend endpoint, and role labels are EN-only (`ticketing.roles` has no `_ne`) | `channels/ticketing-ui/components/settings/workflows/StepCast.tsx` · `ticketing/api/routers/users.py` · `ticketing/models/user.py` | Deferred from the step-cast parity build (v1 = `frame-04.md` §6 GAP1 recommended subset). "owned by another office" roles are filtered server-side (client never sees them); "bound at L3 only" has no endpoint — both need a picker endpoint returning in+out-of-scope roles flagged with a reason. Role `_ne` is RB-1 i18n. Nothing broken; wrong-track greying + roles-clarity shipped. Tracked: [`sprints/2026-07_org_chart_positions/followups/step-cast-why-excluded-and-role-ne.md`](sprints/2026-07_org_chart_positions/followups/step-cast-why-excluded-and-role-ne.md) |

---

*Updated by Claude Code. Stage this file with every relevant commit.*
