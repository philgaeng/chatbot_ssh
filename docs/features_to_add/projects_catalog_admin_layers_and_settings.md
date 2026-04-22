# Feature: Projects catalog (DB) + country-agnostic admin layers + settings CRUD

## Goal

Introduce a **`projects`** table (and later chatbot **project picker** / `project_uuid` on grievances) so projects are **managed from backend settings**, not only free text. Geography on each project should be **country-agnostic** in the schema while still matching the chatbot’s location vocabulary where the bot runs (e.g. Nepal).

## Design decisions (agreed)

### 1. Location hierarchy for the chatbot stays in JSON (for now)

- **`ContactLocationValidator`** continues to use `backend/dev-resources/location_dataset_*_cleaned.json` for province → district → municipality validation and UX.
- **Do not** duplicate the full national admin tree in Postgres solely for the validator unless product later requires shared reference tables, admin UI for boundaries, or multi-service reads.

See: `backend/shared_functions/location_validator.py`.

### 2. Projects table: link to geography with generic column names

Store geography on each project using **neutral** names so the model is not “Nepal-only” in DDL:

| Column (proposed) | Role |
|-------------------|------|
| `country` or `country_code` | ISO or display country |
| `administrative_layer_level_1` | First subdivision below country (for **Nepal**: province, e.g. `Koshi`) |
| `administrative_layer_level_2` | Next level (for **Nepal**: district, e.g. `Jhapa`) |
| Optional later: `administrative_layer_level_3` | e.g. municipality if filtering needs it |

**Rule:** values in layer 1 / 2 (and 3) must **match the canonical strings** in the cleaned location JSON for that deployment so filters, scoring, and complainant slots align without a FK to a location dimension table.

**Documentation line for implementers:** *For Nepal, `administrative_layer_level_1` = province, `administrative_layer_level_2` = district; slot names in the bot may remain `complainant_province` / `complainant_district`.*

### 3. Other project fields (align with catalog spec)

Minimum fields to align with [`docs/Refactor specs/April20_seah/08_seah_outro_and_project_catalog.md`](../Refactor%20specs/April20_seah/08_seah_outro_and_project_catalog.md) (Part A):

- `project_uuid` (PK)
- `name_en`, `name_local`
- Project **short code / denomination** (e.g. `KL_ROAD`) — exact column name TBD (`short_code`, `project_code`, etc.)
- `adb` (boolean)
- `inactive_at` (nullable)
- Timestamps as needed

### 4. Settings / backend administration

- **CRUD** for `projects` lives in the **backend** (FastAPI or existing admin patterns): list, create, update, soft-deactivate (`inactive_at`).
- Chatbot reads projects via a **read API** (and optional cache policy TBD in service layer), per spec 08.

### 5. Relationship to existing SEAH tables

- **`seah_contact_points`** already exists (runtime DDL + seed in `DatabaseManager`); rows can use the same **layer 1 / 2** string convention (or keep legacy `province` / `district` column names until a migration renames them for consistency).
- **`find_seah_contact_point`** scoring can continue to use complainant slots; project rows can optionally set `project_uuid` on contact points when a center is project-specific.

## Out of scope (this feature doc)

- Full migration of `ContactLocationValidator` to read hierarchy from Postgres.
- Renaming **existing** `seah_contact_points` columns from `province` / `district` to layer names (optional follow-up migration once `projects` DDL is stable).

## Implementation checklist (when picked up)

1. DDL: `CREATE TABLE projects` (or agreed name) with UUID PK, country, `administrative_layer_level_1`, `administrative_layer_level_2`, names, short code, `adb`, `inactive_at`.
2. `DatabaseManager`: ensure table on startup or use a versioned migration tool if the repo adopts one.
3. Seed / fixtures: at least one row (e.g. KL ROAD) for dev, strings matching JSON.
4. FastAPI (or existing module): secured admin endpoints for CRUD.
5. Later: chatbot **`project_uuid`** + picker UX (`08` spec); deprecate free-text `seah_project_identification` on the surface.

## References

- [`docs/Refactor specs/April20_seah/08_seah_outro_and_project_catalog.md`](../Refactor%20specs/April20_seah/08_seah_outro_and_project_catalog.md) — project catalog, payload, `project_uuid`
- [`docs/Refactor specs/April20_seah/01_seah_route_and_slots.md`](../Refactor%20specs/April20_seah/01_seah_route_and_slots.md) — routing / slots
- `backend/shared_functions/location_validator.py` — current location source (JSON + optional DB reference tables for ward/village and GRM offices)
