# Follow-up — the router rate-limits, and reports it as *"you have depleted your monthly credits"*

> **Raised:** 2026-08-20, on DPG-21's first probe run.
> **Logged as deviation D-50** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** ✅ **DIAGNOSIS CORRECTED AND WORKED AROUND, same day.** Originally logged as *"the
> account has no inference credit"*. **That was wrong**, and §The correction has the evidence.
> **Size:** S — a backoff and a pause between models, both landed.

---

## ⚠ The correction — read this before the original finding below

**The original diagnosis was wrong, and it was wrong in the direction that costs the most:** it
declared six of seven candidate models *unmeasurable* on the strength of an error message.

What is actually happening is a **short-window rate limit**. Measured the same day:

| What was run | Result |
|---|---|
| Seven candidates, six probes each, back to back | model 1 passed all six; **every later model returned 402** |
| `Qwen/Qwen3.5-27B` alone, by curl, four times, seconds later | **200, 200, 200, 200** |
| `Qwen/Qwen3.5-27B` alone, all six probes in-container | **all six pass** |

The provider's words are *"You have depleted your monthly included credits."* The behaviour is about
the last minute, not the month. **A harness that believes the message publishes "unmeasurable" for a
model that works** — which is the same class of error as reporting a 402 as a capability limit, one
level up, and it very nearly went into a document as a result.

**The fix, landed:** `_run()` now backs off (20 s / 45 s / 90 s) and retries before recording
`blocked`, a **model refusal is never retried** (a 400 on `json_schema` is the answer, not an
obstacle), and `--pause` spaces models apart — defaulting to 25 s, which is correctness rather than
courtesy. Three tests pin it, with the clock **injected** rather than endured.

**The general lesson, which is the third time this sprint has taught it:** *believe the behaviour,
not the message.* A 402 that says "monthly" and means "this minute" is the same failure as a 401 that
reads as *"the model cannot detect harassment"* (D-44) and a 402 that reads as *"this model does not
support temperature"* (the first version of this very script).

⚠ **How confident to be about "rate limit".** What is *established* is narrower than that word:
**the message does not mean what it says.** The account served **250+ further calls** after
announcing that its monthly credits were depleted, and paced probing recovered every model that had
just 402'd. Whether the underlying mechanism is a burst limiter, a windowed allowance, or something
else is **not** established, and this document should not claim it is. What follows operationally —
back off, pace, and never record a 402 as a model property — holds either way.

### ⚠ And the thing that *is* now established, checked 2026-08-20

Against Hugging Face's own pricing documentation and the account itself (`whoami-v2`:
`type=user`, `isPro=false`, no organizations):

| | |
|---|---|
| **A configurable spending limit** | ⚠ **Does not exist for this account.** It is a **Team/Enterprise organization** feature. DPG-24's acceptance criterion *"set a hard token cap on the HF account before the first run"* was **unactionable as written**, and the job header now says so instead of restating it |
| **Free tier** | ~$0.10 of included credits per month; past that, requests 402 |
| **Extra usage** | **Pre-paid.** The balance you load *is* the ceiling — load $20 and $20 is the most that can ever be spent. That is the real cap, achieved by not topping up rather than by a setting |

⭐ **The consequence for DPG-24, which matters more than the terminology:** on the free tier the
credits go within a few runs, after which every live test skips, and the job's *nothing-passed*
guard correctly fails it. **So a small pre-paid balance is not optional if that job is to run
per-commit** — the alternative is the documented degraded cadence (nightly + release tags) with the
badge saying so.

---

## The original finding (kept, because the reasoning is what was wrong, not the observation)

The token authenticates (`whoami-v2` → 200, user `pgaeng`, fine-grained with Inference permission)
and the first requests succeeded — `openai/gpt-oss-20b` completed all six capability probes, served
by Groq. Then, partway through the second model:

```
HTTP 402 Payment Required
x-error-message: You have depleted your monthly included credits. Purchase pre-paid credits to
continue using Inference Providers. Alternatively, subscribe to PRO to get 20x more included usage.
```

Every subsequent request, on every model, returns the same. Free-tier included credits are gone for
the month.

## Why this is logged rather than absorbed

