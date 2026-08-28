# Follow-up — nobody has measured the one path the classification budget exists for

> **Raised:** 2026-08-19 as **D-41**; written up 2026-08-27 while reconciling
> [`02-llm-agnostic-spec.md`](../02-llm-agnostic-spec.md) against the code, where it is the one
> DPG-15b acceptance box that is not ticked.
> **Status:** ⬜ **OPEN** — risk mitigated, number unmeasured.
> **Size:** XS. One run through the flow with a stopwatch, folded into the next manual browser sweep.

---

## The finding

`CLASSIFICATION_WAIT_SECONDS` is 30 s. Whether that is generous or tight depends entirely on **how
long the complainant spends between triggering classification and reaching the review step** — and
that gap is not one number, it is two very different ones.

Q-20's tracing established the normal path: classification fires when the grievance form completes,
the complainant then fills `form_contact` and `form_otp` — **an SMS round-trip** — and only then
reaches the review step. Against a measured 14–20.5 s classification, that is comfortable.

**But `complainant_consent is False` makes `form_otp.required_slots()` return `[]`**
(`backend/actions/forms/form_otp.py:181-183`). The SMS round-trip disappears, `form_contact` shrinks,
and the gap collapses to seconds.

⚠ **So the fast path through the flow is the privacy-conscious path.** The complainant who declines to
share contact details is the one who reaches the review step *before* the classification does, and is
shown a *not ready yet* message where everyone else sees their categories. That is the wrong way round
for a grievance mechanism: anonymity should not cost you the chance to check how your complaint was
understood.

## What is already mitigated

DPG-15b shipped the controls: a 30 s budget from the registry, a reachable terminal `LLM_failed` so
the poll stops on knowledge rather than running the clock, and a message in **every** branch — ready,
not ready yet, will not arrive — where the pending branch used to render nothing at all. The short
path is documented in [`02_flow_spec.md`](../../../rest_chatbot/02_flow_spec.md).

**None of that is the measurement.** It bounds the damage without telling anyone how often it happens.

## What would close it

One pass through the flow with `complainant_consent` declined, recording the wall-clock gap between
the classification trigger and the review step. Then compare it with the measured classification
latency (p95 **24.6 s** against a 30 s budget — `docs/dpg/model-benchmarks.md`) and say plainly what
fraction of contact-refusing complainants would see *not ready yet*.

⚠ **The answer changes a decision, which is why it is worth a stopwatch.** If the gap is a few
seconds, then for anonymous complainants the review step is effectively never populated, and the
honest fix is not a longer budget — a longer budget is a longer spinner — but showing the
classification somewhere they can still reach it, or accepting the gap and saying so.

## Related

- [`../PROGRESS.md`](../PROGRESS.md) → **D-41** — the finding, with the flow evidence
- [`../02-llm-agnostic-spec.md#dpg-15b`](../02-llm-agnostic-spec.md#dpg-15b) — the acceptance box this leaves unticked
- [`../../../deployment/17_manual_browser_sweep.md`](../../../deployment/17_manual_browser_sweep.md) — where this belongs
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
