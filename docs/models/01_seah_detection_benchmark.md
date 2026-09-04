# Benchmarking the SEAH detection check

**Status (2026-08-19):** the method below is agreed and the collection instrument exists. **The test
set does not exist yet** — the request has gone to the Nepal team. No number in this document has
been measured; every figure is a sample-size calculation, not a result.
**Owner:** the text-model evaluation work, building on the benchmark set it defined.

---

## 1. The decision this supports

One question: **is a candidate model safe to put on the SEAH detection path?**

Not "which model is best". That distinction is the whole design constraint — see §4 — and getting it
wrong would mean publishing a ranking the data cannot support.

The check reads every grievance and decides whether it reports sexual or gender-based harassment.
When it says yes, the grievance is routed into the confidential SEAH channel. So there are two ways
to be wrong, and both cost something real:

| Error | What it costs |
|---|---|
| **Miss** (harassment not flagged) | The report is handled as an ordinary road complaint. **The reason the SEAH route exists is that this must not happen**, and it is not recoverable — nobody downstream knows to look |
| **False alarm** (ordinary complaint flagged) | A SEAH officer reads an ordinary grievance and returns it to the standard queue. Costs review time and delay; **carries no risk to the complainant**, because a SEAH officer seeing a dust complaint discloses nothing to anyone |

⭐ **These costs are deliberately asymmetric, and the detector is tuned accordingly.** The system
**prefers false alarms to misses on purpose**: the cheap error is recoverable by a trained human, the
expensive one is not. So a false-alarm figure on this page is **a measured price, not a defect**, and
it must never be reported as one.

⚠ **Two consequences that follow immediately, and both are easy to get wrong:**

1. **A benchmark that measures only recall will happily recommend a model that flags everything** —
   so false alarms are still measured, to price the trade rather than to fail a candidate on it.
2. **Tightening the prompt to reduce false alarms trades away the property the design is built on.**
   Any such change must be measured against recall **first**. Reducing this number is not, by itself,
   an improvement.

⚠ **The trade is only safe while the return path works.** If a cleared case cannot be sent back to the
standard queue, the cheap error stops being cheap and this whole table is wrong. See
[`../dpg/00_compliance_status.md`](../dpg/00_compliance_status.md) §9 for the state of that path.

## 2. What is actually being measured — there are three signals, not one

Detection is not a single model call, and a benchmark that forgets this will understate the floor:

| Signal | Where | Model? |
|---|---|---|
| Deterministic keyword detector, scored | `backend/shared_functions/keyword_detector.py`, run as slot validation **inside the conversation** | none |
| The LLM detection call | `detect_sensitive_content_llm` | yes |
| The classification's own categories | the review step keeps any category containing `"gender"` | yes, same call |

**Report two numbers: the LLM call alone, and the system (keyword ∪ LLM).** The first is what a model
change moves. The second is what a complainant actually experiences, and it is the number that
Q-14's fail-open decision rests on — see [`06_llm_service.md`](../services/06_llm_service.md).

## 3. The data

### 3.1 Where it comes from, and the rule that cannot bend

Seeds are **authored by the Nepal team from professional experience** — realistic in phrasing and
scenario, invented in every detail.

> ⚠ **No real case material, ever.** Not case files, not notes, not a redacted real complaint. For
> SEAH in a ward-sized community, removing names does not de-identify: *"the woman whose husband
> works at the culvert site"* is an identification. This is the most sensitive data class in the
> project, and the privacy assessment's central claim depends on it never entering the repository.
> Q-15 already committed to synthetic for phase 1; this stays inside that.

### 3.2 The collection instrument

An Excel workbook, sent to the team, holding its own instructions so the covering email stays short:

| Sheet | Contents |
|---|---|
| **1. Read me first** | Purpose · the no-real-cases rule · which sheet to use · how to write the text · script mix · worked examples |
| **2. Full set (10 categories)** | 50 rows, `should_flag` and `why` pre-filled, 5 per category |
| **3. Short set (6 categories)** | 30 rows, 3 flag / 3 no-flag — the fallback when time is short |

Columns: `complaint_text` · `should_flag` · `why (category)` · `script` · `note (optional)`.
The contributor writes only the text and picks the script; everything else is a dropdown.

Two properties of the request that matter more than they look:

- **Script mix.** Roughly 3 in Devanagari and 2 in Roman Nepali per category, plus some
  Nepali-English code-mixing. Romanised Nepali is what a large share of complainants actually type
  on a phone, and a set written only in Devanagari measures a cleaner problem than production.
- **The `note` column.** One line on how the contributor drew the line. It is what allows faithful
  expansion (§3.3) and what lets a later reviewer adjudicate a disagreement about a label.

### 3.3 Where the dataset lives — deliberately not in git

**The completed workbook and every derived dataset stay out of the repository.** Reasons, in order:

1. The repository is public under Apache-2.0 and part of a DPG submission. Three hundred realistic
   Nepali harassment complaints sitting in it will be read as leaked case data by somebody,
   regardless of how the file is labelled.
2. It is test material, not product. Nothing in the running system loads it.
3. ⚠ **It must never be seeded into the demo database.** Officers browsing the demo would see what
   look like real SEAH cases.

The consequence to accept honestly: **the published numbers are not independently reproducible from
the repository alone.** State that wherever they are published, and keep the workbook with the
project owner.

### 3.4 Expansion — what it buys, and what it does not

Seeds can be expanded with an LLM into a larger set. This is worth doing, and it is worth being
precise about why, because the obvious reading is wrong:

> **Paraphrases multiply rows, not evidence.** Ten paraphrases of one scenario share its vocabulary,
> its framing, and the generating model's fingerprint. They are one scenario measured ten times, not
> ten scenarios.

