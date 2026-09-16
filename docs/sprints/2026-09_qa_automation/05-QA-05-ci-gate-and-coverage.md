# QA-05 — Run it in CI

> **Join point · 1–2 days · depends on QA-02, QA-03, QA-04a · the only ticket that edits `ci.yml` for Stream B**
> ⚠ **Revised 2026-09-04 after a completeness review.** Three things this ticket assumed QA-02/QA-03
> would hand it did not exist in their specs: a resolvable image tag for a PR commit, a way to select
> the `-bypass` UI variant, and an `ephemeral-up` service set big enough for QA-04d. They are now
> QA-02 scope 1–2 and QA-03 scope 4. **Do not work around a missing one here** — that is how the join
> point silently absorbs two other tickets' work.

## Context

CI runs five jobs today (`backend-tests`, `ui-checks`, `webchat-checks`, `docs-links`,
`dpg-platform-independence`) on `pull_request` and on pushes to `main`, `integration/**`, `dev/**`,
`dpg/**`. None of them starts a full stack; `backend-tests` gets Postgres and Redis as services and runs
pytest. This ticket adds the first job that stands up the **whole application** and drives it.

~~**Verified 2026-09-04 via the GitHub API: `main` has no branch protection at all**~~ ✅ **Superseded
the same day** — a ruleset now covers `main` and `integration/*` with all five existing CI jobs as
required checks, **active and verified through the API on 2026-09-04**. So **"add a required check" is one
action again**: add the e2e job's context to the existing ruleset when its report-only period expires.
✅ **Decided:** e2e lands **report-only with an expiry date**, then becomes required. ⭐ **Separately and
now — enabling protection for the three checks that already exist is a ten-minute repo-admin action**
and does not belong to this ticket; it is listed in [`PROGRESS.md`](PROGRESS.md) so it is not lost.

## Scope

