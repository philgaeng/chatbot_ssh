# T2 — self-hosted vLLM: documented and costed, not deployed

> **Status (2026-09-03): ⚠ documented and costed, not deployed.** T2 is **parked**: nobody owns the
> GPU running costs. Not starting is the right call — an excellent system nobody funds to keep running
> is worse than one not built. **This document exists so that unparking is a procurement decision
> rather than an engineering one.**

> ## ⭐ The headline
>
> **The T1/T2 crossover is unreachable at any plausible GRM volume.** At pilot traffic it is about
> three orders of magnitude away; at a hypothetical national ceiling the cheapest self-hosted option
> still needs **8× more volume than the whole country would generate**.
>
> **So this is not a cost decision. It is a data-sovereignty decision**, and presenting it as a price
> comparison would imply that volume growth eventually justifies T2. It does not.
>
> > **T1 is cheaper at every volume this system will ever see. T2 buys one thing, and it is not
> > savings: it is that grievance text never leaves the country.**
>
> That makes it a **policy decision with a stated price** — one a ministry can take — rather than a
> break-even calculation. The price of sovereignty is roughly the difference between single-digit
> dollars a month and a few hundred, plus an operator.

> ## Updated 2026-09-03 — what the redaction layer did to this argument
>
> Grievance text is now **pseudonymised before it leaves the process** (87.5% measured recall). It
> would be easy to read that as *"T2 matters less now."* **It does not, and the reason is worth
> stating precisely, because the mistake is attractive.**
>
> | | Redaction buys | T2 buys |
> |---|---|---|
> | Text | Names, phones and addresses mostly removed — **87.5%, not 100%** | Everything stays, and nothing crosses the border |
> | Status of the data | **Still personal data** — the mapping exists, so this is pseudonymisation, not anonymisation | Not transferred at all, so §3.7's cross-border analysis does not arise |
> | Audio | ⛔ **Nothing.** A waveform cannot be redacted; there is no step between microphone and model | ⭐ **The only thing that has ever solved it** |
> | The legal event | Unchanged. **The transmission is what needs a lawful basis**, whatever it carries | Removed |
>
> ⭐ **So redaction narrowed the exposure and did not touch the argument for T2.** If anything it
> sharpened it: the residual — a measured 12.5% miss rate, plus an audio path with no control at all —
> is now a **named number** rather than a general worry, and a named number is what a procurement
> decision can be taken against.
>
> ⚠ **The one thing that did change:** with redaction absent, T2 was the *only* control on the model
> boundary and unparking it was urgent. It is now the *second* control and the pressure is off. **Off
> is not gone** — and note what that pressure was actually removed by, which was a funding decision
> about voice, not a privacy one.

---

## 1. Why the code needs nothing

Same code, different `LLM_BASE_URL` — the point of [the model registry](../../backend/config/llm_config.py).

```bash
# chat / classification / summary / SEAH detection
vllm serve <chosen-text-model> \
  --host 0.0.0.0 --port 8000 \
  --quantization awq --max-model-len 8192 \
  --gpu-memory-utilization 0.90 --api-key "$LOCAL_LLM_KEY"

# transcription — vLLM exposes /v1/audio/transcriptions
vllm serve <chosen-asr-model> \
  --host 0.0.0.0 --port 8001 --api-key "$LOCAL_ASR_KEY"
```

Both endpoints match what the code already calls, and vLLM has guided decoding built in — which makes
[the structured-output schemas](open-model-configuration.md) a **T2 enabler**, not only a robustness
fix.

⭐ **T2 also fixes the one thing T1 cannot do at all:** the Hugging Face router serves no
`/v1/audio/*` route, so the ASR half of `.env.open` is unserviceable
([`open-model-configuration.md`](open-model-configuration.md)). A self-hosted vLLM would serve it.

---

## 2. Deployment requirements

All marked `⚠ not deployed`. Carry into [`13_security.md`](../deployment/13_security.md).

| Requirement | Why |
|---|---|
| **Private subnet**, reachable only from the application security group | An open inference endpoint is an open door to a machine holding grievance text in memory |
| **TLS at a reverse proxy** | "Inside the VPC" is not an authentication story |
| **An API key even on a private network** | Defence in depth. ⚠ The codebase already carries one service bound to `0.0.0.0` *"because the firewall holds"* — **do not add a second** |
| **Snapshot the instance once configured** | Weights are tens of GB; re-downloading them during an incident is the wrong time to discover the bandwidth |
| **Monitoring and a restart policy, with a named owner** | ⏸ **The parked item.** Not the hardware — the *person* |

---

## 3. The crossover — and why it decides nothing {#3-the-crossover-and-why-it-decides-nothing}

**T1 costs ≈ 3,700 prompt + 3,361 completion tokens per grievance**, across both model calls.
Provenance, and which half is measured rather than derived, is in
[`model-benchmarks.md`](model-benchmarks.md) §6 — stated once there. **When the meter is re-run,
replace this table rather than annotating it.**

