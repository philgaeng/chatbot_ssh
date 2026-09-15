# `GRM-127` — AI case findings are gated on role keys the cast model does not issue

**Found 2026-09-15** while fixing `GRM-084`, which is the same defect on a different control. Logged here
and in [`SPINE.md`](../../../SPINE.md) per the standing deferral rule. **Kind:** `deviation` — read in
the code, not driven in a browser.

## What is true today

Both halves use the same fixed list of legacy role keys: `grc_chair`, the `adb_*` observers,
`super_admin` and `local_admin`.

- The *AI findings* card on the ticket page (`app/tickets/[id]/page.tsx`, `FINDINGS_ROLES`) renders
  only for those keys.
- `POST /api/v1/tickets/{id}/findings` (`ticketing/api/routers/tickets/summary.py`) refuses everyone
  else with `403`, admins apart.

The cast model issues workflow-slot keys instead. The seeded GRC chair holds only
`wf:KL_ROAD_STANDARD:LEVEL_3_GRC:actor`, and `local_admin` was retired. As far as the seeded roster
shows, **only the super admin can see or regenerate findings**. That includes the GRC chair: the
officer the card was written for, the one who holds the case at the hearing.

⚠ **Not measured:** whether any deployed officer still holds an `adb_*` key. The e2e roster holds none.

## Why it was not fixed with `GRM-084`

`GRM-084` had a rule to match: the server already allowed the assigned officer to convene, and only
the UI was wrong. Here **the server and the UI agree, and both use the legacy list.** Fixing it means
deciding, in the cast model's terms, who may read an LLM-generated synthesis of a whole case. That
decision needs a better reason than "the old list said so":

- **the case's supervisor and above** (the step's `supervisor` slot, then the escalation chain);
- **the step's actor** (the GRC chair at L3, whoever holds the case elsewhere);
- **observers** (the ADB roles map to `observer` slots now).

⚠ **Privacy, not just access.** The findings are a summary of the whole case, which is exactly what
the client's managers were refused in the Excel (`resolution-reporting`). Widening who reads them
deserves the same care. It should not be granted by a role-key rename.

## Verification owed

After the decision, a test that pins who gets `202` and who gets `403` on the endpoint, plus the card
shown to the same set in a browser.
