# Agent runbooks — Tier-2 Quality & Performance

One runbook per workstream. Prerequisite for ALL: the Tier-1 sprint is merged and CI is green on `integration/seah-claude` — verify before branching; if not, stop and report.

| Runbook | Tickets | Branch |
|---|---|---|
| [backend-refactor.md](backend-refactor.md) | H2-02, H2-03, H2-07 | `tier2/h2-02-03-07-backend` — land before backend-perf |
| [backend-perf.md](backend-perf.md) | H2-04, H2-05 | `tier2/h2-04-05-perf` |
| [portal.md](portal.md) | H2-01, H2-06 | `tier2/h2-01-06-portal` |
| [seah-chatbot.md](seah-chatbot.md) | H2-08 | `tier2/h2-08-seah` |

## Common rules (all agents)

1. Read `CLAUDE.md`, [`../README.md`](../README.md) conventions, and your ticket spec(s) **before touching code**. Spec line numbers are July-2026 snapshots — re-locate with grep first.
2. Branch off `integration/seah-claude`. Never commit to `main`.
3. Tests in your spec are acceptance criteria; ship them with the code. CI must be green before `done`.
4. Smallest diff that satisfies the spec. Adjacent findings → `../PROGRESS.md` Deviations, not your diff.
5. Update `../PROGRESS.md` (status, checklist ticks, measurements, deviations) at every commit; execute your spec's manual verification and record results.
6. Commit messages: imperative, ticket ID first (e.g. `H2-04: watermark grievance sync and page in batches`).
