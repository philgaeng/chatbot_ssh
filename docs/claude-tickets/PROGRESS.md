# GRM Ticketing — Session Progress & Status

> **This file is updated at every commit.**
> Read it before any code decision. It tells you current state, deviations from spec, and what's next.
> For open gaps and future features → **`docs/claude-tickets/TODO.md`**
> Last updated: `qr-token-feature` — 2026-05-07

---

## ⚡ QUICK STATE (60-second session recovery)

### What's done
- ✅ **Week 1 backend complete** — schema, models, migrations, CRUD API, escalation engine, Celery tasks, seed
- ✅ **Settings UI** — full admin panel: workflows, users (scopes), organisations, locations, projects, packages
- ✅ **Demo DB seeded** — 6 tickets across both demo scenarios, all 12 roles, 2 workflows
- ✅ **Escalation gaps closed** — auto-assign on escalation + automatic complainant notification on RESOLVE/ESCALATE
- ✅ **LLM translation + findings** — per-note translation to English (gpt-4, Celery); AI case-findings card (role-gated); `POST /tickets/{id}/findings` endpoint; Alembic migration `c1d5f8a2e047`
- ✅ **Chatbot → ticketing webhook** — `backend/actions/utils/ticketing_dispatch.py` (fire-and-forget); wired into both `BaseActionSubmit.execute_action` (standard) and `ActionSubmitSeah.execute_action` (SEAH); env vars `TICKETING_API_URL` + `TICKETING_SECRET_KEY` added to `env.local`
- ✅ **Spec 12 tier model** — 4-tier permission model (Actor/Supervisor/Informed/Observer) fully implemented:
  - Alembic migration `k0l2n4p6r8`: `tier` column on `ticket_viewers`, `complainant_reply_owner_id` on `tickets`
  - Backend: `POST /tickets/{id}/informed` (add to Informed), `PUT /tickets/{id}/complainant-reply-owner`
  - Escalation: previous actor auto-moves to Informed on escalation; TIER_CHANGED event emitted
  - `should_notify()` gate reads `notification_rules` from settings JSON
  - Frontend: ViewersBar split into Informed (purple) + Observer (gray) rows
  - Frontend: Actor/Informed tier badges on note bubbles in event thread
  - Settings: tier config per step + WorkflowNotificationsPanel (event × tier × channel grid)
- ✅ **Settings UI polish** (2026-05-06):
  - Sidebar: hides redundant email in bypass/demo mode (MockRoleSwitcher already in header)
  - Workflow step editor: removed redundant "Stakeholders notified" box (superseded by Informed tier)
  - Org roles dropdown: seeded 9 spec-defined roles (Project Owner, Donor, CSC, etc.)
  - Org ID auto-generation: removed manual field; derived from name initials + country code prefix (ADB = no prefix)
  - WCAG contrast fixes in Packages list: ghost text, italic labels, location badges all pass 4:1
  - Officer Edit button: wired to `OfficerEditModal` (was no-op stub)
  - Add Role button: wired to `RoleEditModal` in create mode (was hard-disabled)
  - Permissions editor: stripped from roles (superseded by Actor/Supervisor/Informed/Observer tiers)
- ✅ **Demo seed polish** (2026-05-06):
  - Fixed ADB observer scope: `organization_id` changed from ADB→DOR (tickets belong to executing agency DOR)
  - Fixed SEAH HQ scope: same fix (DOR not ADB)
  - GRV-2025-003 and GRV-2025-005: location moved to NP_D006 (Morang) so Site L1 has 2 tickets in My Queue
  - GRV-2025-004: left in ESCALATED status (not pre-acknowledged) so Escalated tab is non-empty
  - Cleaned test/dev tickets (GRV-SYNC-TEST, GRV-TEST-PII, GRV-TEST-SCOPE) from DB via --reset reseed

