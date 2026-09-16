# Follow-up — actor-role catalog kept, not dropped (DECISION 2026-07-10 half-done)

**Logged:** 2026-07-30 (during the doc 10–14 reconciliation).
**Severity:** medium — spec-vs-code gap; no correctness bug (new model is primary, legacy is fallback), but dead-ish tables are still seeded and cited as fallback.

## What the DECISION said vs what shipped

[`DECISION-project-participants-and-supervision.md`](../DECISION-project-participants-and-supervision.md) §1 said **drop** the per-project actor-role catalog (`project_actor_roles`, `project_organizations.org_role`, `package_organizations`, `project_types.actor_roles`, `routing_org_role`, `GET/PUT /projects/{id}/actor-roles`).

**As-built (verified 2026-07-30):** the new model landed and is **primary** — `projects.implementing_agency_org_id` + `project_donors` + the staffing go-live gate (`project_go_live.py` C5). But the old catalog was **kept**:

- Models still defined: `ProjectActorRole`, `ProjectOrganization` (`ticketing/models/project.py`), `PackageOrganization` (`ticketing/models/package.py`).
- `drop_table` for the three exists **only in `downgrade()`** (`e8d4b6a0f291`, `s1t3u5v7`) — never a forward drop.
- Still **live**: `ticketing/services/project_actor_roles.py`; new projects still **seed** `project_actor_roles` (`ticketing/api/routers/locations.py:1390`); `project_types.actor_roles` still carried.
- Still **read as back-compat fallback**: `resolve_ticket_organization()` prefers `implementing_agency_org_id`, falls back to `routing_org_role`/`project_organizations`/`package_organizations` for pre-field projects; `project_go_live.py` still references `org_role`.

## Amended 2026-08-04 — the catalog came back as primary, and the split is now clean

[`DECISION-author-defined-slots`](../DECISION-author-defined-slots.md) reversed the July call: the organization catalog is **the type's**, and it is primary. Not keeping (B) was the right outcome — dropping it in July would have deleted the model the platform now runs on. What shipped 2026-08-04:

- **`project_types.actor_roles` is the catalog**, read by `effective_role_catalog()`; `project_organizations.org_role` holds the filled values. Both primary.
- **`project_actor_roles` is no longer written for a typed project** — `instantiate_project_from_type` stopped copying it (a per-project copy is how vocabularies drift), and `PUT /projects/{id}/actor-roles` returns **409** on a typed project, naming the type as the place to edit. It is still seeded and read for a **legacy untyped** project, which is now the only way to have one.
- **`implementing_agency_org_id` + `project_donors` are legacy reads only** — routing resolves through `routing_org_role` first (`c3d22de5`), and go-live B1 accepts them so no pre-existing project was blocked by the change.

### Residual debt (deliberate, not forgotten)

| Left behind | Why it is still there | When it goes |
|---|---|---|
| `ticketing.project_actor_roles` table + `seed_project_actor_roles` | The only fallback for a pre-types project. Dead for every typed one | A cleanup migration once no untyped project exists anywhere (staging + prod) |
| `projects.implementing_agency_org_id`, `ticketing.project_donors` | B1 and the routing fallback read them for old projects | Same sweep — back-fill each into a `project_organizations` row first, then drop |
| `setProjectActorRoles` in `lib/api.ts` | Unused by any screen since the catalog moved to the type | With the table |
| `apply_donor_informed_defaults` keys on the literal `'donor'` role | Convenience pre-fill, not a gate — a type whose donor slot is called something else simply gets no pre-fill | When the pre-fill is re-expressed against the type's catalog |
| [`ui/04`](../../../ticketing_system/ui/04_projects_packages_redesign.html) still mocks "Implementing agency + Donors" | Wireframe, not code — the built screen renders the catalog | Next pass over the wireframe |

## Decision — DECIDED (B), 2026-07-30 *(superseded above)*

**Chosen: (B) keep the legacy catalog as deprecated back-compat.** No code cleanup. The docs already reflect this ("deprecated, legacy, still present"). The catalog is dormant — the new model is primary — and harmless as a routing fallback.

**(A) — not pursued** (kept for the record if ever revisited): drop the 3 tables + `project_types.actor_roles` + `routing_org_role`; delete `project_actor_roles.py`; stop seeding; remove the routing/go-live fallback + the `…/organizations`/`…/actor-roles` endpoints; then flip docs to "removed".

## Touch list if (A)

Migration (drop tables + type fields) · `models/project.py`, `models/package.py` · `services/project_actor_roles.py` (delete) · `api/routers/locations.py` (stop seeding) · `services/project_routing.py` + `project_go_live.py` (remove fallback) · `api/routers/` actor-role/org endpoints · docs 02/03/04/10/11/13/14 (flip to "removed").
