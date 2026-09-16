# `GRM-125` — the Workflows list hides sensitive workflows from the admins who configure them

**Found 2026-09-15**, while building `GRM-119`'s end-to-end check. Logged here and in
[`SPINE.md`](../../../SPINE.md) per the standing deferral rule.
**Kind:** `deviation` — the code and [D-007](../../../DECISIONS.md) disagree on which capability decides it.

## What the code does

[`WorkflowsTab.tsx`](../../../../channels/ticketing-ui/components/settings/workflows/WorkflowsTab.tsx)
filters workflows and templates with `canSeeSeah` — **case access**, which D-007 made cast-only:

```ts
if (!canSeeSeah && workflowTrackOf(w) === "seah") return false;
```

D-007 separates two answers: *seeing* a sensitive case (cast only — no admin, not `super_admin`) and
*configuring* a sensitive workflow (`can_configure_sensitive`). The server follows it: `GET /workflows`
filters on `can_configure_sensitive`. The UI filter is the case-access one, so **an admin who may
configure a sensitive workflow cannot find it in Settings.** Measured on the local stack: the platform
admin's list shows no SEAH workflow; the SEAH officer who can see the cases has no Settings.

## Consequence

- Nobody can open a SEAH workflow's editor in the browser today: its steps, cast and resolution panel
  are reachable only through the API.
- `GRM-119`'s e2e cannot drive the SEAH panel state (one line, no controls); it is pinned by API and
  unit tests instead.

## Proposed resolution

Filter with `canConfigureSensitive` — already on `useAuth()` — in both places in `WorkflowsTab.tsx`
(workflows and templates) and in `NewWorkflowModal`'s `canSeeSeah` prop, and add the SEAH panel state
to `settings-resolution-panel.spec.ts`. ⚠ A `+SENSITIVE` change by kind: it widens who *lists* sensitive
workflows (to exactly the server's set), so the isolation review checks that no case data rides along.
