# GRM Ticketing — Session Progress & Status

> **This file is updated at every commit.**
> Read it before any code decision. It tells you current state, deviations from spec, and what's next.
> For open gaps and future features → **`docs/TODO.md`**
> Last updated: 2026-08-18 — **DPG Sprint 0 complete** (licensing, dependency audit, privacy assessment, project hygiene, README truth). Tracker: [`sprints/2026-08-llm/PROGRESS.md`](sprints/2026-08-llm/PROGRESS.md). Earlier: 2026-08-04 — author-defined slots finished (project types are the template; go-live A3/A5 → B1). Earlier: 2026-07-04 moved from `docs/sprints/claude-tickets/` to `docs/`; stale Cognito-era rows cleaned (auth is Keycloak as-built, see `docs/deployment/16_auth_keycloak.md`)

---

## ⚡ QUICK STATE (60-second session recovery)

### What's done
- ✅ **DPG Sprint 0 — the platform is submittable on licensing, and honest about privacy** (2026-08-18, branch `dpg/sprint0-licensing`, `tests/repo` 46 passed). **DPG-01:** Apache-2.0 `LICENSE` + `NOTICE` with an explicit `⚠ PENDING` copyright holder (not guessed), **585 SPDX headers** maintained by `scripts/ops/add_spdx_headers.py` and pinned by test. **DPG-02:** `docs/dpg/dependency-licenses.md` — 153 packages across four dependency sets scanned **in-container**, zero unknown or non-OSI, and the scan now runs **nightly** in `ops/security.py` beside `pip-audit`. **DPG-04:** `docs/dpg/privacy-assessment.md` — 13 data-flow legs verified at file and line, assessed against Nepal's Individual Privacy Act 2018, **17 findings** including three nobody knew about: encryption at rest **fails open** when `DB_ENCRYPTION_KEY` is unset or pgcrypto raises (`base_manager.py:243-252`), `*_hash` search tokens are **unsalted SHA-256** of phone/email/name/address so the phone hash is reversible (`:502-511`), and `backup_db.sh` writes an **unencrypted** dump + uploads tar by default. It carries a mandatory honesty marker: drafted by an AI agent, **no legal review**. **DPG-05:** `SECURITY.md` (private channel — this platform holds SEAH reports), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.github` templates with `blank_issues_enabled: false`. **DPG-06:** root `README.md` rewritten from the compose files — the Rasa service on :5005 and the Action Server on :5055 never existed, and neither did any of the three environment URLs it advertised. ⏸ **DPG-03 (IP ownership) is blocked on ADB's Office of the General Counsel** and named as a clock in the sprint tracker
- ✅ **A package is where the project works — and the only place it says so** (2026-08-08, migration `t6v8x0z2`, suite 739 passed / 4 skipped; the 10 pre-existing `test_grievance_sync` / `test_ticket_uniqueness` failures are unrelated and fail on a clean tree too). A package is **code + name + description + locations**, decided by Philippe. **Linked locations merged into Packages**: they were two sections linking districts against the same tree, and only the package copy routed anything (location → package → officer), so they drifted — staging had a project with 5 packages and **0** project locations, and another with 2 project locations and **no** package coverage at all. Go-live **D1 deleted; B2 inherited its blocking role**, so coverage is asked for exactly once. **Every project now has at least one package**, `is_unnamed` — a project with one package looks like a project with none, and the screen asks for a code and name only when there are two to tell apart (API returns **409** if you try to unname one of two). **Per-package organizations moved to Organizations**, listed under the project-level slot they override, instead of a permanently open form on every package card that made a rare exception look like a required step. **Packages may overlap** — a bridge contract covers several road packages, and a grievance there reaches every covering package's officers. `project_locations` is left unread pending [`followups/drop-project-locations.md`](sprints/followups/drop-project-locations.md). Spec: [13 §5C](ticketing_system/13_projects_and_packages.md)
- ✅ **"lot" is retired — one object, one word** (2026-08-08). [`ui/05 §4.1`](ticketing_system/ui/05_ui_copy_style.md) used to bless both ("**package** (a.k.a. **lot**)"), which is permission rather than a rule, and the screens took it: a section headed "Packages (lots)" with a "+ Add a lot" button and rows warning "This lot still needs…". Swept from the UI, the go-live messages, the tests and the specs; `package` won because the database, the API and the routing already say it
- ✅ **Project creation guesses nothing** (2026-08-04). The organization chosen in **New project** decides which types are offered and fills **no slot**. It briefly filled the type's first required role — which assumed catalog order said something about which role an organization plays, so a type listing "Donor" first put a government department in the donor slot and the legacy donor guard failed the whole creation. Organizations are named by role on the project screen; **B1** blocks until the required ones are
- ✅ **Go-live's organization gates agree with the screens** (2026-08-04, suite 735 passed / 4 skipped). **B3 promoted to a blocker**, matching B1: "must be named" and "named for each lot" are the same authorial statement at two scopes, so one cannot stop activation while the other only advises. A lot missing a per-lot organization now uses the project's **warning element** (amber + `IconWarning` + the words "Needs Main Contractor"), and it fires on the same rule the check uses — a project-level naming covers every lot, so neither warns where the other passes
- ✅ **A job's name comes from the workflow, and only from there** (2026-08-04, suite 733 passed / 4 skipped). Doc 12 §6.2 has said since June that the author names each job at a level ("Safeguard Officer", "GRC Chairperson") and that those names — never generic words — are what the staffing and case screens show. The model and editor shipped 2026-08-04, but **nothing was ever authored**, so every screen fell back to the bound **role's** display name: right by accident, and it made the workflow screen look ignored. Closed by three changes together — `r4t6v8x0` back-fills the name each screen was already showing; a level cannot be **saved** and a workflow cannot be **published** with an unnamed job; and the role-name fallback is **deleted** from the staffing screen and go-live's message. Seeds author names so a fresh deployment can publish its own workflow
- ✅ **A level says how it is staffed; the project console follows the setup order** (2026-08-04, suite 725 passed / 4 skipped). `workflow_steps.staff_per_package` (migration `p2r4t6v8`) records whether a level is staffed **lot by lot** or **once for the project** — set by the workflow author, so a typed project inherits it. **Staffing became one screen**: a tab per workflow, levels **last → first**, and a per-lot level asks for an officer on each lot inline (per-lot staffing left the Packages section, where you had to open each lot to find where it differed). The **go-live staffing gate stopped guessing** — it used to accept a project-wide officer *or* full per-lot coverage for every level because nothing recorded the intent. Console order is now Identity → Workflows → Messaging → Locations → Packages → Partner organizations → Staffing, group headings dropped: you cannot name a lot's contractor before the lot exists
- ✅ **Organization membership decides reporting** (2026-08-04, suite 715 passed / 4 skipped). An organization's grievances are **the ones on its projects** — every organization named on a project sees them (donor, ministry, department, contractor alike), a lot-level naming reaches that lot only, and a **parent organization sees what its children see** via the org tree. `ticketing/services/org_reach.py` is the single rule, used by the ticket list, the report query and the XLSX export; the export column became **"Organizations"** and lists them all. This **retires `routing_org_role`** — the anchor that made one organization the owner of a grievance and every other one on the project the owner of nothing (ADB, the donor funding KL Road, matched zero grievances). GRC convening now resolves members from the project's staffing. `tickets.organization_id` survives as a descriptive stamp only. Decision: [`DECISION-organization-membership`](sprints/2026-07_org_chart_positions/DECISION-organization-membership.md)
- ✅ **Author-defined slots — complete** (2026-08-04, suite 711 passed / 3 skipped). A **project type is the template**: it names the workflows a project runs and the organizations it must have, in the author's own words, and says which of them a grievance is recorded against. Creating a project is **organization → its types → name it**; the chosen organization is written straight into the type's routing slot. Go-live's hardcoded organization gates (**A3 implementing agency, A5 donor informed**) are **deleted** — **B1** is the blocker now, and it names the gap with the author's word ("Name the organization for: Ward Office"), reading `implementing_agency_org_id` / `project_donors` as legacy fallbacks so no existing project broke. `POST /projects` now **requires** `project_type_key`. Type authoring is org-scoped (`super_admin` anywhere, `org_admin` in its subtree) and **frozen while a live project runs on it** — read-only summary + *Use as template*. Migrations `j6l8n0p2` · `l8n0p2r4` · `n0p2r4t6`. Plan + record: [`sprints/2026-07_org_chart_positions/`](sprints/2026-07_org_chart_positions/HANDOVER-author-defined-slots-build.md) §7
- ✅ **Week 1 backend complete** — schema, models, migrations, CRUD API, escalation engine, Celery tasks, seed
- ✅ **Settings UI** — full admin panel: workflows, users (scopes), organisations, locations, projects, packages
- ✅ **Project-level officer SMS** (2026-06-12) — `officer_messaging` on `ticketing.projects`; `GET/PATCH /projects/{id}/messaging`; Celery `notify_officer_assignment`; wired on create / escalate / reassign; Settings → Projects → Messaging UI; go-live check **F1**
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
  - Sidebar: hides redundant email in bypass/demo mode (BypassRoleSwitcher in header)
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

