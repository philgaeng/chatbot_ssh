# Follow-up — the grievance taxonomy is authored in two files, and only one of them seeds anything

> **Raised:** 2026-08-27, while diagnosing why `backend-tests` had been red on
> `dpg/sprint2-open-models` since 2026-08-23 · logged as deviation **D-58** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** 🟡 **OPEN** — the drift is repaired and pinned; the second copy still exists.
> **Size:** M — it needs a schema decision (`intake_route` in the CSV) across a chatbot/ticketing boundary.
> **Why it is not in this sprint:** collapsing the two sources changes what
> `load_default_catalog()` reads, which is a shared boundary, days before a promotion to `main`.
> Repairing the drift and pinning it is the bounded piece; removing the duplication is not.

---

## The finding

The classification taxonomy is authored twice, and nothing compared the copies:

| File | Read by |
|---|---|
| `backend/dev-resources/grievances_categorization_v1.1.csv` | `backend/config/constants.py`, `dev-scripts/seed_reference_data.py` |
| `ticketing/constants/grievance_categories_default.json` | `load_default_catalog()` → `ticketing.settings` → `sync_categories_to_public_taxonomy()`, which **DELETEs `public.grievance_classification_taxonomy` and re-INSERTs from the JSON** |

By 2026-08-27 they disagreed on **64 fields**:

- **D-49 (`1d794c6c`, 2026-08-21)** repaired `high_priority` on four categories — **in the CSV
  only**. CI seeds the taxonomy through `ticketing.seed.mock_tickets`, which takes the JSON, so the
  repair reached no environment seeded that way. `Environmental - Air Pollution` (the dust
  complaint) and `Gender - Gender Discrimination And Harrassment` (the SEAH route) — the two
  `tests/backend/test_benchmark_set.py` names as the ones that matter — were still
  `high_priority=False`.
- **D-51 (`71a91b8a`, 2026-08-21)** rewrote the six Road Hazard categories — CSV only. The JSON kept
  the June text, down to `सडक खतरा` where the CSV says `सडक जोखिम`.
- `Gender - Gender Discrimination And Harrassment` carried the literal string `"True"` as its
  `description` in the JSON — a column-shift artefact, the same class of bug as the ragged CSV rows
  D-49 found, and nobody had a reason to look at it.

## Why the existing test could not catch it

`test_the_seeded_taxonomy_matches_the_authored_csv` compares the **seeded database** to the CSV. It
went red on every CI run from 2026-08-23 onward and it was right to — but:

- it can only see `high_priority`, the single field it reads, so 58 of the 64 differences were
  invisible to it;
- its remedy line says *"Re-seed this environment"*, and re-seeding through the ticketing path
  **re-applies the stale JSON**. The test's own docstring warns about this — "the half that
  re-applies itself" — but names the CSV as the thing to repair, which is the copy no running
  system reads.

**A test that reports the symptom and prescribes the thing that reproduces it is worse than no
test**, because following its advice confirms the bug.

## What was done (2026-08-27)

- `scripts/ops/sync_category_catalog_json.py` — rewrites the JSON from the CSV, preserving
  `intake_route` (which the CSV cannot supply) and entry order. `--check` reports without writing.
- `tests/repo/test_category_catalog_sources.py` — compares the two **authored files** directly, so
  drift fails in the repository before any database exists. Imports the script rather than
  mirroring its field list, per the `test_spdx_headers.py` arrangement.
- The JSON was regenerated: 69 lines changed, all 64 differences resolved, 30 categories and all 30
  `intake_route` values preserved.

## What is still owed

**Two files in sync is not one file.** The pin makes drift loud; it does not remove the thing that
drifts. Collapsing them means teaching `load_default_catalog()` to read the CSV, which needs an
`intake_route` column in the CSV (`new_grievance` / `road_hazard_grievance` / `seah_intake`) and a
decision about who owns a file that both the chatbot and ticketing read.

Note also that `normalize_category_entry()` **drops `intake_route`** — it builds its output from
`category_key`, `_STRING_FIELDS` and `high_priority` — so the field never reaches
`ticketing.settings` today. Whether it should is part of the same decision.

## Definition of done

- [ ] Decide the single owner of the authored taxonomy, and record the reason with the rule
- [ ] Add `intake_route` to the CSV, or accept losing it and say so explicitly
- [ ] Delete `ticketing/constants/grievance_categories_default.json`, or the CSV, but not keep both
- [ ] Retire `scripts/ops/sync_category_catalog_json.py` and its pin in the same commit — a sync
      script outliving its second copy is how a mirror gets rebuilt
- [ ] Check whether any deployed environment still carries the stale `high_priority=False` rows —
      the repair only lands where the taxonomy is re-seeded

## Related

- [`ci-has-been-red-for-ten-days.md`](ci-has-been-red-for-ten-days.md) — closed 2026-08-19 on the
  premise that "red means something there again". This is the first test of that premise, and the
  answer was four days of red before anyone looked.
- [`road-hazard-categories-have-no-benchmark-items.md`](road-hazard-categories-have-no-benchmark-items.md)
  — the same six categories, from the benchmark side
- [`../../../TODO.md`](../../../TODO.md) 🔵 TECH DEBT
