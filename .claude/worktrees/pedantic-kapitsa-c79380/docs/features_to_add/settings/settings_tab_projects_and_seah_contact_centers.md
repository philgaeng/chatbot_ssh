# Settings tab (Ticketing / management): Projects + SEAH contact centers

## Purpose

This document is the **product + engineering contract** for a **Settings** area in the **Ticketing / management** application (separate from the chatbot UI, but sharing the same Postgres database). It covers:

1. **Projects** — create, edit, deactivate, list, filter, and **bulk import via CSV**.
2. **SEAH contact centers** — `seah_contact_points` rows used by the chatbot outro (`action_seah_outro`) and optional project linkage.

It is written so a ticketing-team engineer can implement the tab without re-deriving behavior from scattered chatbot code.

## Related documents and code (read first)

| Artifact | Role |
|----------|------|
| [`docs/features_to_add/projects_catalog_admin_layers_and_settings.md`](../projects_catalog_admin_layers_and_settings.md) | Country-agnostic project columns, JSON alignment rule |
| [`docs/Refactor specs/April20_seah/08_seah_outro_and_project_catalog.md`](../../Refactor%20specs/April20_seah/08_seah_outro_and_project_catalog.md) | Catalog behavior, `project_uuid`, outro |
| [`docs/Refactor specs/April20_seah/10_seah_db_migration_inventory.md`](../../Refactor%20specs/April20_seah/10_seah_db_migration_inventory.md) | DB inventory and rollout notes |
| `backend/services/database_services/postgres_services.py` | `find_seah_contact_point`, `_ensure_seah_contact_points_table` |
| `backend/actions/action_seah_outro.py` | Consumes `seah_contact_points` + complainant slots |
| `scripts/database/seeds/projects_demo.csv` | Example **projects** CSV (column order) |
| `scripts/database/seeds/seah_contact_points_jhapa_demo.csv` | Example **contact points** CSV |
| `scripts/database/import_seah_demo_seed_csv.py` | Reference **upsert** logic for bulk import |

---

## 1. Settings tab — scope and placement

### 1.1 Where it lives

- **Application:** Ticketing / management web app (auth-required).
- **Section name (suggested):** `Settings` → sub-tabs:
  - `Projects`
  - `SEAH contact centers`

### 1.2 Who can use it

Define roles (exact names are a ticketing-app concern). Minimum:

| Role | Projects | SEAH contact centers |
|------|----------|----------------------|
| **Admin** | Full CRUD + CSV import | Full CRUD + CSV import |
| **Operator (read-only)** | List + view | List + view |
| **Auditor** | Read + export | Read + export |

All mutating actions should be **audit-logged** (who, when, what changed, optional CSV file id).

---

## 2. Data model (current database truth)

### 2.1 Table: `projects`

Used for catalog rows; geography is **country-agnostic** in column naming.

| Column | Type | Required | Notes |
|--------|------|----------|--------|
| `project_uuid` | `TEXT` (PK, UUID string) | Yes | Primary key; chatbot will store this in `project_uuid` slot when picker ships |
| `country` | `TEXT` | Yes | Default `Nepal` in seeds; use ISO display or full name consistently |
| `administrative_layer_level_1` | `TEXT` | Recommended | Nepal: **province** (must match location JSON, e.g. `Koshi`) |
| `administrative_layer_level_2` | `TEXT` | Recommended | Nepal: **district** (must match JSON, e.g. `Jhapa`) |
| `administrative_layer_level_3` | `TEXT` | Optional | Nepal: **municipality** when product needs finer filter than district |
| `name_en` | `TEXT` | Yes | |
| `name_local` | `TEXT` | Optional | Same as `name_en` if not differentiated |
| `project_short_denomination` | `TEXT` | Recommended | Unique code for reporting (e.g. `KL_ROAD`); enforce unique index in DB |
| `adb` | `BOOLEAN` | Yes | ADB-funded flag for reporting |
| `inactive_at` | `TIMESTAMP` nullable | No | Soft-delete / hide from picker when set |
| `created_at` | `TIMESTAMP` | Auto | |
| `updated_at` | `TIMESTAMP` | Auto | |