- ✅ **Chatbot-side QR integration** (2026-05-07, Cursor):
  - `channels/REST_webchat/app.js` + `channels/webchat/app.js` — `getUrlParams()` reads `t`; `/introduce` payload now JSON with `province`, `district`, `flask_session_id`, `t`
  - `backend/orchestrator/config/domain.yml` — 5 new custom slots: `qr_token`, `package_id`, `package_label`, `project_code`, `location_code`
  - `backend/actions/utils/ticketing_dispatch.py` — `fetch_qr_scan(token)` helper (GET `/api/v1/scan/{token}`, treats 404/410/422/network errors as "no token", never raises); `dispatch_ticket(... package_id=…)` forwards to ticketing
  - `backend/shared_functions/location_mapping.py` — `resolve_location_code_to_names()` (joins `ticketing.locations` + `location_translations` to derive district + province from a `location_code`)
  - `backend/actions/generic_actions.py` — `ActionIntroduce.parse_introduce_payload()` + `_resolve_qr_token()`; sets all 7 slots when token is valid; `ActionMainMenu` uses utterance index 3 ("You are reaching out from {package_label}, {district} District.") when QR data is present
  - `backend/actions/utils/utterance_mapping_rasa.py` — added EN + NE utterance index 3 for `action_main_menu`
  - `backend/actions/action_submit_grievance.py` — both standard + SEAH submit paths now pass `project_code=tracker.get_slot("project_code") or "KL_ROAD"` and `package_id=tracker.get_slot("package_id")` to `dispatch_ticket`
  - `tests/test_qr_token_integration.py` — 17 unit tests (fetch_qr_scan happy/error paths, location resolution, dispatch_ticket package_id propagation)
  - Operational notes (env override + 422 data gotcha + local recipe): see "QR Token Scan Flow" in `docs/COMMIT_STRATEGY.md`

