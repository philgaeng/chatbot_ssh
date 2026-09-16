# Phase 2 (positions-as-titles) — deferrals / sequencing notes

> Logged same-commit per the repo deferral rule. Both are small and bounded; neither is a
> design change (DESIGN-cast-model §3.2 is fully honoured — a title carries no role/tier).

## 1. Owning-level (`owner_organization_id`) re-scope is now API-only

The position-type modal dropped the "Owning level" picker (spec §3.2 modal table: *remove
from modal; advanced re-scope only, on edit*). Owner is server-stamped from the author's
scope (`catalog_owner_for`). The backend `PositionTypeUpdate` still accepts
`owner_organization_id`, so re-scoping an existing catalogue item is possible via the API but
has **no UI**. Build a small "advanced" affordance on edit if admins need to re-home a title.

## 2. `assign_officer_position` default-role fallback retirement

Assign now **requires an explicit `role_key`** when the position has no default role (the new
normal). A legacy position with a **non-null** `default_role_key` (only the seeded DoR rows
today) still pre-fills for back-compat. That fallback goes fully dead once the seed drops
position defaults (spec §8, done in Phase 3's seed refresh) — at which point the
`role_key = body.role_key or pt.default_role_key` line can drop its second operand entirely.

## TODO
See `docs/TODO.md` → "Cast-model follow-ups".
