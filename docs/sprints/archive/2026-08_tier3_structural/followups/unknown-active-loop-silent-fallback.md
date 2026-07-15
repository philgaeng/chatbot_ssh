# `status_check_form`'s unknown-`active_loop` fallback is silent

**Status:** ✅ **CLOSED 2026-07-15** — fixed by the `run_flow_turn` postcondition **plus** the point fix, i.e. both halves this doc asked for.
> **Opened:** 2026-07-15 by **T3-02 p2** (D-52) · **Size:** XS-S · **Severity:** low (reachability unproven)

## Outcome

Both DoD items 1 and 2, because they fix different halves and this bug needed both:

1. **The postcondition** (`run_flow_turn`) catches the **symptom**: the turn dispatched nothing,
   so the user is recovered and — critically — `_recover_from_unknown_state` clears
   `active_loop`/`requested_slot`, which is what **un-wedges** the session. A message alone
   would have left the bogus loop in place to re-silence every later turn.
2. **The point fix** names the **cause**: the form-selection `else` now logs at error with the
   offending `active_loop`. This is not redundant with (1) — `status_check_form` is a perfectly
   *valid* state, so an operator reading only the postcondition's log would go looking in the
   wrong place entirely. The postcondition says "this turn went silent"; this says "because the
   loop was `totally_unknown_loop`".

**One guard closed four instances** (D-08/D-51/D-52/D-59), as this doc predicted: *"a single
postcondition … subsumes all three and any future sibling."*

A trap worth recording for the next person: `story_route` is the hinge, and **D-51 and D-52 need
opposite values of it**. D-52 only reproduces when it is *set* (`form_status_check_1` collects it,
so unset ⇒ the form prompts and the turn is not silent); D-51 only reproduces when it is *unset*.
Getting this wrong made two of the new tests pass pre-fix for the wrong reason — caught only by
red-verification, which is exactly what that discipline is for.

Now owned by `tests/orchestrator/test_no_silent_turns.py`. The characterization pin was
**deleted**, on the signal its docstring specified.

---

### Original finding (kept for the record)


## The finding

`run_flow_turn`'s `status_check_form` branch picks which form to run from `active_loop`
(`backend/orchestrator/state_machine.py:1674-1683`):

```python
if active_loop == "form_status_check_1":      form = _get_status_form_1()
elif active_loop == "form_otp":               form = _get_otp_form()
elif active_loop == "form_status_check_2":    form = _get_status_form_2()
elif active_loop == "form_status_check_skip": form = _get_status_form_skip()
else:                                         form = _get_status_form_1()   # <-- silent
```

The bare `else` treats **any** unrecognized `active_loop` as `form_status_check_1`. On a
session whose status-check slots are already filled, that form dispatches nothing, so the
turn returns **zero messages** — and because nothing clears the bogus `active_loop`, every
subsequent turn does the same. The session is wedged, silently.

Measured (T3-02 p2 probe, `active_loop="totally_unknown_loop"`): `next_state=status_check_form`,
**0 messages**, `active_loop` unchanged.

## Why this is the third instance of one class

| # | Where | Caught by p1's terminal `else`? |
|---|---|---|
| D-08 | unrecognized **state** falls off the 22-arm chain | ✅ yes — that is what p1 fixed |
| D-51 | `add_more_info_flow` completes, `action_ask_story_step` no-ops on unset `story_route` | ❌ state is recognized |
| **D-52** | unrecognized **active_loop** inside `status_check_form` | ❌ state is recognized |

**The pattern is the finding.** "Never return empty messages" is a convention this file
states explicitly (`state_machine.py:1629`) and honours in some places, but it is enforced
*nowhere*. Each instance is a different guard site, so each gets fixed (or missed)
separately. A single postcondition on `run_flow_turn` — *no turn returns zero messages;
log at error with the state and active_loop if one would* — subsumes all three and any
future sibling. **That is the recommended fix, and it is worth more than the three point
fixes.** Weigh it against any legitimately-silent turn (check `attachment_ids_sync` first).

## Reachability — UNPROVEN, deliberately

`active_loop` is set by this module and by `form_loop.py`. For an unknown value to appear
you would need a rename across a deploy (a persisted session naming a retired loop), a
partially-migrated session, or a bug elsewhere. That is the same mechanism that makes p1's
terminal `else` worth having — so this is not exotic, merely untraced.

Not traced here because T3-02's spec is explicit that characterization records behaviour and
does not fix it. D-13 is the standing precedent for *not* guessing reachability on this
codebase: it estimated three sites as harmless re-prompt branches and found a mainline
branch and an HTTP 500.

## Pinned, not fixed

`tests/orchestrator/test_status_check_form_characterization.py::test_unknown_active_loop_falls_back_to_status_form_1_silently`
asserts the **current, wrong** behaviour (zero messages). **If it ever fails, the bug was
fixed — delete the test and record the fix; do not relax the assertion.**

## Definition of done

1. Prefer the general guard: a `run_flow_turn` postcondition that no turn returns zero
   messages, logging state + active_loop at error. Closes D-08's class for good.
2. If fixing at the point instead: make the `else` loud — log at error and fall back to
   re-showing the choices (the `:1629` convention), and clear the bogus `active_loop` so the
   session is not wedged.
3. Delete both characterization tests (this and D-51's) as part of the fix, and say so.
4. Re-run the p2 characterization suites — they are the net that proves the fix changed only
   what it meant to.

## Related

- [`add-more-info-silent-turn.md`](add-more-info-silent-turn.md) — D-51, same class
- D-08 / T3-02 p1 — `tests/orchestrator/test_unknown_state_fallback.py`
- `state_machine.py:1629` — the convention all three violate
