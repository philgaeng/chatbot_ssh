# Sprint — Tier-2 Quality & Performance (target: August 2026)

> **Status: QUEUED** — starts after the Tier-1 Hardening sprint ([`../2026-07_hardening/`](../2026-07_hardening/)) is fully merged; this sprint builds on its CI gate (HR-05), authz test matrix (HR-02), escalation test suite (HR-04), and vitest seed (HR-06).
> Source: [`docs/reviews/devils_advocate_codebase.md`](../../reviews/devils_advocate_codebase.md) §3 Tier 2.
> Goal: overall quality ~68% → ~78% — end officer data loss at token expiry, make the ticket state machine testable, protect the shared DB at scale, and fix the SEAH-critical duplication + Nepali copy defects.

## Tickets

| ID | Title | Area | Effort | Spec |
|---|---|---|---|---|
| H2-01 | OIDC refresh-grant in `apiFetch` (single-flight, retry-once) | ticketing-ui auth | M | [01-portal-auth-and-thread-spec.md](01-portal-auth-and-thread-spec.md) §1 |
| H2-06 | Shared `useTicketThread` hook (desktop + `/m`) | ticketing-ui | M | [01-portal-auth-and-thread-spec.md](01-portal-auth-and-thread-spec.md) §2 |
| H2-02 | Split `tickets.py`; move `perform_action` into `engine/` | ticketing API | M | [02-backend-router-split-spec.md](02-backend-router-split-spec.md) §1 |
| H2-03 | Authz matrix extension (full endpoint × role × scope) | ticketing tests | S/M | [02-backend-router-split-spec.md](02-backend-router-split-spec.md) §2 |
| H2-07 | Escalation test suite extension (chains, SEAH, interleaving) | ticketing tests | S | [02-backend-router-split-spec.md](02-backend-router-split-spec.md) §3 |
| H2-04 | Grievance sync: watermark + paging (+ cache refresh out of GET) | ticketing tasks | S/M | [03-backend-performance-spec.md](03-backend-performance-spec.md) §1 |
| H2-05 | Onboarding sync cached out of the auth dependency | ticketing API | S | [03-backend-performance-spec.md](03-backend-performance-spec.md) §2 |
| H2-08 | SEAH form mixin + Nepali copy repair | chatbot actions | M | [04-seah-chatbot-quality-spec.md](04-seah-chatbot-quality-spec.md) |

Two review rows are deliberately **not** separate tickets here: "Authz test matrix" and "Escalation engine test suite" were delivered in baseline form by HR-02/HR-04 — H2-03/H2-07 only extend them.

## Execution order & workstreams

Four independent workstreams, one agent run each (runbooks in [`agents/`](agents/)):

```
A: H2-02 → H2-03 → H2-07   backend refactor (router split first; test extensions target the new engine layout)
B: H2-04 → H2-05           backend performance (independent of A except tickets.py touchpoints — land A first or rebase)
C: H2-01 → H2-06           portal (auth first; thread hook next)
D: H2-08                   SEAH chatbot quality (fully independent)
```

**Conflict notes:** A rewrites `ticketing/api/routers/tickets.py` into a package — B's small `tickets.py` edit (cache-refresh removal) and any other open branch touching it must rebase on A. C's two tickets both touch `lib/api.ts`/auth plumbing — same agent, sequential.

## Conventions (binding — same as Tier 1)

- Branches off `integration/seah-claude`: `tier2/h2-02-03-07-backend`, `tier2/h2-04-05-perf`, `tier2/h2-01-06-portal`, `tier2/h2-08-seah`. Never touch `main`.
- Tests ship in the same commits as code; the per-ticket test lists are acceptance criteria. CI (from HR-05) must be green before a workstream is `done`.
- **H2-02 is a pure refactor**: URL surface, response shapes, and behavior byte-identical — the existing suite plus the HR-02 matrix are the safety net and must pass unchanged.
- Smallest diffs otherwise; adjacent findings → [`PROGRESS.md`](PROGRESS.md) Deviations.
- Update [`PROGRESS.md`](PROGRESS.md) at every commit.
- Sprint close: summary doc `docs/sprints/2026-08_tier2_quality.md`, move this folder to `archive/`, re-score `devils_advocate_codebase.md`.

## Definition of done (sprint level)

- [ ] All 8 tickets ✅ with tests green in CI
- [ ] Zero behavior change verified for H2-02 (full suite + matrix unchanged)
- [ ] Officer session survives token expiry without data loss (H2-01 manual check recorded)
- [ ] Grievance sync runtime measured before/after on a seeded DB (H2-04, numbers in PROGRESS)
- [ ] Nepali SEAH copy signed off by a human reviewer (H2-08 — agent prepares, human approves; sign-off recorded in PROGRESS)
- [ ] `devils_advocate_codebase.md` re-scored
