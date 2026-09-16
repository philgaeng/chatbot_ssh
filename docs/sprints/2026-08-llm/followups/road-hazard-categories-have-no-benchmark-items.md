# Follow-up — the six new Road Hazard categories have no benchmark items

> **Raised:** 2026-08-21, adding the categories the owner approved under [D-51](../PROGRESS.md).
> **Status:** ⬜ **OPEN — a coverage gap, not a defect.** Nothing is broken; something is unmeasured.
> **Size:** S — roughly 20 authored items, no inference cost to write.

---

## The finding

`Road Hazard - Dust · Potholes · Flood And Landslide · Accident · Animal On Road · Others` were added
to the live taxonomy on 2026-08-21, taking it from 24 categories to 30.

**The benchmark has no gold items for any of them.** They appear only as `categories_acceptable` on
twelve existing items — dust complaints, road-safety complaints, wildlife-crossing complaints — which
means a model naming them is neither rewarded nor penalised.

**So nothing currently measures whether a model picks them correctly**, and the published accuracy
covers **23 of 30** categories.

## Why it matters more than an ordinary coverage gap

These six were added *because* both candidate models kept inventing them — `Road Hazard - Dust`
seven times, `- Accident` five, and `gpt-oss-20b` produced `Road Hazard - Dust` on both of the two
items it managed to classify before hitting the rate limit. Two vendors, two architectures, the same
fabricated label.

⚠ **That makes the obvious hypothesis untested rather than confirmed.** The reasoning for adding them
was *"the models keep reaching for a category the taxonomy lacks, so give them one"*. Whether adding
it actually **reduces invention** — or simply moves it, or introduces a new confusion between
`Road Hazard - Dust` and `Environmental - Air Pollution` — is exactly what these items would measure.

⭐ **And the confusion is designed-in, not accidental.** The owner's reasoning for keeping both
categories: *"Air pollution can be related to cement plants as well as road construction, anyway we
allow multiple classification."* That is right, and it means a dust complaint on an active works site
has **two** defensible answers. A benchmark that never presents that case cannot tell a model
resolving it well from one guessing.

## What to author

About 20 items, following `tests/data/benchmark/README.md` §4:

| Category | Needs | Note |
|---|---|---|
| `Road Hazard - Dust` | 4–5 | ⭐ **The important ones.** Include cases that are *road-surface* dust (gold: Road Hazard) and cases that are *plant or machinery emissions* (gold: Air Pollution), plus at least one where **both** genuinely apply and both are gold |
| `Road Hazard - Potholes` | 3 | The archetypal maintenance item |
| `Road Hazard - Flood And Landslide` | 3 | ⚠ Confusable with `Environmental - Drainage And Sewage Management` — include one of each |
| `Road Hazard - Accident` | 3 | ⚠ Confusable with `Safety - Road Safety Provisions` — the distinction is *an incident occurred* versus *a control is missing* |
| `Road Hazard - Animal On Road` | 3 | ⚠ Confusable with `Wildlife, Environmental - Wildlife Passage` — cause versus consequence |
| `Road Hazard - Others` | 2 | ⚠ **And two NEGATIVES** — items that fit a specific category, to check the catch-all is not absorbing them. A junk bucket that swallows everything is the failure mode this category invites |

Then re-run and compare the **invented-category rate** against the pre-change measurement:
**18 of 105 items on `gpt-5-nano`**, which is the number this change was meant to move.

## Definition of done

- [ ] ~20 items authored, covering all six, with the confusable pairs above
- [ ] `test_readme_records_the_uncovered_taxonomy_category` reduced to the SEAH category alone
- [ ] `tests/data/benchmark/README.md` §1 updated — the "gap, not a decision" row removed
- [ ] Invented-category rate re-measured and compared against 18/105
- [ ] ⚠ If invention did **not** fall, say so — the hypothesis behind D-51 would be wrong, and that
      is worth more than a quiet re-label

## Related

- [`the-model-invents-categories-and-they-are-stored.md`](the-model-invents-categories-and-they-are-stored.md) — D-51, why these were added
- [`../../../dpg/model-benchmarks.md`](../../../dpg/model-benchmarks.md) §3.1, §3.4 — the measurements
- [`../../../../tests/data/benchmark/README.md`](../../../../tests/data/benchmark/README.md) §1