So the reporting unit differs from the row:

| Unit | What it measures | How it is reported |
|---|---|---|
| **Scenario** (a team seed) | recall / false-alarm rate — the numbers that go in the evidence pack | per scenario, majority across its variants |
| **Variant** (an expansion) | robustness to phrasing, script and register | phrasing sensitivity, separately |

Two rules follow:

- **Never expand with the model under test, or its family.** A model finds its own idiom easy.
- **Disclose the direction of the bias.** LLM-written text is systematically easier for *any* LLM to
  parse than human text, so expanded figures flatter every candidate. Publish gold-seed-only and
  expanded numbers side by side; **where they disagree, the gold number wins.**

## 4. How many — and what the set can never tell us

Sample sizes for a proportion (Wilson, 95%), assuming a model that truly catches ~90%:

| Independent positive scenarios | 95% CI on recall | Verdict |
|---|---|---|
| 20 | [0.70, 0.97] — ±14pp | catches a broken model, nothing else |
| **30** | [0.74, 0.97] — ±11pp | **minimum defensible go/no-go** |
| **50** | [0.79, 0.96] — ±9pp | **a figure that can be published** |
| 100 | [0.83, 0.94] — ±6pp | tighter; roughly two days of authoring |

⚠ **And the limit that decides the framing.** Comparing two models needs paired discordance
(McNemar), which is far more expensive:

| Recall gap to detect | Paired positive scenarios needed (80% power) |
|---|---|
| 30pp | ~87 |
| 20pp | ~196 |
| 15pp | ~348 |
| 10pp | ~784 |

**No hand-authored set will resolve a 10pp difference between two decent models.** Therefore:

- the benchmark is a **screening instrument** — it stops an unsafe change;
- **any published table must say so**, and must not rank candidates that differ by a few points;
- a 3pp "win" is noise, and reporting it as a result is the failure mode this section exists to
  prevent.

## 5. Composition

Positives are stratified by **explicitness**, because a set of only explicit cases scores full marks
on every model and discriminates nothing. Negatives are the **confusable** ones, because that is
where over-flagging comes from.

| # | Category | Flag? | Why it is in the set |
|---|---|---|---|
| 1 | Sexual favour demanded in exchange for something | yes | The classic infrastructure-project pattern |
| 2 | Unwanted physical contact | yes | Includes the explicit floor — missing these disqualifies a model |
| 3 | Sexual comments, propositions, obscene messages | yes | |
| 4 | Following, staring, filming, waiting outside | yes | The prompt explicitly asks for these to be flagged |
| 5 | ⭐ **Not said directly** — hints, shame, fear, only the consequence | yes | **Where models actually differ**, and where the cultural framing lives |
| 6 | Reported by someone else on the person's behalf | yes | Different grammatical shape; matches the focal-point route |
| 7 | ⭐ Land, compensation or property dispute, including threats | no | Explicitly excluded by the prompt; the commonest false alarm |
| 8 | Violence or abuse with no sexual element | no | Explicitly excluded |
| 9 | Ordinary complaint from or about women and girls | no | Gender of the complainant is not the signal — a real trap |
| 10 | Wages, unpaid work, unsafe conditions | no | |

The short set merges these into six (3 flag / 3 no-flag): clear harassment · not said directly ·
reported by another · land and compensation · non-sexual violence · ordinary complaints from women.

**If only part of the set arrives, categories 5 and 7 are the ones that carry the decision.**

## 6. Running it

Requirements on the harness, each of which comes from something that has already gone wrong:

1. ⚠ **Prove authentication before reporting a single miss.** Assert that one known-positive is
   detected, and abort if it is not. On 2026-08-18 a 401 presented as *"the model cannot detect
   harassment"* — a config error reading exactly like a quality finding, because the SEAH path
   fails open by design — an LLM outage degrades the second pass and leaves the deterministic
   keyword detector running, which is what makes fail-open defensible. Any benchmark that skips this
   will eventually publish a broken key as a model result.
2. **Run the same items through every candidate**, so comparison is paired.
3. **Record the raw reply**, not just the verdict — a miss caused by truncation or a schema
   violation is a different problem from a miss caused by judgement.
4. **Report the confusion matrix**, not recall alone: misses and false alarms have different costs
   (§1), and one number hides that.
5. **Report `level` agreement as observational only.** The set is not sized for a three-class metric.
6. Report **cost per call**, not per thousand tokens — a reasoning model spends thousands of hidden
   tokens per call, so per-token pricing understates it by an order of magnitude.

## 7. Publishing

Every figure carries three labels: **synthetic (phase 1)**, the **number of independent scenarios**
(not rows), and whether it is **gold-seed or expanded**. A recall figure without a scenario count is
not interpretable, and one without the synthetic marker overstates what was tested.

State the known weaknesses in the same place as the result — authored text is cleaner than real
complaints, expansion flatters every model, and the set cannot resolve small differences. A reviewer
who finds an unstated limitation stops trusting the stated ones.

## 8. Related

- [`../dpg/model-benchmarks.md`](../dpg/model-benchmarks.md) — what the models score on the committed
  Nepali set, one dated value per metric, with the open-accuracy column marked as the gap it is
- [`../DECISIONS.md`](../DECISIONS.md) — the public record of forks taken, with what was rejected
- [`06_llm_service.md`](../services/06_llm_service.md) — the three SEAH signals, and the measured
  per-model capability table
- [`00_compliance_status.md`](../dpg/00_compliance_status.md) — where these numbers are published
- [`privacy-assessment.md`](../dpg/privacy-assessment.md) — why real case material cannot be used
