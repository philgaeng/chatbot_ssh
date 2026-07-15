# Follow-up — per-tab render smoke tests for Settings

> Opened by **T3-05** (2026-07-15, `dev/tier3-structural`). Deferred, not dropped.
> Source: [`04-portal-settings-spec.md`](../04-portal-settings-spec.md) §Tests — *"Add at least a smoke test per extracted tab (render + assert the tab's heading/primary control) … If skipped for scope, log it as a followup + TODO.md row — do not leave it silently untested."*

## What was asked

A render smoke test per extracted settings tab: mount the component, assert its heading / primary control.

## What was delivered instead

Pure-logic unit tests for the extracted leaf helpers — 27 tests, the **first** coverage of anything under `components/settings/` (closes the coverage-from-zero half of sprint D-12):

| File | Covers |
|---|---|
| `components/settings/workflows/workflowHelpers.test.ts` | `statusBadge`, `typeBadge`, `workflowTrackOf`, `emptyBinding`, `bindingsFromProject`, `publishedWorkflowOptions`, the NOTIF_* vocab |
| `components/settings/roles/roleEntry.test.ts` | `mapGrmRoleToEntry` defaulting, `owningLevelLabel` |
| `components/settings/lib/friendlyError.test.ts` | the 34-call-site error contract |

Both suites were **mutation-checked** (drop `publishedWorkflowOptions`' `selectedId` guard ⇒ red; swap `mapGrmRoleToEntry`'s `??` for `||` ⇒ red), so they are not vacuous.

## Why the render tests were deferred

**The portal has no DOM test harness at all.** This is not "a test was skipped" — the capability does not exist:

- `package.json` devDeps: no `@testing-library/react`, no `@testing-library/jest-dom`, no `jsdom`/`happy-dom`, no `@vitejs/plugin-react`.
- `vitest.config.ts` is `environment: "node"`, `include: ["**/*.test.ts"]` — **`.tsx` is not even collected** — and its header comment states the intent outright: *"Tests are plain TS logic (no JSX/DOM), so `node` env only."*

Standing one up means:
1. adding ~3 dev dependencies (+ lockfile churn, + a `grm_ui` image rebuild — the Dockerfile `npm ci`s at build time);
2. switching the **shared** vitest config to `jsdom` and widening `include` to `.tsx`, under all 88 existing tests;
3. a React plugin for JSX transform.

That is a **scope and dependency decision**, not part of a verbatim move, and it would have made a "move code, change nothing" commit series also change the test infrastructure for the whole portal. T3-05's spec is explicit that the safety net for this ticket is `tsc` + `eslint` + `build` + manual click-through.

## What to do

Decide whether the portal wants a component-test harness at all. If yes:

1. `npm i -D @testing-library/react @testing-library/jest-dom jsdom @vitejs/plugin-react` (inside Docker per CLAUDE.md; rebuild `grm_ui`).
2. `vitest.config.ts`: `plugins: [react()]`, `environment: "jsdom"`, `include: ["**/*.test.ts", "**/*.test.tsx"]`, add a setup file for `jest-dom` matchers.
3. Smoke test per extracted tab — mount + assert heading/primary control:
   `AdminAccessTab`, `LocationsSection`, `SystemConfigTab`, `RolesTab`, `WorkflowsTab`, `ProjectsSection`.
   Each needs `useAuth` mocked (they read `AuthProvider`) and `@/lib/api` stubbed.
4. Wire into CI alongside the existing `npm test`.

**Effort:** S/M (the harness is the work; the tests themselves are small now that the components are individually mountable — which is precisely the benefit the extraction bought).

## Related

- Sprint deviation **D-12** — `app/settings/page.tsx` had zero direct test coverage. Partially addressed (helpers now covered); the render half is this follow-up.
- [`dead-project-workflow-select.md`](dead-project-workflow-select.md) — sibling T3-05 follow-up.
