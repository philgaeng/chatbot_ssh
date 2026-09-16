# `GRM-129` — staging has two "Project Directorate (ADB)" organizations, and one was a second ministry

**Found 2026-09-15** while deploying `resolution-reporting` to staging (`GRM-128`). Logged here and in
[`SPINE.md`](../../../SPINE.md) per the standing deferral rule. **Kind:** `debt`, in staging data and
not in code.

## What was true

| Id | Name | Parent | Created |
|---|---|---|---|
| `NP_PDA` | Project Directorate (ADB) | **none: a top-level organization** | 2026-06-12 |
| `NP_PDA_2` | Project Directorate (ADB) | `DOR` | 2026-09-07 |

`NP_PDA` implements the Kakarbhitta–Laukahi highway project. As a root, it read to migration
`b3d5f7h9` as **a second ministry beside DOR**, so the migration could not pick an owner for
`KL_ROAD_STANDARD` or `KL_ROAD_SEAH`, and it would have seeded no resolution actions. `aws-deploy`
starts containers before migrating, so the deploy would have left staging on new code with the old
schema.

## What was done

With the owner's decision (2026-09-15), `NP_PDA` was moved under `DOR` through the organizations
update handler, which checks for cycles and carries the category over; its category stayed
`government`. The migration was simulated against staging's data first, then again after the move, and
ran cleanly in the deploy.

## What is left

- **Two organizations with the same name under DOR.** `NP_PDA_2` looks like the inline create flow
  (`GRM-089`) being used to add a directorate that already existed as a root, so the duplicate finder
  did not offer it. Merge them (move `NP_PDA_2`'s projects, positions and staff to `NP_PDA`, then
  deactivate it), or decide both are intended.
- **Production has not run `b3d5f7h9`.** Before its deploy, run the same read-only simulation
  against production. A root organization that implements a project there hits exactly this.
