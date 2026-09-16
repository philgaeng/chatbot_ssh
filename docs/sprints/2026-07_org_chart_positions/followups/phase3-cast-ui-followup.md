# Phase 3e follow-up — the per-package Cast matrix SCREEN (§3.6)

> **UPDATE 2026-07-23: the Cast matrix screen is now BUILT** — `ProjectCastSection.tsx`, mounted
> in the Project editor (Projects & packages) between Packages and the legacy staffing roster.
> Package tabs (Project-wide + each package) × steps × enabled tiers, assign/remove officers per
> slot via `staffCastSlot`/`unstaffCastSlot`, project-wide rows shown greyed/inherited on a
> package tab, SEAH workflow selectable via the workflow dropdown. What remains below are §3.6
> *niceties*, not blockers.

## What IS done (Phase 3, committed + green)

- **Backend enforcement (tested, `test_cast_staffing.py`):** synthetic per-step-tier keys
  (`services/cast_staffing.py`), the staffing endpoints `POST/GET/DELETE /projects/{id}/cast`
  (`routers/cast.py`) writing `officer_scopes` via `create_scope_row`, the §3.3 self-escalation
  guard, and per-package auto-assign (two contractors, same tier, different packages → correct
  routing). An admin can staff a package **end-to-end via the API today.**
- **Step editor → tier toggles** (`StepCast`/`StepForm`): the surface the review flagged.
- **Operational Roles tab removed** (frontend).

## What remains (§3.6 niceties — the core screen is built)

1. **Cast screen niceties** — the built `ProjectCastSection` covers the two-level model +
   assign/remove. Still to add: **"Copy from package …"** (pre-fill a package from a sibling),
   an explicit **Override / clear-to-revert** affordance per cell (today a package tab simply
   shows inherited rows greyed + lets you add package rows), **inline "Add officer"** (email +
   invite + inline position-add) in the picker (today it reuses the existing roster; new officers
   are invited under Organizations & officers), and a **derived-territory / org picker** (today
   `organization_id` is the project's implementing agency; a contractor-specific employer org
   would need a picker).
2. **Seed refresh (§8)** — optional/fidelity only: the demo seeds (`kl_road_standard.py`,
   `kl_road_seah.py`, `mock_tickets.py`) still use **named** role keys, which **coexist** with
   synthetic keys (§6) and keep both demo scenarios working unchanged. Refreshing them to the
   synthetic-key + staffing model is a fidelity improvement, not a correctness requirement, and
   retires the last `position_type.default_role_key` fallback (see phase2 note).

## TODO
See `docs/TODO.md` → "Cast-model follow-ups".