- ✅ **Demo bypass roster** (2026-05-12, `07edd4d` + `dee4421`):
  - **Backend:** dev bypass `CurrentUser.organization_id` reads optional `X-Internal-Organization-Id` (still defaults to `DOR` when absent).
  - **ticketing-ui:** Removed hardcoded `MOCK_OFFICERS`. With `NEXT_PUBLIC_BYPASS_AUTH=true`, the header switcher lists officers from `GET /api/v1/users/roster` (same `ticketing.user_roles` as Settings). Cookie renamed to `grm_bypass_user` (proxy forwards org); legacy `grm_mock_user` is cleared on write and still read if the new cookie is missing.
  - **API client:** `OfficerRosterEntry` + `listOfficerRoster()` in `lib/api.ts`.

- ✅ **Roles catalog + officer onboarding + Keycloak webhook** (2026-05-12, `c60d8ee` + `578ef24`):
  - **Alembic:** `n4p6r8t0` → `roles.description`, `roles.workflow_scope`; `o5p7q9r1` → `ticketing.officer_onboarding` (`invited` \| `active`), backfill existing roster users as `active`. Run from repo root: `cd ticketing/migrations && alembic upgrade head` (see `docs/deployment/DOCKER.md`).
  - **Backend:** `ticketing/constants/grm_role_catalog.py` + `ticketing/seed/grm_roles.py`; `POST /api/v1/webhooks/keycloak` (header `X-Keycloak-Webhook-Secret` = `KEYCLOAK_WEBHOOK_SECRET`); invite seeds `UserRole` + `OfficerOnboarding`; roster includes `onboarding_status`; `ticketing/utils/organization_identifier.py` for server-allocated org IDs; locations/org create path updated.
  - **Compose:** `KEYCLOAK_WEBHOOK_SECRET` passed into `ticketing_api` and `ticketing_api_auth` (`docker-compose.grm.yml`).
  - **ticketing-ui:** Settings — role catalog editor (`PATCH /api/v1/roles/{id}`), officers roster Invited/Active badges, invite copy; `lib/api.ts` — `GrmRole`, `listRoles`, `updateRole`, optional `organization_id` on org create.