**Critical rule:** For Nepal deployments, `administrative_layer_level_*` values must **exactly match** canonical strings in `backend/dev-resources/location_dataset_en_cleaned.json` (and Nepali side where applicable), or chatbot filters and complainant slot matching will drift.

### 2.2 Table: `seah_contact_points`

Used for referral / center copy in SEAH outro.

| Column | Type | Required | Notes |
|--------|------|----------|--------|
| `seah_contact_point_id` | `TEXT` (PK) | Yes | Stable id, e.g. `jhapa-birtamod-seah` |
| `province` | `TEXT` | Optional | Legacy column name; Nepal: province string |
| `district` | `TEXT` | Optional | Nepal: district |
| `municipality` | `TEXT` | Optional | Finer match for scoring |
| `ward` | `TEXT` | Optional | Optional finer match |
| `project_uuid` | `TEXT` | Optional | Link to `projects.project_uuid` when center is project-specific |
| `seah_center_name` | `TEXT` | Yes | Display name |
| `address` | `TEXT` | Optional | Full address line(s) |
| `phone` | `TEXT` | Optional | |
| `opening_days` | `TEXT` | Optional | |
| `opening_hours` | `TEXT` | Optional | |
| `is_active` | `BOOLEAN` | Yes | Default `true` |
| `sort_order` | `INTEGER` | Optional | Tie-break for `find_seah_contact_point` |

**Lookup behavior (chatbot):** `find_seah_contact_point` prefers province match, then scores district / municipality / ward / `project_uuid`. Inactive rows should set `is_active = false` and be excluded from queries.

---

## 3. Settings UI — Projects

### 3.1 List view

- **Filters:** country, layer 1, layer 2, layer 3, `adb`, active vs inactive (`inactive_at` null / not null), text search on `name_en` / `name_local` / `project_short_denomination`.
- **Columns:** names, geography layers, short code, ADB flag, active, `updated_at`.
- **Actions per row:** View, Edit, Deactivate (set `inactive_at`), Reactivate (clear `inactive_at`), Delete (only if policy allows hard delete; prefer soft deactivate).

### 3.2 Create / edit form

- **Geography:** dropdowns should ideally be fed from the same canonical source as the chatbot (today: JSON-derived API). If the ticketing app cannot embed that yet, use **validated free text** with server-side checks against allowed values for the selected country.
- **Short code:** enforce uniqueness before save.
- **ADB:** boolean toggle.
- **Preview:** show how the row will appear in a future project picker (name + district + short code).

### 3.3 CSV bulk import (Projects)

#### 3.3.1 UX flow

1. User selects **country** (optional default Nepal).
2. User uploads CSV.
3. Server validates **all rows** (dry-run). Return:
   - valid row count
   - invalid rows with line number + reason
4. User confirms apply.
5. Server runs upsert in a **transaction**; partial failure rolls back unless product explicitly wants partial commit (not recommended).

#### 3.3.2 CSV format (authoritative column header order)

Use the same headers as `scripts/database/seeds/projects_demo.csv`:

```text
project_uuid,country,administrative_layer_level_1,administrative_layer_level_2,administrative_layer_level_3,name_en,name_local,project_short_denomination,adb,inactive_at
```

- **`adb`:** truthy if (case-insensitive) one of `1`, `true`, `yes`, `y`, `t`; otherwise **false** (matches `import_seah_demo_seed_csv.py` `_to_bool`).
- **`inactive_at`:** ISO-8601 timestamp or empty for active.
- **`administrative_layer_level_3`:** may be empty.

#### 3.3.3 Validation rules (server)

- `project_uuid` must be valid UUID string.
- `country` non-empty.
- `name_en` non-empty.
- `project_short_denomination` unique globally (after trim).
- For Nepal: layers must match allowed lists from location dataset service (recommended) or reject with explicit error.
- Reject duplicate `project_uuid` rows within the same upload file.

