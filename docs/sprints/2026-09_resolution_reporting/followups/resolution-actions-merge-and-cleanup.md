# `GRM-123` — unused and duplicate resolution actions have no way out of the catalog

**Deferred 2026-09-15**, while simplifying `GRM-119` and `GRM-121` with the owner (Q-10). Logged here
and in [`SPINE.md`](../../../SPINE.md) per the standing deferral rule.
**Kind:** `debt` — question 4: deliberately cut to keep the admin screens simple; correct today, and
knowingly incomplete once the catalog has lived for a while.

## What was cut, and why

The authoring wireframe first had a catalog screen with **retire** (choosing a replacement per
workflow), **restore**, **widening** an office's action to its parent organization, and a platform
admin's **merge** of duplicates across organizations, with reports counting a merged action under its
replacement. The owner judged it *"too complex for the future admins."* The lane kept one panel per
workflow, a limit of 8 actions, and *counts as* a shared action.

## What that leaves

1. **Nothing leaves the catalog.** An action removed from every workflow still appears in the panel's
   search for workflows that can use it. The limit of 8 keeps each **list** short; nothing keeps the
   **catalog** short.
2. **Duplicates stay.** The similarity check (`GRM-121`) suggests an existing action but never blocks;
   two offices can still end up with *Culvert cleared* and *Drain cleaned*.
3. **National statistics are not affected** — both count as a DOR shared action (DESIGN §3.1.1). This
   is why the cut is safe: the harm left is clutter in a search list, not wrong totals.

`resolution_actions.is_active` exists (`GRM-116`) and nothing sets it yet — the column the clean-up
needs is already there.

## Definition of done

1. A platform or ministry admin can **retire** an action no workflow uses (hidden from search, kept for
   history) and bring it back.
2. Retiring an action still in use is refused, naming the workflows — no replacement mapping.
3. Optionally, **merge** two local actions of one ministry: the kept one replaces the other in every
   list; the retired one keeps its code for history; reports need nothing new, because both already
   count as a shared action.
4. Tests: a retired action is absent from `available` and present in reports by label.

## Trigger

**Any** of: an admin reports the *Add an action* search is hard to use; a ministry's catalog passes
**50** actions; a second ministry is onboarded (`GRM-120`).