- ✅ **Reports — Overview, Pivot, Quarterly email** (2026-05-26, `b871b75` + `840cbea` on `integration/seah-claude`):
  - **Spec:** `docs/ticketing_system/09_reports_and_report_builder.md` — §2–§11 implemented; **§12 Summary** specified; §13 answered; **§14 overdue episodes locked** (`ticket_overdue_episodes` + `tickets.current_overdue_episode_id`; `days_overdue` at end; display days on read).
  - **Backend:** `report_rows.py`, `pivot_table.py`, `report_export.py`, `report_limits.py`, `quarterly_assignments.py`, `quarterly_library.py`; `ticketing/api/routers/reports.py` — query, build, export, quarterly-plan/library/assignments.
  - **UI:** `channels/ticketing-ui/app/reports/page.tsx` — tabs: Overview | Pivot | Quarterly email (`local_admin`); `QuarterlyPlanTab.tsx`; auth-safe XLSX download via `downloadApiFile`.
  - **Quarterly model:** Report **library** (named templates) + **assignments** (max 3 per role per calendar quarter); Celery sends one email per assignment; caps in `report_limits` (super_admin JSON).
  - **Auth stack:** `grm_ui_auth` :3002 → `ticketing_api_auth` :5003.

**Restore / revert roles batch:** `git revert 578ef24` (UI), then `git revert c60d8ee` (backend). After reverting the backend commit, roll back DB with Alembic if needed: `alembic downgrade o5p7q9r1` then step before `n4p6r8t0` per your head revision (see `DOCKER.md`).

