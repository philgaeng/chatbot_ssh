# `GRM-116` — every case resolves from the same five outcomes, whatever its workflow

**Origin:** user request (client, 2026-09-15) · **Lane:** `resolution-reporting` · **Reported:** 2026-09-15
**Design:** [`DESIGN-resolution-reporting.md`](DESIGN-resolution-reporting.md) §2, §3.1 (incl. §3.1.1–§3.1.3), §3.3, §4, §5, §6

> **Revised 2026-09-15, before any build**, by the owner's answers to Q-06 and Q-07: a SEAH case
> records no action (was: a SEAH list), and actions live in one org-scoped catalog that workflows
> select from (was: a list copied onto each workflow). Size M → L.
>
> **Revised again 2026-09-15 — Q-10, the owner's review of the authoring wireframe.** Five changes land
> here because this item owns the tables and the service: **no global actions** (seeded actions belong
> to the ministry); **every workflow and template gets an organization** in the migration; a local
> action **counts as** a shared one (`counts_as_code`, replacing `replaced_by_code`); **at most 8
> actions per workflow**; a new workflow starts **empty** and cannot be published until it has one.
> DESIGN §3.1.1 is the model.
>
> ⚠ **An implementation of the previous version exists, uncommitted, in the working tree** (measured
> 2026-09-15: `b3d5f7h9_resolution_actions.py` applied to the dev DB, `resolution_catalog.py`,
> `test_resolution_catalog.py`, and the UI/report changes). Nothing is committed or deployed, so the
> rework edits that migration **in place** and re-runs it on dev (downgrade, upgrade) — no second
> migration. The checklist is under *Rework of the in-progress build*.

## Kind

**`feature`** — question 1: no live spec claims per-workflow resolution actions.
[`08`](../../ticketing_system/08_ticket_resolution_and_case_summary.md) §2.2 specifies the single list.

## Profile

| ✓ | Question | Fires |
|---|---|---|
| ✔ | Changes user-visible behaviour | `G-PRODUCT` · `G-SPEC` · `G-VERIFY` |
| ✔ | A UI surface changes shape | `G-DESIGN` — the resolve form's list source, its label, and a text-only variant for sensitive workflows; DESIGN §4 |
| ✔ | Schema changes | `G-DATA` — `resolution_actions`, `workflow_resolution_actions`; **a data change to `workflow_definitions.owner_organization_id`** (every workflow and template gets an organization) |
| ✔ | PII · auth · SEAH · complainant channel · new egress | `G-SENSITIVE` — what a SEAH case records; org-scoped availability across ministries; the complainant closure page |
| ✔ | API or event shape changes | `G-CONTRACT` — ticket detail gains `resolution_options`; payload gains `resolution_category_label`; `RESOLVE` validation narrows |
| ✔ | Deployed | `G-RELEASE` |
| ■ | always | `G-TEST` |

> **profile:** `UI feature` +DATA +CONTRACT **+SENSITIVE** · **gates:** PRODUCT · DESIGN · DATA · SENSITIVE · CONTRACT · SPEC · TEST · VERIFY · RELEASE
> **model:** Opus · **size:** L

## Blocked by

**Nothing.** Q-08 answered 2026-09-15 (the org-scoped ownership rule, DESIGN §3.1.1); Q-06 answered
(the road-works five are the starting set, there is no SEAH list). Q-09 answered: **no** read-only
panel here — `GRM-119` builds the editable one next.

## The change

1. **Models + migration** (ticketing stream) — `ResolutionAction` and `WorkflowResolutionAction`,
   exactly as DESIGN §3.3: `owner_organization_id` **`NOT NULL`**, `ON DELETE RESTRICT` (not the
   `SET NULL` `workflow_definitions` uses — DESIGN §3.3 says why), and **`counts_as_code`** (self-FK,
   nullable) in place of `replaced_by_code`. `is_active` stays; no screen sets it in this lane.
