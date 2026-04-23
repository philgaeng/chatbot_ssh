# Public `contact_info` — model, party links, and ticketing alignment

## Intent (risk posture)

**Goal:** reduce **casual** identity ↔ grievance linkage by storing **reachability attributes** (phone hashes/tokens, email, structured address references) in **`public.contact_info`**, while **case narrative and party role** live on **role tables** (`complainants`, `complainants_seah`, `users`, `resource_persons`, …).

**Honest constraint:** anyone with access to **both** `contact_info` and a role table (or logs joining them) can still re-link. The win is **schema + API defaults**: narrow services, audit paths, and fewer “wide rows” that bundle story + phone.

**Not claimed:** “impossible to link” without operational controls.

---

## Core table: `public.contact_info` (name TBD)

**Surrogate PK:** `contact_id` (UUID or `TEXT` ULID — pick one standard for public schema).

**Suggested columns (illustrative — implementation agent finalizes types and encryption):**

| Column | Purpose |
|--------|---------|
| `country_code` | `TEXT` NOT NULL, FK **logical** to `ticketing.countries.country_code` (no cross-schema FK if Postgres policy forbids; enforce in app or use FK if same DB + allowed). |
| `location_code` | `TEXT` nullable — deepest resolved node in `ticketing.locations` (best-match leaf when available). |
| `level_1_name` .. `level_6_name` | `TEXT` nullable — free-text location labels captured from conversation/import (always allowed). |
| `level_1_code` .. `level_6_code` | `TEXT` nullable — canonical `ticketing.locations.location_code` per level when mapping exists. |
| `phone_e164` or hashed phone | Channel token — align with existing encryption/hashing utilities used by `complainants`. |
| `email` | Encrypted or hashed per existing policy. |
| `address_line` | Optional free text only if product requires; prefer **not** duplicating full hierarchy text if `location_code` exists. |
| `location_resolution_status` | `TEXT` enum-like: `mapped_full`, `mapped_partial`, `free_text_only`. |
| `created_at` / `updated_at` | |

**Explicitly omit from `contact_info`:** `full_name` as primary grievance identifier (per your direction — names live on party rows). Legal name variants, if needed later, are a **separate** decision.

---

## Party / role tables (link only)

Each table holds **role-specific** fields and **`contact_id` → `public.contact_info`**.

| Table | Schema | Role |
|-------|--------|------|
| `complainants` | `public` | Legacy GRM complainant; eventually `contact_id` + grievance link. |
| `complainants_seah` | `public` | SEAH intake party row(s); `contact_id`; retain `seah_reporter_category` or generalize to `party_kind` on this row. |
| `users` (or Django auth profile) | `public` / app-specific | Optional `contact_id` for **non-auth** address book only — **do not** merge password hashes into `contact_info`. |
| `resource_persons` | `public` | Focal points and other **bot-side actors** who are not full product users. |

### `resource_persons` (minimal identifiers)

As discussed: **display + weak attributes**, not uniqueness.

| Column | Notes |
|--------|--------|
| `resource_person_id` | Surrogate PK. |
| `contact_id` | Nullable until enriched. |
| `full_name` | Display / roster. |
| `birthdate` | Optional; sensitive — store only with policy. |
| `country_code` | For multi-country roster filtering. |
| `role_key` | e.g. `site_safeguards_focal_person` — align with ticketing role keys where applicable. |
| `metadata` | `JSONB` optional for import source ids. |

**Uniqueness:** do **not** rely on `(full_name, birthdate)` as PK; collisions span countries.

---

## Relationship to `grievances` / `grievances_seah`

- **One or many** `contact_id` references per case (reporter vs subject) — see prior architecture discussion: prefer **explicit dual FK** on case table or bridge `case_party(case_id, party_kind, contact_id)` in a **later** revision once SEAH focal two-party model is finalized.
- **`grievances_seah.seah_payload`**: may retain JSON snapshot for audit; **canonical** structured fields should migrate toward normalized columns + `contact_id` over time.

---

## Ticketing alignment

- **`country_code`:** must match `ticketing.countries` values used in production for that deployment.
- **`location_code` and `level_n_code`:** must match `ticketing.locations.location_code` when resolved; bot validation layer maps user text → codes using reference data (read-only from ticketing or a synced read replica — **no PII in ticketing**).
- **Partial mapping is valid:** if a country has only 2 or 3 configured levels, save available codes and keep remaining levels as free text (`level_n_code = NULL`).
- **Nepal default:** province/district/municipality may map to codes; lower levels (e.g., ward, village/tole) remain in `level_4_name` / `level_5_name` free text when canonical datasets are unavailable.

## Mapping behavior (operational)

At write time (bot or importer), resolve from top to bottom:

1. Capture labels into `level_1_name`..`level_6_name` (free text, no blocking on mapping).
2. Attempt canonical mapping level-by-level.
3. For each successful level, set `level_n_code`.
4. Set `location_code` to the deepest mapped level (or `NULL`).
5. Set `location_resolution_status`:
   - `mapped_full`: all expected levels for that country mapped
   - `mapped_partial`: at least one level mapped, at least one unresolved
   - `free_text_only`: no level mapped

---

## Phasing (recommended)

1. **Ticketing Alembic:** land `countries`, `location_level_defs`, `locations`, `location_translations` (this spec’s §01).
2. **Public Alembic:** create `contact_info` + `resource_persons` (empty or seed); **no** mass rewrite of `complainants` yet.
3. **Dual-write (optional):** new intakes write `contact_id` while legacy columns remain.
4. **Read path switch** + backfill job for historical rows.
5. **Deprecate** duplicated columns on `complainants` / `complainants_seah` only when ticketing + chatbot both agree.

---

## Migration execution

- **Ticketing:** `python -m alembic -c ticketing/migrations/alembic.ini …`
- **Public:** `python -m alembic -c migrations/public/alembic.ini …`

Use a **dedicated agent** with both specs in context (`May5_seah/*`, `MIGRATIONS_POLICY.md`, `CLAUDE.md` database section).
