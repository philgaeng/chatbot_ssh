# Admin-scope org-staffing gaps — RESOLVED (2026-07-25)

> **Status: both gaps implemented and green (2026-07-25).** Originally logged as deferred debt
> (held 2026-07-24), then built 2026-07-25 on request. Full ticketing suite: 649 passed / 0 failed.
> See the per-gap "Implemented" notes below for the exact sites. Migration: `h4j6l8n0`.
>
> Surfaced while wiring the **Admin access** screen to scope org_admins to an org node
> (`AdminAccessTab.tsx` now sends `organization_id` instead of a free-text country code; dedup
> re-keyed on `organization_id` in `users.py`). An audit of "can a scoped org_admin build child
> orgs / add donor officers / create contractor companies" found all three **already work** — plus
> the two adjacent guard gaps below, now closed.

The three capabilities and their status (audit, 2026-07-24):

| # | Capability | Status |
| --- | --- | --- |
| 1 | org_admin creates a **child org** in his own subtree | ✅ works, correctly guarded (`locations.py:435-451` — parent must be in subtree; gov/donor roots blocked to super_admin). No gap. |
| 2 | org_admin adds a **donor (ADB) officer** to his project | ✅ works — actor/officer employer org is deliberately *not* subtree-constrained (see Gap B caveat). |
| 3 | org_admin creates a **third_party contractor** + attaches to his project | ✅ works to create+attach; ✗ can't maintain afterward → **Gap A**. |

---

## Gap A — a contractor an org_admin creates becomes unmaintainable by him (functional)

**Symptom.** An org_admin can create a `third_party` company and attach it to his project, but
**cannot later edit / rename / delete it** — only super_admin can. This partly undercuts the
intent "he can create other companies so they can be added to his project": creation works,
ongoing maintenance doesn't.