2. **Organizations for workflows and templates, in the migration, before the seed** — DESIGN §3.1.1
   *Where a workflow's organization comes from*:
   - for each workflow and template with no owner: the **ministry** (top organization) above the
     implementing agency of every project that uses it (`project_workflows` → `projects.implementing_agency_org_id` → walk `parent_organization_id` to the top);
   - used by no project → the one ministry that implements projects, **if there is exactly one**;
   - used by projects of two ministries, or unused when several ministries implement projects →
     **raise, naming the workflow**. A guess would hand one ministry's workflow to another.
   - Workflows that already have an owner are left alone.
   ⚠ **Measured on the dev DB:** `KL_ROAD_STANDARD`, `KL_ROAD_SEAH` and the draft `sampple2` have no
   owner; both projects using them are implemented by `DOR` → all three become DOR's.
3. **Seed, in the migration:** the general five (codes and wording unchanged) and the road-works five,
   **owned by that ministry**, `counts_as_code = NULL` (shared). On a database with no ministry found
   (empty, fresh) the migration seeds nothing — `kl_road_standard.py` creates them under DOR. Then
   backfill selections per DESIGN §3.1.2: sensitive → none; road-hazard-bound → road works; otherwise
   (templates included) → general. **Downgrade** drops both tables and **leaves the workflow owners it
   set** — an owned workflow works with the previous release; say both in the rollback note.
