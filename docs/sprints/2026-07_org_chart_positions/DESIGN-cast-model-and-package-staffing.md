# DESIGN — Tier cast, positions-as-titles, per-package staffing & reassignment authority

> **Status:** proposed (design locked with product owner 2026-07-23) · **Owner:** settings/workflows/officers · **Size:** L (multi-phase; foundational to the operational-role plane) · **Type:** domain-model simplification
>
> **Purpose:** replace the open operational **role catalogue** with a small, fixed-but-extensible set of **cast tiers**, make **positions** literal job titles (display only), move **who-plays-which-tier** to **per-package staffing at the project level**, and make **reassignment authority** an explicit, configurable capability. Self-contained: read this + the linked files and you can implement it.
>
> **Why this exists:** a manual review of the workflow step editor found it too complex — every step forces an admin to pick a *named role* per slot, and the ~15-role catalogue (roles + archetypes + per-role permissions) is conceptual overhead nobody outside the build understands ("what is an archetype?"). Field reality: 4–5 workflows per ministry, **hundreds of projects**, **positions that differ per project**, and contractors who give everyone inflated vanity titles that carry **zero** role information. The fix is to stop encoding org reality in the workflow and the role catalogue, and encode it where it lives: **per package, at the project level.**
>
> **Supersedes / extends:** `DESIGN-settings-redesign.md` §4.3–4.4 (StepCast, "acts as" role catalogue). Where they disagree, this wins. **Obviates** `followups/roles-catalog-cleanup-brief.md` (see §12).

---

## 1. TL;DR

1. **Collapse the operational role catalogue into 4 fixed cast tiers** — **Actor · Supervisor · Participant · Observer** — hard-coded and extensible (adding a tier is a code + seed change, never a user-facing catalogue). These tiers **already exist** as the four fields on every workflow step; we are formalising them and deleting the catalogue layer above them.
2. **Permissions become tier-derived**, not per-role. The whole archetype / per-role-permission / admin-leak-guard apparatus retires.
3. **`role_key` survives as invisible plumbing** — the enforcement layer (auto-assign, ticket access, escalation, PII boundary) keeps matching on `role_key`. The admin never sees it; the UI shows tiers.
4. **Positions become literal job titles, display-only.** One catalogue for all (government + contractor), with frictionless inline-add (server-minted `position_key`, exactly the pattern shipped in `32e80792`). Positions carry **no role/tier link** (`position_type.default_role_key` removed) — the tier is chosen at package staffing.
5. **Per-package staffing is the matrix.** Open a package → a roster of `officer · literal title · tier (per step)` → this **generates `officer_scopes`** (the enforcement rows — unchanged). Two different titles → same tier is normal and explicit.
6. **Reassignment authority is a capability (`can_reassign`), configured per project**, resolved through a fallback chain that can never dead-end. The product owner's "5th role (Resolver)" is modelled as *the staffed holder of this capability* — call it **Dispatcher**, not Resolver (clashes with the RESOLVE action).
7. The **admin ladder** (`super_admin / org_admin / project_admin / officer_admin`, `admin_scopes`) is a **separate plane and is untouched.**

The workflow stays abstract (4–5 workflows; steps = tier toggles + SLAs). The messy per-project/per-contractor reality moves out of the workflow and into per-package staffing — which is exactly the complexity the review flagged.

---

## 2. Current architecture (ground truth)

Four layers, already decoupled — read before changing anything:

```
Workflow step ──names──▶ role_key ◀──holds── officer_scope(role_key, org/loc/project/package) ──▶ officer
  (process/SOP)         (contract)              (enforcement + auto-assign)                        (person)
                              ▲
                     position.default_role_key   ← the "matrix": a position implies a role (global today)
```

- **Workflow step** already has **four tier fields** — this is the load-bearing fact for this whole design:
  `assigned_role_key` (Actor), `supervisor_role` (Supervisor), `informed_roles[]` (Participant), `observer_roles[]` (Observer), plus `informed_pii_access`. See `ticketing/models/workflow.py:78-89`.
