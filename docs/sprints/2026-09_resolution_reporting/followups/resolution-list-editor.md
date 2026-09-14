# `GRM-119` — a workflow's resolution actions can only be changed by a migration

**Deferred 2026-09-15**, while specifying `GRM-116`. Logged here and in
[`SPINE.md`](../../../SPINE.md) per the standing deferral rule.
**Kind:** `debt` — question 4: the owner chose not to build the editor in this lane (Q-04, answer (a)).

## What is built, and what is not

`GRM-116` puts an ordered list of resolution actions on each workflow definition, copied from three
starter lists in code. **Nothing on screen reads or writes that list outside the resolve form.** A
workflow author in Settings → Workflows cannot see which list a workflow uses, let alone change it.

## Why not now

The client asked for different lists per workflow, not for editable ones. The lists change rarely,
and building the editor would double the lane: authoring UI, validation, sensitive-workflow write
permissions (only those who configure sensitive workflows may edit a SEAH list), and a rule for what
happens to open cases when a code they could resolve with is removed.

## What it costs meanwhile

- **Changing a list takes a developer**: edit `STARTER_RESOLUTION_LISTS` and write a data migration
  touching every workflow that copied the old list.
- **A new workflow created from scratch (not a template or clone) gets the `general` list**, and its
  author has no way to know that.

## Definition of done

1. Settings → Workflows shows a workflow's resolution actions (read-only is an acceptable first step).
2. An author with write on the workflow can add, rename, reorder and **retire** an action. Retiring,
   not deleting: a code already in a `RESOLVED` event must still resolve to its label, and the
   snapshot in the event payload (`GRM-116`) is what makes that safe.
3. Editing a sensitive workflow's list follows the existing sensitive-workflow write gate.
4. `12_workflows_configuration.md` documents it.

## Endgame

Once the editor exists, `STARTER_RESOLUTION_LISTS` survives only as template seed data.
