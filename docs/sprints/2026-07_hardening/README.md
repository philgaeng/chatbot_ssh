# Sprint — July 2026: Tier-1 Hardening

**Audience:** internal — excluded from the public repository (lifecycle §10.4).

> **Status: ACTIVE** · Source: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md) §3 Tier 1
> Goal: close the highest-risk, lowest-effort findings from the July 2026 adversarial codebase review. Target: overall quality ~55% → ~68% (security 55→75, correctness 55→70, portal robustness 48→60).
> Estimated total effort: ~2 engineer-weeks including tests.

## Tickets

| ID | Title | Area | Effort | Spec |
|---|---|---|---|---|
| HR-01 | Fail-closed auth (refuse startup on missing auth config) | ticketing + backend API | S | [01-auth-hardening-spec.md](01-auth-hardening-spec.md) §1 |
| HR-02 | `require_ticket_access` dependency on file/PII endpoints | ticketing API | S | [01-auth-hardening-spec.md](01-auth-hardening-spec.md) §2 |
| HR-03 | Unique partial index on `tickets.grievance_id` | ticketing schema | S | [02-data-integrity-spec.md](02-data-integrity-spec.md) §1 |
| HR-04 | Savepoints + row locking in the SLA escalation watchdog | ticketing engine | S/M | [02-data-integrity-spec.md](02-data-integrity-spec.md) §2 |
| HR-05 | CI pipeline: pytest + tsc + eslint gates | repo | S | [03-ci-pipeline-spec.md](03-ci-pipeline-spec.md) |
| HR-06 | Portal: list error states, settings hooks crash, `error.tsx` | ticketing-ui | S | [04-portal-robustness-spec.md](04-portal-robustness-spec.md) |
| HR-07 | Webchat: session persistence, send lock, SRI, banner XSS | REST_webchat | S | [05-webchat-robustness-spec.md](05-webchat-robustness-spec.md) |

## Execution order & workstreams

Five independent workstreams; each is one agent run (runbooks in [`agents/`](agents/)):

```
C: HR-05 CI            ← start FIRST (or in parallel); every later PR merges behind the gate
A: HR-01 → HR-02       ← sequential (both touch ticketing/api/dependencies.py + routers/tickets.py)
B: HR-03 → HR-04       ← sequential (migration first; HR-04's tests rely on the unique index)
D: HR-06 portal        ← independent
E: HR-07 webchat       ← independent
```

**Conflict note:** A and B both touch `ticketing/api/routers/tickets.py` (A: endpoint gates; B: intake error handling). Land A before B, or rebase B on A.

## Conventions (binding for all agents)

- Branch per workstream off `integration/seah-claude`: `hardening/hr-01-02-auth`, `hardening/hr-03-04-data`, `hardening/hr-05-ci`, `hardening/hr-06-portal`, `hardening/hr-07-webchat`.
- **Never touch `main`.** See CLAUDE.md git workflow.
- Every ticket ships **with its tests in the same commit**. The test requirements in each spec are acceptance criteria, not suggestions.
- Migrations: ticketing stream only (`ticketing/migrations/`), safety header required, real `downgrade()`.
- No behavior changes outside the ticket's scope; if you find an adjacent bug, log it in `PROGRESS.md` → Deviations, don't fix it.
- Update [`PROGRESS.md`](PROGRESS.md) at every commit (status + checklist ticks + deviations).
- When the sprint closes: write `docs/sprints/2026-07_hardening_tier1.md` (summary, June5 pattern), move this folder to `docs/sprints/archive/`, and update the scores in `docs/reviews/devils_advocate_codebase.md`.

## Definition of done (sprint level)

- [ ] All 7 tickets ✅ in PROGRESS.md with tests passing in CI
- [ ] CI green on the integration branch (pytest + tsc + eslint jobs)
- [ ] Manual verification checklists in each spec executed (recorded in PROGRESS.md)
- [ ] `docs/deployment/13_security.md` updated with a "fail-closed guarantees" section (part of HR-01)
- [ ] Devil's advocate codebase doc re-scored for the affected dimensions