**T2 costs a monthly instance**, whatever the volume. So:

> crossover volume = monthly instance cost ÷ per-grievance T1 cost

| T1 price ($/M in, $/M out) | T1 $/1,000 | at $300/mo | at $600/mo | at $900/mo | at $1,500/mo |
|---|---|---|---|---|---|
| 0.05 / 0.40 | $1.53 | 196,000 | 392,000 | 588,000 | 980,000 |
| 0.10 / 0.40 | $1.71 | 175,000 | 351,000 | 526,000 | 877,000 |
| 0.15 / 0.60 | $2.57 | 117,000 | 233,000 | 350,000 | 584,000 |
| 0.30 / 1.20 | $5.14 | 58,000 | 117,000 | 175,000 | 292,000 |

*(Crossover in grievances per month. ⚠ **Prices are placeholders** — get quotes and record the date.
The shape of the conclusion holds across the whole range, which is why a range is shown.)*

### Put a real volume beside it

Two districts generate grievances in the **tens per month**. Nepal has **77 districts**; at 100 a
month each that is **7,700 nationally**. **The lowest crossover in the table is 58,000.**

- At pilot volume, T1 costs single-digit dollars a month and T2 costs hundreds.
- At national volume, T1 costs **$12–$40 a month** — **8× to 127× cheaper** than the cheapest
  self-hosted option.
- **Volume growth does not close the gap.**

**Why so lopsided.** Classification is **one request per grievance**, not per conversational turn.
This is intake-shaped, bursty traffic — around road works and public meetings — not chat-shaped. A
dedicated GPU is idle almost all the time, and idle GPU time is the entire cost.

⚠ **State the margin at the volume it applies to**, because the two differ by two orders of
magnitude: three orders at pilot traffic, **8×** at the national figure. So a per-district rate would
have to come in **eight times** the pilot's before the cheapest self-hosted option merely broke even.
That is the claim someone can check.

⚠ **The national figure is an extrapolation from a base that does not exist yet** — the grievance
table holds only seed and demo rows. Method: assume each district behaves like the pilot, multiply by
77. **Re-run it against real pilot volume before it goes to anyone.**

⚠ **T1's price is not the only number in the comparison.** Under T1 grievance text — including SEAH
narratives — leaves Nepal, reaches a provider selected per request unless pinned, and is unredacted
until redaction ships ([privacy assessment](privacy-assessment.md) F-17). **T2 parked makes T1 the
steady state rather than a transition**, which promotes redaction from prudent to necessary.

⭐ **The cost lever was the prompt, and it has been pulled** — a 70% cut
([`model-benchmarks.md`](model-benchmarks.md) §7), which pushed every crossover figure *further* from
self-hosting. **The remaining lever is reasoning effort, not prompt size**, and it carries a quality
risk the prompt cut did not.

---

## 4. Sizing, if it is ever unparked

**Do not inherit the $700–900/month, 5–15-concurrent-user figure from the source narrative.** That is
a generic chat-workload estimate, and this is not a chat workload. Size against what is measured:

| Input | Value | Source |
|---|---|---|
| Requests per grievance | **2** (classify + SEAH detect) | measured |
| Prompt tokens per grievance | **≈ 3,700** | [`model-benchmarks.md`](model-benchmarks.md) §6 |
| Completion tokens per grievance | **3,361**, of which **93.8% reasoning** | same |
| Peak shape | bursty around road works and public meetings | design, not measured |
| Model size target | fits one 24 GB GPU at 4-bit | the candidate filter |
| Latency budget | 30 s interactive, raisable with a stated cost | the interactive deadline policy |

⚠ **The completion figure is the sizing trap.** Reasoning tokens are billed on T1 and are
*GPU-seconds* on T2. **A sizing built from visible output length undersizes the instance by roughly
16×.**

---

## 5. ⏸ Deferred, explicitly

- **An end-to-end test against a live vLLM endpoint.** It cannot run without an instance, and it is
  what would turn *documented* into *demonstrated*. Logged, not silently dropped.
- **Jurisdiction** (where a self-hosted GPU would sit) and **operator-and-payer** are parked **with
  their analysis**, so unparking starts from it. Jurisdiction is moot while this stays parked;
  **the operator is what actually blocks, and it is a person, not a budget line.**

---

## 6. Related

- [`open-model-configuration.md`](open-model-configuration.md) — the tier ladder, and what is supported today
- [`model-benchmarks.md`](model-benchmarks.md) — where the token costs come from
- [`../deployment/13_security.md`](../deployment/13_security.md) — the network posture, `⚠ not deployed`
- [`privacy-assessment.md`](privacy-assessment.md) — F-17, why pinning a provider is not knowing the jurisdiction