### In progress / next
- ✅ **SLA overdue episodes (§14)** — migration `x9y1z3a5`, writers in escalation/tickets, backfill script
- ✅ **Reports Summary tab (§12–§13)** — `GET /api/v1/reports/summary` + UI tab
- 🔲 **Visual test + polish** — click through all demo scenarios in browser (http://localhost:3002 auth / :3001 bypass)
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

**Proto auth / demo:** `ticketing/api/dependencies.py` — when `KEYCLOAK_ISSUER` is unset, requests without a Bearer token resolve to `mock-super-admin` unless the Next.js proxy sends `X-Internal-User-Id` / `X-Internal-Role` (and optionally `X-Internal-Organization-Id`) from the `grm_bypass_user` cookie (`NEXT_PUBLIC_BYPASS_AUTH` demo UI). Replace with Keycloak JWT validation for production (`KEYCLOAK_ISSUER` set).

---

## COMMIT LOG — feature/grm-ticketing (GRM work only)

| Hash | Date | What changed |
|------|------|-------------|
| `840cbea` | 2026-05-26 | **feat(reports)** Quarterly email tab: report library + role assignments (3/quarter/role); `QuarterlyPlanTab.tsx` |
| `b871b75` | 2026-05-26 | **feat(reports)** Overview four-section query, pivot builder, export, report_limits, Celery per-assignment dispatch |
| `71de359` | 2026-05-12 | **docs** PROGRESS: document `c60d8ee` + `578ef24`, migrations, revert / Alembic downgrade notes |
| `578ef24` | 2026-05-12 | **feat(ticketing-ui)** Settings roles editor + roster onboarding UI + org create optional id; api client `GrmRole` / `listRoles` / `updateRole` |
| `c60d8ee` | 2026-05-12 | **feat(ticketing)** Migrations `n4p6r8t0` + `o5p7q9r1`; Keycloak webhook; invite/onboarding; `grm_role_catalog` + seed; org id allocator; compose webhook secret |
| `db8e679` | 2026-05-12 | **docs** PROGRESS for demo bypass roster (`07edd4d` / `dee4421`) |
| `dee4421` | 2026-05-12 | **feat(ticketing-ui)** Demo bypass: officer switcher driven by `GET /api/v1/users/roster`; cookie `grm_bypass_user`; `listOfficerRoster` in api client |
| `07edd4d` | 2026-05-12 | **feat(ticketing)** Dev bypass auth honors `X-Internal-Organization-Id` (from proxy cookie) instead of hardcoding DOR only |
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
| ~~`ticketing/api/dependencies.py`~~ | ~~Cognito JWT validation~~ | ✅ Resolved — Keycloak JWT verification live (`ticketing/auth/keycloak_jwt.py`); mock fallback only when `keycloak_issuer` unset |
| `ticketing/tasks/notifications.py` | SMS fallback phone lookup | Needs `GET /api/grievance/{id}` from backend |
| ~~`ticketing/tasks/reports.py`~~ | ~~Cognito email dispatch~~ | ✅ Resolved — officer emails come from Keycloak-synced accounts; quarterly email dispatch built |
| `ticketing/tasks/grievance_sync.py` | `session_id` lookup | Needed for chatbot reply; see comment in file |
| `ticketing/clients/grievance_api.py` | PII fetch | Called from ticket detail to show complainant name |

---

## KNOWN ISSUES / TECH DEBT

| Issue | Severity | File | Notes |
|-------|----------|------|-------|
| `seed_workflow_assignment` log message still says `PROVINCE_1` | Low | `kl_road_standard.py:340` | Cosmetic only — actual stored value is `NP_P1` |
| `OfficerScope` seed creates `UserRole` rows only, no `OfficerScope` rows | Medium | `mock_tickets.py` | Auto-assign returns `None` for new tickets created via API; pre-seeded tickets have hardcoded `assigned_to` so demo is unaffected |
| `_scope_candidates` calls `_location_and_ancestors` twice for branch B + C | Low | `workflow_engine.py` | Minor perf: combine into one call when both branches are active |
| ~~Cognito user pool not created yet~~ | — | — | ✅ Obsolete — Cognito abandoned; Keycloak realm shipped (invites, SMTP, onboarding webhook). See `docs/deployment/16_auth_keycloak.md` |

---

## CURSOR HANDOFF

The full frontend brief is at: `docs/sprints/archive/claude-tickets/session-3-cursor-handoff.md`

That doc has: all API endpoints, request/response shapes, SLA urgency → color mapping, tab query params, action types, SEAH handling rules, and demo data IDs.

---

*Updated by Claude Code at each commit on `feature/grm-ticketing`.*
