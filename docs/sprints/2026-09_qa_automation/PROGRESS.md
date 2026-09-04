# QA sprint — progress

> **Status: not started.** Tracker skeleton — fill as work lands, not at the end.
> Sprint: [`README.md`](README.md) · Why: [`DESIGN-qa-and-build-pipeline.md`](DESIGN-qa-and-build-pipeline.md) · Open input: [`QUESTIONS.md`](QUESTIONS.md)

## Ticket status

| Ticket | Stream | Status | Branch | Commit | Notes |
|---|---|---|---|---|---|
| QA-01 deploy safety | A | ⬜ not started | — | — | Blocked on nothing. Measure the real Next build peak before picking the heap cap. |
| QA-02 CI-built images | A | ⬜ not started | — | — | Blocked on Q-01…Q-05 |
| QA-03 stack isolation | A | ⬜ not started | — | — | Blocked on QA-02 |
| QA-04a harness | B | ⬜ not started | — | — | Blocked on Q-06…Q-10 |
| QA-04b route smoke | B | ⬜ not started | — | — | After 04a |
| QA-04c driven flows | B | ⬜ not started | — | — | After 04a; flow list from Q-09 |
| QA-04d webchat sweep | B | ⬜ not started | — | — | Only if Q-11 = yes |
| QA-05 CI gate | join | ⬜ not started | — | — | After QA-02, QA-03, QA-04a |

## Measurements to record (the sprint is not done without these)

| What | Why it matters | Value |
|---|---|---|
| Peak RSS of `npm run build` | Sets QA-01's heap cap honestly | — |
| Staging peak memory during a **pulled** deploy | Proves QA-02 removed the OOM class | — |
| Image build time, cold and cached | Tells us whether the cache is working | — |
| e2e wall-clock in CI | Decides whether it can ever be a required check | — |
| Routes covered / 22 | The honest coverage number, not a claim | — |

## Deviations log

| Date | Ticket | Deviation / adjacent finding | Action |
|---|---|---|---|
| — | — | — | — |

## Acceptance — sprint level

- [ ] A deploy to staging builds nothing on the host, and it is verified inside the container that the running code is the intended commit
- [ ] `make aws-deploy IMAGE_TAG=<older-sha>` is a working rollback
- [ ] Two isolated stacks run side by side on one machine
- [ ] A browser drives the officer UI in CI, and a deliberate regression turns the build red
- [ ] Every number in the table above is filled in with a measured value
