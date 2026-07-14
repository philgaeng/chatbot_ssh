# Follow-up — remove pre-existing dead imports/locals in `routers/tickets.py`

> **Status:** open (unstarted) · **Owner:** backend · **Priority:** low (lint-only; no runtime effect)
> **Origin:** H2-02 Pass 3 (`docs/sprints/2026-08_tier2_quality/PROGRESS.md` deviation, 2026-07-14). Surfaced by a pyflakes pass while extracting `perform_action` into `engine/ticket_actions.py`. All five items were **already present at HEAD** before Pass 3 — left untouched to keep the extraction diff surgical.

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

- [ ] Drop the four unused imports (keep `_ensure_viewer`).
- [ ] Either consume `rerouted` (e.g. surface it in the response / an event note) or drop the assignment — decide which is intended; it reads like a dropped feature, so check `maybe_reroute_ticket_workflow`'s contract before deleting.
- [ ] `pyflakes ticketing/api/routers/tickets.py` clean; full `tests/ticketing` suite green unchanged.
- [ ] Fold into the Pass 4 `routers/tickets/` package split if that lands first (the import block gets rewritten there anyway).
