# The grievance benchmark set — general slice

> **Status (2026-08-20):** built and committed. **Phase 1 — synthetic, authored, not resourced
> labellers.** Every number this set produces must be published as **synthetic (phase 1)**.
> **Owner:** [DPG-20](../../../docs/sprints/2026-08-llm/03-open-models-spec.md#dpg-20).
> **Consumed by:** [DPG-23](../../../docs/sprints/2026-08-llm/03-open-models-spec.md#dpg-23) (text-model
> evaluation), [DPG-35](../../../docs/sprints/2026-08-llm/04-pii-redaction-spec.md) (PII redaction).

---

## 1. What is here, and what is deliberately not

| File | Items | What it is |
|---|---|---|
| `general_classification.jsonl` | **105** | The benchmark. Categories, districts, scripts, PII spans, voice-origin subset |
| `gate_fixtures.jsonl` | **8** | **Not benchmark items.** They pin the `MIN_CLASSIFY_CHARS` gate itself — see §5 |

### ⚠ The SEAH slice is not in this repository, and that is a decision

Harassment and abuse narratives are **not committed here and never will be**. The reason, in the
owner's decision of 2026-08-19 and written up in
[`docs/models/01_seah_detection_benchmark.md`](../../../docs/models/01_seah_detection_benchmark.md) §3.3:

> *"Three hundred realistic Nepali harassment complaints sitting in it will be read as leaked case
> data by somebody, regardless of how the file is labelled."*

**The consequence, stated here so it is stated wherever the numbers are:** SEAH recall figures are
**not independently reproducible from this repository**. That is a real weakness in the evidence
pack and it is the right trade. Do not "fix" it by committing the SEAH set, and do not drop the SEAH
numbers either — sensitive-content recall is the one metric with a safeguarding consequence.

**What this means for the taxonomy.** The live taxonomy has **30** categories. This set has gold
items for **23**, and seven are uncovered for two different reasons:

| Uncovered | Why |
|---|---|
| `Gender - Gender Discrimination And Harrassment` | **Deliberate and permanent.** It is the category the SEAH route keys on, so authoring realistic items for it would be authoring the very material §3.3 excludes |
| The six `Road Hazard - *` categories | ⚠ **A gap, not a decision.** Added 2026-08-21 (D-51) after *both* candidate models independently invented a road-hazard category. They appear here only as **acceptable alternates** on existing items, so **nothing in this set measures whether a model picks them correctly.** Authoring gold items for them is [a logged follow-up](../../../docs/sprints/2026-08-llm/followups/road-hazard-categories-have-no-benchmark-items.md) |

⚠ **Do not read the headline accuracy as covering the whole taxonomy.** It covers 23 of 30, and the
seven it does not cover include the newest and least-tested.

**What this set does carry, and why it matters more than it looks:** eight `seah_confusable` items —
gender-related grievances that are emphatically **not** harassment (unequal pay, no separate
toilet, an unlit route home, a woman alone when the demolition crew arrived). Those are the
**false-alarm** half of the SEAH measurement, and they are safe to commit because none of them
describes an incident. A benchmark that measures only recall will happily recommend a model that
flags everything; these items are what stops that.

## 2. Provenance — synthetic, and the sentence that must travel with every number

**Decided [Q-15](../../../docs/sprints/2026-08-llm/DECISIONS.md), 2026-08-17: phase 1 is synthetic and
committed; a hybrid pass follows once the live project has generated real grievances.** Read with
**Q-16 — there is no budget or staff time for labellers**, which reshapes this from a labelling
programme into *a small authored set that grows with the project*.

- **Authored by:** the engineer implementing DPG-20, 2026-08-20, from the project's own scenario
  material (`ticketing/seed/mock_tickets.py`, the KL Road category taxonomy, the demo scenarios in
  `CLAUDE.md`) and from the road-project grievance patterns those describe.
- **Invented in every detail.** No real complainant, no real case, no real name, no real number.
  Every phone number below is in the `98…` mobile range but is not a working Nepali number.
- **Not expanded by an LLM.** Every item was written directly. There are no paraphrase variants, so
  each row is an independent scenario and the row count *is* the scenario count. (Contrast the SEAH
  method doc §3.4, where expansion is planned and the reporting unit therefore differs from the row.)
- **Single author, so there is no inter-labeller agreement figure.** ⚠ That is a limitation, not an
  omission: with one author the labels encode one person's reading of the taxonomy, and the
  `note` field on every item exists so a second reader can adjudicate rather than guess.

### ⚠ What synthetic data cannot tell you

Authored text is **cleaner than real complaints** — better punctuated, more complete, less
elliptical. Every accuracy number from this set is therefore an **upper bound** on production
accuracy. Say so wherever a number appears. A 91% on synthetic data reported as production accuracy
is the kind of claim that discredits an otherwise sound submission.

### ✅ What synthetic data does better than real data, which is why phase 1 is honest rather than a compromise

Edge cases that matter most are rarest in real traffic, so a real corpus of this size would contain
none of them. Here they are guaranteed:

| Edge tag | Items | Why it is in the set |
|---|---|---|
| `devanagari_digits` | 6 | A phone number written `९८४१२३४५६७`. A redactor matching `\d` misses it completely — see `gen-0066` |
| `mixed_digits` | 1 | Latin **and** Devanagari digits in one sentence (`gen-0104`). Real on a Nepali phone keyboard |
| `code_switching` | 6 | Nepali–English mixing inside a sentence, which is the normal register here |
| `third_party_name` | 2 | A name belonging to someone who never consented (`gen-0068`, `gen-0069`). The hardest case for DPG-35 |
| `self_identification` | 5 | Name and number in the narrative itself, which is what voice intake produces |
| `multi_label` | 8 | Genuinely two categories. Single-label scoring marks a correct answer wrong — this is why DPG-23 scores set-level |
| `seah_confusable` | 8 | Gendered but not harassment. The false-alarm control (§1) |
| `voice_origin` | 6 | Structurally different: no field boundaries, self-identification in the opening sentence, fillers, run-on |

## 3. Phase 2 — hybrid, and what triggers it

**Trigger:** the pilot generating real grievances in the two demo districts. When that happens:

- a **held-out real set stays outside this repository**, exactly as the SEAH slice does;
- this committed synthetic set remains, because it is the reproducibility artefact indicator 4 wants
  and the one a reviewer can run themselves;
- **every published number says which set it came from.** A synthetic number and a real number are
  not comparable and must never appear in the same column without a label.

This is recorded so a later reader knows the hybrid pass was **planned**, not forgotten.

## 4. Item schema

```jsonc
{
  "id": "gen-0001",                    // stable; referenced from result files and from docs
  "text": "…",                         // the grievance as a complainant would enter it
  "script": "devanagari|roman_nepali|english|code_mixed",
  "origin": "typed|voice",             // voice-origin text is structurally different — see §2
  "district": "Jhapa|Morang|Sunsari",  // the KL Road districts, per the ticketing seed
  "categories": ["…"],                 // GOLD. One or more, canonical form (§4.1)
  "categories_acceptable": ["…"],      // also defensible; scored as neither right nor wrong (§4.3)
  "high_priority": true,               // from the taxonomy's own column, NOT from intuition (§4.2)
  "sensitive": false,                  // SEAH route expected? false for every committed item (§1)
  "pii": [{"type": "person_name|phone|address", "text": "…"}],   // §4.4
  "edge": ["devanagari_digits", …],    // why this item earns its place
  "note": "…"                          // how the label line was drawn, for a second reader
}
```

### 4.1 ⚠ Category strings exist in two forms, and grading depends on knowing which

The taxonomy is loaded into `CLASSIFICATION_DATA` under a **canonical key**:

```python
f"{row['classification'].replace('-', ' ').title()} - {row['generic_grievance_name'].replace('-', ' ').title()}"
```

…but the **classification prompt** shows the model the *raw* CSV values
(`backend/services/LLM_services.py:263`). So the model is asked to reply with
`"Gender, Social - Gender-Based Access Issues"` while the canonical key is
`"Gender, Social - Gender Based Access Issues"` — hyphen versus space, and different casing on
`"Relocation issues - …"`.

**`categories` in this file is always the canonical key form**, matching
`backend/dev-resources/lookup_tables/list_category.txt`, and the harness normalises model output to
it before scoring. Grading raw strings against canonical keys would deflate every accuracy number by
the width of that mismatch, and it would look like a model problem.

⚠ **The fold is the product's, not the harness's** (changed 2026-08-25, D-51). It lives in
`backend/services/category_resolution.py` and the harness imports it, because the classifier now uses
the same rule to repair an off-catalogue value before storing it. Two copies of "what counts as the
same category" would mean the benchmark reporting a precision the product does not have.

### 4.2 ⚠ `high_priority` is the taxonomy's value, and it disagrees with production

Severity is **not** the author's judgement of how bad a grievance is. It is the taxonomy's own
`high_priority` column, combined across an item's gold categories with the same rule production
uses — *"True when any selected category is marked high_priority"*
(`backend/actions/utils/ticketing_dispatch.py:117`).

⚠ **It is read from the CSV's final field positionally, not through `CLASSIFICATION_DATA`**, because
those two do not agree. Five rows of `grievances_categorization_v1.1.csv` carry a column count the
header does not declare, so `csv.DictReader` hands `row["high_priority"]` a follow-up-question string
instead of `True`, and four categories silently load as not-high-priority — among them
`Environmental - Air Pollution` (the dust complaint, demo scenario 1) and
`Gender - Gender Discrimination And Harrassment` (the SEAH route). The defect is in the seeded
database too, so re-seeding re-applies it.

**This set records the authored value, so it is already right when the loader is fixed.** Two tests
hold that line, one of them a canary that fails when the defect is repaired so this note gets
removed rather than outliving it. Full write-up:
[`followups/taxonomy-csv-column-drift-silently-clears-high-priority.md`](../../../docs/sprints/2026-08-llm/followups/taxonomy-csv-column-drift-silently-clears-high-priority.md).

### 4.3 `categories_acceptable` is not a second gold label

The system returns `grievance_categories` **and** `grievance_categories_alternative`, so a model
naming a defensible neighbour is not wrong. Items where two categories genuinely both apply carry
**both in `categories`** and are tagged `multi_label`. `categories_acceptable` is the weaker case: a
reading a careful officer would accept but would not have chosen first. The harness neither rewards
nor penalises it.

### 4.4 PII is stored as a substring, not as an offset pair

Character offsets into Devanagari text are error-prone to author and silently rot the first time a
typo is fixed. So each span is stored as the **literal substring**, and
`tests/backend/test_benchmark_set.py` asserts every one of them occurs **exactly once** in its item.
Offsets are derived by search at load time and are therefore correct by construction. An ambiguous
span fails the build rather than producing a wrong offset.

## 5. `gate_fixtures.jsonl` — pins, not benchmark items

`MIN_CLASSIFY_CHARS = 25` ([DPG-19](../../../docs/sprints/2026-08-llm/PROGRESS.md)): below it, **no
model is called** and the result is `{"skipped": "too_short"}`. An item under the floor therefore
measures the gate, not the model, and would silently deflate every accuracy number.

**Every item in `general_classification.jsonl` is above the floor** — the shortest is 83 characters —
and a test pins that so nobody later adds a short one. These eight fixtures live in a separate file
so that nobody later "fixes" them into the benchmark.

⚠ **`gate-06` exists because the documentation was wrong.** `llm_config.py` and `.env.open` both
described the threshold as *"non-whitespace characters"*. The code is
`len((text or "").strip()) < min_classify_chars` — leading and trailing whitespace is stripped, but
**internal whitespace counts**. `gate-06` is 25 characters and only 13 non-whitespace, and it is
**not** skipped. Both comments were corrected in the same commit that added this file.

## 6. Licence of the data

**[CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/) — public domain dedication.**

`SPDX-License-Identifier: CC0-1.0`

The DPG questionnaire's indicator 4 asks for dependencies of *"the code, the model **and the
data**"*. This is an evaluation set with no restrictions of any kind, so a reviewer can run it,
publish results from it, or extend it without asking anyone.

> **The data limb is narrower here than it looks, and that is worth stating.** This system does no
> training and no fine-tuning — every model call is zero-shot prompting against an author-maintained
> category taxonomy. There is therefore **no training-data licence question at all**. What was
> missing was an *evaluation* set, which is what this is. Whether the DPGA also expects the eval set
> **and the prompt templates** published as artefacts is open with the consultant
> ([`00_compliance_status.md`](../../../docs/dpg/00_compliance_status.md) Q-04-04); if the answer
> is yes, this directory is already half of it.

⚠ The **taxonomy** the labels are drawn from (`backend/dev-resources/grievances_categorization_v1.1.csv`)
is project material under the repository's Apache-2.0 licence, not CC0. The category *strings* appear
here as labels; the taxonomy file itself is not redistributed by this directory.

## 7. Size — recorded against the aspirational target

| | Target in the spec | Actually built |
|---|---|---|
| Text items | ~300 | **105** |
| Voice items | ~50 | **6** (text only — see below) |
| Independent scenarios | — | **105** (no expansion, so rows = scenarios) |

**The 300/50 target was aspirational and never resourced** ([Q-16](../../../docs/sprints/2026-08-llm/DECISIONS.md):
no labeller budget or staff time). Nothing here implies labellers were funded. 105 items is sized
for **signal, not volume**, which [Q-19](../../../docs/sprints/2026-08-llm/DECISIONS.md) makes a cost
decision as well as a time one: every item is re-run per candidate per task in DPG-23, and the
inference envelope is shared with the pilot's own traffic.

⚠ **What 105 items can and cannot support.** With 23 categories covered at 2–7 items each, this set
is a **screening instrument**: it will catch a model that is broken on Nepali, on Devanagari digits,
or on multi-label output. It **cannot** resolve a few points of difference between two decent
candidates, and no table built from it may rank candidates that differ by a few points. The
sample-size arithmetic is in
[`docs/models/01_seah_detection_benchmark.md`](../../../docs/models/01_seah_detection_benchmark.md) §4
and it applies here too.

⚠ **There is no audio.** The six `voice_origin` items are **transcript-shaped text**, which is what
the classification and extraction tasks consume. Measuring **word error rate** needs recorded audio
with verbatim transcripts, and nothing in this repository can author a recording.
[DPG-22](../../../docs/sprints/2026-08-llm/03-open-models-spec.md#dpg-22) needs that audio and does not
have it — logged as a deferral in
[`followups/no-audio-subset-for-asr-benchmark.md`](../../../docs/sprints/2026-08-llm/followups/no-audio-subset-for-asr-benchmark.md).

## 8. Running it

```bash
# validate the set (no model calls, no network, no cost)
make test-backend                     # or: pytest tests/backend/test_benchmark_set.py -v

# score a model against it — see DPG-23
python -m scripts.ops.llm_benchmark --help
```
