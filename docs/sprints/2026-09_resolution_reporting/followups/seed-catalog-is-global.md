# `GRM-120` — DOR's seeded catalog is global, so a second ministry would inherit it

**Deferred 2026-09-15**, while specifying `GRM-116`. Logged here and in
[`SPINE.md`](../../../SPINE.md) per the standing deferral rule.
**Kind:** `debt` — question 4: correct for one ministry today, knowingly wrong for two, and not this
lane's to fix.

> **Narrowed 2026-09-15 (Q-10).** The owner decided that resolution actions belong to one organization
> and that **every workflow and template belongs to an organization**. So this lane now does the
> workflow and template part itself: `GRM-116`'s migration gives each its projects' ministry, and
> `GRM-122` lets admins move it lower. **What stays here:** position types, roles and project types;
> the delete rule; the read filter and write guards on the rest of the workflow editor.

## How it was found

The owner asked what happens to the resolution-action catalog *"if tomorrow we have ministry of
interior or customs plugged in the same grievance redressal software."* The answer is the org-scoped
catalog rule ([`11`](../../../ticketing_system/11_roles_and_permissions.md) §3.3): an item owned by an
organization is visible only at that organization and below; an item with no owner is global. Checking
how the seed uses that rule found the gap.

## Measured inventory — dev DB, 2026-09-15

| Catalog item | Global (`owner_organization_id IS NULL`) | Owned by `DOR` | After this lane |
|---|---|---|---|
| Workflow definitions | **3 of 3** (`KL_ROAD_STANDARD`, `KL_ROAD_SEAH`, one draft) | 0 | **all owned** — `GRM-116`, `GRM-122` |
| Templates | none on dev | — | **owned** — `GRM-116`, `GRM-122` |
| Resolution actions | — | — | **never global** — `GRM-116` |
| Position types | 3 of 8 | 5 | unchanged — **this item** |
| Roles, project types | not measured | not measured | unchanged — **this item** |

⚠ **Dev DB only.** Staging and production are not measured; the seed is the same code, so expect the
same shape.

## Why it matters

The seed's rule is *"system/TOR seed = global"*, which was right when the platform served one
ministry. It conflates two things: items that are genuinely platform-wide (a *super_admin* role) and
items that are **DOR's** (DOR position titles, road-project roles). On the day a Ministry of Interior
root is created, its `org_admin` sees DOR's position titles in staffing and DOR's project types in its
pickers.

## Why not now

One ministry is live. Nothing is wrong for it. Re-homing is a data decision about each seeded item.

## Definition of done

1. Every seeded **position type, role and project type** is classified **platform-wide** (stays
   global) or **DOR's** (owned by the DOR root). The classification is written down, not inferred.
2. A data migration re-homes DOR's items; the seed scripts create them owned by DOR from then on.
3. A test: with a second government root seeded, none of DOR's items is listed for its `org_admin`.
4. **Codes for a second ministry's resolution actions.** Action codes are platform-unique and the
   starter codes (`CLASSIFIED`, `ROAD_REPAIRED` …) are DOR's. Decide how a second ministry's starter
   actions are coded before it is onboarded.
5. **Decide the delete rule.** `workflow_definitions.owner_organization_id` (and, per doc 11 §3.3, the
   other catalog kinds) is `ON DELETE SET NULL`: deleting an organization leaves its workflows with no
   owner — and a workflow with no owner can offer no resolution action. The resolution-action catalog
   uses `RESTRICT`. Measure each kind's FK and choose one rule for all.
6. **Check the read filter.** `apply_catalog_scope` (`services/admin_access.py`) shows a scoped
   `org_admin` global items plus items owned **within** its subtree — not items owned **above** it,
   though the ownership rule makes those usable there. `GRM-122` adds an ancestor-aware template list;
   whether the position-type and role pickers need the same was not checked. ⚠ Also: a
   **country-wide** `org_admin` (scope with no organization) and any non-admin caller pass through
   that filter unnarrowed — with two ministries in one country, that admin sees both ministries'
   catalogs.
7. **Check the write guards** *(added 2026-09-15, `GRM-119` review)*. `can_mutate_workflow` checks
   only the **track**, and `_load_workflow` loads by id with no ownership check — so any
   standard-track `org_admin` can edit the steps of another organization's workflow. `GRM-119`'s
   resolution panel and `GRM-122`'s organization change check reach on the workflow's organization;
   decide whether steps, notifications and bindings get the same rule. ⚠ Also `catalog_owner_for`
   stamps **global** on items a country-wide `org_admin` authors.
8. **Project bindings vs a workflow's organization** *(added 2026-09-15, `GRM-122`)*. Nothing checks
   that the projects using a workflow sit under its organization; `GRM-122` shows them and does not
   refuse. Decide whether a binding across ministries should be possible at all.

## Trigger

**Before any second ministry or institutional root is onboarded** — not before.
