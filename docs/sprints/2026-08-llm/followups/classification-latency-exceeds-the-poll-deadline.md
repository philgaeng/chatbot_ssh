# Follow-up — classification sometimes takes longer than the chatbot waits for it

> **Raised:** 2026-08-18 by [DPG-14.1](../02-llm-agnostic-spec.md#dpg-14)'s liveness check — three live
> calls against `gpt-5-nano`, which answered a question nobody had asked.
> **Logged as deviation D-30** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** 🔵 open · **Size:** S to measure properly, M to fix well · **Owner:** unassigned

## What was measured

Three classifications of one realistic Nepali grievance, in-container, against the live key
(`backend/services/LLM_services.py` → `classify_and_summarize_grievance`, model `gpt-5-nano`):

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `finish_reason` | `stop` | `stop` | `stop` |
| Completion tokens | 3,087 | 2,222 | 2,157 |
| — of which reasoning | 2,880 | 2,048 | 1,984 |
| **Server processing time** | **20.5 s** | 15.2 s | 14.0 s |

The retrieve step polls for the classification with a hard deadline of **20 seconds**
(`CLASSIFICATION_POLL_MAX_SECONDS = 20.0`, `backend/actions/grievance_intake/classification.py`,
0.5 s interval). **One run of three exceeded it**, and that figure is server processing time alone —
it excludes Celery queue wait, network, and the time between the row being written and the worker
picking the task up.

## Why it matters

When the deadline is missed, the complainant is shown the empty-classification path — no summary, no
categories, and the follow-up question the flow depends on — **even though the model succeeded**. The
row is filled moments later, after the conversation has moved on. From the outside this is
indistinguishable from the model failing, which is exactly the confusion DPG-14.1 set out to resolve
in the other direction (it asked whether `gpt-5-nano` was silently failing; it is not).

It also means the degraded-mode design is being exercised routinely by *success*, not only by outage
— which is not what DPG-15's audit table assumes.

## Where the time goes

92% of run 1's completion budget was **reasoning tokens** (2,880 of 3,087). The prompt is 20,725
characters: the full category catalogue, plus `result_dict_str` — the same catalogue again with the
per-language keys stripped — plus district and province. Both halves are addressable, and neither
should be guessed at:

- **Prompt size** is ours. The catalogue is injected twice in different shapes.
- **Reasoning effort** is a request parameter on this model family, not a fixed property.

## Definition of done

- [ ] Latency measured over ≥20 calls, not 3, and reported as a distribution (p50/p95), not a mean
- [ ] The 20 s deadline set from that distribution — or the poll replaced by something that does not
      need a deadline (the classification already lands in the row; the flow could read it later)
- [ ] A decision recorded on prompt size and reasoning effort, with the cost delta measured
      (⚠ this is the same budget question as **Q-19**, which is unanswered)
- [ ] Whatever is chosen, the complainant-visible behaviour on a slow-but-successful classification is
      written down in [`docs/services/06_llm_service.md`](../../services/06_llm_service.md)

## Why it is not fixed here

DPG-14 is a defect ticket with three named defects; this is a fourth, found by it. Changing the poll
deadline is a change to live intake behaviour with no measurement behind it — three samples is an
observation, not a distribution. The sprint convention is to log and keep moving.

⚠ **It is also a genuine cost question, and there is no LLM budget** (Q-19). Anyone tempted to fix
this by lowering reasoning effort should price the quality delta first: this is the model DPG-23
benchmarks the open candidates against, and a baseline that moves mid-benchmark is worse than a slow one.

## Where it is tracked

`TODO.md` → 🔵 TECH DEBT · `PROGRESS.md` → **D-30** · related: DPG-15 (degraded-mode audit),
DPG-23 (benchmark baseline), Q-19 (budget)