- **Role catalogue** — `ticketing.roles`: `role_key` + `permissions[]` + `workflow_scope` + `jurisdiction_mode` + `archetype`. Seeded from `ticketing/constants/grm_role_catalog.py`; archetype→permission templates in `ticketing/constants/role_archetypes.py`.
- **`officer_scopes`** — the enforcement + auto-assign source of truth: `(user_id, role_key, organization_id, location_code, project_id, project_code, package_id, includes_children)`. `ticketing/models/officer_scope.py`.
- **Auto-assign** matches on `role_key` + jurisdiction: `auto_assign_for_workflow_step` → `_scope_candidates` (`ticketing/engine/workflow_engine.py:432-749`). Positions are **not** in this path.
- **Positions** — `position_types` (catalogue, carries **required** `default_role_key`) + `officer_positions` (holder rows, descriptive). Staffing a position **already generates a scope**: `assign_officer_position` resolves `role_key = body.role_key or pt.default_role_key`, territory from `org.territory_location_code`, then calls `create_scope_row` (`ticketing/api/routers/officer_positions.py:110-175`). Positions are *never* an access-control source (CLAUDE.md rule; keep it).

**Reassignment (as built):**
- Assignee bounces up: `REASSIGNMENT_REQUESTED` action (assignee-only), needs a reason code, routes the ticket to the resolved supervisor (`ticketing/engine/ticket_actions.py:480-533`).
- Supervisor/admin routes it on: `PATCH /tickets/{id}` `assign_to_user_id`, gated by `_can_assign_ticket` (supervisor or admin) and validated in-scope by `is_step_assignee_eligible` (`ticketing/api/routers/tickets/crud.py:587-597`).
- "Supervisor" is resolved by a **heuristic** — `resolve_supervisor` (`ticketing/services/supervisor.py`) has its explicit per-(project,step) tier stubbed as *future work* and falls back to "the next step's Handler pool." **This design fills that stub.**

---

## 3. Target model

### 3.1 The tiers (fixed, extensible)

| Tier | Meaning | Maps from today's field | Core capability |
|---|---|---|---|
| **Actor** | owns & works the case at a step | `assigned_role_key` | acknowledge, note, escalate, resolve, reply-to-complainant |
| **Supervisor** | oversees; escalation/reassign target | `supervisor_role` | + reassign, resolve, notified on SLA breach |
| **Participant** | informed **and can add notes** | `informed_roles[]` | view + note (+ assigned tasks); **no** workflow actions |
| **Observer** | informed, read-only | `observer_roles[]` | view only |

Implemented as a hard-coded constant, e.g. `ticketing/constants/tiers.py`:

```python
TIERS = ["actor", "supervisor", "participant", "observer"]   # extensible: append + seed perms
TIER_PERMISSIONS = { "actor": [...], "supervisor": [...], "participant": [...], "observer": [...] }
```

Adding a tier later = append here + a permissions migration. **No user-facing catalogue, no per-role permission editor, no `ADMIN_ONLY_PERMISSIONS` leak guard** (all retire — permissions are fixed by tier and admin caps live only on the admin plane).

**Two capabilities are NOT universal tiers — do not add tiers for them:**
- **GRC convene/decide** — a capability of *the Actor at the GRC step only*. Model as a **per-step capability flag** (e.g. `step.is_grc` or `step.extra_capabilities`), not a tier. Otherwise every Actor could convene.
- **SEAH access** — a **workflow-track** property, not a role. You can see a SEAH case because you are cast on a **SEAH-track workflow's** step. Re-key SEAH visibility from role → track + cast (find the current role-keyed SEAH filter and migrate it; see §11).

### 3.2 Positions = literal titles (display only)

- **One `position_types` catalogue for all** (government + contractor). A position is a **job title**, nothing more. It is **display-only** and must never gate access (enforce the existing "descriptive, never access-control" invariant).
- **Frictionless inline-add** during staffing: searchable picker, type a new title → created inline with a **server-minted `position_key`** (reuse `_unique_position_key`, shipped in `32e80792`). Government ladders (SDE, AE) get reused; a contractor's one-off "Senior Project Manager" is added on the spot.
- **`position_type.default_role_key` → removed** (currently `NOT NULL`, `ticketing/models/position_type.py:63`). Positions carry **no role/tier link at all**: a title's tier is inherently **per-step** (an SDE is Actor at L1, could be Supervisor elsewhere), so a position cannot hold one meaningful default. The **tier is always chosen at package staffing** (a title carries no role information — "Senior Project Manager, Company A" and "Project Officer, Company D" can be the same tier). `assign_officer_position` must require the tier explicitly (no `pt.default_role_key` fallback); `_validate_matrix`'s default-role check retires with it.