1. **An `e2e` job** in `.github/workflows/ci.yml`:
   - pull the images published by QA-02: `IMAGE_TAG` = this commit's sha for the app image, and
     `UI_IMAGE_TAG=<sha>-bypass` for `grm_ui`.
     ⚠ **Both of these are QA-02's deliverables and must exist before this job is written.**
     `UI_IMAGE_TAG` is the variable that lets one stack mix `app:<sha>` with `ui:<sha>-bypass`
     (QA-02 scope 1) — without it there is no way to express this, and this job **must not** work
     around it by editing a compose file. And an image for *this commit's sha* only exists if
     `images.yml` builds on the branch or PR under test (QA-02 scope 2); if QA-02 chose the fallback
     route instead, **use the fallback order it documented** rather than inventing one here.
     **Verify a tag resolves as the job's first step and fail with that message** — "no image for
     $SHA; see QA-02" is a diagnosable failure, a `docker compose pull` error is not.
   - `make ephemeral-up` (QA-03) with a run-scoped `COMPOSE_PROJECT_NAME`, and **the service set the
     specs need** — 04d's webchat items require the chatbot half of the stack plus nginx (QA-03 scope 4);
   - run all three migration streams, **in the order this repo already uses** — see the note below —
     then the same two seed commands `backend-tests` already uses;
   - `npx playwright test`;
   - **always** upload screenshots, traces and container logs as artifacts — the logs matter most on the
     runs where the suite fails to start at all;
   - `make ephemeral-down` in an `always()` step, volumes included.
   > ⚠ **Migration order — do not "fix" it here.** This ticket's earlier draft said *"the documented
   > order (public → ticketing → ops)"*. There are **two orders in the repo and they disagree**:
   > `ci.yml:206-208` runs public → ticketing → ops, while `Makefile:129-131` (`REMOTE_DEPLOY_CORE`)
   > and `migrate_all` (`Makefile:419`) run **ticketing → public → ops**, and
   > [`07_migrations_policy.md`](../../deployment/07_migrations_policy.md) §"May5 SEAH rollout"
   > documents ticketing → public. **This job copies `backend-tests`' steps verbatim**, because they
   > demonstrably work against the same seed. Reconciling the two is a real question and it belongs to
   > a migrations ticket, not to a test-harness one — log it per the standing deferral rule
   > ([Q-19](QUESTIONS.md#q-19--which-migration-order-is-the-documented-one)).

2. **Report-only first** — `continue-on-error`
   for an agreed window, with the expiry date written in the job header so it cannot quietly become
   permanent. This repo has a documented history of gates that decorate rather than gate; say when it stops.
   ⚠ **The expiry controls nothing on its own.** Q-13 verified that `main` has **no branch protection
   at all**, so "report-only, then required" describes a transition into a pipeline where no check is
   required either. **A-3 in [`PROGRESS.md`](PROGRESS.md) — enabling protection for the three existing
   checks — is the precondition that gives this clause meaning**, and it needs a named owner and a date
   before this ticket's expiry is written, not after. It is still not this ticket's work to do.
3. **Any PR with no image for its commit must skip cleanly, not fail.** ⚠ Fork PRs are the obvious
   case — this repo is **public**, so they get no secrets and no package-write permission. But **the
   fork test is the wrong gate on its own**: with QA-02's trigger set the *internal* `qa/*` →
   `dev/qa-automation` PRs in this very sprint would also have no `<sha>` image, and they do have
   secrets. **Gate on image availability, not on token presence** — resolve the tag first, skip with a
   notice if nothing resolves. Left alone, every external contribution *and* half the internal ones
   show a red X for a reason that has nothing to do with the change. **Follow the precedent already in `ci.yml`:** the
   `dpg-platform-independence` job gates on token presence and emits a `::notice`, with the reasoning
   written into the step — *"a red X here would be the wrong signal on a public-good repository."* Do the
   same here: detect the fork case, skip with a notice that says why, and never fail on it.
4. **A concurrency group** so a new push cancels the previous run — a full stack per run is the most
   expensive job in this pipeline.
5. **Fan-out coordination:** QA-04b/c/d land against this job as they complete. Each adds spec files
   only; none should need to touch the workflow again.
6. **Retire what it replaces.** QA-04d is in scope, so tick HR-07's sweep checkbox in
   `2026-07_hardening/PROGRESS.md` **with the run link as evidence** — do not tick it because the tests
   exist; tick it because they ran and passed.

## Not in scope

Branch protection itself (a repo-admin action — ask, do not attempt it from CI). Pixel-diff gating
(v1 captures only). Deploying anything.

## Files

| File | Change |
|---|---|
| `.github/workflows/ci.yml` | the `e2e` job; header comment updated to name **six** jobs — the existing header undercounted its own jobs once already, and that is recorded in it |
| `Makefile` | `ephemeral-up`/`down` used as-is from QA-03 (no new targets expected) |
| `docs/sprints/2026-07_hardening/PROGRESS.md` | HR-07 sweep ticked **only if** it actually ran |
| `docs/engineering/04_testing.md` | how to run the suite locally and read its artifacts |

## Acceptance

- [ ] The job goes green on a PR, and the artifacts contain a screenshot per smoke route
- [ ] A deliberately broken UI change (e.g. remove a nav link the canary asserts) turns it **red** — the
      test that proves the gate is real
- [ ] Total added CI wall-clock recorded in `PROGRESS.md`; if it exceeds ~10 minutes, say so and propose
      a split rather than quietly accepting it
- [ ] No leaked containers, volumes or networks after a run, including a **cancelled** one
- [ ] **A fork PR is green-with-a-notice, never red** — test it with a branch that cannot see secrets
- [ ] **A PR whose commit has no published image is also green-with-a-notice** — test it on an internal
      branch, not just a fork; this is the case QA-02's trigger set decides
- [ ] The stack runs the **bypass** UI (`UI_IMAGE_TAG=<sha>-bypass`) while every other service runs
      `app:<sha>` — assert it in the job, since a Keycloak-built UI fails the suite confusingly
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
