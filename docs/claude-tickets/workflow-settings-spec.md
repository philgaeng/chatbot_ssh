# Workflow Settings — Product + Engineering Spec

# Status: DRAFT — open questions marked ❓

# Last updated: 2026-04-21

---

## 1. Purpose

Allow GRM administrators to design, version, and assign escalation workflows
**without writing code**. An admin picks a template (Default GRM or Default SEAH),
customises the steps, sets SLA targets and role assignments, and publishes.
New tickets automatically follow the latest published version of their assigned workflow.

---

## 2. Scope

| In scope                                                    | Out of scope                                              |
| ----------------------------------------------------------- | --------------------------------------------------------- |
| Create / edit / publish workflow definitions                | Conditional branching (always-linear chain for now)       |
| Step reorder (up/down), add step, remove step               | Parallel steps                                            |
| SLA per step (response hours + resolution days)             | Automated complainant notifications per step (post-proto) |
| Role assignment per step                                    | Cross-organisation workflow sharing                       |
| Template library (Default GRM, Default SEAH, admin-created) | Workflow import/export (future)                           |
| Workflow assignment to org/project/priority                 |                                                           |
| Version snapshots (in-flight tickets unaffected by edits)   |                                                           |
| `admin_seah` role gates SEAH workflow editing               |                                                           |

---

## 3. Roles

### 3.1 New role: `admin_seah`

Add to the role table and SEAH_CAN_SEE_ROLES set.

| Role          | Can edit Standard workflows | Can edit SEAH workflows | Can manage templates |
| ------------- | --------------------------- | ----------------------- | -------------------- |
| `super_admin` | ✅                          | ✅                      | ✅                   |
| `local_admin` | ✅                          | ❌                      | ✅ (standard only)   |
| `admin_seah`  | ❌                          | ✅                      | ✅ (SEAH only)       |

SEAH workflow definitions must be **hidden** from non-SEAH admins in the UI
(same gate as SEAH tickets: `canSeeSeah`).

---

## 4. Data model changes

### 4.1 `ticketing.workflow_definitions` — add columns

| New column           | Type                                   | Purpose                                              |
| -------------------- | -------------------------------------- | ---------------------------------------------------- |
| `version`            | `INTEGER` default 1                    | Increments on each publish                           |
| `is_template`        | `BOOLEAN` default false                | True = reusable template, not directly assigned      |
| `template_source_id` | `STRING` nullable                      | ID of template this was cloned from                  |
| `status`             | `ENUM('draft','published','archived')` | Only published workflows are assigned to new tickets |
| `workflow_type`      | `ENUM('standard','seah')`              | Gates visibility by role                             |
| `updated_by_user_id` | `STRING` nullable                      | Audit                                                |

### 4.2 `ticketing.workflow_steps` — add columns

| New column         | Type                    | Purpose                                                            |
| ------------------ | ----------------------- | ------------------------------------------------------------------ |
| `stakeholders`     | `TEXT[]` nullable       | Role keys notified at this step (already in model, ensure exposed) |
| `expected_actions` | `TEXT[]` nullable       | Informational list shown to officer                                |
| `is_deleted`       | `BOOLEAN` default false | Soft-delete when step removed from a draft                         |

### 4.3 `ticketing.tickets` — add column

| New column         | Type      | Purpose                                                       |
| ------------------ | --------- | ------------------------------------------------------------- |
| `workflow_version` | `INTEGER` | Snapshot of `workflow_definitions.version` at ticket creation |

**In-flight ticket rule (see §6):** once a ticket is created it holds
`workflow_version`. Edits to the workflow do NOT affect existing tickets.

### 4.4 New table: `ticketing.workflow_assignments`

Already exists. Ensure it has:

| Column            | Type              | Notes                                      |
| ----------------- | ----------------- | ------------------------------------------ |
| `assignment_id`   | `STRING` PK       |                                            |
| `workflow_id`     | `STRING` FK       | Points to a **published** workflow         |
| `organization_id` | `STRING` nullable | Null = applies to all orgs                 |
| `location_code`   | `STRING` nullable | Null = all locations                       |
| `project_code`    | `STRING` nullable | Null = all projects                        |
| `priority`        | `STRING` nullable | Null = all priorities                      |
| `is_default`      | `BOOLEAN`         | True for the org/project-agnostic fallback |

❓ **Q-A** Does the current `WorkflowAssignment` model already have `is_default`?
If not, we add it in the migration.

---

## 5. Templates

### 5.1 Built-in templates (seeded, never editable directly)

**Default GRM** (`template_key: default_grm`)

| Order | Step key      | Display name              | Role                         | Response (h) | Resolution (d) |
| ----- | ------------- | ------------------------- | ---------------------------- | ------------ | -------------- |
| 1     | LEVEL_1_SITE  | Level 1 — Site Safeguards | site_safeguards_focal_person | 24           | 2              |
| 2     | LEVEL_2_PIU   | Level 2 — PD/PIU          | pd_piu_safeguards_focal      | 48           | 7              |
| 3     | LEVEL_3_GRC   | Level 3 — GRC             | grc_chair                    | 72           | 21             |
| 4     | LEVEL_4_LEGAL | Level 4 — Legal           | adb_hq_safeguards            | null         | null           |

