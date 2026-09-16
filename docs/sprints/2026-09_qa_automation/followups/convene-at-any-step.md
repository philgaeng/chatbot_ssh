# `GRM-126` — the server convenes a GRC hearing at any step

**Found 2026-09-15** while fixing `GRM-084`. Logged here and in [`SPINE.md`](../../../SPINE.md) per the
standing deferral rule. **Kind:** `bug` — read in the code and shown by an existing test, not driven
in a browser.

## What is true today

`POST /api/v1/tickets/{id}/actions` with `GRC_CONVENE` checks two things: that the caller is the
assigned officer or an admin, and that the case is not `ESCALATED`. **Nothing checks the step.** The
handler (`ticketing/engine/ticket_actions.py`, `grc_convene`) moves the case to
`GRC_HEARING_SCHEDULED` and notifies every GRC member of the project, wherever the case sits.

So the L1 officer holding a case can call the API directly and "convene the GRC" on it: its status
changes, and the GRC members are notified of a hearing for a case that never reached them. The
existing unit test `test_grc_convene_schedules_hearing` does exactly this, on a ticket at the
workflow's first step, and it passes.

The officer UI offers the control only at the step keyed `LEVEL_3_GRC`, so nobody reaches this by
clicking. It is reachable by anyone with the API and a case assigned to them.

## Why it was not fixed with `GRM-084`

`GRM-084` was the UI gate: the GRC chair could not see the control. It is fixed by matching the UI to
the server's rule, which is the assigned officer or an admin.

This one needs a decision. **How does the server know a step is a GRC step?** The only marker today is
the step key `LEVEL_3_GRC`. The UI hard-codes it, and so does the demo seed. Workflows are
configurable, though, and a second ministry's GRC step need not carry that key. There are three
options:

1. **Refuse `GRC_CONVENE` unless `step_key == "LEVEL_3_GRC"`.** One line. It matches the UI, and it
   encodes a seed convention as a rule.
2. **Add a step property** (for example `holds_grc_hearing`). The workflow editor sets it, and the UI
   and server both read it. This is a migration plus an editor control.
3. **Derive it from the step's cast.** A step with an `informed` GRC-member slot is a GRC step. There is
   no schema change, but the rule is implicit.

⭐ **Recommended: (1) now, (2) when a workflow without that key needs a hearing.** (1) closes the gap
at the same boundary the UI already draws. (2) is the honest long-term shape, but it has no second
user yet.

## Verification owed

A test at the API level: `GRC_CONVENE` on a case at a non-GRC step returns `422` and changes nothing.
The existing unit test must move its ticket to the GRC step.
