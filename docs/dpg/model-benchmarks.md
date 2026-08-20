# Model benchmarks — what this system actually scores

> **Status (2026-08-20): half the table is measured.** The **closed baseline** is complete —
> `gpt-5-nano`, the model production runs today, over all 105 items of the committed benchmark set.
> The **open column is empty**, and the reason is not technical: the Hugging Face account has no
> inference credit (**D-50**). Every open cell below says `⚠ Not measured` rather than sitting blank.
> **Owner:** [DPG-23](../sprints/2026-08-llm/03-open-models-spec.md#dpg-23) · **Set:**
> [`tests/data/benchmark/`](../../tests/data/benchmark/README.md) · **Harness:**
> [`scripts/ops/llm_benchmark.py`](../../scripts/ops/llm_benchmark.py)

> ⚠ **Every number on this page comes from synthetic, authored data (phase 1).** Authored text is
> cleaner than real complaints — better punctuated, more complete, less elliptical — so each figure
> is an **upper bound** on production accuracy, not an estimate of it. See
> [the set's provenance](../../tests/data/benchmark/README.md) §2.

---

## 1. Method, in one paragraph

The harness calls **the product's own functions** — `classify_and_summarize_grievance` and
`detect_sensitive_content_llm` — with the product's prompts, resolved through the registry the
product reads. Nothing is reimplemented. That is what makes this a **pre-flight check on a
production change** ([Q-04](../sprints/2026-08-llm/DECISIONS.md): production will run the open
configuration) rather than a parallel universe that agrees with production only by luck. Calls run
with `interactive=False`, so the 30-second interactive deadline does not truncate the very latency
measurement the run exists to produce.

Reproduce it:

```bash
docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \
  run --rm --no-deps -v "$PWD:/app" -w /app \
  backend python -m scripts.ops.llm_benchmark --models gpt-5-nano --tasks classify,detect \
  --concurrency 8 --json report.json
```

---

## 2. The benchmark table

**Baseline:** `gpt-5-nano` (`LLM_BASE_URL=https://api.openai.com/v1`), 105 items, 2026-08-20.
**Open:** `⚠ Not measured` — D-50.

| Metric | Current (closed) — `gpt-5-nano` | Open config | Delta |
|---|---|---|---|
| Classification precision *(set-level)* | **0.740** | ⚠ Not measured | — |
| Classification recall *(set-level)* | **0.805** | ⚠ Not measured | — |
| Category-set **F1** *(multi-label)* | **0.771** | ⚠ Not measured | — |
| Exact-set accuracy *(every gold label, no invented extras)* | **0.676** | ⚠ Not measured | — |
| Sensitive-content **recall** | ⚠ **Not measured — no positive scenarios in the committed set** (§5) | ⚠ Not measured | — |
| Sensitive-content **false-alarm rate** | **0.067** *(7 / 105)* | ⚠ Not measured | — |
| Field extraction F1 | ⚠ Not measured — the extraction path **has no production caller** (D-37) | ⚠ Not measured | — |
| Translation quality (chrF++ / human) | ⚠ Not measured | ⚠ Not measured | — |
| Nepali ASR **WER** | ⚠ **No baseline — voice has never been live** ([Q-13.2](../sprints/2026-08-llm/DECISIONS.md)), and there is no audio set ([followup](../sprints/2026-08-llm/followups/no-audio-subset-for-asr-benchmark.md)) | ⚠ Not measured | n/a |
| **p95 latency** vs the 30 s interactive budget | **24.6 s — PASSES** | ⚠ Not measured | — |
| **p99 latency** vs the 30 s interactive budget | **40.6 s — FAILS** (§4) | ⚠ Not measured | — |
| **Cost / 1,000 grievances** | **11.36 M prompt + 3.36 M completion tokens** (§6) | ⚠ Not measured | — |

---

## 3. ⚠ What the baseline run found, which is about production today

These are not open-versus-closed comparisons. They are measurements of **the model this system runs
right now**, and three of them are defects rather than quality scores.

### 3.1 ⭐ The model invents categories, on 17% of grievances

The classification prompt says *"Do not create new categories"*. On **18 of 105 items** it created
one anyway, and not at random — it produced a coherent, entirely fictional `Road Hazard - *` family:

| Invented category | Times |
|---|---|
| `Road Hazard - Dust` | 7 |
| `Road Hazard - Accident` | 5 |
| `Road Hazard - Animal On Road` | 3 |
| `Road Hazard - Others` | 2 |
| `Wildlife Passage` *(malformed — the classification half is missing)* | 2 |
| `Road Hazard - Flood And Landslide` | 1 |
| `Road Hazard - Potholes` | 1 |

**21 of the 32 false positives are invented categories.** Precision against the *real* taxonomy
would be 0.88 rather than 0.74 if these were the only error — so this single behaviour accounts for
most of the precision gap.

⚠ **Production logs these and stores them anyway.** `_warn_about_unlisted_categories`
(`LLM_services.py:358`) is explicit that it *"logs — never rejects"*, and the reason given is
sound for a near-miss name: *"a complainant's classification is not worth discarding because the
model named a category slightly wrong."* `Road Hazard - Dust` is not a near-miss name. It is a
category that exists nowhere, and it is **stored, shown to the complainant in the review step, and
synced to ticketing** — where it matches no filter, appears in no report grouped by category, and is
not found by the `high_priority` lookup (`ticketing_dispatch.py:117`), so it silently contributes
nothing to priority.

Logged as [D-51](../sprints/2026-08-llm/PROGRESS.md) with a
[follow-up](../sprints/2026-08-llm/followups/the-model-invents-categories-and-they-are-stored.md).

### 3.2 ⭐ The SEAH detector flags 5 of the 8 deliberate confusable negatives

Overall false-alarm rate is **6.7%** (7 of 105). But the committed set contains **8 items authored
specifically as the hard case** — gendered, and emphatically not harassment — and **5 of those 8
were flagged**:

| Item | What it is | Flagged |
|---|---|---|
| `gen-0034` | No separate toilet for women workers at the site | ❌ flagged |
| `gen-0035` | Unlit diversion route; a parent afraid for daughters walking home | ❌ flagged |
| `gen-0101` | Women paid less than men for the same work | ❌ flagged |
| `gen-0102` | One tap for the whole labour camp; women queue longest | ❌ flagged |
| `gen-0103` | Refused work by the contractor on the grounds of being a woman | ❌ flagged |
| `gen-0073` | Crop destruction; the contractor shouted at the complainant *(non-sexual abuse)* | ❌ flagged |
| `gen-0093` | Resettlement scattered a community | ❌ flagged |

**Why this matters more than a precision number.** The SEAH route is access-isolated: a flagged
grievance moves into a channel **most officers cannot see**. So an unequal-pay complaint, a
water-access complaint and a job-discrimination complaint do not merely get a wrong label — they
**effectively disappear** from the queue of the people who would have fixed them. That is exactly
the cost [`01_seah_detection_benchmark.md`](../models/01_seah_detection_benchmark.md) §1 sets out,
and the reason a benchmark measuring only recall is dangerous: it would rate this behaviour as
excellent.

⚠ **The prompt is the likely cause and it is fixable.** It says *"be extra sensitive… anything that
may imply sexual or gender harassment should be flagged"* and excludes *"land issues, property
disputes, or physical violence"* — but says nothing about **gender-related grievances that are not
harassment**, which is the entire confusable class. Logged as
[D-52](../sprints/2026-08-llm/PROGRESS.md).

⚠ **This is a false-alarm finding only.** It says nothing about whether the detector *catches*
harassment, because the committed set contains no harassment (§5). A prompt change made to reduce
these false alarms **must be re-measured against the owner's held-out positive set before it ships**
— tightening a recall-first detector without measuring recall is how a safeguarding miss gets
introduced by a well-intentioned fix.

### 3.3 The classification path over-routes to SEAH too

`Gender - Gender Discrimination And Harrassment` appears as a **false positive 3 times** in
classification. The review step keeps any category containing `"gender"`
([`01_seah_detection_benchmark.md`](../models/01_seah_detection_benchmark.md) §2), so classification
is a **second, independent** route into the confidential channel. Both signals over-fire on the same
material, and the system figure is the union — worse than either alone.

---

## 4. ⚠ Latency: p95 passes, p99 does not

| | classify | detect |
|---|---|---|
| p50 | 14.84 s | 3.73 s |
| p95 | **24.60 s** | 8.78 s |
| p99 | **40.64 s** | 20.91 s |
| max | 40.66 s | 42.04 s |
| over 30 s | **1.9%** | 0.95% |
| over 45 s | 0.0% | 0.0% |
| over 60 s | 0.0% | 0.0% |

**Read against the budget.** `CLASSIFICATION_WAIT_SECONDS = 30`. p95 fits with 5.4 s of headroom;
**p99 does not fit at all**, and the two slowest items took 40.6 s each.

**What that costs, precisely — less than it sounds and more than nothing.** The grievance is already
filed by the time the poll runs, and the classification reaches the officer through the two-minute
ticketing sync regardless. What ~2 complainants in 100 lose is **the chance to see and correct how
their own grievance was understood** — the accountability half of the feature.

**The recommendation.** The owner made the budget *a knob, not a wall* (2026-08-20). On this
evidence it does not need moving **for the closed model**: 45 s would capture 100% of measured
calls, but it would also make 98 complainants in 100 wait longer for a spinner they currently never
see, to rescue 2. ⚠ **Re-decide it when the open column exists.** A slower open model turns this
from a 2% tail into a routine event, and *then* the raise is the right call — at which point
`CLASSIFICATION_WAIT_SECONDS` **and** `TIMEOUT_CLASSIFY_INTERACTIVE` move **together** (DPG-15b's
tests pin that they stay coherent).

⚠ **These numbers are a floor.** The run used concurrency 8 against a warm provider from a
data-centre network. A complainant on a rural mobile connection adds latency this measurement does
not contain.

---

## 5. ⚠ Sensitive-content **recall** is not measured, and cannot be from this repository

The committed benchmark contains **zero positive SEAH scenarios**, by decision, not by omission: the
harassment narratives are held by the project owner and never enter the repository, because *"three
hundred realistic Nepali harassment complaints sitting in it will be read as leaked case data by
somebody, regardless of how the file is labelled"*
([`01_seah_detection_benchmark.md`](../models/01_seah_detection_benchmark.md) §3.3).

**So the SEAH numbers on this page are not independently reproducible from this repository.** That
is a real weakness in the evidence pack and it is the right trade. The harness accepts
`--seah-set /path/outside/the/repo.jsonl` and **refuses a path inside it**.

Recall is the metric with a safeguarding consequence, so:

- **it must be measured before any model change ships**, on the owner's set;
- it must be reported with the **number of independent scenarios**, not the row count, and
  labelled gold-seed or expanded;
- and no table may rank two candidates that differ by a few points — a hand-authored set cannot
  resolve that ([§4](../models/01_seah_detection_benchmark.md) has the arithmetic).

---

## 6. Cost — measured in tokens, priced separately

Tokens are the measurement and they do not drift. Prices do, so they are stated separately with the
date they were read.

| | Measured, 105 grievances × 2 model calls each |
|---|---|
| Calls | 212 |
| Prompt tokens | 1,192,578 |
| Completion tokens | 352,899 |
| **of which reasoning** | **330,944 — 93.8%** |
| **Per grievance** | 11,358 prompt + 3,361 completion |
| **Per 1,000 grievances** | **11.36 M prompt + 3.36 M completion** |

⚠ **93.8% of the completion budget is reasoning tokens** — invisible in the reply, fully billed.
This independently reproduces D-30's 92% at 40× the sample size. **Any cost estimate built from
output length understates this system by roughly 16×**, and any token cap sized for the visible
answer returns empty content (D-40).

⚠ **Cost scales with the taxonomy, not with the grievance.** The classification prompt injects the
24-category catalogue **twice, in two shapes** (`LLM_services.py:263-267`) — about 20,700 characters
before the complaint is added. Adding categories raises the per-grievance cost of every grievance.
**This is the single most promising cost lever in the system** and it is a prompt change, not a
model change.

**In dollars** — at a rate of `$0.05 / M` prompt and `$0.40 / M` completion, per 1,000 grievances:

> **≈ $1.91 per 1,000 grievances**
> ⚠ **The rate is a placeholder, not a measurement.** Confirm the current published price before
> quoting this figure to anyone, and record the date you read it. The token counts above are
> measured and stand on their own; the dollar figure is arithmetic on a number this document did
> not verify.

This is one half of the costed proposal to the Nepal Government that
[Q-19](../sprints/2026-08-llm/DECISIONS.md#q-19) commits to; the other half is
[DPG-25](../sprints/2026-08-llm/03-open-models-spec.md#dpg-25)'s self-hosted figure and the
crossover between them.

---

## 7. What is not measured, and why — no blanks

| Row | Why |
|---|---|
| **The entire open column** | **D-50** — the Hugging Face account's included inference credits are exhausted (HTTP 402). Unblocking is a purchase, not a commit. The harness, the set and the scoring rules are all built and tested; re-running is one command |
| Sensitive-content **recall** | The committed set has no positives, by decision (§5). Needs the owner's held-out set |
| **ASR / WER** | Two independent blockers: voice has never been live so there is **no baseline to beat** (Q-13.2 — the honest framing is *"we shipped a working ASR path where there was none"*, never *"we matched the incumbent"*), and there is **no audio** in the benchmark set |
| **Field extraction F1** | The contact-extraction path has **no production caller** (D-37). Benchmarking a dead path would spend budget to measure nothing |
| **Translation quality** | Needs either chrF++ against reference translations (which the set does not carry) or human rating. Neither is resourced |
| **Per-task token split** | The meter is global, so classify and detect cannot be priced separately from this run. The combined figure is the right unit anyway — production makes **both** calls per grievance |

---

## 8. Related

- [`tests/data/benchmark/README.md`](../../tests/data/benchmark/README.md) — the set, its provenance, and its limits
- [`open-model-configuration.md`](open-model-configuration.md) — the mechanism and the capability matrix
- [`../models/01_seah_detection_benchmark.md`](../models/01_seah_detection_benchmark.md) — the SEAH method, sample sizes, and why this is a screening instrument
- [`00_compliance_status.md`](00_compliance_status.md) — where these numbers are cited
- [`../sprints/2026-08-llm/PROGRESS.md`](../sprints/2026-08-llm/PROGRESS.md) — D-50, D-51, D-52
