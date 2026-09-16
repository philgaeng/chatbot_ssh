# Follow-up — the final submit erased the LLM's SEAH detection, in the window that exists for it to catch up

> **Raised and fixed:** 2026-08-27, tracing DPG-34 step 3 after the owner corrected my model of the
> intake flow.
> **Status:** ✅ **FIXED and verified against the live database.** Kept as a record because the *way*
> it was found is more transferable than the fix.
> **Deviation:** D-64.

---

## The defect

`detect_sensitive_content_task` writes `grievance_sensitive_issue = True` to `public.grievances`
seconds after dispatch. The tracker slot, meanwhile, still holds the **keyword** result from the
0.9-second poll at the end of `form_grievance` (`get_sensitive_issue_slots_on_submit`, 3 × 0.3 s) —
which almost never catches a detection that measures **p50 3.73 s**.

Then the final submit, after contact and OTP, collected that stale slot (`collect.py:48`), routed it
through `get_complainant_and_grievance_fields` into `grievance_fields`, and `update_grievance` wrote
it — with no falsy filtering — **straight over the model's True**.

⭐ **It fired in exactly the case the LLM leg exists for: keywords miss it, the model catches it**
(D-52). And the ticket's `is_seah` is read from that column by the two-minute sync
(`grievance_sync.py:172` → `ticket_intake.py:467`), so the erasure reached the ticket: **a harassment
report silently not routed to the SEAH workflow.**

## The fix

`grievance_sensitive_issue` only ever escalates:

```sql
grievance_sensitive_issue = (COALESCE(grievance_sensitive_issue, false) OR %s)
```

Applied in **both** writers (`update_grievance` and `update_grievance_with_tracking`) via one
helper, because they are two independent paths to the same column.

⚠ **In SQL, not read-modify-write, and that is not a style preference.** Reading the current value
and OR-ing in Python leaves a window: read False → the LLM task writes True → we write False. The
window is small and the consequence is a missed harassment report, so the update has to be atomic.

⚠ **Safe as a blanket rule** because nothing legitimately writes False here to clear a real
detection — every False in the codebase is a slot default or a form reset (`session_store.py:21`,
`form_grievance.py:68`, `:218`, `form_road_hazard.py:73`). Clearing a false positive is a
ticketing-side action on a reviewed case, not a rewrite of the chatbot's column. Recall-first by the
owner's decision: over-flagging is reviewed-and-returned; a miss is a safeguarding failure.

## ⭐ How it was found, which is the part worth keeping

**It was found by being corrected.** I had written that the LLM SEAH leg barely mattered — the 0.9 s
poll misses it, so "the keyword detector is what actually sets the slot". The owner pointed out that
submission is **two-stage**: the description goes to the LLM at one point, and the *actual* submit
happens after contact details, which is precisely the window that lets the LLM leg finish.

That was right and my framing was wrong. Following the correction meant asking what reads the flag
*after* that window — which led to the sync reading the DB column, which led to asking what *writes*
that column at final submit. The defect was three steps down a path I only walked because a claim of
mine had been challenged.

**The transferable bit:** the wrong model was not idle. It had a conclusion attached — *the LLM leg
degrades gracefully* — which, if left standing, would have made this erasure look unimportant if
anyone had stumbled on it later.

## ⚠ And the first fix was on the wrong method

I put the escalation rule in `update_grievance_with_tracking`. The defect goes through
`update_grievance` — `submit_grievance_to_db` calls that one. **The test caught it, because it drove
the real method instead of re-implementing the rule.** An assertion that recomputed the logic in the
test would have passed against a fix sitting on an unused path.

That is the third decorative-test catch in this sprint, all three by the same discipline: assert the
behaviour of the code that runs, never a restatement of what it should do.

## Verification

- 7 assertions in `tests/backend/test_sensitive_flag_only_escalates.py`, including one that the rule
  is **not** a read-modify-write (the test fails if `update_grievance` reads the row to decide).
- 3 mutations checked red: the call removed from `update_grievance`; the OR reduced to a plain
  assignment; the rewrite widened to every field.
- **Driven against the live database in-container**, the full scenario:
  `False` → LLM writes `True` → stale `False` submit → **stays True** → restored.

## Related

- [`../PROGRESS.md`](../PROGRESS.md) → **D-64**, and **D-52** for the false-positive design it protects
- [`../../dpg/pii-egress-inventory.md`](../../../dpg/pii-egress-inventory.md) — the DPG-34 work this came out of
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
