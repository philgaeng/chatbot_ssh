# Org Chart & Positions Sprint — Progress

> Update at **every commit** on a sprint branch. Status values: `todo` · `in_progress` · `blocked` · `review` · `done`.
> Sprint definition: [README.md](README.md) · Feature source: [`docs/ticketing_system/16_org_chart_and_positions.md`](../../ticketing_system/16_org_chart_and_positions.md)

## Ticket status

| ID | Title | Workstream | Status | Branch | Commits | Notes |
|---|---|---|---|---|---|---|
| OC-06 | Admin-setup UX/UI evaluation | ux-evaluation | todo | — | — | **Run first** — shapes OC-05 |
| OC-01 | Org tree on `organizations` + CSV import | backend-org-tree | todo | — | — | Migration serializes after HR-03 |
| OC-02 | `position_types` + matrix + `/position-types` | backend-org-tree | todo | — | — | Chains after OC-01 migration |
| OC-03 | `officer_positions` + invite pre-fill + supervisor resolver | backend-positions | todo | — | — | Needs OC-01/02 tables |
| OC-04 | Chart behaviors + SEAH leak-proofing | backend-positions | todo | — | — | Rebase on HR-04; needs OC-03 |
| OC-05 | Portal org-chart UI | portal | todo | — | — | After OC-01..04 **and** HR-06 |

## Migration head coordination (critical)

Record the actual head each migration chains onto, to keep the ticketing Alembic chain linear across both sprints.

| Revision | Ticket | Chained on (`down_revision`) | Notes |
|---|---|---|---|
| — | HR-03 (hardening) | `g0h2i4j6` | Watch: whichever lands first is the new head |
| — | OC-01 org columns | (record actual) | After HR-03 if landed, else on `g0h2i4j6` + coordinate rebase |
| — | OC-02 position_types | (OC-01 rev) | — |
| — | OC-03 officer_positions | (OC-02 rev) | — |

## Acceptance checklists

### OC-06 — UX evaluation
- [ ] Cold-start walk done as all four admin personas on the running stack (screenshots)
- [ ] Journey map (4-in-1 flow, inter-tab jumps marked)
- [ ] Scored findings table with file:line / screenshot evidence + owner per finding
- [ ] Top-5 low-IT-literacy friction points ranked with fixes
- [ ] Orphaned-state catalogue (which OC-01..04 validations already close them)
- [ ] Nepali/i18n readiness note for the admin surface
- [ ] "Does org-chart actually help?" verdict recorded **before OC-05 starts**
- [ ] Report published at `docs/ticketing_system/ui/03_admin_setup_flow_evaluation.md`; blockers/majors triaged below

### OC-01 — Org tree
- [ ] Migration: `parent_organization_id` self-FK, `unit_type`, `territory_location_code`, `territory_includes_children`, `display_name_ne`; backfill + real downgrade + safety header
- [ ] Model columns + self-relationship; `descendant_org_ids` CTE helper with cycle guard
- [ ] Router: new fields on GET/POST/PATCH; `tree=true` + `root_id` filter; cycle/unit_type/territory validation
- [ ] `POST /organizations/import` CSV: whole-file validate → single-transaction insert → idempotent upsert
- [ ] Gated at country tier (reuse `admin_access`); **authz matrix** green
- [ ] `tests/ticketing/test_org_tree.py` green (incl. authz matrix + CSV all-or-nothing)
- [ ] Manual: upgrade→downgrade→upgrade clean; existing orgs still resolve on tickets

### OC-02 — Position types + matrix
- [ ] Migration + model for `position_types` (all columns incl. `display_name_ne`)
- [ ] `/position-types` CRUD; `position_key` immutable; delete guard on in-use types
- [ ] Matrix validation (`default_role_key`, `allowed_unit_types`, `reports_to_position_key`)
- [ ] `default_role_key` edit does not re-sync holders (no side effect)
- [ ] **Authz matrix** green; SEAH-track authoring open-question logged
- [ ] `tests/ticketing/test_position_types.py` green
- [ ] Seed ~5 real DoR position types committed

### OC-03 — Officer positions + invite pre-fill
- [ ] Migration + model for `officer_positions`
- [ ] Invite pre-fill routes through existing `upsert_user_role_row` + `create_scope_row` (no direct enforcement-row writes)
- [ ] Override (explicit role/scope beats matrix); dual-hat; transfer ends old row without silent re-scope
- [ ] `/users/{id}/positions` GET/POST/DELETE; `/users/{id}/supervisor` resolver (override→derived→null)
- [ ] `validate_jurisdiction` still enforced; **authz matrix** (incl. project_admin own-scope) green
- [ ] `tests/ticketing/test_officer_positions.py` green
- [ ] Manual: invite-by-position produces correct role/scope; resolver returns override then derived

### OC-04 — Chart behaviors + SEAH
- [ ] §5.1 display (position title on roster/chips/timeline/reports)
- [ ] §5.3 supervisor visibility in Watching, `visibility_mode`-bounded, **SEAH-filtered inline**
- [ ] §5.4 prefer-own-office ranking in `auto_assign_officer` (preference, not filter)
- [ ] §5.5 escalation-notify via resolved supervisor, **suppressed on SEAH unless supervisor holds SEAH role**
- [ ] Rebased on HR-04; notify attached to post-HR-04 seam (base commit recorded)
- [ ] `tests/ticketing/test_chart_behaviors.py` green **incl. both SEAH-leak tests**
- [ ] Manual: standard supervisor sees no trace of subordinate SEAH case

### OC-05 — Portal UI
- [ ] `OrgTreeTab.tsx` (tree editor + CSV import) — new component
- [ ] `PositionTypesTab.tsx` (matrix editor + review-holders prompt) — new component
- [ ] Invite pre-fill flow (tree picker → position → pre-filled editable fields + override badge)
- [ ] Display surfaces show position title with role-label fallback
- [ ] `lib/api.ts` typed wrappers for all OC-0x endpoints; `apiFetch` signature unchanged
- [ ] **God-file untouched beyond ~5-line tab wiring**; landed after HR-06
- [ ] Vitest for extracted logic; tsc/eslint(0 hooks)/build green
- [ ] Manual flows recorded; existing tabs no regression

## Deviations / findings log

| Date | Ticket | Deviation / adjacent finding | Action |
|---|---|---|---|
| — | — | — | — |

## Sprint close checklist
- [ ] All 6 tickets `done`, CI green on integration branch
- [ ] `docs/ticketing_system/16_org_chart_and_positions.md` status → as-built (cite migrations/routers)
- [ ] Doc 16 §10 open questions resolved and recorded
- [ ] OC-06 evaluation published; findings triaged
- [ ] Summary doc written; this folder moved to `docs/sprints/archive/`; sprints index updated
