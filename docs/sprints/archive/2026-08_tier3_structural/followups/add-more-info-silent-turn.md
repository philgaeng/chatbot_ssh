# `add_more_info_flow` completes into a silent turn when `story_route` is unset

**Status:** OPEN · **Opened:** 2026-07-15 by **T3-02 p2** (D-51) · **Size:** S · **Severity:** low-to-medium (reachability unproven)

## The finding

`run_flow_turn`'s `add_more_info_flow` branch, on the non-cancelled completion path
(`backend/orchestrator/state_machine.py:1916-1932`), sets `next_state = "status_check_form"`
and re-shows the story step by invoking `action_ask_story_step`.

That action's **entire body is guarded**:

```python
# backend/actions/action_ask_commons.py:28-48
story_route = tracker.get_slot("story_route")
if story_route in ["route_status_check_grievance_id", "route_status_check_phone"]:
    ...   # every dispatcher.utter_message lives in here
return []
```

If `story_route` is anything else — including `None` — the action dispatches **nothing** and
returns `[]`. The branch extends `dispatcher.messages` with an empty list and the turn returns
**zero messages**. The user submits the extra detail they just typed and the chatbot says
nothing.

Measured directly (T3-02 p2 probe, identical sessions but for the slot):

| `story_route` | `next_state` | messages |
|---|---|---|
| unset | `status_check_form` | **0** ⇐ dead air |
| `route_status_check_grievance_id` | `status_check_form` | 1 |

## Why this is not covered by T3-02 p1

This is **D-08's class — dead air — one level down.** p1 added a terminal `else` to the
22-arm state chain, which catches an *unrecognized state*. Here the state is perfectly
recognized (`status_check_form`); the silence comes from a *recognized branch* invoking an
action that no-ops. A chain-level `else` structurally cannot see it. Nor can the p4 handler
table — the dict lookup succeeds.

**The general lesson, which is worth more than this instance:** "never return empty messages"
was enforced at the dispatch boundary. Nothing enforces it at the *turn* boundary. A
`run_flow_turn` postcondition — "no turn returns zero messages" — would catch this class
wherever it hides, and would have caught D-08 too.

## Reachability — UNPROVEN, deliberately

To reach `add_more_info_flow` the user goes status-check → modify menu → "add more info",
and the real status-check flow sets `story_route` on the way in. So on the mainline this is
probably unreachable, which is why it is **logged, not fixed** (T3-02's spec: *"Bugs found
while characterizing are recorded, not fixed — you would be changing behavior under a test
net you just wrote"*).

What is **not** established, and would decide the severity:
- whether any path reaches `add_more_info_flow` with `story_route` unset (session expiry +
  rehydration? a resumed session? `/introduce` mid-flow?)
- whether `story_route` can be cleared while `status_check_grievance_id_selected` survives

Note the precedent for treating this seriously: T3-01's D-13 estimated its three sites as
"error/re-prompt branches only, which is why nobody noticed", and tracing found one was a
*mainline* branch and another a **HTTP 500**. Reachability guesses on this codebase have a
poor record — trace it before dismissing it.

## Pinned, not fixed

`tests/orchestrator/test_add_info_flows_characterization.py::test_add_more_info_submit_is_silent_when_story_route_is_unset`
asserts the **current, wrong** behaviour (`_texts(body) == []`). That is deliberate: it is a
characterization net for p3/p4. **If a future change makes this path speak, that test fails —
that is the signal to delete the test and record the fix, not to relax the assertion.**

## Definition of done

1. Trace reachability: can `add_more_info_flow` be entered with `story_route` unset? Record the
   verdict (the D-13 pattern: static trace + an empirical probe, both).
2. If reachable ⇒ fix. Cheapest correct fix is at the branch: if `action_ask_story_step`
   dispatched nothing, fall back to a message (or re-show the modify menu) rather than return
   an empty turn.
3. Consider the general guard instead of / as well as the point fix: a postcondition in
   `run_flow_turn` that no turn returns zero messages, with the offending state logged at
   error. That subsumes D-08, this, and the next one. Weigh against the legitimate
   zero-message turns (if any — `attachment_ids_sync` is worth checking first).
4. Delete the characterization test as part of the fix and say so in its place.
5. If unreachable ⇒ say so in the code, and consider whether `action_ask_story_step`'s
   silent `return []` should log at error instead.

## Related

- D-08 / T3-02 p1 — the chain-level terminal `else` (`tests/orchestrator/test_unknown_state_fallback.py`)
- D-13 / T3-01 — the reachability-guess precedent
- `state_machine.py:1629` — the in-file "re-show choices so we never return empty messages"
  convention this path fails to honour
