# Agent runbook — OC-01 + OC-02: Org tree + position types & matrix

**Branch:** `orgchart/oc-01-02-tree` off `integration/seah-claude` · **Model:** Opus (high effort — new admin endpoints on a PII system + matrix validation) · **Spec:** [`../01-org-tree-and-positions-spec.md`](../01-org-tree-and-positions-spec.md) · Read [`README.md`](README.md) common rules first. Do OC-01 fully (migration + router + tests) before OC-02.

## Mission

Put the ministry org tree on `ticketing.organizations` (parent/unit_type/territory + `display_name_ne`, plus CSV import), then add the `ticketing.position_types` catalog and the position→role matrix. Both are **additive** — existing flat orgs become tree roots, nothing about tickets/roles/scopes changes here.

## OC-01 steps

1. Read `ticketing/models/organization.py:20-44` and the organizations endpoints in `ticketing/api/routers/locations.py` (:252-364, DELETE guard :333-364). Read `ticketing/services/admin_access.py` (the country-tier gate you will reuse) and the location reference model (`docs/ticketing_system/18_geography_and_locations.md`) for `territory_location_code` validation.
2. **Check the live head:** `cd ticketing/migrations && alembic heads`. Chain the new revision on the actual head; if HR-03 has landed, chain after it. **Record the revision + `down_revision` in [`../PROGRESS.md`](../PROGRESS.md) head table** and coordinate rebase with HR-03 if the head moves. Safety header + real `downgrade()`.
3. Migration per spec §1: add `parent_organization_id` (self-FK), `unit_type`, `territory_location_code`, `territory_includes_children`, `display_name_ne`; backfill existing rows (`unit_type` sensible default, NULL parent); index the parent column. Model gets the columns + self-relationship + `descendant_org_ids` CTE helper (cycle guard).
4. Extend `locations.py`: new fields on GET/POST/PATCH, `tree=true` + `root_id` filter, cycle/unit_type/territory validation, tighten the gate to **country_admin standard / super_admin** via `admin_access`.
5. `POST /organizations/import` CSV per spec: whole-file validate (row errors as a list, nothing written on any error) → single-transaction insert → idempotent upsert; two-pass parent resolution. Mirror the CSV pattern in `features/settings/settings_tab_projects_and_seah_contact_centers.md`.
6. `tests/ticketing/test_org_tree.py` — migration round-trip, self-FK + cycle rejection, territory, **authz matrix**, CSV all-or-nothing + upsert. Manual: upgrade→downgrade→upgrade on the seeded DB; existing orgs still resolve.

## OC-02 steps

1. Migration (chained after OC-01) + model `ticketing/models/position_type.py` for `position_types` — all columns incl. `display_name_ne` (spec §2). Safety header, real downgrade.
2. `/api/v1/position-types` CRUD: `position_key` immutable after create; delete guard blocks in-use types (mirror the org DELETE guard); country-tier gate.
3. Matrix validation on save: `default_role_key` resolves in `grm_role_catalog`; `allowed_unit_types` valid; `reports_to_position_key` exists. Editing `default_role_key` stores the new default and **does not** touch existing holders.
4. `tests/ticketing/test_position_types.py` — CRUD, immutability, delete guard, matrix validation, no-side-effect on default edit, **authz matrix** (log the SEAH-track-authoring open question). Seed ~5 real DoR position types pointing at catalog role keys.

## Constraints

- Additive only — no changes to `tickets`, `user_roles`, `officer_scopes`, or the assignment engine (those are OC-03/04). `tickets.organization_id`/`officer_scopes` FKs unchanged.
- Every endpoint gated at the country tier by **reusing `admin_access`** — no new ad-hoc permission check.
- Ticketing-stream migrations only; coordinate the head with HR-03.
- Leave `# INTEGRATION POINT:` where OC-03's invite pre-fill will read these tables.

## Done means

OC-01 + OC-02 checklists ticked in [`../PROGRESS.md`](../PROGRESS.md); both test files + authz matrices green in the full ticketing suite; migration round-trips verified; position-type seed committed; head table updated.
