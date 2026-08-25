# Open questions for the project owner

> **24 of 27 answered.** This file holds **only what is still live** — **one open and two awaiting an
> external answer** (⚠ Q-25, Q-26 and Q-27 are new, 2026-08-25, out of Sprint 4's planning; **Q-26 and Q-27 were
> asked and answered the same day**, and Q-27's answer restated the classifier's purpose — read it). ⚠ **The next free number is Q-28** — Q-24 is taken by *"how many open models"*
> in [`DECISIONS.md`](DECISIONS.md), and Sprint 4's questions were numbered 24–26 for half a day before
> that collision was caught. Check both files before numbering a new one. **Q-20, Q-21 and Q-22 came out of the owner's review of Sprint 1 and were all
> answered the same day**; they are in [`DECISIONS.md`](DECISIONS.md) with the code that confirms each.
> **Nothing in the second wave is blocked.** The register below records every decision in one line each.
>
> **The answered questions moved to [`DECISIONS.md`](DECISIONS.md)** with the owner's answer verbatim, the
> original framing, and a pointer to the spec each landed in. Nothing was discarded: **expand any row by
> following its link.** Each decision also lives in the ticket it governs — per
> [`06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md), a decision that lives
> only in a questions file is half-propagated.
>
> Status mirror: [`PROGRESS.md`](PROGRESS.md) → Question status.

---

## Still live — 4

| Q | Subject | State | What it blocks |
|---|---|---|---|
| [**Q-02**](#q-02) | Which open licence — Apache-2.0 or MIT | 🔴 **open** | **[DPG-01](01-licensing-and-governance-spec.md#dpg-01)** — delegated to the consultant, so `LICENSE` now waits on *two* externals: which text (Q-02) and which holder (Q-01). Indicator 2 fails outright with no licence at all, so this is the cheapest unblock on the list |
| [**Q-19**](#q-19) | The LLM budget | ✅ **answered 2026-08-20** — a few hundred USD, owner-funded, covering the pilot | **Most of Sprint 2** — [DPG-22](03-open-models-spec.md#dpg-22), [DPG-23](03-open-models-spec.md#dpg-23), [DPG-24](03-open-models-spec.md#dpg-24). Raised by the answers themselves: there is no inference budget, and those three tickets are made of inference calls |
| [**Q-01**](#q-01) | Who opens the ADB OGC IP request | 🔶 in flight | **[DPG-03](01-licensing-and-governance-spec.md#dpg-03)** and the submission. ⚠ The owner is writing to the *DPG consultant*, which is not the OGC channel the question meant |
| [**Q-25**](#q-25) | Does a held-out SEAH set **with positives** exist, and who authors it | 🔶 **requested 2026-08-25, awaiting** | **[DPG-44](05-prompt-engineering-spec.md#dpg-44) entirely.** There is no baseline SEAH **recall** figure at all, so a detection-prompt change can only be scored on the error the design deliberately accepts. ⚠ Until this is answered the honest status of SEAH detection is *unmeasurable*, not *unimproved* |

---

## Decision register — 23 answered

Full text, verbatim answers and reasoning: [`DECISIONS.md`](DECISIONS.md).

| Q | Subject | Decision | Detail |
|---|---|---|---|
| **Q-27** | One category or three when unsure | **A — the complainant's screen does not change.** ⭐ And the classifier's purpose is now on the record: **coverage, not per-item precision** — the officer is the correction point | [→](DECISIONS.md#q-27) |
| **Q-26** | Officer sees the confidence, or only ordered by it | **Order only** — a queue order cannot lose a detection; a *"low confidence"* label that discourages reading can | [→](DECISIONS.md#q-26) |
| **Q-20** | Where the review step sits | **After submission** — verified in the state machine. The wait is already last; only the budget changes | [→](DECISIONS.md#q-20) |
| **Q-21** | Which single text model | **Two models: Whisper + `gpt-5-nano`** — eight keys, two values | [→](DECISIONS.md#q-21) |
| **Q-22** | The four unreachable LLM paths | **Not legacy — the parked voice-notes flow.** Declare and label; delete nothing | [→](DECISIONS.md#q-22) |
| **Q-18** | Shared LLM config module | `backend/config/llm_config.py`, pydantic-settings, dep moved to `requirements.txt` | [→](DECISIONS.md#q-18) |
| **Q-03** | T2 jurisdiction | **T2 parked** — jurisdiction moot until unparked | [→](DECISIONS.md#q-03) |
| **Q-05** | T2 operator + payer | **T2 parked** — no run-cost owner, so no T2 | [→](DECISIONS.md#q-05) |
| **Q-04** | Which config production runs | **The open one**, on cost; closed held in reserve on quality complaints | [→](DECISIONS.md#q-04) |
| **Q-10** | Open config as repo default | Yes, flipped in Sprint 2 | [→](DECISIONS.md#q-10) |
| **Q-11** | One model or per-task | One text model first, then downsize per task; HF pricing is the driver | [→](DECISIONS.md#q-11) |
| **Q-12b** | Redact when | **At transmission.** Both representations stored → the restore mapping is PII | [→](DECISIONS.md#q-12b) |
| **Q-12c** | Where the ML dependency lives | Dedicated service, **medium term, its own initiative** — leaves Sprint 3 | [→](DECISIONS.md#q-12c) |
| **Q-12** | Nepali NER licence | Email the author; budget an openly-licensed fine-tune as fallback | [→](DECISIONS.md#q-12) |
| **Q-13** | `gpt-5-nano` · voice live? | Deliberate cost choice · **voice transcription is not live** | [→](DECISIONS.md#q-13) |
| **Q-14** | SEAH fail open/closed | **Fail-open stays** — a deterministic pre-filter is the backup, **verified in code** | [→](DECISIONS.md#q-14) |
| **Q-15** | Benchmark provenance | Synthetic in phase 1; hybrid once the live project has data | [→](DECISIONS.md#q-15) |
| **Q-16** | Benchmark size + labellers | **No labeller budget** — the set grows with the project | [→](DECISIONS.md#q-16) |
| **Q-06** | Licence scan scheduled? | Scheduled, in `ops/security.py` | [→](DECISIONS.md#q-06) |
| **Q-07** | Privacy-assessment author | Agent drafts, consultant advises — **no legal review; must be disclosed** | [→](DECISIONS.md#q-07) |
| **Q-08** | Assess against what | Nepal's Individual Privacy Act 2018 | [→](DECISIONS.md#q-08) |
| **Q-09** | Translation: specialist? | LLM first; dedicated service only if materially better | [→](DECISIONS.md#q-09) |
| **Q-17** | Provider outage blocks merges? | Runs every commit, never a required check | [→](DECISIONS.md#q-17) |

### The two that changed the plan beyond their own ticket

Worth re-reading before planning any sprint, because several tickets inherit them:

1. **T2 is parked (Q-03 + Q-05).** **T1 — a hosted third-party provider — is the steady state, not a
   stepping stone.** Grievance text leaves the country **indefinitely** rather than during a transition, which
   **promotes [Sprint 3](04-pii-redaction-spec.md) from prudent to necessary** and removes the
   vLLM-in-production sentence from the indicator-4 answer.
2. ~~**There is no LLM budget (Q-13) → [Q-19](#q-19).**~~ ✅ **Answered 2026-08-20** — a few hundred USD,
   owner-funded, covering benchmarking *and* the pilot's own inference, with a costed proposal to the
   Nepal Government to follow. Sprint 2 is unblocked. The paragraph below is kept because the shape of the
   problem it describes did not go away — it acquired a ceiling. Sprint 2 is built almost entirely from inference calls
   — a benchmark across several models and a CI job that calls a live API on every commit. **Nobody priced
   them.** This is the binding constraint on Sprint 2.

---

## 🔴 Still open

### Q-02 — Apache-2.0 confirmed over MIT? {#q-02}

**→ open — delegated to the consultant**

> **🔴 STILL OPEN — delegated.** The licence choice now waits on the consultant's recommendation. ⚠ **This is the one answer that moves a ticket backwards:** DPG-01 previously read *"Use Apache-2.0 over MIT"* as settled, and it is now gated. Since indicator 2 fails outright without **any** licence, and DPG-03 already blocks naming a copyright holder, DPG-01 is now blocked on two external answers. [`01` DPG-01](01-licensing-and-governance-spec.md#dpg-01) states the Apache-2.0 case as a *recommendation awaiting confirmation* rather than a decision.

**Owns:** DPG-01

⭐ **Recommendation: Apache-2.0.** It carries an express patent grant, which matters when a government
adopts the code and other countries fork it. MIT does not.

**Answer:** will be recommended by consultant

---

---

---

### Q-19 — What is the LLM budget for benchmarking and for CI? {#q-19}

**Owns:** DPG-22, DPG-23, DPG-24 · **Raised by:** the answers to Q-13, Q-16, Q-17 · **New 2026-08-17**

Q-13 says voice transcription is not live *because there is no LLM budget* — *"I can shoulder a few calls
per day to nano, not transcription."* Sprint 2 is made of inference calls:

| Ticket | What it spends |
|---|---|
| **DPG-22** ASR eval | Every candidate model over the whole voice subset, plus the incumbent baseline that Q-13 says does not exist |
| **DPG-23** text eval | Every candidate model over every text item, across six task types — the largest line |
| **DPG-24** CI job | A live third-party call **on every commit**, forever. Q-17 says run it every commit; that was answered as a flakiness question, not a cost one |

Three of these are unpriced and one of them recurs indefinitely. **A benchmark nobody can afford to run
is a spec that fails silently** — and the CI job is the single strongest piece of indicator-4 evidence
available, so degrading it is not free either.

⭐ **Recommendation, in the order I would take it:**
1. **Cap the CI job first** — it is the only recurring cost. Keep it on every commit for a small
   fixed live subset (a handful of round-trips, not the suite), put a hard token cap on the Hugging Face
   account, and record the measured monthly spend in the job header. If even that is too much, run it
   **nightly plus on release tags** and say so in the badge — weaker evidence than per-commit, still
   honest, still un-rottable.
2. **Price DPG-23 before building it.** Items × models × tasks is knowable arithmetic. Hugging Face
   Inference Providers bills per token; the benchmark set is a few hundred short texts. This is plausibly
   tens of dollars, not hundreds — **get the number, because "no budget" and "$40" may not be in conflict.**
3. **Ask ADB for a metered inference line, not a lump sum.** The DPG work *is* the justification: an
   evaluation that substantiates a claim in an ADB-endorsed submission. It is a far easier ask than the
   T2 GPU that just got parked, and it is two orders of magnitude smaller.
4. **Sequence DPG-22 last.** ASR is the most expensive per item (audio tokens) and the least decision
   relevant right now, since voice is not live.

**Answer:** I can pay for all the inferences during first months of demo in 2 districts - I will eventually expense it for so long it is a few 100 USD. Then we will submit to Nepal Gvt the choices they need to make moving forward with realistic budget.

---

### Q-25 — Is there a held-out SEAH set with positive items, and who authors it? {#q-25}

**Owns:** [DPG-44](05-prompt-engineering-spec.md#dpg-44) · **New 2026-08-25**

The committed benchmark set holds **no positive SEAH items** — your decision of 2026-08-19, and the right
one: *"three hundred realistic Nepali harassment complaints sitting in it will be read as leaked case data
by somebody, regardless of how the file is labelled."* The harness has a `--seah-set` flag for a set that
lives outside git. **Nothing has ever been run through it.**

⚠ **The consequence is sharper than "a missing number."** With no positives, the only measurable detection
outcome is the **false-alarm rate** — the error the recall-first design deliberately accepts. Any prompt
change therefore has an unmeasured effect on the outcome that matters, and a *measured* effect that will
look like improvement whichever way recall actually moved: false alarms drop, the benchmark goes green,
and an oblique report stops being flagged.

**What is needed:** a set with positives, authored by someone who knows what a real oblique report looks
like, held outside this repository. Volume matters less than authenticity — twenty genuinely oblique items
are worth more than two hundred obvious ones, because the obvious ones are already caught.

**Answer (2026-08-25):** 🔶 **Not yet — requested, owner following up.** *"not yet I have requested it and
need to follow up today."*

⚠ **What that means for the meantime, stated so nobody has to infer it:** DPG-44 stays ⛔ blocked and the
detection prompt stays **unchanged**. The honest status of SEAH detection is **unmeasurable, not
unimproved** — and every other ticket in Sprint 4 is unaffected, because none of them touches that prompt.

---

## 🔶 Position taken — awaiting an external answer

---

## 🔶 Position taken — awaiting an external answer

### Q-01 — Who opens the ADB OGC IP request, and has it been opened already? {#q-01}

**→ in flight — but check it is the right channel**

> **🔶 POSITION TAKEN, NOT A DETERMINATION.** The owner is writing to the **DPG consultant** to initiate the discussion. ⚠ **The question asked about the ADB Office of the General Counsel**, which is a different channel: a consultant can advise on the DPG process but cannot issue an IP determination. If the consultant is the route *to* OGC, that is fine — record it that way. **Nothing here is decided until OGC responds in writing**, and DPG-01's `NOTICE` still needs a copyright holder. Record the date sent in `PROGRESS.md`.

**Owns:** DPG-03 · **Spec:** [`01`](01-licensing-and-governance-spec.md#dpg-03)

Indicator 3 requires documented ownership, and if any of this was written under an ADB contract the IP
may not be yours to donate. **This is the only item nobody working on this repo can resolve**, and it has
the longest lead time on the list — weeks, plausibly months.

Nothing in the code is blocked by it. **The submission is.** And DPG-01's `NOTICE` file needs the answer
to name a copyright holder.

⭐ **Recommendation:** open it in writing this week, before any code work starts, so the clock runs in
parallel. Record the date sent in `PROGRESS.md`.

**Answer:** I am writing to the consultant to initate this discussion

---

---

## ✅ Decided

> Each of these is settled and propagated. **Reopening one means editing the spec it landed in** — the
> pointer is in its decision block.

---

## Questions I did **not** ask, and why

Stated so you know they were considered and settled rather than overlooked:

- **"Should we do this at all?"** — Sprint 0's licence gap is a categorical DPG fail and a five-minute
  fix regardless of everything else. The rest follows from a decision already taken.
- **"Which exact models?"** — a DPG-22/23 measurement, not an owner decision. Model tags move faster than
  this document; the specs carry selection *criteria* instead.
- **"Is Rasa a licence risk?"** — the source narrative flagged this as a week-one alarm. There is no
  Rasa: no `rasa_chatbot/` directory, no Rasa service in either compose file, only `rasa-sdk==3.6.2`
  (Apache-2.0). DPG-02 confirms it mechanically in an hour. Nothing to decide.
- **"Should ticketing import the backend's LLM *client*?"** — no. `ticketing/clients/llm_client.py:5`
  states the independence rule, CLAUDE.md backs it, and this sprint does not relitigate service
  boundaries. Two factories, each owning its own construction and lifecycle.
  ⚠ **But "one pattern, replicated" was the wrong conclusion** — replicating the *registry* is what
  produced four files of duplicated model names and one falsified provenance field. Two factories, **one
  config**: DPG-17. Where that shared config lives is Q-18, and it is a `backend/config/` module, not a
  `backend/services/` one — a distinction the original bullet elided.

---

