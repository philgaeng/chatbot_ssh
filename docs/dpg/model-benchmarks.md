# Model benchmarks — what this system scores

> **What this is.** Measured results for the models this system calls, on a committed 105-item Nepali
> grievance set. **Measurements dated 2026-08-20 / 08-21**; where a finding has since been acted on,
> it says so and carries its own date. ⛔ **The classification measurements are now stale** — see the
> box below.
>
> **What it is not.** Not a model selection — see [§4](#4-the-open-column--the-one-gap) and
> [§5](#5-seah-recall--not-measurable-from-this-repository). Not an estimate of production accuracy:
> the set is authored, so every figure is an **upper bound**
> ([provenance](../../tests/data/benchmark/README.md)).
>
> **One value per metric.** [§2](#2-the-results) holds the current number for every cell, dated. Where
> a number changed, the change is in [§7](#7-what-changed-on-2026-08-21-and-why) and nowhere else.
>
> ## ⛔ Read this before quoting any classification number (added 2026-09-03)
>
> **Every classification figure below was measured against a code path that no longer exists.** On
> 2026-09-03 redaction became the **default** at the model-call chokepoint, so the text the model now
> receives has names, phones and addresses replaced by `<PERSON_1>`-style placeholders. The harness
> calls **the product's own function** — deliberately, and it is the right design — which means it
> now inherits that default and would measure something different.
>
> **What this does and does not invalidate:**
>
> | | |
> |---|---|
> | ⛔ **Stale for the live path** | Every classification cell in §2, the 08-21 baseline (P 0.773 / R 0.752 / exact 0.686), and §3.1's invention rate |
> | ✅ **Still valid** | SEAH detection figures — the detection prompt and its inputs are unchanged; latency and token counts, which move with prompt size, not with placeholder substitution |
> | ⚪ **Unaffected in kind** | §4 (the open column is still unmeasured) and §5 (SEAH recall is still not measurable here) |
>
> ⚠ **The direction of the effect is unknown and should not be guessed.** The design reasoning for
> substituting a token rather than deleting the words — the sentence keeps its grammatical shape, so
> the classifier still parses it — is a **stated rationale, not a measurement.** It may cost nothing;
> it may cost something; nobody has run it.
>
> ⭐ **This is a cheap re-run and it is the highest-value one available**, because it is the only
> number in this document that is blocked on neither money nor absent data. It needs one command.
>
> **Set:** [`tests/data/benchmark/`](../../tests/data/benchmark/README.md) ·
> **Harness:** [`scripts/ops/llm_benchmark.py`](../../scripts/ops/llm_benchmark.py)

---

## 1. Method

The harness calls **the product's own functions** — `classify_and_summarize_grievance` and
`detect_sensitive_content_llm` — with the product's prompts, resolved through the registry the product
reads. Nothing is reimplemented, which is what makes this a pre-flight check on a production change
rather than a parallel universe that agrees with production only by luck. Calls run with
`interactive=False`, so the 30-second deadline does not truncate the latency measurement.

```bash
docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \
  run --rm --no-deps -v "$PWD:/app" -w /app \
  backend python -m scripts.ops.llm_benchmark --models gpt-5-nano --tasks classify,detect \
  --concurrency 8 --json report.json
```

---

## 2. The results

**Closed:** `gpt-5-nano` on `api.openai.com` — what production runs today. **Open:**
`openai/gpt-oss-20b` via the Hugging Face router. 105 items per task. Every cell carries its
measurement date; every empty cell names its blocker.

| Metric | Closed — `gpt-5-nano` | Open — `openai/gpt-oss-20b` |
|---|---|---|
| Classification precision *(set-level)* | **0.773** · 08-21 | ⚠ Not measured — [§4](#4-the-open-column--the-one-gap) |
| Classification recall *(set-level)* | **0.752** · 08-21 | ⚠ §4 |
| Category-set **F1** *(multi-label)* | **0.762** · 08-21 | ⚠ §4 |
| Exact-set accuracy | **0.686** · 08-21 | ⚠ §4 |
| Items with an **invented** category | **4 / 105** · 08-21 ([§3.1](#31--the-model-invents-categories)) | ⚠ Not measured — but **2 of the 2 items it reached** invented one ([§3.4](#34--both-models-invent-the-same-category--which-makes-it-a-taxonomy-finding)) |
| Sensitive-content **recall** | ⚠ **Not measurable from this repository** — [§5](#5-seah-recall--not-measurable-from-this-repository) | ⚠ Same — and it is the number that decides the row below |
| Sensitive-content **false-alarm rate** *(⭐ a priced trade, not a defect — [§3.2](#32--the-seah-detector-flags-5-of-the-8-deliberate-confusable-negatives))* | **0.067** *(7 / 105)*, incl. **5 of 8** confusables · 08-20 | **0.000** *(0 / 105)*, incl. **0 of 8** · 08-20 — ⚠ **uninterpretable without recall** ([§3.5](#35--the-open-model-flags-nothing--which-is-not-the-same-as-being-better)) |
| **p95 / p99 latency**, classification *(30 s budget)* | **20.3 s / 24.5 s — both pass** · 08-21 | ⚠ §4 |
| **p50 / p95 latency**, SEAH detection | 3.73 s / **8.78 s** · 08-20 | 0.35 s / **0.49 s** · 08-20 — **≈18× faster** |
| **Prompt tokens** per classification | **3,277** · 08-21 | ⚠ §4 |
| **Completion tokens** per grievance *(both calls)* | **3,361**, **93.8% reasoning** · 08-20 | ⚠ §4 |
| Field extraction F1 | ⚠ The extraction path **has no production caller** — benchmarking it would spend budget to measure nothing | ⚠ Same |
| Translation quality *(chrF++ / human)* | ⚠ Needs reference translations the set does not carry, or human rating. Neither is resourced | ⚠ Same |
| Nepali ASR **WER** | ⚠ **No baseline — voice has never been live**, and the set holds no audio | ⚠ And the router **serves no `/v1/audio/*` route** ([`open-model-configuration.md`](open-model-configuration.md)) |

⚠ **Why detection is dated 08-20 and classification 08-21.** The 08-21 change
([§7](#7-what-changed-on-2026-08-21-and-why)) touched the **classification** prompt and the taxonomy
only. The detection figures stand as measured, and will move only if the detection prompt changes.

⛔ **And why every classification cell is now stale**, including the ones dated 08-21: the input to
that path changed on 2026-09-03 — see the box at the top. **Two independent reasons to re-run**, and
they arrived three weeks apart: the D-51 storage guard (2026-08-25) and redaction (2026-09-03).
Neither has been run. **One command clears both.**

⚠ **Only one open candidate has been benchmarked at all.** The other five reachable candidates have
capability measured but no accuracy ([`open-model-configuration.md`](open-model-configuration.md)).

---

## 3. What the measurements found

### 3.1 ⭐ The model invents categories {#31--the-model-invents-categories}

The prompt says *"Do not create new categories"*. On **4 of 105 items** it created one anyway — down
from 18 before the taxonomy change ([§7](#7-what-changed-on-2026-08-21-and-why)). **3 of the 4 are not
new concepts**: they are `Cultural Site Disturbances` and `Wildlife Passage` with the classification
half of the name missing — a **formatting** failure that predates the change. **The fourth,
`Road Hazard - Noise Pollution`, is not a new concept either** — `Noise Pollution` is a real category
under `Environmental`, and the model filed it under the wrong parent. Read together, **every one of
the four is a correct leaf with a wrong or missing parent**, which is what made a deterministic repair
possible.

✅ **Fixed 2026-08-25 — an off-catalogue category no longer reaches storage.** Until then it did:
the check *"logged — never rejects"*, which is right for a near-miss name and wrong for a category
that exists nowhere. Such a value was **stored, shown to the complainant as the system's understanding
of their complaint, and synced to ticketing**, where it matched no filter, appeared in no report, and
was missed by the `high_priority` lookup (`ticketing_dispatch.py:117`) — contributing nothing to
priority, silently.

**What replaced it** (`LLM_services.py:416` → [`category_resolution.py`](../../backend/services/category_resolution.py)):

| Tier | Mechanism | Effect |
|---|---|---|
| 1 | The permitted categories are sent as a **JSON-Schema enum**, rebuilt from the live catalogue on every call | A provider that honours `json_schema` **cannot** return one that does not exist. ⚠ Not a guarantee — `Qwen3.5-9B` accepts the schema and ignores it, and the ladder degrades on weaker models |
| 2 | Values are folded to the canonical key form and matched; an unmatched value is resolved by its **leaf**, which is unique across the taxonomy | Repairs all four of the cases above, deterministically, with **no second model call** |
| 3 | Anything still unresolved is **dropped and logged**, never stored. If that leaves an item with no category at all, the model's own top **alternative** is promoted | The stored value is always a real category — and the item does not lose its classification |

⚠ **No fuzzy matching and no repair prompt.** An ambiguous leaf — one two classifications could claim
— is refused rather than guessed, because a wrong category is stored and displayed just as silently as
an invented one. A second model call was considered and rejected: it would have cost a round trip on
the interactive path, and it would have **buried the signal** — eighteen items asking for a
`Road Hazard` family is precisely how the taxonomy gap in [§7](#7-what-changed-on-2026-08-21-and-why)
was found.

⚠ **The figure above is a *model* metric and stays one.** Because the repair happens inside the
function the harness calls, a re-run would otherwise report a flattering **0 / 105** for any model.
`InventionMeter` reads the rate from the resolution log instead, so the row keeps measuring what the
model did rather than what the product now tolerates.

⏳ **Not yet re-measured.** The guard changes what is *stored*, not what the model *says*, so the
`4 / 105` above stands. Set-level precision in [§2](#2-the-results) is scored against the returned
categories, which are now repaired, so it should rise on the next run — **by how much is unmeasured
until that run happens**.

### 3.2 ⭐ The SEAH detector flags 5 of the 8 confusable negatives — which is the design working {#32--the-seah-detector-flags-5-of-the-8-deliberate-confusable-negatives}

False-alarm rate is **6.7%** (7 of 105). The set contains **8 items authored as the hard case** —
gendered, and emphatically not harassment — and **5 were flagged**: no separate toilet for women
workers · an unlit route home from school · unequal pay for the same work · one tap for the whole
labour camp · refused work for being a woman. *(Plus non-sexual abuse and a resettlement complaint.)*

⭐ **This is a priced trade, not a defect.** The detector is **deliberately tuned recall-first**,
because the two errors are not symmetric:

- a **miss** leaves a harassment report in the ordinary queue where nobody knows to look for it —
  **unrecoverable**, and the reason the SEAH route exists;
- a **false alarm** costs a SEAH officer a review. **A SEAH officer reading a dust complaint discloses
  nothing to anyone and creates no risk for the complainant.**

The system prefers the cheap, recoverable error on purpose. **The prompt says *"be extra sensitive"*
because it is meant to.**

⚠ **What the figure obligates is the return path** — the trade is sound only while a SEAH officer who
clears a case can send it back. That path exists and is one step short of complete; its state is
assessed in [`00_compliance_status.md`](00_compliance_status.md) §9.

⛔ **Do not "fix" this number by tightening the prompt.** That trades away the property the design
rests on, and **any change must be measured against the owner's held-out positive set first**
([§5](#5-seah-recall--not-measurable-from-this-repository)) — tightening a recall-first detector
without measuring recall is how a well-intentioned fix introduces a safeguarding miss.
[Tracked](../sprints/2026-08-llm/followups/seah-detector-flags-gendered-non-harassment-complaints.md).

### 3.3 Classification is a second route into the same channel

`Gender - Gender Discrimination And Harrassment` appears as a **false positive 3 times**, and the
review step keeps any category containing `"gender"` — so classification routes into the confidential
channel independently of the detector, and the system figure is the **union** of the two.

**Consistent with the recall-first design** ([§3.2](#32--the-seah-detector-flags-5-of-the-8-deliberate-confusable-negatives)):
a miss now requires *both* signals to fail. It is recorded because **the union is the rate that
matters** — measuring the detector alone understates the review load the return path carries.

### 3.4 ⭐ Both models invent the *same* category — a taxonomy finding {#34--both-models-invent-the-same-category--which-makes-it-a-taxonomy-finding}

`gpt-oss-20b` classified only 2 items before the rate limit stopped the run
([§4](#4-the-open-column--the-one-gap)), and on **both** returned `Road Hazard - Dust` — one of the
categories `gpt-5-nano` invented seven times.

Two vendors, two architectures, **the same fabricated label**. That is weak evidence about either
model and strong evidence about the **taxonomy**: the catalogue had no road-hazard grouping, dust was
filed under `Environmental - Air Pollution`, and independent models kept reaching for the category a
road project would expect to exist. ⭐ **Acted on, and it worked** ([§7](#7-what-changed-on-2026-08-21-and-why)).
**The transferable finding: when two unrelated models invent the same label, that is a signal about
your taxonomy, not their quality.**

### 3.5 ⭐ The open model flags **nothing** — which is not the same as being better {#35--the-open-model-flags-nothing--which-is-not-the-same-as-being-better}

`gpt-oss-20b` flagged **0 of 105**, including **0 of the 8** confusables, at a tenth of the latency.
Read naively that is a clean win over the closed model's 7. **Do not read it naively.**

⚠ **A detector that flags nothing has a perfect false-alarm rate and catches nothing.** The set
contains **no harassment reports at all** ([§5](#5-seah-recall--not-measurable-from-this-repository)),
so two hypotheses fit the data equally: that it distinguishes gendered *access and discrimination*
grievances from harassment — the line `gpt-5-nano` fails to hold — or that it says *no* to everything
and a real harassment report would go unflagged. **Nothing in this repository can tell them apart**,
and the second is a safeguarding failure.

⛔ **So `gpt-oss-20b` must not be selected on this evidence, and its 0.000 must not appear in a
submission as an improvement.** Under a recall-first design
([§3.2](#32--the-seah-detector-flags-5-of-the-8-deliberate-confusable-negatives)) **a zero
false-alarm rate is a warning sign, not a selling point**: this system accepts false alarms in order
to avoid misses, and a candidate producing none on a set built to be hard is behaving in exactly the
way the design exists to avoid.

### 3.6 🔴 The benchmark measured a detector whose answer production was throwing away

**Found in live code 2026-08-27, and it changes how §3.2 should be read.** The detection figures
above measure what the **model returns**. They do not measure what the **system does with it** — and
for months the system was discarding it.

The asynchronous LLM detection writes `grievance_sensitive_issue=True` during the contact and OTP
steps. The final submit then collected a tracker slot still holding the **keyword** detector's
earlier result and wrote `False` over the model's `True`. ⭐ **It failed in precisely the case the
model exists for**: the one where keywords miss and the model catches — the class of item
[§3.2](#32--the-seah-detector-flags-5-of-the-8-deliberate-confusable-negatives) is about. The flag
now only ever escalates, in SQL rather than read-modify-write, so the write cannot lose the race.

⚠ **The transferable lesson for this document.** A benchmark scores a **function**. The safeguarding
property anyone actually cares about is a property of the **pipeline**, and every figure in §2 was
consistent with a pipeline that routed nothing. **Detector accuracy is necessary and it is not
sufficient**, and no re-run of this harness would have found it — it was found by driving the flow
against a live database after the owner corrected a wrong model of it.

⏭ **What would close the gap between the two:** an end-to-end measurement — a grievance in, a
`is_seah` ticket out — rather than a function-level one. Not built, and it is the measurement §5's
held-out set would be worth the most against.

---

## 4. The open column — the one gap {#4-the-open-column--the-one-gap}

⭐ **The single labelled hole in this document, stated once here rather than annotated across the
tables above.**

**What exists:** `gpt-oss-20b` completed all **105 detection items** on 2026-08-20 — the open
detection column in §2 is real.

**What does not:** open **classification**. The run reached **2 of 105**; the other 103 hit the
router's short-window token limit, which reports itself misleadingly as credit exhaustion
([`open-model-configuration.md`](open-model-configuration.md)). The same run's detection calls all
completed, because the detection prompt is short.

⚠ **That contrast was a finding about our prompt, not the model.** The classification prompt injected
the catalogue three times; it is now **3,277 tokens**, a 70% cut
([§7](#7-what-changed-on-2026-08-21-and-why)), so the run that could not complete should now fit
comfortably.

**Status: the blocker is removed and the measurement has not been taken.** Re-running spends
inference from a time-boxed, owner-funded envelope shared with pilot traffic (~105 classification +
105 detection calls per model); the owner deferred it on 2026-08-24. **It needs a decision and a few
minutes, not new engineering** — and the same run would re-meter the cost table's completion half
([§6](#6-cost--measured-in-tokens-priced-separately)).

**What this gap does and does not stop:**

- It does **not** stop the indicator-4 claim, which is about the *mechanism* and is pinned by tests
  ([`open-model-configuration.md`](open-model-configuration.md)).
- It does **not** stop the cost and sovereignty analysis, which turns on volume rather than on which
  open model wins ([`vllm-deployment.md`](vllm-deployment.md) §3).
- ⛔ It **does** stop **naming an open model as the production default.** That stays open until this
  column and §5 both exist.

---

## 5. ⚠ SEAH recall is not measured, and cannot be from this repository {#5-seah-recall--not-measurable-from-this-repository}

The committed benchmark contains **zero positive SEAH scenarios**, by decision: the harassment
narratives are held by the project owner and never enter the repository, because *"three hundred
realistic Nepali harassment complaints sitting in it will be read as leaked case data by somebody,
regardless of how the file is labelled"*.

**So the SEAH numbers on this page are not independently reproducible here.** That is a real weakness
in the evidence pack and it is the right trade. The harness accepts `--seah-set` outside the
repository and **refuses a path inside it**.

⭐ **This is the blocking measurement of the sprint, and unlike §4 money cannot unblock it.** Recall
is the metric with a safeguarding consequence, so it **must be measured before any model change
ships**; it must be reported with the **number of independent scenarios** rather than the row count;
and **no table may rank two candidates that differ by a few points** — a hand-authored set cannot
resolve that.

---

## 6. Cost — measured in tokens, priced separately

Tokens are the measurement and do not drift. Prices do, so they are stated separately.

⚠ **Read the provenance column before quoting a row.** The prompt half was re-metered after the 08-21
change; the completion half was not. **The fix is to re-run the meter, not to annotate this table** —
one run replaces every row.

| Per grievance *(both calls)* | Value | Provenance |
|---|---|---|
| Model calls | **2** — classify + SEAH detect | measured 08-20 |
| Prompt tokens, classification | **3,277** | ⭐ **measured 08-21**, after the cut |
| Prompt tokens, detection | **≈ 460** | ⚠ derived — the 08-20 meter recorded 11,358 prompt tokens against a ~10,900-token classification prompt |
| **Prompt tokens, total** | **≈ 3,700** | ⚠ derived |
| **Completion tokens** | **3,361**, of which **93.8% reasoning** | ⚠ measured 08-20, **not re-metered**. A prompt change is not expected to move completion length, but that expectation is not a measurement |
| **Per 1,000 grievances** | **≈ 3.70 M prompt + 3.36 M completion** | part measured, part derived |

⚠ **93.8% of the completion budget is reasoning tokens** — invisible in the reply, fully billed. **Any
cost estimate built from output length understates this system by roughly 16×**, and any token cap
sized for the visible answer returns empty content.

⭐ **The cut moved where the money is, and that changes the next lever.** Prompt was 77% of tokens and
is now about 52% — but completion is priced several times higher, so the prompt is roughly **12% of
the bill**. **Prompt engineering is no longer the cost lever. Reasoning effort is** — a different
change with a quality risk the prompt cut did not carry, and it should be measured before it is made.

**In dollars**, at `$0.05 / M` prompt and `$0.40 / M` completion:

> **≈ $1.53 per 1,000 grievances** *(3.70 M × $0.05 = $0.19; 3.36 M × $0.40 = $1.34)*
> ⚠ **The rate is a placeholder.** Confirm the published price before quoting this, and record the
> date. The token counts stand on the provenance above; the dollar figure does not.

This is one half of the costed proposal to the Nepal Government; the other half is the self-hosted
figure and the crossover between them ([`vllm-deployment.md`](vllm-deployment.md) §3).

---

## 7. What changed on 2026-08-21, and why {#7-what-changed-on-2026-08-21-and-why}

⭐ **The only place on this page where a superseded number appears**, and it appears because the change
is the finding. Every current value is in [§2](#2-the-results).

Two changes shipped together: the six `Road Hazard - *` categories
[§3.4](#34--both-models-invent-the-same-category--which-makes-it-a-taxonomy-finding) argued for, and
four token reductions to the classification prompt — measured on the same 105 items, same model.

| | Before | After |
|---|---|---|
| Items with an invented category | 18 / 105 | **4 / 105** — ⭐ **−78%** |
| …of which a genuinely *new concept* | 18 | **1** |
| **p99 latency**, classification | **40.6 s** | **24.5 s** — ⭐ **inside the 30 s budget for the first time** |
| p95 latency, classification | 24.6 s | **20.3 s** |
| Share of calls over 30 s | 1.9% | **0.9%** |
| **Prompt tokens** per classification | ~10,900 | **3,277** — ⭐ **−70%** |
| Categories in the taxonomy | 24 | **30** |

**What did not move:** accuracy. F1 0.771 → 0.762, precision 0.740 → 0.773, recall 0.805 → 0.752,
exact-set 0.676 → 0.686.

⚠ **This is not a clean A/B.** Three things changed at once — prompt, taxonomy, and the benchmark's
acceptable-alternate lists — so the −0.009 in F1 cannot be attributed to any one of them, and with 105
items it is inside the noise floor either way. **Read the invention, latency and token rows; do not
read the accuracy rows as an effect.**

### What the prompt change was

The catalogue was sent **three** times — a flat list twice plus the full dictionary once — and the
dictionary was **51,213 characters for an English grievance against 15,121 for a Nepali one.**

⚠ **That asymmetry was a bug.** The filter read `if "_" + language_code not in k`, which strips the
`_ne` keys for a Nepali grievance and **nothing** for an English one, because no key contains `_en`.
Every English classification carried every Nepali translation, JSON-escaped at six bytes per
character, for a model that never used them.

Four changes, all applied: **fix the language filter**; **send the flat list once**; **drop three
fields** (`high_priority` is routing metadata, `short_description` restates `description`, and the
`*_extra` pair served two categories while being charged to all thirty); and **drop the flat list
entirely**, so the model chooses from the dictionary **keys**.

⭐ **The last one is a correctness fix as much as a saving:** the flat list was built from *raw* CSV
values while every downstream consumer matches the *canonical* key. **The model was shown one form and
read in another.**

**Net: 62,736 → 13,147 characters for an English grievance (−79%), 18,567 → 13,147 for a Nepali one
(−29%) — while adding six categories.**

⚠ **Still unmeasured:** the six new categories have **no gold items** — they appear only as acceptable
alternates, so nothing scores whether a model picks them *correctly*, only that it stops inventing
them.
[Logged](../sprints/2026-08-llm/followups/road-hazard-categories-have-no-benchmark-items.md).

---

## 8. Related

- [`tests/data/benchmark/README.md`](../../tests/data/benchmark/README.md) — the set, its provenance and its limits
- [`open-model-configuration.md`](open-model-configuration.md) — the mechanism and the capability matrix
- [`../models/01_seah_detection_benchmark.md`](../models/01_seah_detection_benchmark.md) — the SEAH method and why this is a screening instrument
- [`vllm-deployment.md`](vllm-deployment.md) — where these token counts become a crossover
- [`00_compliance_status.md`](00_compliance_status.md) — where these numbers are cited
