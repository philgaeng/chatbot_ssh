# Phase 3e follow-up — the per-package Cast matrix SCREEN (§3.6)

> Logged per the repo deferral rule. **The enforcement backend and the two review-flagged UI
> changes are DONE and shipped**; what remains is the dedicated authoring *screen*.

## What IS done (Phase 3, committed + green)

- **Backend enforcement (tested, `test_cast_staffing.py`):** synthetic per-step-tier keys
  (`services/cast_staffing.py`), the staffing endpoints `POST/GET/DELETE /projects/{id}/cast`
  (`routers/cast.py`) writing `officer_scopes` via `create_scope_row`, the §3.3 self-escalation
  guard, and per-package auto-assign (two contractors, same tier, different packages → correct
  routing). An admin can staff a package **end-to-end via the API today.**
- **Step editor → tier toggles** (`StepCast`/`StepForm`): the surface the review flagged.
- **Operational Roles tab removed** (frontend).

## What remains (deferred)

1. **The §3.6 Cast matrix screen** — Project → Cast, with the two-level model (Project-wide +
   per-package tabs), inheritance ("from project-wide: X" greyed) + per-package Override, the
   officer picker (search by name/email/title, inline "Add officer" with inline position-add),
   derived territory, and "Copy from package …". This is net-new UI over the **working, tested**
   endpoints above. Slot it into `ProjectEditor.tsx` near the existing Packages / `ProjectStaffingSection`.
   - Add the `lib/api.ts` client methods first: `staffCastSlot` (POST), `readCast` (GET),
     `unstaffCastSlot` (DELETE), + a `CastScope` type mirroring `CastScopeOut`.
2. **Seed refresh (§8)** — optional/fidelity only: the demo seeds (`kl_road_standard.py`,
   `kl_road_seah.py`, `mock_tickets.py`) still use **named** role keys, which **coexist** with
   synthetic keys (§6) and keep both demo scenarios working unchanged. Refreshing them to the
   synthetic-key + staffing model is a fidelity improvement, not a correctness requirement, and
   retires the last `position_type.default_role_key` fallback (see phase2 note).

## TODO
See `docs/TODO.md` → "Cast-model follow-ups".
