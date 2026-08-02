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

## Decision — DECIDED (B), 2026-07-30

**Chosen: (B) keep the legacy catalog as deprecated back-compat.** No code cleanup. The docs already reflect this ("deprecated, legacy, still present"). The catalog is dormant — the new model is primary — and harmless as a routing fallback.

**(A) — not pursued** (kept for the record if ever revisited): drop the 3 tables + `project_types.actor_roles` + `routing_org_role`; delete `project_actor_roles.py`; stop seeding; remove the routing/go-live fallback + the `…/organizations`/`…/actor-roles` endpoints; then flip docs to "removed".

## Touch list if (A)

Migration (drop tables + type fields) · `models/project.py`, `models/package.py` · `services/project_actor_roles.py` (delete) · `api/routers/locations.py` (stop seeding) · `services/project_routing.py` + `project_go_live.py` (remove fallback) · `api/routers/` actor-role/org endpoints · docs 02/03/04/10/11/13/14 (flip to "removed").
