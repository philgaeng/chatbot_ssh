# Spec 22: `dev-resources`, `dev-scripts`, DB-backed reference data, remove pandas

**Status:** ✅ Completed (dev-resources rename, `dev-scripts/seed_reference_data.py`, DB tables + runtime reads, pandas removed from production requirements; optional `requirements-dev.txt` for tooling.)  
**Depends on:** [21_remove_rasa_chatbot_folder_and_colocate_domain.md](21_remove_rasa_chatbot_folder_and_colocate_domain.md) (optional — orthogonal if already done)

---

## Mission

1. **Rename** `backend/resources/` → **`backend/dev-resources/`** so it is explicit that files there are **development sources of truth**, not required at runtime in production once data is loaded into Postgres.
2. **Add** a top-level **`dev-scripts/`** directory for **one-off and maintenance scripts** (CSV → DB seeding, exports, validation). **Do not copy** this folder into Docker images (see §4).
3. **Stop using pandas** in production code by **loading reference data from Postgres** (location/office tables, classification data) instead of DataFrames / filesystem reads on the hot path.
4. **Treat LLM / OpenAI classification prompts** the same way: canonical **CSV (and related files) live in `dev-resources`**; production reads from **Postgres** (or a **single JSON blob** in DB or on disk — see §6 decision).

---

## Background (current state)

### Path constants today

[`backend/config/constants.py`](../../../backend/config/constants.py) sets `PROJECT_ROOT = Path(__file__).parent.parent` → the **`backend/`** package root. Today:

| Constant | Path (under `backend/`) |
|----------|-------------------------|
| `LOOKUP_FILE_PATH` | `resources/lookup_tables/list_category.txt` |
| `DEFAULT_CSV_PATH` | `resources/grievances_categorization_v1.1.csv` |
| `LOCATION_FOLDER_PATH` | `resources/location_dataset/` |

There is also [`backend/resources/location_dataset/`](../../../backend/resources/location_dataset/) (JSON + CSVs) and other folders under `backend/resources/` (e.g. QR tooling). **All** of these should move with the rename to `dev-resources/`.

### Runtime consumers

- **[`backend/shared_functions/location_validator.py`](../../../backend/shared_functions/location_validator.py)** — uses **pandas** for `municipality_villages` CSV and `office_in_charge` CSV (and filters). **Primary target** to switch to DB queries.
- **[`backend/shared_functions/helpers_repo.py`](../../../backend/shared_functions/helpers_repo.py)** — imports pandas but **does not use** it; remove import when pandas is dropped.
- **`load_classification_data()`** in [`constants.py`](../../../backend/config/constants.py) — uses **`csv` stdlib** (not pandas) to read **`grievances_categorization_v1.1.csv`**, builds in-memory dict, and **writes** `list_category.txt` as a side effect at import. This should become **DB-backed** (or JSON) and **must not** rely on missing files in production containers.

### OpenAI / LLM “questions” CSV

The **grievance classification** CSV (`DEFAULT_CSV_PATH`) holds categories, descriptions, follow-up question text (EN/NE), etc. It is the main “structured prompt / taxonomy” input for classification flows — align storage with the same **dev → seed → prod DB** pattern as location data.

---

## 1. Rename `resources` → `dev-resources`

- **From:** `backend/resources/`  
- **To:** `backend/dev-resources/`

**Actions for the implementing agent:**

- Move the entire tree (preserve internal layout: `location_dataset/`, `lookup_tables/`, etc.).
- **Global search** for `resources/` (and `backend/resources`) in code, notebooks, docs, and scripts; update to `dev-resources/`.
- Update **`constants.py`** paths to `dev-resources/...`.
- Update **[`.gitignore`](../../../.gitignore)** / **[`.dockerignore`](../../../.dockerignore)** if any pattern referenced `resources/` explicitly.

**Note:** After this rename, **production Docker images** should either:

- **Exclude** `backend/dev-resources/` via `.dockerignore` (recommended once DB seeding is mandatory for prod), **or**
- Keep a **minimal** subset only if some process still requires files in-container (avoid long-term; prefer DB-only in prod).

---

## 2. Add `dev-scripts/` (repo root)

**Location:** `dev-scripts/` at the **repository root** (sibling of `backend/`, `Dockerfile`, etc.).

**Purpose:**

- Scripts that **read** from `backend/dev-resources/` and **write** into Postgres (seed, upsert, migrations helpers).
- Optional: export-from-DB-to-CSV for backup or diff review.
- **Not** imported by `backend` at runtime.

**Convention:**

- Document each script with a short header: inputs, env vars (e.g. `DATABASE_URL`), idempotency, whether safe to re-run.
- Prefer `python -m` or `python dev-scripts/foo.py` from repo root with `PYTHONPATH` set as for other tools.

---

## 3. `.dockerignore`: exclude `dev-scripts/` and (when ready) `dev-resources/`

Add to [`.dockerignore`](../../.dockerignore):