**Default SEAH** (`template_key: default_seah`)

| Order | Step key              | Display name               | Role                  | Response (h) | Resolution (d) |
| ----- | --------------------- | -------------------------- | --------------------- | ------------ | -------------- |
| 1     | SEAH_LEVEL_1_NATIONAL | SEAH L1 — National Officer | seah_national_officer | 24           | 7              |
| 2     | SEAH_LEVEL_2_HQ       | SEAH L2 — HQ Officer       | seah_hq_officer       | 48           | 14             |

### 5.2 Admin-created templates

Any workflow can be saved **as a template** (`is_template = true`).
Templates appear in the "New workflow" picker alongside the two built-ins.
Templates are never directly assigned to projects — they are always cloned first.

---

## 6. In-flight ticket versioning

**Recommendation adopted:** version snapshot on publish.

When an admin publishes edits to a workflow:

1. `workflow_definitions.version` increments.
2. New tickets created after the publish get the new `workflow_version`.
3. Existing tickets keep their original `workflow_version` — the step IDs
   they hold remain valid (we never hard-delete steps, only soft-delete).
4. The UI warns: _"X tickets are currently active on version N.
   They will continue on that version. New tickets will use version N+1."_

**No migration of in-flight tickets.** This is the safest default.
Post-proto: add a "migrate in-flight" action for admins who want it.

❓ **Q-B** Is this acceptable for the demo? Or does the demo need simpler
"edits take effect immediately" behaviour (acceptable if there are zero real
in-flight tickets)?

---

## 7. UI — Workflows tab

### 7.1 Tab layout

```
Settings → Workflows tab

[+ New workflow]                                    [Search…]

┌──────────────────────────────────────────────────────────┐
│ KL Road Standard GRM          Standard  v3  Published    │
│ 4 steps · assigned to KL_ROAD / DOR                 Edit │
├──────────────────────────────────────────────────────────┤
│ KL Road SEAH  🔒              SEAH     v1  Published      │
│ 2 steps · assigned to KL_ROAD / DOR                 Edit │
├──────────────────────────────────────────────────────────┤
│ Default GRM Template          Standard  v1  Template      │
│ 4 steps · built-in                    Clone / View        │
├──────────────────────────────────────────────────────────┤
│ Default SEAH Template  🔒     SEAH     v1  Template       │
│ 2 steps · built-in                    Clone / View        │
└──────────────────────────────────────────────────────────┘
```

- SEAH rows hidden from non-SEAH admins.
- Status badge: `Draft` (yellow) / `Published` (green) / `Archived` (gray) / `Template` (blue).

### 7.2 Workflow editor — step pipeline

Opened by clicking Edit or creating a new workflow.
Steps are displayed as **a flat vertical list of tiles**, one per step.
Think Spotify queue: each step is a row with drag handles replaced by
up ▲ / down ▼ buttons on the left.

```
┌─────────────────────────────────────────────────────────────┐
│  Workflow: KL Road Standard GRM         Status: Draft  [Publish]
│  Type: Standard   Version: 3 (editing)
└─────────────────────────────────────────────────────────────┘

▲▼  ①  Level 1 — Site Safeguards
        Role: site_safeguards_focal_person
        Response: 24h   Resolution: 2d          [Edit]  [✕]

▲▼  ②  Level 2 — PD/PIU Safeguards
        Role: pd_piu_safeguards_focal
        Response: 48h   Resolution: 7d          [Edit]  [✕]

▲▼  ③  Level 3 — GRC
        Role: grc_chair
        Response: 72h   Resolution: 21d         [Edit]  [✕]

▲▼  ④  Level 4 — Legal
        Role: adb_hq_safeguards
        Response: —     Resolution: —           [Edit]  [✕]

        [+ Add step]

────────────────────────────────────────────────
Assigned to:
  DOR · JHAPA · KL_ROAD · (all priorities)   [✕]
  DOR · MORANG · KL_ROAD · (all priorities)  [✕]
  [+ Add assignment]

[Save draft]  [Discard changes]  [Publish]
```

### 7.3 Step edit — inline expand (not a modal)

Clicking **Edit** on a step expands it in-place (accordion style):

```
▲▼  ②  Level 2 — PD/PIU Safeguards              [Collapse] [✕]
   ┌────────────────────────────────────────────────────────┐
   │ Display name   [PD/PIU Safeguards Focal          ]     │
   │ Step key       [LEVEL_2_PIU                      ]     │
   │ Assigned role  [pd_piu_safeguards_focal      ▾]        │
   │ Response time  [48] hours                              │
   │ Resolution     [7 ] days                               │
   │ Stakeholders   [adb_national_project_director    ] + ✕ │
   │                [adb_hq_safeguards                ] + ✕ │
   │                [+ Add stakeholder]                     │
   │ Expected       [Investigate root cause           ] + ✕ │
   │ actions        [Contact contractor               ] + ✕ │
   │                [+ Add action]                          │
   └────────────────────────────────────────────────────────┘
```

