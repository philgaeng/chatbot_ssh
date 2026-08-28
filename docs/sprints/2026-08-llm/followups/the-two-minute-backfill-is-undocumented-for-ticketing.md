# Follow-up — the two-minute back-fill is what makes the design work, and the ticketing spec does not mention it

> **Raised:** 2026-08-27, reconciling [`02-llm-agnostic-spec.md`](../02-llm-agnostic-spec.md) against
> the code.
> **Status:** ⬜ **OPEN** — a DPG-15b acceptance item, half done and in a different file.
> **Size:** XS to document. S if the "verified with a real late arrival" limb is honoured too.

---

## The finding

DPG-15b's acceptance says:

> *"The two-minute sync's back-fill of a late classification **and** of the complainant's review edits
> verified in-container with a real late arrival, and written into `11_llm_pipeline_policy.md` — **it
> is undocumented and it is what makes the whole design work**."*

Two things happened instead:

1. **T-15b-c established the back-fill already existed** — `grievance_sync` refreshes summary,
   categories and location every two minutes (Q-20) — so it was documented rather than rebuilt. Good
   call: building a late-update path that already exists is the expensive kind of duplicate.
2. **It was documented in [`02_flow_spec.md`](../../../rest_chatbot/02_flow_spec.md), not in
   [`11_llm_pipeline_policy.md`](../../../deployment/11_llm_pipeline_policy.md).** The chatbot flow
   spec is a reasonable home for it. It is not the *only* home it needs.

## Why the second file matters

The back-fill is the reason a slow classification is survivable. It is the answer to *"the complainant
gave up waiting — does the officer still get the categories?"*, and **the officer's side is the
ticketing side**. `11_llm_pipeline_policy.md` is what a ticketing engineer opens to learn how LLM
output reaches a ticket; today it describes the two ticketing pipelines and says nothing about the
chatbot classification arriving late through `grievance_sync`.

So the guarantee is written down where the person who needs it does not look.

## Also outstanding: the verification limb

The acceptance asked for it *"verified in-container with a real late arrival"*. What happened was
establishing that the mechanism **exists**, which is a weaker claim than watching a late classification
land on a ticket. That is the part worth doing when someone next has the stack up: hold the model
response past the 30 s budget, let the complainant reach the review step and be told *will not
arrive*, then confirm the summary, categories and location appear on the ticket within two minutes —
**and that the complainant's own review edits are not overwritten when they do**. The second half is
the one with a data-loss shape and it is the one nobody has driven.

## What would close it

- A short section in `11_llm_pipeline_policy.md`: what `grievance_sync` back-fills, on what cadence,
  and why the interactive budget can be short because of it. Cross-link `02_flow_spec.md` rather than
  restating the flow.
- The in-container run above, with the result recorded — including the edit-precedence question.

## Related

- [`../02-llm-agnostic-spec.md#dpg-15b`](../02-llm-agnostic-spec.md#dpg-15b) — the ticket
- [`../TESTS.md`](../TESTS.md) → T-15b-c — where the "already existed" finding is recorded
- [`../../../rest_chatbot/02_flow_spec.md`](../../../rest_chatbot/02_flow_spec.md) — where it is documented today
- [`../../../deployment/11_llm_pipeline_policy.md`](../../../deployment/11_llm_pipeline_policy.md) — where it is missing
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
