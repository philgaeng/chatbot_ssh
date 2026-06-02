# Ticketing geography — reference model (alignment source)

## Status

This document is the **target contract** for ticketing-side geography. The implementation agent should **match Alembic models and migrations** to this shape unless an explicit decision updates this spec.

Chatbot / public tables **reference** these codes (`country_code`, `location_code`) as **opaque FKs** — they must not duplicate the hierarchy in long-lived form (short-term caches or import staging are OK if documented).

---

## `ticketing.countries`

| Column | Type | Notes |
|--------|------|--------|
| `country_code` | `TEXT` PK | ISO-style short code, e.g. `NP`, `PH`. |
| `name` | `TEXT` | Display default (English or neutral); localized names can move to translations later if needed. |
| `created_at` | `TIMESTAMPTZ` | |
| `updated_at` | `TIMESTAMPTZ` | |

**Example rows**

| country_code | name |
|--------------|------|
| NP | Nepal |
| PH | Philippines |

---

## `ticketing.location_level_defs`

Defines **admin level semantics per country** (province / district / municipality / …).

| Column | Type | Notes |
|--------|------|--------|
| `(country_code, level_number)` | PK composite | `country_code` FK → `ticketing.countries`. |
| `level_name_en` | `TEXT` | |
| `level_name_local` | `TEXT` | e.g. Nepali label. |

**Example (Nepal)**

| country_code | level_number | level_name_en | level_name_local |
|--------------|--------------|---------------|------------------|
| NP | 1 | Province | प्रदेश |
| NP | 2 | District | जिल्ला |
| NP | 3 | Municipality | नगरपालिका |

**Wards**

- **No level 4** in the default Nepal definition — wards are **integers** in the thousands at the leaf; not used for GRM scoping in v1.
- **Per-deployment** level 4 (or ward as attribute) may be added later via new rows in `location_level_defs` + data migration — document in a follow-up spec when introduced.

---

## `ticketing.locations` (redesigned)

Hierarchical **admin tree** per country.

| Column | Type | Notes |
|--------|------|--------|
| `location_code` | `TEXT` PK | Stable code, e.g. `NP_P1`, `NP_D001`, `NP_M0001`. |
| `country_code` | `TEXT` FK | → `ticketing.countries`. |
| `level_number` | `INT` | Matches `location_level_defs` for that country. |
| `parent_location_code` | `TEXT` FK nullable | Self-FK to `locations`; `NULL` for roots (e.g. province). |
| `source_id` | `INT` or `TEXT` | Original numeric/string id from import dataset — **match EN/NE files** during import and for **re-sync**. |
| `is_active` | `BOOLEAN` | |

**Example rows**

| location_code | country_code | level_number | parent_location_code | source_id | is_active |
|---------------|--------------|--------------|----------------------|-----------|-----------|
| NP_P1 | NP | 1 | NULL | 1 | true |
| NP_D001 | NP | 2 | NP_P1 | 1 | true |
| NP_M0001 | NP | 3 | NP_D001 | 1 | true |

---

## `ticketing.location_translations`

Localized names for each `location_code`.

| Column | Type | Notes |
|--------|------|--------|
| `(location_code, lang_code)` | PK composite | `location_code` FK → `ticketing.locations`. `lang_code` e.g. `en`, `ne`. |
| `name` | `TEXT` | |

**Example**

| location_code | lang_code | name |
|---------------|-----------|------|
| NP_P1 | en | Koshi Province |
| NP_P1 | ne | कोशी |
| NP_D001 | en | Bhojpur |
| NP_D001 | ne | भोजपुर |

---

## Chatbot alignment rules

1. **`public.contact_info`** (and any party/address tables) should store **`country_code`** compatible with `ticketing.countries.country_code` (same string domain).
2. Public contact capture should support a **6-level hierarchy** (`level_1..level_6`) with optional per-level codes (`level_1_code..level_6_code`) so countries with incomplete canonical data still store usable addresses.
3. When the bot resolves location text to canonical nodes, persist **`location_code`** (deepest mapped level) and matching `level_n_code` values; unresolved levels remain free text.
4. This means countries with only 2 configured levels are supported without blocking intake (`mapped_partial` path in `02_public_contact_info_and_party_links.md`).
5. **No duplicate geography dimension tables** in `public.*` for the same meaning as `ticketing.locations` — avoid drift across countries.

## PII boundary (LOCKED)

Per `CLAUDE.md`: **no complainant PII inside `ticketing.*`**. Geography tables are **reference data** only (no phone, email, name of complainant).