Changes are saved to the draft in-memory until **Save draft** or **Publish**.

### 7.4 New workflow flow

1. Admin clicks **+ New workflow**.
2. Modal: "Start from template"
   - Default GRM (4 steps) ← pre-selected for standard
   - Default SEAH (2 steps) ← only shown to `canSeeSeah`
   - Any admin-created template
   - Blank (0 steps)
3. Admin enters a name and type (Standard / SEAH).
4. Editor opens pre-populated with template steps (all editable).

### 7.5 Workflow assignment panel

Below the step list. Lets admin bind the workflow to
`(organization_id, location_code, project_code, priority)` tuples.
Any field can be left blank to mean "all".

One row = one assignment. Admins can add multiple rows.
Example: one row for NORMAL, one for HIGH, one for SEAH.

❓ **Q-C** Should there be a visual conflict detector that warns when two
published workflows match the same assignment tuple?

---

## 8. API endpoints needed

All under `/api/v1/` in the ticketing backend.

| Method   | Path                                          | Purpose                                 |
| -------- | --------------------------------------------- | --------------------------------------- |
| `GET`    | `/workflows`                                  | List all (filtered by type, status)     |
| `POST`   | `/workflows`                                  | Create new (from template or blank)     |
| `GET`    | `/workflows/{id}`                             | Full detail with steps                  |
| `PATCH`  | `/workflows/{id}`                             | Update metadata (name, status)          |
| `POST`   | `/workflows/{id}/publish`                     | Publish draft → increments version      |
| `POST`   | `/workflows/{id}/clone`                       | Clone to new draft (for templates)      |
| `POST`   | `/workflows/{id}/archive`                     | Archive published workflow              |
| `GET`    | `/workflows/{id}/steps`                       | List steps                              |
| `POST`   | `/workflows/{id}/steps`                       | Add step                                |
| `PATCH`  | `/workflows/{id}/steps/{step_id}`             | Edit step                               |
| `DELETE` | `/workflows/{id}/steps/{step_id}`             | Soft-delete step                        |
| `POST`   | `/workflows/{id}/steps/reorder`               | Submit new order array `[step_id, ...]` |
| `GET`    | `/workflows/{id}/assignments`                 | List assignments                        |
| `POST`   | `/workflows/{id}/assignments`                 | Add assignment                          |
| `DELETE` | `/workflows/{id}/assignments/{assignment_id}` | Remove assignment                       |
| `GET`    | `/workflows/templates`                        | List templates only                     |

---

## 9. Migration checklist

- [ ] Add `version`, `is_template`, `template_source_id`, `status`, `workflow_type`,
      `updated_by_user_id` to `ticketing.workflow_definitions`
- [ ] Add `is_deleted` to `ticketing.workflow_steps`
- [ ] Add `workflow_version` to `ticketing.tickets`
- [ ] Verify `is_default` exists on `ticketing.workflow_assignments` (Q-A above)
- [ ] Add `admin_seah` to `ticketing.roles` seed + AuthProvider `SEAH_CAN_SEE_ROLES`
- [ ] Backfill: set `version=1`, `status='published'`, `workflow_type` on existing rows

---

## 10. Open questions for implementation

| #   | Question                                                                                                                                          | Owner | Status                                                                        |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ----------------------------------------------------------------------------- |
| Q-A | Does `WorkflowAssignment` already have `is_default`? Check model file.                                                                            | Dev   | we can use the hardcoded ones as default for both grievance and seah workflwo |
| Q-B | For the demo: version snapshot or "edits take effect immediately"? (Zero real in-flight tickets on demo day makes "immediate" safe.)              | Phil  | edits take effect                                                             |
| Q-C | Show conflict warning when two published workflows match the same assignment tuple?                                                               | Phil  | ok                                                                            |
| Q-D | Step key (`LEVEL_2_PIU` etc) — admin-editable or auto-generated from display name? Auto-gen is safer but less readable.                           | Phil  | autogenerared then editable                                                   |
| Q-E | Hard delete of a step that has tickets currently sitting on it — block or warn + soft-delete?                                                     | Phil  | block                                                                         |
| Q-F | Templates: can a `local_admin` create templates, or super_admin only?                                                                             | Phil  | can                                                                           |
| Q-G | Workflow assignment: should an unassigned workflow (no assignment rows) be allowed to publish? Or enforce at least one assignment before publish? | Phil  | I need you to explain more                                                    |

---

## 11. Build order (suggested)

1. **Migration** — schema changes + backfill
2. **Backend** — workflow CRUD + step CRUD + reorder + publish endpoints
3. **Workflows tab list view** — cards with status badges
4. **Workflow editor** — step tiles + up/down reorder
5. **Step inline expand** — accordion edit form
6. **Assignment panel** — add/remove assignment rows
7. **New workflow modal** — template picker
8. **Template management** — save-as-template + template list
9. **`admin_seah` role** — backend guard + frontend gate

Items 1–6 cover the demo. Items 7–9 are polish.
