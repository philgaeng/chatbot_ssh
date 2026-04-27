# GRM Ticketing — TODO / Backlog

> This file tracks open gaps, pending tasks, and future features.
> Updated alongside `PROGRESS.md`. Read both before picking up work.
> Last reviewed: 2026-04-26

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

---

## 🟡 POST-DEMO FEATURES (prioritised)

### 4. LLM: Note translation + English summary for supervisor/viewer roles
**Rationale:** Field officers in Nepal submit notes in Nepali (or mixed). Supervisors
(ADB roles, GRC chair, senior observers) need to read case notes without a translator.  
**Scope:**
- On `NOTE_ADDED` event: trigger async Celery task → call LLM to produce English
  translation. Store result in `TicketEvent.payload["translation_en"]`.
- On ticket detail load for viewer/supervisor roles: if `translation_en` exists, show
  it alongside (or instead of) the original note with a "translated" chip.
- Aggregate summary: for `grc_chair`, `adb_hq_safeguards`, `adb_hq_exec` roles,
  show a "Case summary" panel on the ticket detail — one LLM call over all notes
  + events for that ticket, cached in `ticketing.tickets.ai_summary_en`. Refresh
  button to regenerate.
**Implementation notes:**
- Use the existing `backend.task_queue.celery_app` LLM queue (DO NOT reimplement).
  Wire via a new Celery task in `ticketing/tasks/llm.py`.
- Language detection: use `langdetect` or pass raw note to LLM with prompt
  "Translate to English if not already in English, else return as-is."
- Store raw note unchanged — translation is additive, never replaces.

### 5. User language preference (per organisation)
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

### 6. Mobile-first ticket management UI (officer field app)
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
**Dependencies:** Requires Week 2 desktop UI to be complete first.

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
