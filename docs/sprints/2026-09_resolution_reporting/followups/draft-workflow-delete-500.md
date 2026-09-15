# `GRM-124` — removing a draft workflow that has steps is a 500

**Found 2026-09-15**, while building `GRM-122`'s end-to-end check. Logged here and in
[`SPINE.md`](../../../SPINE.md) per the standing deferral rule.
**Kind:** `bug` — *Settings → Workflows* offers **Remove** on every draft (`WorkflowsTab.tsx`,
`handleRemoveWorkflow` → `DELETE /api/v1/workflows/{id}`), and for a draft with steps it fails.

## Reproduction — measured on the local stack

1. Clone any workflow that has steps (e.g. `KL_ROAD_STANDARD`) into a draft.
2. *Remove* it, or `DELETE /api/v1/workflows/{id}`.
3. **HTTP 500.** `ticketing_api` logs: `psycopg2.errors.NotNullViolation: null value in column
   "workflow_id" of relation "workflow_steps" violates not-null constraint`.

A draft with **no** steps deletes (204) — which is why nothing caught it: the only callers that
delete workflows in tests create step-less ones or clean up with raw SQL.

## Cause (read, not yet fixed)

`delete_workflow` in `ticketing/api/routers/workflows.py` calls `db.delete(wf)`. The
`WorkflowDefinition.steps` relationship has no `cascade="all, delete-orphan"`, so SQLAlchemy
de-associates the steps by setting their `workflow_id` to NULL — which the column forbids.

## Why not fixed in `GRM-122`

A fix decides what else a deleted draft takes with it — its steps, the per-slot roles
(`wf:<KEY>:<STEP>:<tier>`) minted for them, and staffing rows pointing at those roles
(`test_cast_staffing.py` cleans all three by hand). That is a decision about the role catalog, not a
one-line cascade, and it does not belong inside an ownership item.

## What it costs meanwhile

- An admin cannot remove a draft it cloned; it can only be left in the list.
- `GRM-122`'s e2e cannot drive the refused move, which needs a workflow carrying actions — today only
  a clone of a seeded workflow, which has steps and so cannot be cleaned up.

## Definition of done

1. `DELETE` on a draft with steps succeeds and removes its steps; what happens to its minted slot roles
   and any staffing on them is decided and written into `12_workflows_configuration.md`.
2. A failing test first: clone `KL_ROAD_STANDARD` to a draft, delete it, expect 204 and no rows left.
3. `settings-workflow-organization.spec.ts` gains the refused move.
