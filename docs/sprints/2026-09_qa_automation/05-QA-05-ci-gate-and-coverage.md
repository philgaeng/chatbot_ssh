# QA-05 — Run it in CI

> **Join point · 1–2 days · depends on QA-02, QA-03, QA-04a · the only ticket that edits `ci.yml` for Stream B**

## Context

CI runs five jobs today (`backend-tests`, `ui-checks`, `webchat-checks`, `docs-links`,
`dpg-platform-independence`) on `pull_request` and on pushes to `main`, `integration/**`, `dev/**`,
`dpg/**`. None of them starts a full stack; `backend-tests` gets Postgres and Redis as services and runs
pytest. This ticket adds the first job that stands up the **whole application** and drives it.

**Verified 2026-09-04 via the GitHub API: `main` has no branch protection at all** (`Branch not
protected`, HTTP 404). So "add a required check" is currently two actions, not one — see
[Q-13](QUESTIONS.md#q-13--report-only-or-required-check).

## Scope

1. **An `e2e` job** in `.github/workflows/ci.yml`:
   - pull the images published by QA-02 (`IMAGE_TAG` = this commit's sha), including the **`-bypass` UI
     variant** ([Q-04](QUESTIONS.md#q-04--the-ui-image-bakes-its-auth-mode--do-we-publish-two-variants));
   - `make ephemeral-up` (QA-03) with a run-scoped `COMPOSE_PROJECT_NAME`;
   - run all three migration streams in the documented order (public → ticketing → ops), then the same
     two seed commands `backend-tests` already uses;
   - `npx playwright test`;
   - **always** upload screenshots, traces and container logs as artifacts — the logs matter most on the
     runs where the suite fails to start at all;
   - `make ephemeral-down` in an `always()` step, volumes included.
2. **Report-only first** ([Q-13](QUESTIONS.md#q-13--report-only-or-required-check)) — `continue-on-error`
   for an agreed window, with the expiry date written in the job header so it cannot quietly become
   permanent. This repo has a documented history of gates that decorate rather than gate; say when it stops.
3. **A concurrency group** so a new push cancels the previous run — a full stack per run is the most
   expensive job in this pipeline.
4. **Fan-out coordination:** QA-04b/c/d land against this job as they complete. Each adds spec files
   only; none should need to touch the workflow again.
5. **Retire what it replaces.** If Q-11 put QA-04d in scope, tick HR-07's sweep checkbox in
   `2026-07_hardening/PROGRESS.md` **with the run link as evidence** — do not tick it because the tests
   exist; tick it because they ran and passed.

## Not in scope

Branch protection itself (a repo-admin action — ask, do not attempt it from CI). Pixel-diff gating
(Q-08). Deploying anything.

## Files

| File | Change |
|---|---|
| `.github/workflows/ci.yml` | the `e2e` job; header comment updated to name **six** jobs — the existing header undercounted its own jobs once already, and that is recorded in it |
| `Makefile` | `ephemeral-up`/`down` used as-is from QA-03 (no new targets expected) |
| `docs/sprints/2026-07_hardening/PROGRESS.md` | HR-07 sweep ticked **only if** it actually ran (Q-11) |
| `docs/engineering/04_testing.md` | how to run the suite locally and read its artifacts |

## Acceptance

- [ ] The job goes green on a PR, and the artifacts contain a screenshot per smoke route
- [ ] A deliberately broken UI change (e.g. remove a nav link the canary asserts) turns it **red** — the
      test that proves the gate is real
- [ ] Total added CI wall-clock recorded in `PROGRESS.md`; if it exceeds ~10 minutes, say so and propose
      a split rather than quietly accepting it
- [ ] No leaked containers, volumes or networks after a run, including a **cancelled** one
- [ ] Report-only expiry date written into the job header
- [ ] The workflow header names every job it contains

## Risks

- **A full-stack job is the flakiest thing in any pipeline.** Bound every wait, and make readiness
  failures say which service was not ready — the failure you will actually get is "the API never came
  up", not "the button moved".
- **Cost and queue time.** Concurrency cancellation plus image caching keeps it sane; measure before
  adding more browsers or shards.
- **`continue-on-error` is how a gate becomes decoration.** The expiry date is the control. Put it in
  the header, and put a `TODO.md` row against it per the standing deferral rule.
