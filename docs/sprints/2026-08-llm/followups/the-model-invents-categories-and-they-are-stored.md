# Follow-up — the classifier invents categories on 17% of grievances, and they are stored

> **Raised:** 2026-08-20, by [DPG-23](../03-open-models-spec.md#dpg-23)'s closed-baseline run.
> **Logged as deviation D-51** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** ⬜ **OPEN — a live defect on the production classification path.**
> **Size:** S for the mitigation (a prompt line, or a filter), M to decide *which*, because the two
> options differ in what they throw away.

---

## The finding

Measured over the full 105-item benchmark against `gpt-5-nano` — the model production runs:

**18 of 105 grievances (17%) received at least one category that does not exist in the taxonomy.**
Not noise, either. The model produced a coherent, entirely fictional family:

| Invented category | Times |
|---|---|
| `Road Hazard - Dust` | 7 |
| `Road Hazard - Accident` | 5 |
| `Road Hazard - Animal On Road` | 3 |
| `Road Hazard - Others` | 2 |
| `Wildlife Passage` — malformed, the classification half is missing | 2 |
| `Road Hazard - Flood And Landslide` | 1 |
| `Road Hazard - Potholes` | 1 |

**21 of the 32 false positives in the run are invented categories.** Set-level precision is 0.740;
against the real taxonomy alone it would be ≈0.88. **This one behaviour accounts for most of the
precision gap** — which also means the closed baseline is *better at Nepali classification* than its
headline number suggests, and worse at following instructions.

⚠ The prompt already forbids exactly this: *"Only choose from the following categories… Do not
create new categories."*

## Where it goes

`_warn_about_unlisted_categories` (`backend/services/LLM_services.py:358`) is explicit and, for the
case it was written for, right:

> *"Log — never reject — categories the model invented. […] a complainant's classification is not
> worth discarding because the model named a category slightly wrong."*

⚠ **`Road Hazard - Dust` is not a slightly-wrong name.** It is a category that exists nowhere, and
nothing downstream filters it. It is:

1. **stored** on the grievance as `grievance_categories`;
2. **shown to the complainant** in the review step, as the system's understanding of their complaint;
3. **synced to ticketing** and cached on the ticket (`grievance_categories`, CLAUDE.md DB rule 4);
4. **invisible to every category filter and report** in the officer UI, because it is not in the
   catalogue those are built from;
5. **not found** by the `high_priority` lookup — `ticketing_dispatch.py:117` does
   `if category in CLASSIFICATION_DATA`, so an invented category contributes **nothing** to priority.

Point 5 compounds [D-49](taxonomy-csv-column-drift-silently-clears-high-priority.md): `Air Pollution`
already loses its high-priority flag to a CSV parse defect, and on 7 items the model *also* offered
`Road Hazard - Dust` instead. **A dust complaint can therefore arrive with no priority signal from
either direction.** Neither defect is visible on its own, and together they are silent.

## Why it was invisible

The warning is logged at `WARNING` on the Celery LLM worker and nothing aggregates it. There is no
counter, no metric, no test. A grievance with an invented category looks completely normal in the
UI — a category is displayed, it is simply one nobody can filter by. **The only way to see this is
to score classifications against the catalogue**, which nothing did until the benchmark existed.

## The two fixes, and why the choice is not obvious

**Option A — reject unlisted categories at parse time.** Drop anything not in the live catalogue,
keep the rest. Cheap, deterministic, and it makes the stored value trustworthy.
⚠ It silently *loses information* on items where the invented category was the model's **only**
answer: the grievance ends up with fewer categories, or none. Check how often that happens in the
run before choosing this — the data is in the committed report.

**Option B — repair the prompt.** The model is inventing `Road Hazard - *` categories that a road
project plausibly *should* have, which is worth reading as a signal rather than only as an error:
the taxonomy may genuinely lack a road-hazard grouping, and dust and potholes are being forced into
`Environmental` and `Safety`. A prompt that names the constraint more forcefully — or an explicit
*"if nothing fits, choose the closest and say so"* — may fix the behaviour and surface the gap.
⚠ Prompt changes are unmeasurable without a re-run; do not ship one without re-scoring.

**Recommended: A **and** B.** A is the guard (invented values must not reach storage whatever the
model does); B is the cure. And separately: **take the taxonomy question to the project owner** —
seven independent items wanting a "road hazard, dust" category is a product finding, not only a
model defect.

## Definition of done

- [ ] Invented categories cannot reach `grievance_categories` in storage — with a test
- [ ] The count of items that would lose their **only** category under Option A is measured from
      the committed report, and stated in the decision
- [ ] The `Road Hazard` gap is put to the owner as a taxonomy question, with the seven items
- [ ] The benchmark is re-run and the precision delta recorded here (expected ≈0.74 → ≈0.88)
- [ ] Read together with [D-49](taxonomy-csv-column-drift-silently-clears-high-priority.md) — the
      dust complaint is hit by both, and fixing one alone still leaves it unprioritised

## Related

- [`../../../dpg/model-benchmarks.md`](../../../dpg/model-benchmarks.md) §3.1 — the measurement
- [`taxonomy-csv-column-drift-silently-clears-high-priority.md`](taxonomy-csv-column-drift-silently-clears-high-priority.md) — D-49, which compounds this
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