#### 3.3.4 API (suggested)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/settings/projects/import/preview` | multipart CSV → validation report |
| `POST` | `/api/settings/projects/import/commit` | apply after preview token / hash |
| `GET` | `/api/settings/projects` | paginated list |
| `POST` | `/api/settings/projects` | single create |
| `PATCH` | `/api/settings/projects/{project_uuid}` | update |
| `POST` | `/api/settings/projects/{project_uuid}/deactivate` | set `inactive_at` |

Authentication: service-to-service or session JWT as per ticketing stack.

---

## 4. Settings UI — SEAH contact centers

### 4.1 List view

- **Filters:** province, district, municipality, `project_uuid`, active flag.
- **Columns:** id, center name, geography, linked project, phone, active, sort order.
- **Actions:** View, Edit, Deactivate (`is_active=false`), Reactivate.

### 4.2 Create / edit form

- All fields from section 2.2 exposed with inline help:
  - Explain that **blank province** rows behave as **national fallback** in lookup (see `find_seah_contact_point` query logic).
  - Explain `sort_order` for tie-breaks.
  - Optional `project_uuid` picker (search projects).

### 4.3 CSV bulk import (SEAH contact centers)

#### 4.3.1 CSV format

Use the same headers as `scripts/database/seeds/seah_contact_points_jhapa_demo.csv`:

```text
seah_contact_point_id,province,district,municipality,ward,project_uuid,seah_center_name,address,phone,opening_days,opening_hours,is_active,sort_order
```

- **`is_active`:** same truthy rule as `adb` in the reference script.
- **`sort_order`:** integer (required for import; the reference script uses `int(row["sort_order"])`).

#### 4.3.2 Validation rules (server)

- `seah_contact_point_id` non-empty, unique, URL-safe recommended (lowercase + hyphens).
- `seah_center_name` required.
- If `project_uuid` set, must exist in `projects`.
- If geography provided, validate against canonical lists for Nepal (same rule as projects).
- Phone format warning vs hard reject (product choice).

#### 4.3.3 API (suggested)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/settings/seah-contact-points/import/preview` | CSV validation |
| `POST` | `/api/settings/seah-contact-points/import/commit` | upsert apply |
| `GET` | `/api/settings/seah-contact-points` | list |
| `POST` | `/api/settings/seah-contact-points` | create |
| `PATCH` | `/api/settings/seah-contact-points/{id}` | update |

---

## 5. Operational concerns

### 5.1 Environments

- **Dev:** allow destructive re-import; log SQL counts.
- **Stage:** CSV import behind admin role; snapshot DB before large import if needed.
- **Prod:** require two-person rule or change ticket id in commit metadata (org policy).

### 5.2 Caching

If ticketing or chatbot caches project lists, define **cache invalidation** on any successful project mutation or import.

### 5.3 Chatbot coupling

Until the chatbot ships the **project picker**, these tables still add value for:

- payload snapshots (`seah_payload` already stores dicts),
- `seah_contact_points` outro referral blocks,
- ops reporting in ticketing.

When the picker ships, Settings becomes the **source of truth** for `project_uuid`.

---

## 6. Acceptance criteria (Settings MVP)

1. Admin can **create / edit / deactivate** a project with geography fields aligned to Nepal JSON naming.
2. Admin can **upload projects CSV** with preview + validation errors per row.
3. Admin can **create / edit / deactivate** SEAH contact centers with all table fields.
4. Admin can **upload contact centers CSV** with preview + validation errors per row.
5. All mutations are **audit-logged** and require authenticated admin (or stricter).
6. Import endpoints are **idempotent** (same CSV twice does not duplicate keys).

---

## 7. Implementation handoff (ticketing repo)

Deliverables in the ticketing application:

- Settings routes + UI components described above.
- Server-side validators shared with a small “reference data” module (recommended: HTTP service in chatbot backend or shared lib) for **allowed province/district/municipality** strings.
- Reuse upsert semantics from `scripts/database/import_seah_demo_seed_csv.py` as the canonical SQL shape (port to ticketing service or call chatbot admin API).

This chatbot repo already contains **seed CSVs** and a **working import script** for local parity; ticketing should either call the same logic or duplicate it with tests kept in sync.