4. **One service, `ticketing/services/resolution_catalog.py`,** is the only writer of selections:
   - `available_to_workflow(db, action, workflow) -> bool` — **the action's owner is the workflow's
     organization or above it**. A workflow with **no** organization can use nothing. (Not
     `apply_catalog_scope` in `admin_access.py`: that filters by the *user's* scope; this test's
     target is the *workflow's owner*.)
   - `set_workflow_actions(db, workflow, codes)` — refuses: an unknown or inactive code; an action not
     available to the workflow; **any** code on a sensitive workflow; **more than
     `MAX_RESOLUTION_ACTIONS = 8`** (in `ticketing/constants/resolution.py`); an **empty** list on a
     non-sensitive workflow that is **published**. Empty is allowed on a draft or a template — a new
     one starts that way — and publishing it is refused (step 5).
   - `options_for_ticket(db, ticket)` — the workflow's active selections in `sort_order`.
   - `action_label(db, code)` — for events written before this lane.
5. **Publishing.** `POST /workflows/{id}/publish` refuses a non-sensitive workflow with no active
   action: *"Add at least one resolution action before publishing."* Only a published workflow can be
   bound to a project (`validate_workflow_binding` in `services/project_workflows.py`, verified
   2026-09-15), and step 4 keeps a published one from being emptied — so a case never meets an empty
   non-sensitive list, and the empty list stays the UI's signal for a sensitive workflow (DESIGN §5).
6. **Templates, clone, create.**
   - **Templates get an organization like workflows do**: `create_workflow` stops stamping `NULL` on
     templates and uses `catalog_owner_for`, as for workflows. (A platform admin choosing the
     organization is `GRM-122`; until then a platform admin's new workflow or template has none, so it
     can use no action and cannot be published — build `GRM-122` next.)
   - `BUILT_IN_TEMPLATES` in [`routers/workflows.py`](../../../ticketing/api/routers/workflows.py)
     carry **no** list: they belong to no organization, so they cannot name one's actions.
   - Clone and create-from-template (a template in the database) **copy** the source's list through
     `set_workflow_actions`, so a copy into another organization is re-checked. From a built-in
     template or from scratch → **empty**. A list is never inherited (DESIGN §3.1.1).
   - Seeds `kl_road_standard.py` / `kl_road_seah.py` create DOR-owned workflows and go through the
     same service.
7. **Organization delete.** `GET /organizations/{id}/delete-impact` counts owned resolution actions,
   and delete refuses while any exist — the FK would refuse anyway; the impact screen must say why.
   It also counts owned workflows and templates: their FK is `SET NULL`, and a workflow left with no
   organization can use no action (the delete rule for workflows is `GRM-120`'s to decide).
8. **Ticket detail** (`GET /tickets/{id}`) returns `resolution_options` from `options_for_ticket` —
   empty for a sensitive workflow. No officer gains read on `GET /workflows/{id}`.
9. **`RESOLVE`** (and the `resolution_backfilled` path) — DESIGN §5: category required and a member
   when options are non-empty; **refused when empty**. Both events' payloads gain
   `resolution_category_label` when a category is recorded.
10. **Readers prefer the snapshot**, then `action_label(code)`: `report_rows.py`, `report_summary.py`,
   `resolved_summary_builder.py`, `lib/mobile-constants.ts`. Delete `RESOLUTION_CATEGORIES` from
   [`ticketing/constants/resolution.py`](../../../ticketing/constants/resolution.py) once nothing reads
   it — the seed data lives in the migration and the catalog, not in a third place.
11. **Complainant closure page + PDF** (`closure_pdf.py`, `app/closure/[token]/page.tsx`,
   `ClosureSummaryBody.tsx`): omit the outcome line when the label is empty.
12. **UI** — [`ResolutionSheet.tsx`](../../../channels/ticketing-ui/components/ResolutionSheet.tsx):
    options from the ticket; label **What was done**; default selection `ACCEPTED_OTHER` when present,
    else the first option; **no options → the text-only form** (DESIGN §4). Delete the hard-coded list
    in [`lib/resolution.ts`](../../../channels/ticketing-ui/lib/resolution.ts); keep
    `isResolutionRecordEvent` and `RESOLUTION_MIN_NOTE_LEN`.
13. **State contract:** DESIGN §4 rows *case in a sensitive workflow* and *case moved to another
    workflow*.


## Rework of the in-progress build (Q-10)

Measured against the uncommitted implementation 2026-09-15. Edit in place; on dev run the ticketing
stream `downgrade -1` then `upgrade head` through Docker (`docs/deployment/DOCKER.md`).

- [ ] `b3d5f7h9_resolution_actions.py` — `owner_organization_id NOT NULL`; `counts_as_code` replaces `replaced_by_code`; the workflow/template owner backfill (step 2) **before** the seed; seed owned by the ministry found, nothing on an empty DB; downgrade note (step 3)
- [ ] `models/resolution_action.py` — same two columns
- [ ] `services/resolution_catalog.py` — availability without `NULL` owners; `MAX_RESOLUTION_ACTIONS`; empty refused only when published; **`default_codes_for` removed** (a new workflow starts empty)
- [ ] `constants/resolution.py` — `MAX_RESOLUTION_ACTIONS = 8`
- [ ] `routers/workflows.py` — templates get `catalog_owner_for`; built-in templates carry no list; publish gate (step 5)
- [ ] `seed/kl_road_standard.py`, `seed/kl_road_seah.py` — DOR-owned workflows and actions
- [ ] `routers/locations.py` delete-impact — also counts owned workflows and templates
- [ ] `tests/ticketing/test_resolution_catalog.py` — the G-TEST list below replaces the global cases
- [ ] live specs the build already edited (`04`, `08`, `11`, `12`) — re-read against DESIGN §3.1.1: **no global actions, every workflow and template owned, 8 max, copied not inherited**

## Files it may touch

- `ticketing/models/resolution_action.py` *(new)* · `ticketing/models/__init__.py` · `ticketing/migrations/versions/<new>.py`
- `ticketing/services/resolution_catalog.py` *(new)* · `ticketing/constants/resolution.py`
- `ticketing/api/routers/workflows.py` (templates owned, built-in templates without a list, publish gate) · `ticketing/api/routers/locations.py` (delete-impact) · `ticketing/api/schemas/ticket.py` · `ticketing/api/routers/tickets/crud.py`
- `ticketing/engine/ticket_actions.py`
- `ticketing/services/report_rows.py` · `report_summary.py` · `resolved_summary_builder.py` · `closure_pdf.py`
- `ticketing/seed/kl_road_standard.py` · `ticketing/seed/kl_road_seah.py`
- `channels/ticketing-ui/components/ResolutionSheet.tsx` · `components/ClosureSummaryBody.tsx` · `lib/resolution.ts` · `lib/mobile-constants.ts` · `lib/api.ts` · `lib/useTicketThread.ts` · `app/tickets/[id]/page.tsx` · `app/m/tickets/[id]/page.tsx` · `app/closure/[token]/page.tsx`
- Specs (G-SPEC, same PR): `08` §2.2 · §2.3 · §2.5 · §2.6 · §3.9 · `12` (new section *Resolution actions*: ownership, 8 max, copied not inherited, the publish gate; templates now owned) · `04` (two tables) · `11` §3.3 (fifth catalog item — **the one kind with no global items**)

## Gates — evidence

- **G-DATA** — replays from empty (no ministry → no seed, no error); backfill verified on a DB holding a
  SEAH workflow, a road-hazard-bound workflow, a plain one and a template (selections: none · road ·
  general · general), all of them ending **owned by the projects' ministry**; the migration **raises,
  naming the workflow**, for one used by two ministries' projects and for an unused one with two
  implementing ministries; a workflow that already had an owner keeps it. FKs only within
  `ticketing.*`; no PII.
- **G-CONTRACT** — additive for ticket detail and event payload; **narrowing** for `RESOLVE`, twice
  (a code outside the selection; any code on a SEAH case). Both stated in `08` §2.5, and the UI change
  ships in the same release.
- **G-SENSITIVE** — DESIGN §6 checks 3, 5, 6.
- **G-TEST** —
  - unit, availability (mirroring doc 11 §3d): Jhapa-owned action → not usable by an Ilam or a DOR workflow; DOR-owned → usable by a Jhapa workflow, not by another ministry's; **a workflow with no organization can use nothing**; creating an action with no owner is refused
  - unit, `set_workflow_actions`: refuses on a sensitive workflow; refuses a 9th action (8 accepted); refuses empty on a **published** non-sensitive workflow, accepts it on a draft and a template; refuses an inactive code
  - integration: publish refuses a non-sensitive workflow with no action; a SEAH workflow publishes with none
  - integration: create from a built-in template or from scratch → empty; create from a database template or clone → its list copied; a later change to the source does not reach the copy; templates created by an `org_admin` are owned by its organization
  - unit: each backfill rule; `action_label` finds historical general codes; snapshot preferred over lookup
  - integration: `RESOLVE` on a general case accepts `ACCEPTED_OTHER`, refuses `ROAD_REPAIRED`; on a SEAH case accepts a note alone and refuses any category (422)
  - integration: clone of a workflow into an organization that cannot use one of its actions is refused
  - integration: a case re-classified into another workflow gets that workflow's options in ticket detail
  - integration: deleting an org that owns an action is refused, and delete-impact reports it
  - existing `test_ticket_actions_unit.py`, `test_escalation_engine.py`, `test_closure_publishable.py` stay green
- **G-VERIFY** — e2e: resolve a general case (sees the general five) and a SEAH case (sees text only);
  the SEAH closure page shows no outcome line. Extend `e2e/smoke/closure.spec.ts`.

## Non-goals

The resolution panel in Settings (`GRM-119`); the similarity check (`GRM-121`); choosing and changing
a workflow's organization in Settings (`GRM-122`); national grouping in reports (`GRM-118`). Re-homing
position types, roles and project types (`GRM-120`). Rewriting historical SEAH labels. Any change to the note length rule or
the photo requirement.

## Register line

```
| `GRM-116` — every case resolves from the same five outcomes, whatever its workflow | feature | ui-feature+DATA+CONTRACT+SENSITIVE | `ready` | L | resolution-reporting | … |
```
