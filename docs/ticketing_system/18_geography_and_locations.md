# Geography and locations (reference model + submit-time mapping)

**Status:** As-built (July 2026). Promoted from `docs/sprints/archive/Refactor specs/May5_seah/01_ticketing_geography_reference_model.md` + `03_submission_mapping_and_fallback.md`.
**Last updated:** 2026-07-04 · ⚠ backfilled from git 2026-09-04; not re-verified against the code
**Code:** `ticketing/models/country.py`, `ticketing/seed/location_import_core.py`, `ticketing/seed/import_locations_json.py`, `backend/shared_functions/location_mapping.py`
**Migrations:** `f1a3e9c72b05` (geography redesign), `q9r7s1u3` (canonical `P1` / `P1_*` codes), `y0z2a4b6` (lat/long centroids)
**Related:** [LOCATION_CODES.md](LOCATION_CODES.md) (code scheme), [02_ticketing_domain_and_settings.md](02_ticketing_domain_and_settings.md), [04_ticketing_schema.md](04_ticketing_schema.md), [14_platform_settings.md](14_platform_settings.md) §2 (Locations admin UI)

---

## 1. Purpose

One country-agnostic geography reference model owned by `ticketing.*`. The chatbot / `public.*` tables reference these codes (`country_code`, `location_code`) as **opaque strings** — they never duplicate the hierarchy. Geography tables are reference data only: **no complainant PII** (locked per `CLAUDE.md`).

---

## 2. Data model (`ticketing.*`, verified against `ticketing/models/country.py`)

### `ticketing.countries`

| Column | Type | Notes |
|---|---|---|
| `country_code` | VARCHAR(8) PK | ISO-style short code, e.g. `NP` |
| `name` | TEXT | Display default (English/neutral) |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

### `ticketing.location_level_defs`

Admin-level semantics per country (what level 1/2/3 *means*).

| Column | Type | Notes |
|---|---|---|
| `(country_code, level_number)` | composite PK | `country_code` FK → countries (CASCADE) |
| `level_name_en` | TEXT | e.g. "Province", "District", "Municipality" |
| `level_name_local` | TEXT | e.g. प्रदेश, जिल्ला, नगरपालिका |

Nepal defines **three** levels. Wards are not a level in v1 (they remain free text on the chatbot side); a per-deployment level 4 can be added later via new rows + data migration.

### `ticketing.locations` (adjacency-list tree)

One row per admin node at any level. **Names are not stored on the node** — they live in `location_translations`.

| Column | Type | Notes |
|---|---|---|
| `location_code` | VARCHAR(64) PK | Canonical human-readable code, e.g. `P1`, `P1_JHA`, `P1_JHA_BIR` (see §3) |
| `country_code` | VARCHAR(8) FK | → countries (RESTRICT) |
| `level_number` | INTEGER | Matches `location_level_defs` for the country |
| `parent_location_code` | VARCHAR(64) FK | Self-FK; NULL for roots (provinces) |
| `source_id` | INTEGER | Original ID from the import dataset — used to match EN/NE files and for re-sync |
| `latitude`, `longitude` | NUMERIC(9,6) | District centroids seeded for NP (`y0z2a4b6`) |
| `is_active` | BOOLEAN | |

`includes_children` lives on `officer_scopes`, not here.

### `ticketing.location_translations`

| Column | Type | Notes |
|---|---|---|
| `(location_code, lang_code)` | composite PK | `location_code` FK → locations (CASCADE); `lang_code` `en`, `ne`, … |
| `name` | TEXT | e.g. `P1` → en "Koshi Province" / ne "कोशी" |

---

## 3. Canonical codes

Full scheme: [LOCATION_CODES.md](LOCATION_CODES.md). Summary:

- Provinces: `P1` … `P7` (CAPS, aligned with ISO 3166-2:NP numbering, without the `NP-` prefix).
- Districts: `{province}_{NAME3}` — first three CAPS letters of the district name, e.g. `P1_MOR` (Morang), `P1_JHA` (Jhapa); collision rules in LOCATION_CODES.md §3.
- Municipalities: `{district}_{MUN}` — e.g. `P1_JHA_BIR` (Birtamod).

Legacy `NP_P1` / `NP_D004`-style codes were rewritten in place by migration `q9r7s1u3` (helper: `ticketing/seed/migrate_np_legacy_location_codes.py`); seeds (`kl_road_standard.py` — `LOC_PROVINCE1_CODE = "P1"`, `LOC_MORANG_CODE = "P1_MOR"`, …), officer scopes, and package locations all use canonical codes.

**Import path:** `POST /api/v1/locations/import` (CSV/JSON, templates downloadable) → `ticketing/seed/location_import_core.py`; bulk JSON importer `ticketing/seed/import_locations_json.py` generates codes per the scheme.

---

## 4. Submit-time mapping rule (LOCKED)

Applies to all chatbot grievance/SEAH submit paths. Implemented in `backend/shared_functions/location_mapping.py` → `resolve_location_payload()` (called from `backend/actions/services/submit/collect.py`).

Processing order at submission:

1. **Collect free-text levels first** from tracker slots into `level_1_name` … `level_6_name` (province, district, municipality, village, ward, address).
2. Attempt canonical mapping of each level against `ticketing.locations` (fuzzy match with admin-suffix stripping, `rapidfuzz`).
3. Persist successful mappings to `level_n_code`.
4. Persist `location_code` = deepest mapped code.
5. Persist `location_resolution_status`:
   - `mapped_full` — all expected country levels mapped
   - `mapped_partial` — top levels mapped, lower levels stay free text
   - `free_text_only` — nothing mapped (also the degrade path when the resolver errors)

**Submission never fails because mapping is partial or absent.** Mapping lookup errors log a warning and degrade to `free_text_only`; DB write errors remain blocking as before. Each submission logs `country_code`, `location_resolution_status`, and deepest mapped level for dataset-improvement telemetry.

### Chatbot-side storage

`public.contact_info` (migration `migrations/public/versions/pub002_contact_info_and_normalized_location.py`) carries `country_code`, `location_code`, `level_1_name..level_6_name`, `level_1_code..level_6_code`, `location_resolution_status`; the same normalized columns were added to legacy complainant rows for the dual-write transition. Nepal: ward and village/tole stay free text in `level_4_name` / `level_5_name` — no dedicated ward/village columns.

### Ticketing side

`ticketing.tickets.location_code` stores the canonical code (used for routing, officer scopes, filters); `grievance_location` keeps the human-readable text cache. QR scan (`GET /api/v1/scan/{token}`) returns the package's canonical `location_code` for pre-fill.

---

## 5. Rules

1. No duplicate geography dimension tables in `public.*` — the tree lives only in `ticketing.*`.
2. `location_code` is a stable ID: display renames go through `location_translations`, never code churn. Government splits/merges require an explicit migration with a mapping table.
3. Countries with incomplete canonical data are fully supported — intake works `free_text_only` and improves as reference data is imported.