- ✅ **QR token feature** (2026-05-07):
  - `ticketing/models/qr_token.py` — QrToken model (opaque 8-char hex, package_id FK, is_active, expires_at)
  - `ticketing/migrations/versions/l2m4o6q8s0_qr_tokens_and_ticket_package.py` — creates `ticketing.qr_tokens`; adds `package_id` to `ticketing.tickets`
  - `ticketing/api/routers/scan.py` — 4 endpoints (public scan + admin CRUD); `scan_url` returned in both create and list responses
  - `ticketing/config/settings.py` — `chatbot_webchat_url` setting (overridable via env var, default: `https://grm.facets-ai.com/chat`)
  - `channels/ticketing-ui/lib/api.ts` — QrTokenOut, QrTokenCreateResponse types + listQrTokens / createQrToken / revokeQrToken functions
  - `channels/ticketing-ui/app/settings/page.tsx` — QR Tokens section in PackageRow (list tokens, generate, revoke) + QrCodeModal (QR image via qrserver.com, copy URL, download PNG)

### In progress / next
- 🔲 **Chatbot-side QR integration** — Cursor task: read `?t=` URL param, call `GET /api/v1/scan/{token}`, pre-fill district/province slots, update welcome message, pass `package_id` in ticket dispatch (see handoff note in `docs/claude-tickets/`)
- 🔲 **Visual test + polish** — click through all demo scenarios in browser (http://localhost:3001)
- 🔲 **Staging deploy** — Docker deploy to grm.stage.facets-ai.com

### Active containers
| Container | Port | How to start |
|-----------|------|-------------|
| `ticketing_api` | 5002 | `docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d` |
| `grm_ui` | 3001 | same command |
| `db` | 5433 (host) | same |

### Re-seed demo data
```bash
docker exec nepal_chatbot_claude-ticketing_api-1 python -m ticketing.seed.mock_tickets --reset
```

### Build commands (always run from inside WSL)
```bash
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && docker compose -f docker-compose.yml -f docker-compose.grm.yml build <service>"
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d --force-recreate <service>"
```

---

## BUILD TIMELINE CHECKLIST

```
Week 1 (Apr 21-27) — Backend ← YOU ARE HERE (complete)
  ✅ Session 0: codebase analysis → session-0-codebase-findings.md
  ✅ Session 1: ticketing.* schema + SQLAlchemy models + Alembic migration
  ✅ Session 2: FastAPI skeleton + ticket CRUD API + mock data seeder
  ✅ Session 3: Workflow engine + escalation logic + Celery tasks

Week 2 (Apr 28 - May 4) — Frontend (Cursor)
  🔲 channels/ticketing-ui/ officer queue page
  🔲 Ticket detail + action panel (acknowledge / escalate / resolve)
  🔲 SLA countdown + notification badge
  🔲 Internal notes + file attachments
  🔲 SEAH visual distinction (🔒 badge + red left border)

Week 3 (May 5-9) — Integration + demo prep (Cursor)
  🔲 SEAH workflow + role-based access control
  🔲 Complainant notification (chatbot + SMS fallback)
  🔲 Mock data verified end-to-end for both demo scenarios
  ✅ Chatbot → ticketing webhook (POST /api/v1/tickets on submit)
  🔲 Docker deployment to grm.stage.facets-ai.com
  🔲 Bug fixes + polish

May 10: Demo
```

---

## DEMO DB STATE

Seed: `python -m ticketing.seed.mock_tickets --reset`  
Verified working as of `c171ac4`.

| grievance_id | status | step | is_seah | assigned_to |
|---|---|---|---|---|
| `GRV-2025-001` | `IN_PROGRESS` | L3 GRC (`NP_D006`) | No | `mock-officer-grc-chair` — click CONVENE to demo |
| `GRV-2025-SEAH-001` | `IN_PROGRESS` | SEAH L1 (`NP_D011`) | **Yes** | `mock-officer-seah-national` |
| `GRV-2025-002` | `RESOLVED` | L1 | No | Historical view |
| `GRV-2025-003` | `OPEN` | L1 (`NP_D004`) | No | Unacknowledged — shows NEW badge |
| `GRV-2025-004` | `IN_PROGRESS` | L2 (`NP_D006`) | No | SLA close |
| `GRV-2025-005` | `OPEN` | L1 (`NP_P1`) | No | `sla_breached=true` — shows overdue |

**Mock officer IDs** (used as `assigned_to_user_id` and for proto auth):
```
mock-super-admin            → super_admin @ DOR
mock-officer-site-l1        → site_safeguards_focal_person @ DOR / NP_D006
mock-officer-piu-l2         → pd_piu_safeguards_focal @ DOR / NP_P1
mock-officer-grc-chair      → grc_chair @ DOR / NP_P1
mock-officer-grc-member-1   → grc_member @ DOR / NP_P1
mock-officer-seah-national  → seah_national_officer @ DOR / NP_P1
mock-officer-adb-observer   → adb_hq_safeguards @ ADB
```

Proto auth stub in `ticketing/api/dependencies.py` always returns `mock-super-admin`.
Replace with Cognito JWT for production.

---

## COMMIT LOG — feature/grm-ticketing (GRM work only)

| Hash | Date | What changed |
|------|------|-------------|
| `edfa942` | 2026-04-27 | **feat(llm)** Note translation + case findings summary. `llm_client.py`, `tasks/llm.py`, migration `c1d5f8a2e047`, `FindingsCard` frontend component, translation chip in timeline |
| `d4e2f1a` | 2026-04-27 | **fix(escalation)** Auto-assign officer on `escalate_ticket()`; automatic complainant notification on RESOLVE/ESCALATE via `notify_complainant.delay()` |
| `c171ac4` | 2026-04-26 | **fix(seed)** Location codes → real Nepal codes (`NP_P1`/`NP_D004`/`NP_D006`/`NP_D011`); `project_code` backfill in `add_user_scope`; fix t_dust status `ESCALATED→IN_PROGRESS` |
| `c724f5b` | 2026-04-26 | **feat** `package_id` + `includes_children` wired in `OfficerScope` API + frontend; `_scope_candidates` branch C for package routing via `PackageLocation` |
| `120d543` | 2026-04-25 | **feat** Project packages CRUD, org roles on projects, location API `?q=` search extended to `location_code`; Settings UI org→project navigation, LocationSearch component |
| `8133987` | (earlier) | **feat** Scope endpoints upgraded: `project_id` FK + `includes_children` |
| `cb2a134` | (earlier) | **feat** `includes_children` cascade in officer scope matching (branch B in `_scope_candidates`) |
| `b590b77` | (earlier) | **feat** Locations, countries, and projects CRUD router |
| `b384a5b` | (earlier) | **feat** Multi-country location tree, projects, and scope hierarchy schema |
| `937c21c` | (earlier) | **feat** Workflows editor, officer scopes panel, Docker fixes |
| `285a877` | (earlier) | **feat** Chatbot webhook (grievance sync Celery task) + Docker deployment |
| `ce26809` | (earlier) | **feat** GRM compose targets, port guard, nginx routing |

---

## SPEC DEVIATIONS

Deviations from the original `CLAUDE.md` specs, with rationale.

### 1. Location model moved to `country.py` (not `organization.py`)
- **Spec implied:** Locations are simple org-scoped codes in `organization.py`
- **Built:** Full multilingual location tree (`country.py`) — `Country`, `LocationLevelDef`, `Location`, `LocationTranslation`; 841 Nepal locations imported from geodata
- **Why:** Required for proper KL Road district matching and future multi-country support
- **Impact on seed:** `kl_road_standard.py` now uses real codes (`NP_P1`, `NP_D006`, etc.) instead of `PROVINCE_1`, `MORANG`. `seed_locations()` is verify-only (no insertion — data comes from import scripts).
- **Commit:** `b384a5b`, fixed in seed at `c171ac4`

### 2. `OfficerScope` gained `package_id` + `includes_children` (beyond original spec)
- **Spec:** Scopes matched by `(role, org, location, project_code)`
- **Built:** Also `package_id` (scope a contractor's L1 officers to their civil-works package) and `includes_children` (scope cascades to child locations in the location tree)
- **Why:** Demo requirement — KL Road has multiple contractor packages; officers should see only their package's tickets
- **Routing impact:** `_scope_candidates()` in `workflow_engine.py` has 3 branches: A (exact/wildcard, non-package), B (includes_children cascade, non-package), C (package coverage via `PackageLocation` table)
- **Commits:** `cb2a134`, `8133987`, `c724f5b`

### 3. `project_code` kept as canonical routing key (not replaced by `project_id`)
- **Spec:** `project_code` throughout
- **Built:** `OfficerScope` has both `project_id` (proper FK) and `project_code`; `add_user_scope` backfills `project_code` from `project.short_code` when `project_id` is supplied, so `_scope_candidates` routing (which queries `project_code`) keeps working
- **Why:** Tickets carry `project_code` (string key from chatbot), scopes created via UI now use `project_id` FK; bridge needed without rewriting routing
- **Commit:** `c171ac4`

### 4. Grievance → ticket integration: polling not webhook
- **Spec:** "Chatbot → ticketing webhook (POST /api/v1/tickets on submit)"
- **Built:** `ticketing/tasks/grievance_sync.py` — Celery Beat task polls `public.grievances` every 2 minutes instead. `POST /api/v1/tickets` still exists for direct inbound (chatbot can call it directly too).
- **Why:** Avoids chatbot code changes for proto; polling on a Celery worker is safe, idempotent, and doesn't require modifying `backend/` (DO NOT TOUCH)
- **Integration point:** When chatbot-side webhook wiring is added, both paths can coexist; `grievance_sync` checks for existing tickets and skips duplicates

### 5. Settings page expanded beyond original spec
- **Spec:** "Admin settings" (basic shell)
- **Built:** Full admin panel — Workflows tab (create/edit/publish), Users tab (officers, role assignments, scopes with org/project/package/location dropdowns), Organisations tab (orgs + read-only project context, clickable navigate-to-project), Locations/Projects/Packages tabs
- **Why:** Required for demo — admin needs to configure orgs, workflows, and officer scopes before the demo can run

### 6. `WorkflowAssignment` uses `project_code` FK (not `project_id`)
- **Status:** Kept as-is — `project_code` is the lookup key. Workflow assignments are seeded with `project_code="KL_ROAD"` and matched at ticket creation time via the same string key.
- **No change needed** for demo.

---

## OPEN INTEGRATION POINTS

Things intentionally left incomplete with `# INTEGRATION POINT:` comments. Do not wire without re-reading the comment.

| File | What | Notes |
|------|------|-------|
| `ticketing/api/dependencies.py` | Cognito JWT validation | Stub always returns `mock-super-admin` |
| `ticketing/tasks/notifications.py` | SMS fallback phone lookup | Needs `GET /api/grievance/{id}` from backend |
| `ticketing/tasks/reports.py` | Cognito email dispatch | Needs `ListUsers` call to get officer emails |
| `ticketing/tasks/grievance_sync.py` | `session_id` lookup | Needed for chatbot reply; see comment in file |
| `ticketing/clients/grievance_api.py` | PII fetch | Called from ticket detail to show complainant name |

---

## KNOWN ISSUES / TECH DEBT

| Issue | Severity | File | Notes |
|-------|----------|------|-------|
| `seed_workflow_assignment` log message still says `PROVINCE_1` | Low | `kl_road_standard.py:340` | Cosmetic only — actual stored value is `NP_P1` |
| `OfficerScope` seed creates `UserRole` rows only, no `OfficerScope` rows | Medium | `mock_tickets.py` | Auto-assign returns `None` for new tickets created via API; pre-seeded tickets have hardcoded `assigned_to` so demo is unaffected |
| `_scope_candidates` calls `_location_and_ancestors` twice for branch B + C | Low | `workflow_engine.py` | Minor perf: combine into one call when both branches are active |
| Cognito user pool not created yet | High (post-proto) | `env.local` | `COGNITO_GRM_USER_POOL_ID` empty; all auth stubs for now |

---

## CURSOR HANDOFF

The full frontend brief is at: `docs/claude-tickets/session-3-cursor-handoff.md`

That doc has: all API endpoints, request/response shapes, SLA urgency → color mapping, tab query params, action types, SEAH handling rules, and demo data IDs.

---

*Updated by Claude Code at each commit on `feature/grm-ticketing`.*
