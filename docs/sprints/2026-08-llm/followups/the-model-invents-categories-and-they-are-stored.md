# Follow-up — the classifier invents categories on 17% of grievances, and they are stored

> **Raised:** 2026-08-20, by [DPG-23](../03-open-models-spec.md#dpg-23)'s closed-baseline run.
> **Logged as deviation D-51** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** ✅ **CLOSED 2026-08-25.** Taxonomy on 08-21 (18/105 → 4/105), storage guard on 08-25
> (4/105 → **0 stored**). What shipped is [below](#what-shipped-2026-08-25) — it is **neither** of
> the two options this document weighed, and the reason is the finding.
> **Size:** was S/M. Actual: S — because the four survivors turned out to share one shape.

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

`_warn_about_unlisted_categories` (then at line 358 of `backend/services/LLM_services.py`, removed
2026-08-25) was explicit and, for the case it was written for, right:

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

## What shipped, 2026-08-25 {#what-shipped-2026-08-25}

⭐ **Neither A nor B, because the four remaining cases were not what either option assumed.** B (the
taxonomy) shipped first, on 08-21, and took invention from 18/105 to 4/105. Looking at the four
survivors closely is what changed the plan: **all four are a correct leaf under a wrong or missing
parent.** `Cultural Site Disturbances` and `Wildlife Passage` have the classification half dropped;
`Road Hazard - Noise Pollution` names a leaf that is real and lives under `Environmental`. Category
keys are `Classification - Leaf` and **the leaves are unique**, so the repair is a dictionary lookup —
Option A's information loss simply does not arise for any case the benchmark actually saw.

Three tiers, in [`backend/services/category_resolution.py`](../../../../backend/services/category_resolution.py):

1. **The catalogue is sent as a JSON-Schema enum**, rebuilt from `CLASSIFICATION_DATA` on every call
   by `grievance_classification_schema`. A provider that honours `json_schema` cannot return a
   category that does not exist. Nothing is frozen, so the admin-configurable taxonomy and the
   resync path are untouched — which was the whole objection to a `Literal[...]`.
   ⚠ **Not a guarantee:** `Qwen3.5-9B` accepts the schema and ignores it, and the ladder degrades to
   `json_object` or to prose on weaker models. The enum makes the repair rare, not unnecessary.
2. **Fold and resolve.** The value is folded to the canonical key form (casing, hyphens — the same
   fold the benchmark scores with, now shared rather than reimplemented), then matched; an unmatched
   value is resolved by its leaf.
3. **Drop what is left, and log it.** If dropping would leave the item with no category at all, the
   model's own top **alternative** is promoted — which answers Option A's one real objection without
   a second call.

⛔ **Two things deliberately not built.** No fuzzy matching: an ambiguous leaf (one two
classifications could claim) is refused rather than guessed, because a wrong category is stored and
displayed exactly as silently as an invented one. And **no repair prompt** — a second model call to
map an invented value onto the catalogue was proposed, costed and rejected: it adds a round trip on
the interactive path, it can invent in its own right, and it would have **buried the signal**.
Eighteen items asking for a `Road Hazard` family is how the 08-21 taxonomy change was found; a
silent repair would have folded all eighteen into `Environmental - Air Pollution` and nobody would
ever have seen the gap.

⚠ **The fix hid its own measurement, and that had to be fixed too.** The harness calls
`classify_and_summarize_grievance`, so with repair inside it, `predicted` is in-catalogue by
construction and the invention row would read a flattering **0/105 for any model**. `InventionMeter`
(`scripts/ops/llm_benchmark.py`) now reads the rate from the resolution log, keeping it a *model*
metric. It is coupled to that log's wording, and a test pins the coupling.

⭐ **What the alternatives list turned out to be.** `grievance_categories_alternative` was **never
validated at all** — only the primary list was ever checked — and it is the list the complainant is
*offered to pick from* at the review step. Both lists are resolved now.

## Definition of done

- [x] Invented categories cannot reach `grievance_categories` in storage — with a test
      (`tests/backend/test_category_resolution.py`, plus the flipped T-13-e pair)
- [x] The count of items that would lose their **only** category under Option A is measured — it is
      **zero for the four cases the run produced**, since every one of them resolves by leaf. The
      promotion path exists for the case that has not been observed, not for one that has
- [x] The `Road Hazard` gap was put to the owner and answered — six categories added on 08-21
- [ ] ⏳ The benchmark is re-run and the precision delta recorded here (expected 0.773 → higher;
      **the guard changes what is stored, not what the model says**, so the invention row should be
      unchanged at 4/105 and only precision should move)
- [x] Read together with [D-49](taxonomy-csv-column-drift-silently-clears-high-priority.md) — both
      halves of the dust complaint's missing priority are now closed
- [x] ⭐ **Not foreseen by this document:** the same class of defect was found in our own code and
      fixed alongside — see D-55 in [`../PROGRESS.md`](../PROGRESS.md). Every **Nepali** session
      stored `Air Pollution - Air Pollution`, a value outside the taxonomy, because
      `categories_in_local_language` looked the leaf up in a catalogue keyed by the full name. Same
      invisibility, same lost `high_priority`, on far more grievances than 4 in 105

## Related

- [`../../../dpg/model-benchmarks.md`](../../../dpg/model-benchmarks.md) §3.1 — the measurement
- [`taxonomy-csv-column-drift-silently-clears-high-priority.md`](taxonomy-csv-column-drift-silently-clears-high-priority.md) — D-49, which compounds this
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