**Why.** A `third_party` is created as an independent **root** (`parent_organization_id = NULL`):
`create_organization` (`ticketing/api/routers/locations.py:387-492`) lets it through because
`third_party ∉ INSTITUTIONAL_CATEGORIES` (root-gate `locations.py:435-451` doesn't fire). It
*can't* be created as a child of the org_admin's node when that node is `government` (e.g. DOR),
because children force-inherit the parent's category (`locations.py:418-426`) — a government node
can't parent a third_party. So the contractor lands outside every subtree.

Then the maintenance guards fail: `update_organization` (`locations.py:617-622`) and
`delete_organization` (`locations.py:738-743`) both require
`can_admin_org(db, user, org_id, "standard")`, which is False for a root outside the caller's
subtree. Only super_admin's unbounded scope covers it.

**Decided design (2026-07-24) — ownership by org node, mirroring catalog ownership.** Add
`owner_organization_id` (nullable `String(64)`) to `ticketing.organizations`, analogous to the
`owner_organization_id` on `roles` / `workflow_definitions` / `position_types`. On create, when a
non-super org_admin makes a `third_party`, stamp it with `catalog_owner_for(current_user, "standard")`
— the creator's org **node**, not the person, so ownership survives the creator leaving. The
maintenance guards (`update_organization` `locations.py:617-622`, `delete_organization`
`locations.py:738-743`, and any reparent) then allow super_admin **or** when the contractor's
`owner_organization_id` is inside the caller's subtree. Because the owner is a *fixed* node (the
creator's), authority resolves to exactly **the creating org_admin + any org_admin of a
parent/ancestor org** — a sibling or unrelated org gets nothing. (Confirmed by Phil 2026-07-24:
"belongs to this org_admin and any org_admin of a parent org to his organisation.")

Implementation note: add a dedicated check (`can_admin_org(...) OR owner ∈ admin_org_scope_ids(...)`)
for the maintenance guards rather than silently widening `can_admin_org` for every caller. Rejected
alternative: auto-parenting the contractor under the creator's node — breaks the category model
(forces the contractor to inherit `government`).

**Scope of change:** schema column + ticketing-stream Alembic migration + guard extension
(`admin_access.py:250-261`) + stamp on create (`locations.py` create handler). Pin with a test:
org_admin creates third_party → can update/delete it; a sibling/unrelated org_admin cannot; an
ancestor-org org_admin can.

**✅ Implemented (2026-07-25).** Column `owner_organization_id` on `ticketing.organizations`
(model `models/organization.py`; self-FK, so `parent`/`children` relationships now pin
`foreign_keys=[parent_organization_id]`); migration `h4j6l8n0`. Stamp on create:
`locations.py` `create_organization` sets `owner = catalog_owner_for(current_user, "standard")`
for a non-super org_admin creating a `third_party`. Guard: `admin_access.can_admin_org_or_owned`
(`can_admin_org` OR `owner ∈ caller subtree`), used by `update_organization` / `delete_organization`.
Tests: `tests/ticketing/test_admin_scope_org_staffing.py` (creator/ancestor can, sibling/unowned
cannot, super always; stamp present for org_admin, absent for super).

**Residual (not fixed):** an org_admin can still *set a project's IA* / anchor to a foreign org
(unanchored → open, see Gap B), and a `third_party` created country-wide (NULL-org org_admin) is
stamped owner-less. Both minor; not tracked as debt.

---

## Gap B — project staffing is not subtree-constrained

**Decided rule (2026-07-24, confirmed by Phil).** A non-super org_admin may staff / donor-link /
attach orgs to a project **only if the project's implementing (managing) org is in his subtree — the
org he belongs to + any descendants ("children")**. The **actor / officer org stays unconstrained**
(people from any org) — that half is already correct and must **not** change.

**Current behaviour (the gap).** The project-staffing guards are **tier-only** — no project check at
all — so any org_admin can staff **any** project, including one managed outside his subtree:
- `_require_project_scope` (`locations.py:1795-1807`) short-circuits on `is_super_admin(...) or is_org_admin(...)` at **line 1803** — no project/subtree check.
- `SettingsAction.INVITE_OFFICERS` (`admin_access.py:444-455`) — passes for super/org/project/officer admin, tier only.

Affected endpoints: `add_project_donor` (`locations.py:1830-1864`), `add_project_organization`
(`locations.py:1713-1757`), `add_package_organization` (`locations.py:2293-2327`), `staff_cast_slot`
(`cast.py:83-157`).

**Fix.** Gate those endpoints for non-super org_admins on `_org_admin_covers_project(db,
current_user, project_id, track)` (`users.py:84-96`) — it already resolves "project managed by an org
in my subtree." Replace the bare `is_org_admin(...)` short-circuit at `admin_access.py:451` /
`locations.py:1803` accordingly.

**Critical caveat for whoever implements this:** constrain **which project** the caller may staff,
**not which actor/officer org** may be referenced. Cross-org actor referencing (adding a donor's or
contractor's officer to a project) is intentional — it's exactly what makes Capability 2 & the
attach-half of Capability 3 work (`validate_jurisdiction`, `officer_admin.py:98-113`, only requires
the actor org be linked to the project, not in the caller's subtree). A fix that constrains the
referenced org would break donor/contractor staffing.

**✅ Implemented (2026-07-25).** `admin_access.require_org_admin_project_scope(db, user, project)`
raises 403 when an org_admin's subtree does not manage the project — via
`org_admin_manages_project` (project's IA ∈ subtree; **unanchored project → open**, so first-time
setup / IA assignment isn't locked out). **Only the org_admin tier is checked** — super_admin and
the narrower tiers keep their prior access, so nothing regresses. Wired into: `cast.staff_cast_slot`;
`locations.py` `add/update/remove_project_organization`, `add/remove_package_organization`, and the
org branch of `_require_project_scope` (donor add/remove). The staffed **actor org stays
unconstrained**. Tests: `tests/ticketing/test_admin_scope_org_staffing.py` (IA-in-subtree ok,
foreign org_admin 403, unanchored open, non-org-admin noop).

---

## TODO
See `docs/TODO.md` → "Admin-scope org-staffing follow-ups".
