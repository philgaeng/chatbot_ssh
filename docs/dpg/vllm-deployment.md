# T2 — self-hosted vLLM: documented and costed, **not deployed**

> **Status (2026-08-20): ⚠ DOCUMENTED AND COSTED, NOT DEPLOYED.** T2 is **parked**
> ([Q-03](../sprints/2026-08-llm/DECISIONS.md), [Q-05](../sprints/2026-08-llm/DECISIONS.md)): nobody
> owns the GPU running costs. Not starting is the right call — an excellent system nobody funds to
> keep running is the failure mode that killed Rwanda's Babyl, and it is worse than not building it.
> **This document exists so that unparking is a procurement decision rather than an engineering one.**
> **Owner:** [DPG-25](../sprints/2026-08-llm/03-open-models-spec.md#dpg-25).

> ## ⭐ The headline, and it is not the one this ticket expected
>
> **The T1/T2 crossover is unreachable at any plausible GRM volume — by three to four orders of
> magnitude.** Self-hosting does not pay for itself on this workload and will not at national scale.
>
> **So the T1-versus-T2 decision is not a cost decision at all. It is a data-sovereignty decision**,
> and presenting it as a price comparison would mislead the reader into thinking volume growth
> eventually justifies T2. It does not. See [§3](#3-the-crossover-and-why-it-decides-nothing).

---

## 1. Why the code needs nothing

Same code, different `LLM_BASE_URL`. That is the whole point of
[DPG-17's registry](../../backend/config/llm_config.py), and it is the claim this document exists to
keep true and costed.

```bash
# chat / classification / summary / SEAH detection
vllm serve <chosen-text-model> \
  --host 0.0.0.0 --port 8000 \
  --quantization awq \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.90 \
  --api-key "$LOCAL_LLM_KEY"

# transcription — vLLM exposes /v1/audio/transcriptions
vllm serve <chosen-asr-model> \
  --host 0.0.0.0 --port 8001 \
  --api-key "$LOCAL_ASR_KEY"
```

Both endpoints match what the code already calls. Guided decoding for
[DPG-13's schemas](open-model-configuration.md) is built into vLLM — which is why those schemas are
a **T2 enabler**, not only a robustness fix.

⚠ **And T2 fixes something T1 currently cannot do at all.** The Hugging Face router **does not
expose `/v1/audio/transcriptions`** — verified 2026-08-20, HTTP 404 on every model id tried, while
the same token gets 200 from `/v1/models` and `/v1/chat/completions`. So the ASR half of `.env.open`
is presently unserviceable, and a self-hosted vLLM would serve it. See
[the follow-up](../sprints/2026-08-llm/followups/the-open-config-has-no-working-asr-endpoint.md).

---

## 2. Deployment requirements — carry into [`13_security.md`](../deployment/13_security.md)

All marked `⚠ not deployed`.

| Requirement | Why |
|---|---|
| **Private subnet**, reachable only from the application security group | Never exposed to the internet. An open inference endpoint is an open door to a machine holding grievance text in memory |
| **TLS terminated at a reverse proxy** | The hop is inside a VPC, but "inside the VPC" is not an authentication story |
| **An API key set even on a private network** | Defence in depth. ⚠ The codebase already carries a TODO row about a service bound to `0.0.0.0` *"because the firewall holds"* — **do not add a second** |
| **Snapshot the instance once configured** | A rebuild becomes minutes rather than a day. Model weights are tens of GB; re-downloading them during an incident is the wrong time to discover the bandwidth |
| **Monitoring and a restart policy, with a named owner** | ⏸ [Q-05](../sprints/2026-08-llm/DECISIONS.md) — **this is the parked item.** Not the hardware: the *person* |

---

## 3. The crossover — and why it decides nothing {#3-the-crossover-and-why-it-decides-nothing}

**T1 cost is measured.** From [DPG-23's baseline run](model-benchmarks.md) over 105 real classification
+ detection calls: **11,358 prompt + 3,361 completion tokens per grievance** (both calls, which is
what production makes). Tokens are the measurement; prices are quotes and are stated as such.

> ⚠ **These token counts predate the prompt reduction, and the direction of the error is the useful
> part.** [`model-benchmarks.md`](model-benchmarks.md) §3.7 cut the classification prompt by ~70%
> (~10,900 → ~3,277 tokens), so the real per-grievance cost is now roughly **3,700 prompt + 3,361
> completion**, not 11,358 + 3,361. **A cheaper T1 pushes the crossover *higher*** — by something like
> 2–3× on the prompt-dominated rows — so every figure below is a **conservative floor** and the
> conclusion is strengthened, not weakened, by the staleness. The table is left as measured rather than
> rescaled by arithmetic, because a number nobody metered is not a measurement; re-run the meter and
> replace it. Either way the finding is unchanged, which is the point of stating it as a range.

**T2 cost is a monthly instance**, whatever the volume. So the crossover is:

> crossover volume = monthly instance cost ÷ per-grievance T1 cost

| T1 price ($/M in, $/M out) | T1 $/1,000 grievances | Crossover at $300/mo | at $600/mo | at $900/mo | at $1,500/mo |
|---|---|---|---|---|---|
| 0.05 / 0.40 | $1.91 | 157,000 | 314,000 | 471,000 | 784,000 |
| 0.10 / 0.40 | $2.48 | 121,000 | 242,000 | 363,000 | 605,000 |
| 0.15 / 0.60 | $3.72 | 81,000 | 161,000 | 242,000 | 403,000 |
| 0.30 / 1.20 | $7.44 | 40,000 | 81,000 | 121,000 | 202,000 |

*(Crossover in grievances per month. ⚠ Token counts measured; **prices are placeholders** — get
quotes and record the date. The **shape** of the conclusion is robust across the whole range, which
is the point of showing a range rather than one number.)*

### ⚠ Now put a real volume beside it

A GRM for **two districts** handles grievances in the **tens per month**. Nepal has **77 districts**;
if every one ran this system at 100 grievances a month, that is **7,700 per month nationally**.

**The lowest crossover in the table is 40,000 per month.** So:

- at pilot volume, T1 costs **single-digit dollars per month** and T2 costs hundreds;
- at full national volume, T1 is still **5× to 100× cheaper** than the cheapest self-hosted option;
- **volume growth does not close the gap.** There is no realistic future in which this workload
  outgrows hosted inference on price.

**Why so lopsided.** Classification is **one request per grievance**, not per conversational turn.
This is intake-shaped, bursty traffic — around road works and public meetings — not chat-shaped
traffic. A dedicated GPU sits idle almost all of the time, and idle GPU time is the entire cost.

### ⭐ What that means for the proposal to the Nepal Government

**Do not present T1 and T2 as a price comparison.** The honest framing:

> **T1 is cheaper at every volume this system will ever see. T2 buys one thing, and it is not
> savings: it is that grievance text never leaves the country.**

That makes it a **policy decision with a stated price**, which is a decision a ministry can actually
take — rather than a break-even calculation that quietly implies waiting for volume to justify it.
The price of sovereignty here is roughly *the difference between single-digit dollars a month and a
few hundred*, plus an operator.

⚠ **And T1's cost is not the only number in that comparison.** Under T1 grievance text — including
SEAH narratives — leaves Nepal, reaches a provider selected per request unless pinned, and is
unredacted until [Sprint 3](../sprints/2026-08-llm/04-pii-redaction-spec.md) lands
([privacy assessment](privacy-assessment.md) F-17). T2 parked makes **T1 the steady state, not a
transition**, which is what promotes redaction from prudent to necessary.

### ⚠ The extrapolation, labelled as one

The national figure above is **an extrapolation from a base that does not exist yet**: at the time of
writing the grievance table holds only seed and demo rows, and the two pilot districts have not
generated real traffic. Method: *assume each district behaves like the pilot; multiply by 77.* That
is an estimate with a stated method, not a forecast. **Re-run it against real pilot volume before it
goes to anyone**, and the conclusion will not change — the margin is three orders of magnitude, and
no plausible correction to a per-district rate closes that.

### The one cost lever that is worth more than the tier choice

⚠ **11,358 of the 14,719 tokens per grievance are prompt** — measured before the ~70% prompt cut
(§3.7 of the benchmarks), which is exactly the lever this paragraph identified — and most of that is the category
catalogue, which the classification prompt injects **twice, in two shapes**
(`LLM_services.py:275-296`) — about 20,700 characters before the complaint is added. **Deduplicating
it is a prompt change, not a model change, and it is worth more than any tier decision on this
page.** It is also the reason adding taxonomy categories raises the cost of every grievance.

---

## 4. Sizing, if it is ever unparked

**Do not inherit the $700–900/month, 5–15-concurrent-user figure from the source narrative.** It is a
generic chat-workload estimate and this is not a chat workload.

Size against what is measured here instead:

| Input | Value | Source |
|---|---|---|
| Requests per grievance | **2** (classify + SEAH detect) | measured |
| Prompt tokens per grievance | **11,358** ⚠ pre-§3.7; ~3,700 today | measured (superseded) |
| Completion tokens per grievance | **3,361**, of which **93.8% reasoning** | measured |
| Peak shape | bursty around road works and public meetings | design, not measured |
| Model size target | fits one 24 GB GPU at 4-bit | the candidate filter |
| Latency budget | 30 s interactive, raisable to 45/60 s with a stated cost | DPG-15b |

⚠ **The completion figure is the sizing trap.** 93.8% of generated tokens are reasoning tokens —
billed on T1, and on T2 they are *GPU-seconds*. A sizing built from visible output length
undersizes the instance by roughly 16×.

---

## 5. ⏸ Deferred, explicitly

- **An end-to-end test against a live vLLM endpoint.** It cannot run without an instance, and it is
  the step that would turn *"documented"* into *"demonstrated"*. Logged as a followup + `TODO.md`
  row — **not silently dropped**, because the difference between those two words is the whole
  difference between this document and evidence.
- **Q-03 (jurisdiction)** and **Q-05 (operator and payer)** are parked **with their analysis**, so
  unparking starts from it rather than repeating it. Q-03 is moot while T2 is parked; Q-05 is the
  one that actually blocks, and it is a person, not a budget line.

---

## 6. Related

- [`open-model-configuration.md`](open-model-configuration.md) — the ladder, and what is supported today
- [`model-benchmarks.md`](model-benchmarks.md) — where the measured token costs come from
- [`../deployment/13_security.md`](../deployment/13_security.md) — the network posture, `⚠ not deployed`
- [`privacy-assessment.md`](privacy-assessment.md) — F-17, why pinning a provider is not the same as knowing the jurisdiction
- [`../sprints/2026-08-llm/03-open-models-spec.md#dpg-25`](../sprints/2026-08-llm/03-open-models-spec.md#dpg-25) — the ticket