[Q-19](../DECISIONS.md#q-19) answered the budget question on 2026-08-20 — *a few hundred USD,
owner-funded* — so this is **not** the old "there is no budget" blocker returning. It is the narrower
and more fixable one: **the funded budget has not been applied to the account the code points at.**
Nothing in the repository can fix that, and no amount of engineering makes a 402 into a measurement.

⚠ **And it is the reason to read the sequencing advice again rather than around it.** Q-19's envelope
is *shared with the pilot's own classification traffic across two districts*. A depleted free tier on
day one of the benchmark is a small preview of the real risk the answer named: the sweep and the
pilot draw on one pot, and the sweep is the half that can be re-run later.

## What it blocks, precisely

| Ticket | Blocked | Still reachable without credit |
|---|---|---|
| **DPG-21** | 5 of 7 candidates unprobed; 1 partially | ✅ The probe script, the shortlist, licence verification (model-card lookups are free), and the one complete `gpt-oss` profile — all committed |
| **DPG-23** | **Everything measured.** Accuracy, F1, SEAH recall, latency, cost | The harness, the pricing estimate, the scoring rules, the table skeleton with `⚠ Not measured` |
| **DPG-22** | WER, latency, cost per 1,000 minutes | Licence verification; and it is **already** blocked independently by having no audio ([followup](no-audio-subset-for-asr-benchmark.md)) |
| **DPG-24** | The job's first green run | The job definition, the marker, the skip-without-secrets behaviour |

## ⚠ The thing this nearly cost, which is worth more than the delay

The **first** version of `llm_smoke.py` rendered those 402s as ❌ in the capability matrix. So the
report said, in the same visual language it used for a real 400:

| model | temperature | max_tokens |
|---|---|---|
| `openai/gpt-oss-120b` | ❌ | ❌ |

That reads as *"this model does not support temperature"*. Pasted into `_PROFILES` — which is exactly
what the script prints a tuple for — it would have pinned permanent conservative behaviour into the
running code path on the evidence of an empty wallet, and it would have looked identical to a row
that had been measured.

This is the shape `docs/models/01_seah_detection_benchmark.md` §6.1 makes a standing rule about:

> *"On 2026-08-18 a 401 presented as 'the model cannot detect harassment' — a config error reading
> exactly like a quality finding, because the SEAH path fails open by design."*

**Fixed the same day.** The probe now classifies `blocked` (the account) apart from `refused` (the
model), renders three states rather than two, prints a banner, refuses to emit a `ModelProfile` for
any model with a blocked cell, and exits **3** rather than 0. `tests/backend/test_llm_smoke.py` pins
all of it — 16 tests, including that a `json_schema` reply which omits a required field counts as
*accepted and ignored*, not as a pass.

**The lesson generalises past this incident:** any harness that reports on a paid third-party API
must distinguish *the provider said no* from *the account said no*, before it reports anything at
all. The second one is not a finding.

## What closes it

1. **Put the funded budget on the account the code points at** — pre-paid credits or PRO on the
   Hugging Face account holding `HG_TOKEN`. ⚠ Set the **hard token cap at the same time**, not after:
   DPG-24 acceptance requires it *before* the first CI run, and that job is the only recurring cost
   in the whole plan.
2. Re-run `python -m scripts.ops.llm_smoke --candidates --json report.json`; exit 0 means every cell
   is a measurement. Paste the emitted tuples into `_PROFILES`.
3. Price DPG-23 against **what is left after an estimate of pilot traffic**, then run the cheap first
   pass before the full set.
4. Replace every `⚠ blocked` in `docs/dpg/open-model-configuration.md` and every `⚠ Not measured` in
   `docs/dpg/model-benchmarks.md` with a number, and close this document.

## Related

- [`../DECISIONS.md#q-19`](../DECISIONS.md) — the budget answer, and what it obliges
- [`../03-open-models-spec.md#dpg-21`](../03-open-models-spec.md#dpg-21) · [DPG-23](../03-open-models-spec.md#dpg-23) · [DPG-24](../03-open-models-spec.md#dpg-24)
- [`../../../models/01_seah_detection_benchmark.md`](../../../models/01_seah_detection_benchmark.md) §6.1 — prove authentication before reporting a miss
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
