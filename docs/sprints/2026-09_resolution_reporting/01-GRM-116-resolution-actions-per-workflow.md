# `GRM-116` — every case resolves from the same five outcomes, whatever its workflow

**Origin:** user request (client, 2026-09-15) · **Lane:** `resolution-reporting` · **Reported:** 2026-09-15
**Design:** [`DESIGN-resolution-reporting.md`](DESIGN-resolution-reporting.md) §2, §3.1, §3.3, §4, §5, §6

## Kind

**`feature`** — question 1: no live spec claims per-workflow resolution lists.
[`08`](../../ticketing_system/08_ticket_resolution_and_case_summary.md) §2.2 specifies the single list.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✔ | A UI surface changes shape | `G-DESIGN` — the resolve form's list source and label; wireframe in DESIGN §4 |
| ✔ | Schema changes | `G-DATA` — `workflow_definitions.resolution_options` |
| ✔ | PII · auth · SEAH · complainant channel · new egress | `G-SENSITIVE` — a SEAH list; SEAH wording reaches the complainant closure page |
| ✔ | API or event shape changes | `G-CONTRACT` — ticket detail gains `resolution_options`; event payload gains `resolution_category_label`; validation narrows |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` +DATA +CONTRACT **+SENSITIVE** · **gates:** PRODUCT · DESIGN · DATA · SENSITIVE · CONTRACT · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** M

## Blocked by

**Nothing to start.** ⏳ **Merge waits on Q-06** — the road-works and SEAH lists confirmed by the
client, the SEAH list reviewed by a SEAH officer.

## The change

1. **`STARTER_RESOLUTION_LISTS`** in [`ticketing/constants/resolution.py`](../../../ticketing/constants/resolution.py):
   `general` (today's five, codes and wording unchanged), `road_works`, `seah` — DESIGN §3.1.
   `RESOLUTION_CATEGORIES` becomes the `general` list; `resolution_category_label()` keeps working
   for historical codes by searching all starter lists.
2. **Migration** (ticketing stream): add `workflow_definitions.resolution_options` JSON NOT NULL.
   Backfill, in order of precedence:
   - `lower(workflow_type) = 'seah'` → `seah`
   - bound on any project with `intake_route = 'road_hazard_grievance'` → `road_works`
   - otherwise → `general`

   Templates (`is_template`) are backfilled by the same rule. Downgrade drops the column — **it
   restores nothing a list edit changed**, so say so in the rollback note.
3. **Templates and clone.** `BUILT_IN_TEMPLATES` in
   [`routers/workflows.py`](../../../ticketing/api/routers/workflows.py) carry their starter list
   (`default_grm` → `general`, `default_seah` → `seah`). Clone and create-from-template copy the list.
   Seeds (`kl_road_standard.py`, `kl_road_seah.py`) set it explicitly.
4. **Ticket detail** (`GET /tickets/{id}`) returns `resolution_options` from the case's
   `current_workflow_id` — DESIGN §5. No officer gains read on `GET /workflows/{id}`.
5. **`RESOLVE`** validates `resolution_category` against that list (422 otherwise), and both events'
   payloads gain `resolution_category_label` (snapshot). Same for the backfill path
   (`resolution_backfilled`).
6. **Readers prefer the snapshot**, falling back to `resolution_category_label(code)`:
   `report_rows.py`, `report_summary.py`, `resolved_summary_builder.py`, `lib/mobile-constants.ts`.
7. **UI:** [`ResolutionSheet.tsx`](../../../channels/ticketing-ui/components/ResolutionSheet.tsx) renders
   the options from the ticket; label **What was done**; default selection = the list's first entry
   *unless* it contains `ACCEPTED_OTHER` (today's default, kept for the general list). The
   hard-coded list in [`lib/resolution.ts`](../../../channels/ticketing-ui/lib/resolution.ts) is
   **deleted** — the drift source goes, not just its use. Keep `isResolutionRecordEvent` and
   `RESOLUTION_MIN_NOTE_LEN`.
8. **State contract:** the "case moved to another workflow" 422 row of DESIGN §4.

## Files it may touch

- `ticketing/constants/resolution.py` · `ticketing/models/workflow.py` · `ticketing/migrations/versions/<new>.py`
- `ticketing/api/routers/workflows.py` · `ticketing/api/schemas/workflow*.py` · `ticketing/api/schemas/ticket.py` · `ticketing/api/routers/tickets/crud.py`
- `ticketing/engine/ticket_actions.py`
- `ticketing/services/report_rows.py` · `report_summary.py` · `resolved_summary_builder.py`
- `ticketing/seed/kl_road_standard.py` · `ticketing/seed/kl_road_seah.py`
- `channels/ticketing-ui/components/ResolutionSheet.tsx` · `lib/resolution.ts` · `lib/mobile-constants.ts` · `lib/api.ts` · `lib/useTicketThread.ts` · `app/tickets/[id]/page.tsx` · `app/m/tickets/[id]/page.tsx`
- Specs (G-SPEC, same PR): `08` §2.2 · §2.3 · §2.5 · §2.6 · `12` (new section *Resolution actions*) · `04` (`workflow_definitions`)

## Gates — evidence

- **G-DATA** — migration replays from empty; backfill verified on a DB holding a SEAH workflow, a
  road-hazard-bound workflow and a plain one (three rows, three lists). No FK, no PII.
- **G-CONTRACT** — compatibility: additive for ticket detail and event payload; **narrowing** for
  `RESOLVE` validation (a general code on a SEAH case is refused — intended). Stated in `08` §2.5.
- **G-SENSITIVE** — DESIGN §6 checks 3 and 5. ⚠ The SEAH action label **already** reaches the
  complainant closure page and PDF (`resolution_category_label`); the reviewer confirms each SEAH
  label is fit for the complainant to read.
- **G-TEST** —
  - unit: each backfill rule; label lookup finds historical general codes; snapshot preferred over lookup
  - integration: `RESOLVE` on a SEAH-workflow case accepts `SEAH_REFERRED_SUPPORT`, refuses `ACCEPTED_OTHER` (422); on a general case, the reverse
  - integration: a case re-classified into another workflow gets that workflow's list in ticket detail
  - existing `test_ticket_actions_unit.py`, `test_escalation_engine.py`, `test_closure_publishable.py` stay green
- **G-VERIFY** — e2e: resolve a general case and a SEAH case in the browser; each form shows its own
  list; the thread bubble shows the chosen label. Extend `e2e/smoke/closure.spec.ts`.

## Non-goals

A Settings editor for the lists (`GRM-119`). Grouping across workflows (Q-07). Any change to the note
length rule or the photo requirement.

## Register line

```
| `GRM-116` — every case resolves from the same five outcomes, whatever its workflow | feature | UI feature +DATA +CONTRACT +SENSITIVE | `ready` | M | resolution-reporting | … |
```
