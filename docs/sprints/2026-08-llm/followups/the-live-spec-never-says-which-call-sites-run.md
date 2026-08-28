# Follow-up — the live spec never says which of the nine LLM call sites actually run

> **Raised:** 2026-08-27, reconciling [`02-llm-agnostic-spec.md`](../02-llm-agnostic-spec.md) against
> the code.
> **Status:** ⬜ **OPEN** — a DPG-18 acceptance item that was never done, found by ticking the box.
> **Size:** XS. One table, moved.

---

## The finding

DPG-18's acceptance says:

> *"§18.0's table is reproduced in `docs/services/06_llm_service.md` — the *why* travels with the rule"*

It was not. `docs/services/06_llm_service.md` gained two other things from the second wave — DPG-19b's
**SEAH triple-signal** table and DPG-13's measured capability matrix — but the **live/parked call-site
table never landed there**. The word *parked* does not appear in the file.

## Why it matters more than a missing table

The sprint spent a ticket (DPG-19b) establishing that **nine call sites exist and five of them run**,
because *unreachable* and *switched off on purpose* look identical to a grep, and four documents had
carried "nine" for three weeks as a result. `PARKED_TASKS` now holds that distinction **in code**, and
a test pins it.

But `06_llm_service.md` is the document an engineer opens to learn what this service does — and it
still describes nine capabilities with no indication that four of them are switched off. The next
person to read it will do exactly what the sprint just spent a ticket undoing: count call sites and
treat the count as an inventory of what runs.

⚠ **This is the failure mode the sprint's own §18.0 names**, one document downstream:

> *"That counted call sites, not reachable ones — the same mistake the privacy assessment's leg L4
> made, one week and one document apart."*

## What would close it

Reproduce §18.0's table in `docs/services/06_llm_service.md`, with:

- the **Live?** column, which is the load-bearing one and is still accurate;
- the `Model` column read from the registry rather than restated (all seven text tasks resolve to one
  model since §18.2, so a restated column is a second place to drift);
- a pointer to `PARKED_TASKS` (`backend/task_queue/registered_tasks.py:96`) as the enforced version,
  so the table is a reader's convenience and the code is the authority.

**Do not restate model names in it.** `backend/config/llm_config.py` is the only place a model name is
declared (DPG-17), pinned by `tests/backend/test_llm_config_pins.py`, and a live spec that names one
is the drift that ticket removed.

## Related

- [`../02-llm-agnostic-spec.md#dpg-18`](../02-llm-agnostic-spec.md#dpg-18) — §18.0, the table
- [`../02-llm-agnostic-spec.md#dpg-19b`](../02-llm-agnostic-spec.md#dpg-19b) — why the distinction exists
- [`../../../services/06_llm_service.md`](../../../services/06_llm_service.md) — the destination
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
