# Sprint 4 — Prompt engineering: confidence, top-k, and the signal already thrown away (DPG-40…46)

> ## 🤝 HANDOVER — read this before anything else (written 2026-08-25)
>
> **This sprint was proposed as prompt engineering. Two of its three ideas turn out to be plumbing,
> and the third is gated.** That is the whole of §0, and it changes the order of the work rather
> than its ambition.
>
> **What Sprint 2 hands you.** A 105-item benchmark with gold labels, a harness that calls the
> product's own functions, and a **measured closed baseline** — classification precision 0.773,
> recall 0.752, exact-set 0.686, SEAH false-alarm rate 0.067
> ([`docs/dpg/model-benchmarks.md`](../../dpg/model-benchmarks.md) §2). You can A/B a classification
> prompt against real numbers on the day you start.
>
> **What it does not hand you, and cannot.** A SEAH **recall** figure. The committed set holds no
> positive SEAH items — the owner's decision of 2026-08-19 that SEAH narratives never enter this
> repository — so the only detection number that exists is the one you must not optimise. See §0.3;
> it is the reason [DPG-44](#dpg-44) is written and blocked rather than written and scheduled.
>
> **⚠ Three things changed under this spec between the idea and the writing:**
>
> | | What changed | What it does to your plan |
> |---|---|---|
> | 1 | **The detector is already asked for confidence** (`level: high\|medium\|low`) and the answer is discarded three times | [DPG-40](#dpg-40) is plumbing, not a prompt change — and it is ungated, so it goes first |
> | 2 | **The classifier already produces a top-k list** — `grievance_categories_alternative`, shown to the complainant at review | [DPG-43](#dpg-43) is a *promotion rule*, not a generation change |
> | 3 | **D-51 landed 2026-08-25** — both category lists now resolve onto the taxonomy or are dropped | Your top-k experiment has clean inputs for the first time, and `InventionMeter` keeps the invention rate measurable after the repair |
>
> **⛔ One decision is standing and this sprint does not re-open it.** SEAH detection is tuned
> **recall-first on purpose**: over-flagging is the cheap, recoverable error and a SEAH officer
> reading an ordinary complaint discloses nothing
> ([`model-benchmarks.md`](../../dpg/model-benchmarks.md) §3.2, D-52). **"Improve SEAH detection"
> does not mean "flag less."**

---

## Required reading

1. [`CLAUDE.md`](../../../CLAUDE.md) — §Docker-only, §Service boundaries, §Environment variables, §Migration traceability (DPG-40 adds a column to `public.*`)
2. [`docs/PROGRESS.md`](../../PROGRESS.md) → [`docs/TODO.md`](../../TODO.md)
3. [`docs/engineering/00_engineering_index.md`](../../engineering/00_engineering_index.md) — the ten rules
4. └ [`04_testing.md`](../../engineering/04_testing.md) — **binding**: a benchmark is not a test, and a calibration curve is neither
5. └ [`06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) — honesty markers; an unmeasured cell is `⚠ Not measured`
6. [`docs/deployment/DOCKER.md`](../../deployment/DOCKER.md)
7. [`docs/deployment/07_migrations_policy.md`](../../deployment/07_migrations_policy.md) — DPG-40 uses the **public** stream (`migrations/public/`), not ticketing's
8. [`docs/services/06_llm_service.md`](../../services/06_llm_service.md) — the live spec DPG-42/43 update
9. [`docs/sprints/README.md`](../README.md) — the standing deferral rule
10. [`03-open-models-spec.md`](03-open-models-spec.md) — §DPG-23, the harness and the baseline you measure against
11. [`followups/the-model-invents-categories-and-they-are-stored.md`](followups/the-model-invents-categories-and-they-are-stored.md) — D-51, closed 2026-08-25, and the reason the category lists are trustworthy inputs now

---

## §0 — Corrections carried into this sprint

### §0.1 ⭐ The detector already answers with a confidence, and the product throws it away three times {#01-the-detector-already-answers-with-a-confidence}

**Verified in code, 2026-08-25.** `detect_sensitive_content_llm` asks for
`{"detected": …, "level": "high"|"medium"|"low", "message": …}` (`LLM_services.py:633`), and
`SensitiveContentDetection` (`llm_schemas.py:87`) keeps `level` as a `Literal` **specifically so the
enum reaches the provider**. So a graded signal is produced on every SEAH detection call, today.

Then it is dropped, three times over:

| # | Where | What happens |
|---|---|---|
| 1 | **Never persisted** | `backend/actions/grievance_intake/sensitive.py:103` reads `grievance.get("sensitive_issues_level", "low")` — but **no code writes that column and `public.grievances` has no such column.** The read always returns its default. `sensitive_issues_confidence` is the same, and the LLM path never returns a `confidence` key at all — only the keyword detector does (`sensitive_detection.py:37,39`) |
| 2 | **Never reaches the ticket** | `Ticket.is_seah` is a **boolean** (`ticketing/models/ticket.py:94`), and `case_sensitivity` is derived from it — `"seah" if ticket.is_seah else "standard"` (`ticketing/api/routers/viewers.py:143`) |
| 3 | **So the queue has no ordering** | The SEAH queue is, by design, a queue that contains deliberate false positives. It is presented to the officer as a flat list with no signal about which case the model was sure of |

⭐ **This is the sprint's cheapest win and it needs no prompt change at all.** It also closes a
dangling read: a slot the code pretends to populate and never does is the exact defect class of
D-51 and D-55 — a value that looks present, is a default, and nobody can see is wrong.

⚠ **And it is a safeguarding change, not only a plumbing one.** Showing an officer "the model was
not confident" can bias them toward dismissal, which is the failure mode a recall-first design
exists to avoid. ✅ **Settled by [Q-26](DECISIONS.md#q-26), 2026-08-25 — order only, no score on
screen.** DPG-40 ships the ordering; it ships no label.

### §0.2 The classifier already produces a top-k list {#02-the-classifier-already-produces-a-top-k-list}

`grievance_categories_alternative` is exactly *"the top 3 if you are not confident"*: the prompt asks
for a second list of *"categories that are possibly related to the grievance but that you have not
picked"* (`LLM_services.py:331`), and the complainant is shown it at the review step to modify their
own classification (`form_grievance_complainant_review.py:165`).

So the open question is **not** how to generate alternates. It is:

- what **order** they come in (today: whatever the model emitted);
- **when** an alternate should be promoted to a primary category, or the primary demoted to an alternate;
- whether the complainant should be told the system is unsure — a **UI copy** question, governed by
  [`docs/ticketing_system/ui/05_ui_copy_style.md`](../../ticketing_system/ui/05_ui_copy_style.md), and
  a real one: *"we think it might be one of these three"* reads very differently to a complainant than
  a confident single answer.

### §0.3 ⛔ The measurability split — the constraint that shapes every ticket here {#03-the-measurability-split}

**Read this before planning anything, and do not plan around it.**

| Path | What is measurable today | What is not |
|---|---|---|
| **Classification** | Everything. 105 items, gold labels, acceptable-alternate lists, a committed baseline. Precision, recall, exact-set, precision@k, and **calibration** — confidence against correctness — all computable offline against a funded run | — |
| **SEAH detection** | The **false-alarm rate only** — 7 of 105, on a set with **no positives** | **Recall.** The metric the design exists to optimise. Not measurable from this repository, by decision, and not approximable from what is here |

⚠ **The asymmetry is a trap, and it is the reason this spec exists in this shape.** Optimising the
number you can see, when the number you cannot see moves the other way, produces a change that looks
like a clean win in every artefact this repository can generate: **false alarms drop, the benchmark
goes green, and an oblique harassment report stops being flagged.** Nothing here would notice. That
is the standing 🔴 warning on D-52, and it applies to a *confidence threshold* exactly as much as to a
reworded prompt — a threshold that suppresses low-confidence flags **is** a tightening, wearing a
different hat.

⭐ **The rule this sprint works under:** on the detection path, confidence may **order** the queue.
It may never **gate** the flag. Ordering cannot lose a detection; gating can.

### §0.5 ⭐ What the classifier is *for* — decided 2026-08-25, and it sets the metric {#05-what-the-classifier-is-for}

> *"The classifier is there to automate the process and make sure a category is assigned to all, if I let
> the officers do it, they may do it poorly, with AI I have a baseline."* — owner, [Q-27](DECISIONS.md#q-27)

**The classifier exists for coverage.** Every grievance arrives with a category, applied consistently, so
nothing lands uncategorised and no officer invents a taxonomy under time pressure. The **officer** is the
correction point, at assessment. Most complainants will not confirm the categories at all.

⚠ **So the headline metric is not precision@1.** A grievance with a roughly-right category is a success; a
grievance with **no usable category** is the failure. A prompt change that raises precision while lowering
the share of grievances that get any usable category is a **regression under this purpose**, and would read
as an improvement on the table Sprint 2 built. [DPG-42](#dpg-42) reports coverage first and precision beside
it, for that reason.

⚠ **And it is not a licence for a bad baseline.** An officer who finds the suggestion wrong most of the time
stops reading it — the coverage benefit evaporates and the cost stays. That is why [DPG-46](#dpg-46) measures
the correction rate rather than assuming it.

### §0.4 Self-reported confidence is not confidence until it is calibrated {#04-self-reported-confidence-is-not-confidence}

A model asked "how sure are you" answers fluently and, by default, badly — the number correlates
with phrasing at least as much as with correctness. **Nothing in this product may consume a
confidence value before [DPG-41](#dpg-41) has measured whether it separates right answers from wrong
ones**, and the honest possible outcome of DPG-41 is *"it does not, and we ship the plumbing without
the ranking."* That outcome is a success for this sprint, not a failure of it.

---

## DPG-40 — Keep the confidence we already ask for {#dpg-40}

**Effort: S · Area: backend + migrations + ticketing · Gated on: nothing. Start here.**

Make `level` survive the journey from the model to the officer. No prompt is touched.

### Shape

1. **Persist it.** Add `sensitive_issues_level` (and `sensitive_issues_confidence`, if DPG-41 shows
   the keyword detector's number is worth keeping) to `public.grievances` via the **public** Alembic
   stream — `migrations/public/versions/`, version table `alembic_version_public`. ⚠ Not the
   ticketing stream; see CLAUDE.md §Migration traceability.
2. **Write it** where the detection result is stored, and add the field to
   `grievance_manager`'s expected-fields list *and* to
   `base_manager.map_fields_between_backend_and_database` — that mapping resolves **every** key
   through a fixed dict and raises `KeyError` on an unknown one, which the classification task turns
   into a terminal `LLM_failed` (the trap D-51 documented).
3. **Carry it to the ticket.** `POST /api/v1/tickets` gains an optional graded field beside
   `is_seah`. ⚠ **`is_seah` stays a boolean and stays the access control.** The grade is triage
   metadata; nothing about visibility, routing or the workflow may read it. A grade that gates access
   is §0.3's trap with a database column.
4. **Order the queue by it** — highest first, then SLA. ✅ **[Q-26](DECISIONS.md#q-26), decided
   2026-08-25: order only.** The grade sorts the queue and **does not appear on the officer's screen** —
   *"the model was not confident"* is an invitation to dismiss, and dismissal of a real report is the one
   unrecoverable error here. A queue order cannot lose a detection; a label that discourages reading can.
   ⏳ Revisitable once the return path is first-class and its round-trip measured (D-52).

### Definition of done

- [ ] The value produced by the model is the value on the ticket, verified end to end in-container
- [ ] `sensitive.py:103`'s read returns a real value rather than its default — **the dangling read is closed**
- [ ] A test pins that `is_seah` is unchanged by any grade, including `low`
- [ ] Migration in the public stream, with the standard header
- [ ] `docs/services/06_llm_service.md` and the SEAH spec updated

---

## DPG-41 — Calibration before consumption {#dpg-41}

**Effort: S/M · Area: eval · Gated on: nothing (offline, one funded classification run).**

Measure whether a self-reported confidence means anything **before** anything consumes it.

### Shape

- **Classification:** one run over the 105 items with confidence requested per category. Produce a
  reliability curve — predicted confidence against measured correctness — plus the separation between
  the confidence of correct and incorrect answers. This is the deliverable; a single scalar is not.
- **Detection:** compute the same over the 7 false alarms and the 98 true negatives. ⚠ **State the
  power.** n=7 on one side and **zero positives** on the other: this can show that low-confidence
  flags are *more often* false alarms, and it can show nothing at all about recall. **Write the
  limitation into the output, not into a footnote** — this figure will be read by someone who wants a
  threshold.
- Extend `scripts/ops/llm_benchmark.py`, which already meters usage and inventions; do not write a
  second harness.

### Definition of done

- [ ] Reliability curve committed for classification, with n per bin
- [ ] Detection calibration reported **with its power stated on the same line as the number**
- [ ] An explicit verdict: *is* the confidence usable for ranking — yes or no
- [ ] ⚠ If the answer is no, that is recorded and DPG-42/43 narrow accordingly. Do not proceed on hope

---

## DPG-42 — Classification prompt: confidence, measured {#dpg-42}

**Effort: M · Area: backend + eval · Gated on: DPG-41's verdict.**

Ask the classifier for a confidence per category and measure what it costs and buys, against the
08-21 baseline (precision 0.773 · recall 0.752 · exact-set 0.686).

### Shape

- The schema gains an optional confidence per category. ⚠ **It stays optional in Python** — the
  D-51 rule holds: *constrain the generation, forgive the reply*. A model that omits confidence must
  not cost the complainant their classification.
- ⭐ **Headline: coverage** — the share of grievances receiving **at least one correct or acceptable**
  category. That is the metric the classifier's purpose implies (§0.5), and it is the one a regression
  would hide behind. **Report precision@1, recall@3 and exact-set beside it, not above it.** A change
  that improves recall@3 while degrading precision@1 is a real trade and the table must show both.
- ⚠ **Price it.** Confidence per category lengthens every completion, on a path where 93.8% of
  completion tokens are already reasoning. Report the token delta beside the accuracy delta, against
  the shared pilot envelope (Q-19).
- ⚠ **Not a clean A/B if you change more than one thing** — §7 of the benchmark doc says this about
  the 08-21 change and it was right. One variable per run, or the delta means nothing.

### Definition of done

- [ ] Baseline and candidate measured on the same 105 items, same model, one variable apart
- [ ] Token cost and p95 latency reported with the accuracy figures — the 30 s interactive budget is pass/fail
- [ ] The winning prompt shipped **or** the null result recorded and the prompt left alone

---

## DPG-43 — The promotion rule, and what the complainant is told {#dpg-43}

**Effort: M · Area: backend + UI copy · Gated on: DPG-42.**

Decide when an alternate becomes a primary category, and how that reads to a complainant.

### Shape

- A rule over the resolved lists — both are canonical catalogue keys since D-51, so the rule operates
  on trustworthy input for the first time.
- ⚠ **The existing promotion path is narrower than this one and must not be conflated with it.**
  D-51 promotes the top alternate only when **nothing** survived resolution — a repair for an empty
  result, not a confidence rule. If DPG-43 introduces a second promotion path, one function owns both.
- **The complainant-facing half is the harder half, and it may turn out to be no change at all.**
  Promoting three categories where one used to appear changes what the system *claims about itself*
  at the review step. [Q-27](QUESTIONS.md#q-27) puts the three options to the owner —
  **A** keep today's screen and use the confidence only behind it, **B** show three silently,
  **C** show three and say we are unsure — with **A recommended**, on the same principle Q-26
  settled: the machine's uncertainty is an operational signal, not a message to the person filing a
  grievance. ⚠ **If A is chosen, DPG-43 still ships** — the confidence is still built and still used,
  just not on the complainant's screen. Copy, if any, is governed by
  [`docs/ticketing_system/ui/05_ui_copy_style.md`](../../ticketing_system/ui/05_ui_copy_style.md).
- ⚠ **`high_priority` is computed from the stored categories** (`ticketing_dispatch.py:117`).
  Promoting an extra category can change a grievance's priority. Whatever the rule is, that
  consequence is deliberate and stated, not discovered later.

### Definition of done

- [ ] One promotion function, tested, including the D-51 empty-result case
- [ ] The priority consequence measured over the 105 items: how many change `high_priority`
- [ ] Copy approved against the UI copy spec before it ships

---

## DPG-44 — SEAH detection prompt — ⛔ BLOCKED, and this ticket says why {#dpg-44}

**Effort: M · Area: backend + eval · ⛔ Blocked on: a held-out SEAH set with positives ([Q-25](QUESTIONS.md#q-25)).**

> 🔶 **Status 2026-08-25: requested, not delivered.** The owner has asked for the set and is following
> up. Until it arrives this ticket does not move, and the honest status of SEAH detection stays
> **unmeasurable — not unimproved.** Nothing else in Sprint 4 waits on it.

**Do not start this ticket. It is written so that nobody starts it by accident**, which is a real risk:
it is the most tempting item in the sprint and the benchmark will happily reward the wrong change.

### The blocker, precisely

There is **no baseline recall figure at all**. A detection-prompt change can be scored only on false
alarms, and false alarms are the error this design deliberately accepts. Any prompt edit therefore has
an unmeasured effect on the only outcome that matters, and the measured effect will look like
improvement whichever way recall moved.

### What unblocks it

A held-out set containing **positive** SEAH items, held outside this repository, run through
`--seah-set`. Owner decision of 2026-08-19 governs where it lives; [Q-25](QUESTIONS.md#q-25) asks
whether it exists and who authors it.

### What may be done in the meantime — and only this

- Prepare the **paired** evaluation: recall and false-alarm rate reported together, from one run, so
  the trade is visible in a single table. Build the harness support; run it against nothing.
- ⛔ **Do not** reword the prompt "to test the harness". A prompt change that ships without a paired
  run is the failure this ticket exists to prevent.

---

## DPG-45 — Publish, and keep the instrument honest {#dpg-45}

**Effort: S · Area: docs · Gated on: DPG-41…43.**

### Shape

- Update [`docs/dpg/model-benchmarks.md`](../../dpg/model-benchmarks.md): current values in §2 with
  their dates, the change and its reasoning in a §7-style block. **One value per metric** — that
  document's own rule, and the reason it is readable.
- ⚠ **Check `InventionMeter` still reads.** The invention rate is a *model* metric collected from the
  resolution log since D-51, and a prompt change is exactly the kind of edit that could move the
  wording it depends on. If a re-run reports 0/105, the meter has broken, not the model improved.
- Update the live specs (`docs/services/06_llm_service.md`, the SEAH spec) — not only the evidence pack.

### ⚠ What this sprint does **not** change in the DPG pack

Indicator 4 asks for demonstrated platform independence, and that is already answered by the config
registry and the open configuration. **Model quality is a product decision (Q-04), not a compliance
gate**, so nothing here belongs in `00_compliance_status.md` — the pack can be shared with the
consultant before this sprint starts and again after it finishes, unchanged by it. §5's *"SEAH recall
is not measurable from this repository"* stays true throughout, which is precisely why this sprint
cannot alter it.

---

## DPG-46 — The officer correction rate: the classifier's real-world score {#dpg-46}

**Effort: S/M · Area: backend + ticketing · Gated on: nothing. Added 2026-08-25 out of [Q-27](DECISIONS.md#q-27).**

If the classifier is a **baseline the officer corrects** (§0.5), then *how often the officer changes it* is
the only score that measures the thing we actually care about — on real Nepali grievances, at no authoring
cost, from a system that is already running. **Today it cannot be computed.**

### The gap (D-57)

`PATCH /tickets/{id}/classification` (`ticketing/api/routers/tickets/crud.py:523`) writes the officer's
categories back through `patch_grievance_classification` → `grievance_manager.update_grievance`
(`grievance_manager.py:83`) — a plain `UPDATE grievances`, **no change logging**. The tracking variant
`update_grievance_with_tracking` (`:383`) calls `compare_and_log_field_changes` and writes old→new into
`grievance_status_history.field_changes`. It exists, it is used elsewhere, and this path does not use it.

The ticket event `CLASSIFICATION_VALIDATED` records **that** a validation happened and by whom — so an
officer who confirmed the AI's categories unchanged is **indistinguishable** from one who replaced all of
them.

### Shape

1. Route the officer classification patch through the tracking variant. One call site; the machinery and
   the table already exist.
2. Report, over a period: **confirmed unchanged / added to / replaced**, plus which categories are most
   often corrected *to* and *from*. ⭐ The "corrected to" list is the same taxonomy signal that produced
   the six `Road Hazard` categories — from production instead of a benchmark.
3. Feed it back into [DPG-42](#dpg-42) as the real-world check on whatever the benchmark concluded.

### ⚠ Bounds — read before building

- **Aggregate rate only.** A correction *rate* is a metric. Building a labelled corpus out of real
  grievances is a **separate privacy decision** (Sprint 3's territory) and is explicitly not this ticket.
- **An officer edit is not ground truth**, it is a second opinion — a busy officer may accept a wrong
  suggestion. Report it as *agreement*, never as *accuracy*.
- ⚠ **Do not turn this into an officer performance metric.** A correction rate that reads as a score on
  the officer changes their behaviour toward the classifier, and the measurement destroys itself.

### Definition of done

- [ ] Officer classification edits land in `grievance_status_history.field_changes`, old and new
- [ ] The correction rate is reportable, split three ways, with the "corrected to" tally
- [ ] The three bounds above are written into the report itself, not only into this ticket

---

## Execution order

```
DPG-40 (plumbing) ──▶ ungated, start immediately; closes a dangling read
        │
DPG-41 (calibration) ──▶ one funded run; its verdict gates everything below
        │
        ├── DPG-42 (classification prompt) ──▶ DPG-43 (promotion rule + copy)
        │
        └── DPG-45 (publish) ── after 41/42/43, whatever they concluded
                                  including a null result

⛔ DPG-44 (detection prompt) ── BLOCKED on Q-25. Not scheduled. Not started.
```

---

## Sprint 4 acceptance criteria

- [ ] The model's confidence reaches the officer's queue, and `is_seah` is provably unaffected by it
- [ ] A calibration verdict exists in writing — including, acceptably, *"not usable for ranking"*
- [ ] Every accuracy claim measured on the committed 105 items, one variable per run, with token and
      latency cost beside it
- [ ] Nothing consumes a confidence value that DPG-41 did not validate
- [ ] ⛔ The detection prompt is **unchanged**, unless Q-25 delivered a positive set and a paired
      recall/false-alarm run was published
- [ ] `docs/dpg/model-benchmarks.md` updated; `00_compliance_status.md` **untouched by design**
- [ ] The officer correction rate is computable — and reported as **agreement**, never as accuracy, and
      never as a score on the officer
- [ ] Every deferral logged in `followups/` + `TODO.md`, same commit

---

## What this sprint deliberately does **not** do

- **It does not tighten SEAH detection.** Over-flagging is the priced trade (§3.2, D-52). Fewer false
  alarms is not a goal here and is not evidence of improvement.
- **It does not add an LLM call.** The confidence and the alternates come from calls already made. A
  second model call to second-guess the first was proposed during D-51 and rejected for the reasons
  in that follow-up — cost on the interactive path, and burying the taxonomy signal.
- **It does not change what `is_seah` means.** Access control stays boolean and stays independent of
  any score.
- **It does not re-open model selection.** Which model runs is Q-04, decided on cost. This sprint
  measures prompts against the model in production.
