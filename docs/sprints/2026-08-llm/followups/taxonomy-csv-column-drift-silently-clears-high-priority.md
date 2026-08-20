# Follow-up — four grievance categories silently lost their high-priority flag

> **Raised:** 2026-08-20, while building [DPG-20](../03-open-models-spec.md#dpg-20)'s benchmark set.
> The set labels each item's severity from the taxonomy, so the taxonomy had to be read — and it
> disagreed with itself.
> **Logged as deviation D-49** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** ⬜ **OPEN.** Not fixed here: it changes ticket priority and therefore SLA behaviour on
> a live path, which is a product decision, not a benchmark decision.
> **Size:** S to fix, M to verify (seeded data, SLA expectations and demo scenarios all move with it).

---

## The finding

`backend/dev-resources/grievances_categorization_v1.1.csv` has a 13-column header. **Five of its 24
rows do not have 13 fields.**

| Row | Category | Fields | Why |
|---|---|---|---|
| 5 | Wildlife Destruction | 16 | carries extra follow-up-question columns the header never declares |
| 6 | Air Pollution | 15 | same |
| 16 | Cutting of Trees | 14 | same |
| 20 | Fire Incidents | 14 | same |
| 24 | Gender Discrimination and harrassment | **7** | short — trailing fields simply absent |

`load_classification_data()` (`backend/config/constants.py:646`) reads them with `csv.DictReader`,
which puts surplus fields under the `None` key and leaves missing ones unset. So:

```python
"high_priority": row["high_priority"].lower() == "true" if row.get("high_priority") else False
```

…reads a **follow-up question string** instead of `True`/`False`, and
`'"Can you assess the gravity of their illness on a scale from 1 to 5?"'.lower() == "true"` is
`False`. The short row yields `None`, which the guard also turns into `False`.

**Four categories are high-priority in the authored data and not-high-priority in the running
system:**

| Category | Authored | Live |
|---|---|---|
| **`Environmental - Air Pollution`** | `True` | `False` |
| **`Gender - Gender Discrimination And Harrassment`** | `True` | `False` |
| `Environmental, Social - Cutting Of Trees` | `True` | `False` |
| `Wildlife, Environmental - Wildlife Destruction` | `True` | `False` |

(`Fire Incidents` is also misparsed but its authored value is `False`, so it is accidentally right.)

## Why it matters more than a data-entry slip

`backend/actions/utils/ticketing_dispatch.py:117` computes ticket priority from exactly this flag:

> *"True when any selected category is marked high_priority in CLASSIFICATION_DATA."*

So the two most consequential entries in the table are the two that hurt:

1. **`Environmental - Air Pollution` is the dust complaint** — demo scenario 1 in `CLAUDE.md`,
   the flagship KL Road grievance, children falling sick. It has been filed at normal priority.
2. **`Gender - Gender Discrimination And Harrassment` is the category the SEAH review step keys
   on** (any category containing `"gender"` is kept — `docs/models/01_seah_detection_benchmark.md` §2).
   A safeguarding-adjacent category losing its priority flag is the worst instance of this bug.

**And it propagated.** The seeded database was loaded from this CSV, and
`_load_classification_from_database()` is preferred over the CSV when the table exists — so
re-seeding does not fix it, it re-applies it. Verified on the running stack: `CLASSIFICATION_DATA`
reports `Environmental - Air Pollution → False` with the taxonomy loaded **from Postgres**.

## Why it was invisible

Nothing reads `high_priority` back and compares it to anything. It goes one way — CSV → dict →
ticket priority — and a `False` where `True` was meant produces a ticket that looks completely
normal. There is no error, no log line, and no test. The only way to see it is to read the CSV as
raw rows rather than through `DictReader`, which is what building the benchmark forced.

## What was done here, and what deliberately was not

**Done:** the benchmark set records the **authored** value, so it is already correct when this is
fixed. Two tests pin it (`tests/backend/test_benchmark_set.py`):

- `test_benchmark_severity_follows_the_authored_taxonomy` — the set's severity labels come from the
  CSV's final field, read positionally, never from `CLASSIFICATION_DATA`;
- `test_the_taxonomy_parse_defect_is_still_present_and_still_logged` — a **canary** asserting the
  known extent of the defect, so that fixing it fails loudly and this document gets closed rather
  than quietly outliving the bug.

**Not done, on purpose:** the fix. Flipping four categories to high priority changes SLA clocks,
escalation timing, seeded demo tickets and the queue's red badges. That is a product decision with a
blast radius outside a benchmark commit.

## The fix, when someone takes it

1. **Repair the CSV**, not the parser. Either declare the third follow-up-question pair in the
   header (rows 5, 6, 16, 20 have one) or move `high_priority` to a fixed early column. A header
   that does not describe its rows is the actual defect; a parser that tolerates it hides the next one.
2. **Make the loader loud.** `csv.DictReader` with `restkey`/`restval` set, and a log line — better,
   a startup assertion — when any row's field count differs from the header's. A taxonomy that
   silently half-loads should not be a thing that can happen twice.
3. **Re-seed** `public.grievance_classification_taxonomy`, since the DB copy carries the defect.
4. **Decide the product question explicitly:** four categories become high priority. Confirm that is
   wanted — especially Air Pollution, which is the highest-volume category on a road project and
   will change queue composition immediately.
5. Delete the canary test and close this document.

## Related

- [`../PROGRESS.md`](../PROGRESS.md) — D-49
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
- `tests/data/benchmark/README.md` §4 — how the benchmark records severity, and why