**Position-type modal (finalised).** Reviewed 2026-07-23 — the modal drops every field that assumed the old role coupling. Final shape:

| Field | Fate | Note |
|---|---|---|
| Title (English) * | keep | the literal title — the point |
| Title (Nepali) | keep | optional; "never invented" helper is good |
| Used at (office types) → `allowed_unit_types` | keep, **optional** | now purely descriptive — it also used to filter the default-role picker (`PositionTypeEditor.tsx:148-164`), a job that dies with that dropdown |
| Grievance type → `workflow_track` | **remove** | track is a workflow/staffing property, not a title's |
| Default role → `default_role_key` | **remove** | the position↔role link is gone (§3.2) |
| This position's supervisor sees → `visibility_mode` | **remove** | case visibility comes from cast + scopes, not a position attribute — a confusing parallel mechanism |
| Owning level → `owner_organization_id` | **remove from modal** | catalogue-scoping plumbing; backend already auto-stamps it (`catalog_owner_for`: super→global, org_admin→subtree). Advanced re-scope only, on edit |
| Reports to → `reports_to_position_key` | keep | **already offers positions** (from `allPositionTypes`, not roles). Descriptive-only — does **not** drive supervision/escalation (that's the tier chain; `supervisor.py`). Consider dropping the `reports_to_locus` sub-field |

Backend: drop `workflow_track` / `default_role_key` / `visibility_mode` from `PositionTypeCreate`; keep `owner_organization_id` server-set only (not in the create body). Result: a 4-field modal, one required — the "titles are trivial to add" experience the inline-add flow needs.

### 3.3 Per-package staffing = the matrix

The project-setup surface gains a **per-package staffing table** — this is the "assign roles at the project level" the product owner asked for:

```
Package C1 (Contractor A)                    Workflow: KL_ROAD Standard (4 steps)
────────────────────────────────────────────────────────────────────────────
Officer            Title (display)           Step          Tier
Ram B.             Senior Project Manager     Step 1        Actor
Sita K.            Safeguards Officer         Step 1        Participant
Hari T.            Divisional Chief           Step 1        Supervisor / Step 2 Actor
...
```

Each row **generates/maintains `officer_scopes`** via the existing `create_scope_row` path — the enforcement layer is unchanged. Semantics:
- A person cast into a step's tier for a package → one `officer_scope` keyed on that step-tier's `role_key` + package.
- **Multiplicity is expected**: same position across different levels (Supervisor@L1 + Actor@L2) and across different packages (Actor@L2 on C1 and C2) → multiple scope rows. That is normal and desired.
- **The only forbidden combination**: the same holder as **both Actor and Supervisor of the same step in the same package** (self-escalation). Validate this at staffing time.

### 3.4 Reassignment authority = a capability

Model reassignment as a capability **`can_reassign`**, not a fifth participation tier (a new tier per authority would re-explode the role count we just collapsed). The product owner's three cases fall out of *where the capability is parked*, configured per project:

| Case | Model |
|---|---|
| the supervisor reassigns | `can_reassign` on the **Supervisor** slot (default) |
| the user reassigns | `can_reassign` also granted to the **Actor** (per-step self-serve toggle) |
| another person reassigns | `can_reassign` on a **designated Dispatcher**, staffed per package (this is the "Resolver" the owner meant) |

**Resolution chain** (set at project level; every step MUST resolve to someone — this kills the current dead-end):

```
1. Designated Dispatcher (staffed per package)   ← if set
2. Supervisor slot (staffed per package)          ← default
3. Actor self-serve                                ← if the per-step toggle is on
4. project_admin                                   ← guaranteed backstop, never a dead-end
```

**Where it's configured (decision D):** the Dispatcher lives in the §3.6 per-package staffing screen's reassignment control — **project-wide by default with a per-package override** (the same two-level model), stored underneath as a `can_reassign` scope holder. It is **not** a fifth cast tier and **not** a separate settings page.

**Naming:** do **not** call it "Resolver" — `RESOLVE` already means *close the case*. Use **Dispatcher** (precise) or **Coordinator** (softer for civil servants). Spec uses **Dispatcher**.

### 3.5 Workflow step editor (simplified)

The step editor **stops picking roles or people.** A step declares its **cast structure** (which tiers exist) + **SLA** + **guidance**; who fills each tier is decided at per-package staffing (§3.3). Templates seed sensible defaults so cloning a workflow rarely needs edits. This is the surface the review flagged as too complex — four role-pickers collapse to three toggles.

**Fields (final):**
- **Step name*** — now **load-bearing for legibility.** The functional meaning that used to live in the role name ("Site Safeguards Focal Person handles L1") now lives here ("Level 1 — Site safeguards review"). Discourage generic "Step 1" names — the name *is* the documentation.
- **Step key** — server-minted, **hidden** (consistent with `position_key` / `role_key` minting; no user-facing slug).
- **Tiers — toggles, not pickers:**
  - **Actor** — always on (every step has one owner); shown as a fixed label, no control.
  - **Supervisor** — on/off. When on: escalation/SLA-breach target + default reassignment authority (§3.4).
  - **Participants** (kept informed) — on/off; view + notes, auto-added on step entry. Sub-toggle **"Participants can see complainant PII"** (default off) → `informed_pii_access`.
  - **Observers** (can view) — on/off; read-only, no notifications.
- **SLA** — Response time (hours), Resolution time (days). Last step shows "resolves here; no auto-escalation."
- **Advanced (progressive disclosure):** "Actor can self-reassign at this step" (default off; §3.4 chain otherwise) · Expected-actions guidance list.

**Helper text change:** from *"Each slot is a role — you're choosing roles here, not people or positions"* → **"Choose which tiers this step uses. You'll assign the actual officers per package when you set up each project."**

**Removed:** every role dropdown, "+ Add informed role", "+ Add observer role", and the inline "+ Create role…" flow (`StepForm` → `RoleCreateModal`) — no user roles exist to create.

**Field → storage** (step fields survive, §6): Actor → `assigned_role_key` (synthetic per-step key, always set); Supervisor on/off → `supervisor_role` (synthetic key or null); Participants/Observers on/off → the step's synthetic key held in `informed_roles[]` / `observer_roles[]` (empty = off; **no named multi-select** — multiplicity of people comes from staffing). The **donor-informed guardrail** moves from "name donor roles in the final step's informed cast" to a **staffing rule** (donor org staff cast as Participants on the final step), enforced at project go-live.

### 3.6 Per-package staffing screen (the matrix, drawn)

The one genuinely new surface — it turns "who plays which tier, per package" into `officer_scopes`. Reached from Project → Cast.

**Two-level model — the key to scale.** Not everything is per-package: the upper ladder (L2/L3 actors, GRC), observers, and donors are usually **project-wide**; only the field tiers (L1 Actor/Supervisor) differ per contractor. This maps directly onto the existing scope shape:
- **Project-wide cast** → `officer_scope(project_id set, package_id = NULL)` — covers every package (`_scope_candidates` branch E).
- **Per-package override** → `officer_scope(package_id set)` — contractor-specific field slots (branches A/D).

Set the project-wide cast **once**; override only the cells that differ per package. Most cells inherit → tens of packages stay tractable.

**Layout** — tabs for *Project-wide* + each package; body is the workflow's steps, each showing its **enabled tiers** (from §3.5) with assignment slots:

```
Project: KL Road   ·   Workflow: ADB Standard (4 levels)
[ Project-wide ] [ C1 · Contractor A ] [ C2 · Contractor B ] [ + ]

 C1 · Contractor A   (inherits Project-wide unless overridden)
  Level 1 — Site safeguards review
    Actor *       [ Ram B. · Senior Project Manager  ✕ ]   + assign     ← overridden
    Supervisor    (from project-wide: Hari T. · Divisional Chief) Override ← inherited
    Participants  (from project-wide: Sita K. · ADB focal)        Override
    Observers     —
  Level 2 — PIU / PD review
    Actor *       (from project-wide: Hari T. · Divisional Chief) Override
  Level 3 — GRC   (all project-wide — nothing to staff here)
  Reassignment: (•) Supervisor  ( ) Actor self-serve  ( ) Dispatcher […]
                                              [ Copy from package… ]
```

**Assign interaction:**
- "+ assign" on a (step, tier) slot → officer picker: search existing officers by **name / email / title**, surfacing current assignments so a person is **reused, not duplicated**.
- Not found → "Add officer": email + **title** (inline position-add, §3.2). The tier is the slot; **no role is chosen.**
- Territory is **derived** (office `territory_location_code` / package coverage), with an override — the admin never hand-enters location.

**Cell → rows.** Assigning officer O to (step S, tier T) writes, via the sanctioned writers only (`create_scope_row` / position helpers — never direct inserts):
- `officer_scope(user=O, role_key=synthetic(wf,S,T), organization_id, project_id, package_id = NULL if project-wide else P, location=derived, includes_children)`
- `officer_position(user=O, position_type=title)` — descriptive
- effective-role-key / Keycloak sync, as today.

**Multiplicity & guards:**
- Actor: one primary, pool allowed (auto-assign least-loaded). Supervisor: one/pool. Participants / Observers: many.
- **Self-escalation guard (§3.3):** reject the same person as Actor **and** Supervisor of the same (step, package) — inline error.
- **Every step needs a reachable Actor** at project-wide *or* package level → warning; blocks go-live.

**Inheritance:** a package tab shows every cell; inherited ones read "(from project-wide: X)" greyed; **Override for this package** replaces just that cell; clearing reverts. **Copy from package …** pre-fills a new package from a sibling — the bulk lever for similar contractors.

**Reassignment (§3.4):** a package-level control — Supervisor (default) · Actor self-serve · **Dispatcher** (staff a person). Feeds `resolve_reassignment_authority`; go-live requires every step to resolve to someone.

**SEAH:** a SEAH-track workflow is staffed on its own track view, invisible to standard officers — never mixed into the standard cast (§3.1 track isolation).

**Backend:** an **orchestration over existing primitives** (`create_scope_row`, `assign_officer_position`) — no new enforcement path. A bulk endpoint may batch a package's assignments, but every row lands through the sanctioned writer so §5 invariants hold.

---

## 4. Key reframing — the tier cast already exists

The four step fields (`assigned_role_key`, `supervisor_role`, `informed_roles[]`, `observer_roles[]`) **already are** the tier cast. This design does not add a cast; it:
1. **Removes the open role catalogue** above those fields (no more user-authored named roles / archetypes).
2. **Derives permissions from the tier** (which field the person sits in), not from a per-role `permissions[]`.
3. **Moves staffing to per-package** and generates scopes from it.
4. **Keeps `role_key` as the (now system-managed) join key**, so `_scope_candidates`, ticket access, and escalation are untouched.

This makes the migration far gentler than a teardown — existing workflows keep their step fields; only the layer *above* changes.

---

## 5. Invariants that MUST be preserved

Pinned by tests — do not regress:
- **`officer_scopes` stays the single enforcement + auto-assign source of truth.** Positions/matrix are *authoring/generator* layers only. (`test_ticket_access_matrix`, `test_authz_matrix_extended`)
- **PII boundary** — no complainant PII columns in `ticketing.*`; ticketing decrypts nothing. (`test_pii_boundary`, `test_boundary_policy`)
- **`public.*` boundary** — the closed table set in CLAUDE.md §Data-rules. New tables are `ticketing.*` with soft `String(64)` refs, **no FKs into `public.*`**.
- **Admin plane untouched** — `admin_scopes` + `ADMIN_ROLE_KEYS = {super_admin, org_admin, project_admin, officer_admin}`. (`test_admin_ladder`, `test_org_authz`)
- **Positions never gate access.** (existing invariant)
- All new models: `__table_args__ = {"schema": "ticketing"}`; forward DDL via the ticketing Alembic stream only.

---

## 6. Mechanism — how `role_key` is recycled

**Recommended (lowest risk): keep the four step fields as the tier storage; `role_key` values are per-step-tier and permissions are tier-derived.**

- Existing workflows keep their named `role_key`s in the step fields; each is now understood as *the holder of that tier at that step*, and its effective permissions come from `TIER_PERMISSIONS[tier]` (derived from which field it sits in), **not** from `roles.permissions`.
- New/simplified workflows mint a **synthetic** per-step-tier key when a slot is enabled (e.g. `wf:{workflow_key}:{step_key}:actor`) so pools stay separate per step. The value is opaque plumbing; the UI shows the tier. **Existing named keys coexist** — they are never renamed (don't churn live data); only newly-enabled slots mint synthetic keys.
- Per-package staffing writes `officer_scopes` keyed on whatever the step-tier's `role_key` is. `_scope_candidates(role_key, …)` is unchanged.

**Permissions resolution (decided — Option A):** derive the tier from the **step field** the role sits in — no `roles` schema change, no `tier` column, no materialized view (an MV would re-implement the `_scope_candidates` match in SQL — a second source of truth, forbidden by §5 — and churn on every escalation). Precedence when a user matches >1 field on a step: **Actor > Supervisor > Participant > Observer** (the §3.3 self-escalation guard already prevents the Actor+Supervisor overlap). **Only** if the Supervisor queue tab proves slow, materialize *supervisor membership* at write-time the way `ticket_viewers` already handles informed/observer (`escalation._apply_step_tier_roles`) — a normal projection table maintained by the same Python logic; never an MV or a column. Verify that hot path exists before building it.

**Alternative (cleaner, more invasive — do NOT default to it):** add an explicit `(workflow_step, tier, user_id, package)` cast table and make auto-assign read it directly, deriving `officer_scopes` from it. More elegant, but it moves the enforcement source — out of scope unless Option A proves insufficient.

---

## 7. Workstreams (phased)

Each phase ships independently and keeps the suite green. Build/run/migrate/seed via Docker only (`dcg = docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml`).

### Phase 0 — Roles-catalogue cleanup — **DROPPED**
The original brief (`followups/roles-catalog-cleanup-brief.md`: rename "Archetype" → "This role acts as"; server-mint `role_key`) polishes the operational Roles tab — a surface this design **removes** (§7 Phase 3). Renaming a label and de-slugging a create modal that are both being deleted is throwaway work. **Do not do it.** (Reconsider only if the tier build is deferred for months with the Roles tab live in production — then a one-line stopgap label, nothing more.)

### Phase 1 — Tiers + tier-derived permissions (backend, no UI change yet)
- Add `ticketing/constants/tiers.py` (`TIERS`, `TIER_PERMISSIONS`). Map the four step fields → tiers.
- Introduce tier-derived permission resolution; make it the source for capability checks. Reconcile with the **current** action gates (today ESCALATE/RESOLVE are gated by *assignment*, not by a `tickets:*` permission — see `actions.py:92`). Decide per-capability whether it's assignment-based or tier-permission-based and document it.
- Keep `roles.permissions` readable during transition; stop writing new per-role permissions.
- **Accept:** capability checks pass from tier; `test_ticket_access_matrix`, `test_authz_matrix_extended`, `test_workflow_step_roles` green.

### Phase 2 — Positions as titles
- `position_type.default_role_key` → nullable (schema + Alembic migration in the ticketing stream; header per CLAUDE.md). `PositionTypeCreate.default_role_key` → optional.
- Ensure inline-add title flow works with a null default (tier chosen later at staffing).
- **Accept:** create a position with no default role; `test_position_types` updated + green.

### Phase 3 — Per-package staffing surface (the matrix)
- New per-package staffing view: for a package, list/edit `officer · title · (step, tier)`; each row writes `officer_scopes` via `create_scope_row` (the only sanctioned writer). Enforce the §3.3 self-escalation guard.
- Auto-assign continues to resolve via `_scope_candidates` on the generated scopes.
- **Remove the operational Roles tab entirely** (`RolesTab.tsx` + create/edit/delete/permission UI + the user-facing `POST/PATCH/DELETE /roles` surface). Its jobs move: tiers → the step editor; who + jurisdiction → package staffing; Standard/SEAH → the workflow track. **The `roles` table stays** as invisible plumbing (system tier-holder rows). **The admin role/scope surface** (`admin_scopes`, the ladder) is separate and **untouched.** The step editor becomes tier toggles (Actor required; Supervisor/Participant/Observer optional, seeded by templates) with progressive disclosure.
- **Accept:** staff a package end-to-end (two contractors, different titles, same tier) → tickets auto-assign correctly per package; SEAH still isolated.

### Phase 4 — Reassignment authority
- `can_reassign` capability + per-project config (Dispatcher slot, Actor self-serve toggle, Supervisor default).
- Replace `resolve_supervisor`'s heuristic with `resolve_reassignment_authority` implementing the §3.4 chain (Dispatcher → Supervisor → Actor-self → project_admin). Fix the misleading dead-end message in `request_reassignment` (`ticket_actions.py:492`).
- **Project go-live check:** every step resolves to a reassignment authority (add to `project_go_live` service).
- **Accept:** a bounced ticket always lands on a real authority; go-live blocks a step with no reachable reassigner; `test_escalation_engine` + new reassignment tests green.

### Phase 5 — GRC + SEAH re-keying, cleanup
- GRC convene/decide → per-step capability flag (retire `grc_committee` archetype). SEAH access → track-derived; migrate the role-keyed SEAH filter.
- Remove archetype apparatus (`role_archetypes.py` archetype/permission templates, `validate_operational_permissions`, the archetypes endpoint) once nothing references it.
- **Accept:** GRC step convene works via the flag; SEAH isolation holds via track; `test_seah_leak_notifications`, `test_roles_crud` updated + green.

---

## 8. Migration plan (existing data)

- **Existing workflows/steps:** keep their step fields as-is; they become tier holders with tier-derived permissions. No step rewrite required.
- **Existing operational roles** (`site_safeguards_focal_person`, `pd_piu_safeguards_focal`, `grc_chair`, `grc_member`, `seah_national_officer`, `seah_hq_officer`, observers — from `grm_role_catalog.py`): retained as system roles (plumbing); their permissions become tier-derived. They stop appearing as an editable catalogue.
- **Existing `officer_scopes` / tickets:** unchanged — `role_key`-keyed enforcement keeps working.
- **Seed/demo** (`kl_road_standard.py`, `kl_road_seah.py`, `mock_tickets.py`): update to the tier/staffing model; keep the two demo scenarios intact.

---

## 9. Permissions matrix (proposed — reconcile with current gates in Phase 1)

| Capability | Actor | Supervisor | Participant | Observer | Dispatcher | GRC-step Actor |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| view | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| note | ✅ | ✅ | ✅ | — | ✅ | ✅ |
| acknowledge | ✅ | ✅ | — | — | — | ✅ |
| escalate | ✅ | ✅ | — | — | — | ✅ |
| resolve | ✅ | ✅ | — | — | — | ✅ |
| reassign (`can_reassign`) | toggle | ✅ | — | — | ✅ | — |
| reply-to-complainant | ✅ | ✅ | — | — | — | ✅ |
| grc:convene / decide | — | — | — | — | — | ✅ (flag) |

Admin caps (`settings:write`, `users:invite`, `projects:manage`, …) live only on the **admin plane** and never appear here.

---

## 10. Vocabulary (UI)

- Tiers: **Actor · Supervisor · Participant · Observer** (Participant = informed + can note; Observer = read-only). The step editor shows these as toggles with plain glosses.
- Reassignment authority: **Dispatcher** (or Coordinator) — never "Resolver."
- Position field: **the person's title** (free/inline); tier shown as quiet provenance ("Ram B. — Senior Project Manager · acts as Actor at Step 1").

---

## 11. Test impact

- **Must stay green (invariants):** `test_pii_boundary`, `test_boundary_policy`, `test_ticket_access_matrix`, `test_authz_matrix_extended`, `test_admin_ladder`, `test_org_authz`.
- **Rewrite to the new model:** `test_roles_crud` (catalogue → tiers), `test_workflow_step_roles`, `test_position_types` (nullable default role), `test_role_delete_guard`, `test_escalation_engine` (+ new reassignment-chain cases), `test_seah_leak_notifications` (track-keyed).
- **New:** per-package staffing → scope generation; self-escalation guard; reassignment resolution chain; go-live "every step has a reassigner" check.
- Locate the current **role-keyed SEAH filter** (query-level) and add a test that SEAH isolation holds when keyed on track.

---

## 12. What this does to the original roles-catalogue brief

`followups/roles-catalog-cleanup-brief.md` (Task A rename, Task B server-mint) is **not done** — it is **obviated**, not merely subsumed. Both tasks polish the operational Roles tab, which this design deletes (Phase 3), and the "archetype" it renames retires entirely. There is no user-authored operational role left to mint a key for and no archetype field to relabel. Mark the brief closed as *"obviated by DESIGN-cast-model-and-package-staffing.md — Role tab removed, archetype retired."*

---

## 13. Out of scope / deferrals

- Real-time notification upgrades (SSE) — unchanged, still proto in-app badges.
- The "cleaner but invasive" explicit-cast-table mechanism (§6 alternative) — only if Option A proves insufficient.
- Any change to the **admin plane** or the **PII vault / grievance API** boundary.

> Log any deferral taken during implementation in this sprint's `followups/` + `docs/TODO.md`, same commit (repo deferral-logging rule).