```
dev-scripts/
```

**Phase A (immediate):** ignore `dev-scripts/` so images stay smaller and secrets/scripts are not baked in unnecessarily.

**Phase B (after seeding is reliable in CI/deploy):** add:

```
backend/dev-resources/
```

Only add Phase B when production no longer reads these paths at runtime (see §5). Until then, if the app still loads CSVs from disk, keep `dev-resources` in the image or seed DB before cutting over — coordinate in one migration.

---

## 4. Postgres tables vs JSON for reference data

### 4.1 Location / office (pandas removal)

Create normalized tables (exact names to match existing DB naming conventions), for example:

- **`municipality_villages`** — columns aligned with current CSV columns after the same normalization as today (lowercase headers, municipality title-casing, etc.).
- **`office_in_charge`** (or **`grm_office_in_charge`**) — columns for province, district, municipality, and any GRM fields currently used in [`get_office_in_charge_info`](../../../backend/shared_functions/location_validator.py).

**Seed:** `dev-scripts/seed_location_reference.py` (name illustrative) reads from `backend/dev-resources/location_dataset/*.{csv}` and upserts into Postgres.

**Runtime:** `ContactLocationValidator` loads **once per process** via DB (or lazy query per call if datasets are huge — prefer indexed queries over loading full tables into memory unless profiling says otherwise).

### 4.2 Classification / LLM taxonomy (`grievances_categorization_v1.1.csv`)

**Option A — Postgres (recommended for consistency):**

- Table(s) e.g. **`grievance_classification_rows`** with columns matching CSV fields (`classification`, `generic_grievance_name`, EN/NE text columns, `high_priority`, follow-up fields, etc.).
- Application builds the same **in-memory structures** that `load_classification_data()` produces today, but from SQLAlchemy or raw SQL.
- **Categories list** for lookups: either a **materialized column** / view, or a small **`classification_categories`** table / derived query — replace **`list_category.txt`** with DB rows or a generated artifact only in dev.

**Option B — JSON blob in Postgres:**

- Single row in e.g. **`app_reference_config`** with key `grievance_classification` and JSONB payload mirroring the current nested dict structure.
- Simpler migration, harder to query/edit per row in SQL.

**Option C — JSON file in image (not recommended long-term):**

- Only as a stepping stone; prefer A or B for production.

**Implementing agent:** Pick A unless the team strongly prefers B for a faster first ship; document the choice in this file’s PR description.

### 4.3 Remove pandas

After **`location_validator`** no longer uses DataFrames:

- Remove **`pandas`** and **`numpy`** from [`requirements.txt`](../../../requirements.txt) if no other production module needs them (re-audit with `rg "pandas|numpy"`).
- Keep pandas only in **`requirements-dev.txt`** if any script under `dev-scripts/` or translation tooling still requires it (see [21](21_remove_rasa_chatbot_folder_and_colocate_domain.md) audit for `utterance_translation_mapping_script.py`).

---

## 5. `constants.py` import-time behavior

Today, **`load_classification_data()`** runs at **module import** and may **write** `list_category.txt`. The refactor should:

- **Load classification from DB** (or JSON) in production.
- Avoid **writing files** on import in production; if a dev-only sync is needed, gate it behind **`ENV == development`** or a dedicated management command under `dev-scripts/`.

---

## 6. Implementation checklist (for the executing agent)

- [x] Rename `backend/resources/` → `backend/dev-resources/`; fix all references.
- [x] Create `dev-scripts/`; add **seed_reference_data.py** for location + classification.
- [x] Update `.dockerignore`: `dev-scripts/`; `backend/dev-resources/` not excluded yet (JSON hierarchy still read from disk).
- [x] Add table creation in `base_manager._create_tables` + `database_tables.TABLE_CREATION_ORDER`.
- [x] Refactor `ContactLocationValidator` to use DB (psycopg2 + `DB_CONFIG`) with CSV fallback; remove pandas.
- [x] Refactor classification loading to Postgres with CSV fallback; lazy `CLASSIFICATION_DATA` / `LIST_OF_CATEGORIES` via `__getattr__`.
- [x] Remove `import pandas` from `helpers_repo.py`.
- [ ] Update tests (`test_office_in_charge`, etc.) to use DB fixtures or factories (script-style test remains; optional pytest hardening).
- [x] Run targeted `pytest`; Docker build not run in this environment.

---

## 7. Out of scope

- Changing LLM prompt **wording** or taxonomy semantics (only **storage and loading**).
- Removing **rasa-sdk** (separate effort).
- Moving **notebooks** under `dev-resources` — optional; at minimum, fix hardcoded paths if they reference old `resources/`.

---

## 8. Reference

- Pandas audit (conversation): `location_validator`, `helpers_repo` (unused import), translation tooling scripts, one-off DB scripts.
- [`load_classification_data`](../../../backend/config/constants.py) — stdlib `csv`, not pandas; still must be decoupled from filesystem for prod.
