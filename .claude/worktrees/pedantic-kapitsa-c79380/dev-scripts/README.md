# Dev scripts

One-off and maintenance utilities (not imported by `backend` at runtime).

## `seed_reference_data.py`

Reads canonical CSVs under `backend/dev-resources/` and loads:

- `reference_municipality_villages`
- `reference_grm_office_in_charge`
- `grievance_classification_taxonomy`

Also regenerates `backend/dev-resources/lookup_tables/list_category.txt` from taxonomy keys.

**Prerequisites:** Postgres reachable with credentials from `env.local` / `.env`, and tables created (e.g. run app `recreate_all_tables` or normal DB init so new reference tables exist).

**Run** (from repository root):

```bash
python dev-scripts/seed_reference_data.py
```

Safe to re-run: truncates reference tables then inserts again.
