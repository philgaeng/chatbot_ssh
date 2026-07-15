# Follow-up — remove pre-existing dead imports/locals in `routers/tickets.py`

> **Status:** ✅ RESOLVED in H2-02 Pass 4 (2026-07-14) · **Owner:** backend · **Priority:** low (lint-only; no runtime effect)
> **Origin:** H2-02 Pass 3 (`docs/sprints/2026-08_tier2_quality/PROGRESS.md` deviation, 2026-07-14). Surfaced by a pyflakes pass while extracting `perform_action` into `engine/ticket_actions.py`. All five items were **already present at HEAD** before Pass 3 — left untouched to keep the extraction diff surgical.
>
> **Resolution:** Folded into the Pass 4 `routers/tickets/` package split as planned. The single-file import block was partitioned per submodule, importing only what each uses — so the 4 dead imports were never carried across. The `rerouted` binding was dropped (the `maybe_reroute_ticket_workflow` call is kept for its side effect; its bool return has no response field). `pyflakes` is clean on all new modules; full `tests/ticketing` suite green unchanged (408 passed / 5 skipped). The old `routers/tickets.py` no longer exists.

## The gap

`pyflakes ticketing/api/routers/tickets.py` reports five dead items unrelated to the action extraction:

| Line (at Pass 3) | Item | Kind |
|---|---|---|
| import | `ticketing.engine.escalation._apply_step_tier_roles` | unused import (`_ensure_viewer` on the same line **is** used) |
| import | `ticketing.engine.workflow_engine.auto_assign_for_workflow_step` | unused import |
| import | `ticketing.engine.workflow_engine._scope_candidates` | unused import |
| import | `ticketing.models.country.Location` | unused import |
| `validate_ticket_classification` | `rerouted` local | assigned but never read |

Confirmed pre-existing: `git show HEAD:ticketing/api/routers/tickets.py | python -m pyflakes` reports the same five.

## Definition of done

- [x] Drop the four unused imports (keep `_ensure_viewer`). — none carried into the split modules; `_ensure_viewer` lives in `collaboration.py`.
- [x] Either consume `rerouted` or drop the assignment — **dropped** the binding (`crud.py` `validate_ticket_classification`); the `maybe_reroute_ticket_workflow` call (side-effecting) is preserved. Contract confirmed `-> bool` with no response field to surface it.
- [x] `pyflakes` clean on every new `routers/tickets/*.py` module; full `tests/ticketing` suite green unchanged (408 passed / 5 skipped).
- [x] Folded into the Pass 4 `routers/tickets/` package split (the import block was rewritten there).
