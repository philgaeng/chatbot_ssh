# Agent runbooks — Tier-2 Quality & Performance

One runbook per workstream. Prerequisite for ALL: the Tier-1 sprint is merged and CI is green on `integration/seah-claude` — verify before branching; if not, stop and report.

| Runbook | Tickets | Model | Branch |
|---|---|---|---|
| [backend-refactor.md](backend-refactor.md) | H2-02, H2-03, H2-07 | **Opus** | `tier2/h2-02-03-07-backend` — land before backend-perf |
| [backend-perf.md](backend-perf.md) | H2-04, H2-05 | **Opus** | `tier2/h2-04-05-perf` |
| [portal.md](portal.md) | H2-01, H2-06 | **Opus** | `tier2/h2-01-06-portal` |
| [seah-chatbot.md](seah-chatbot.md) | H2-08 | **Opus** | `tier2/h2-08-seah` |

## Model selection (per workstream)

Pick the model by **difficulty and blast radius, not diff size**. Rationale per ticket:

| Ticket(s) | Model / reasoning effort | Why |
|---|---|---|
| H2-02 / H2-03 / H2-07 (refactor) | **Opus**, high effort | 2,468-line God-router split with **zero behavior change** as the acceptance bar, plus authz/escalation test matrices. Behavior-preserving refactors at this scale are exactly where a weaker model drifts. |
| H2-04 / H2-05 (perf) | **Opus**, high effort | Watermark/paged sync, moving writes off the GET path, and TTL cache with correct invalidation — transaction-placement and correctness reasoning under measurement. |
| H2-01 / H2-06 (portal) | **Opus**, high effort | H2-01 is a subtle single-flight OIDC refresh + retry-once with rotation edge cases (drives model to Opus). H2-06 (shared thread hook) alone is Sonnet-level; the runbook bundles them, so run it on **Opus**. |
| H2-08 (SEAH chatbot) | **Opus**, high effort | Stack-introspection utterance lookup, mixin extraction on the **most sensitive flow in the product**, and Nepali copy repair (translator-gated). Judgment and care dominate. |

**Haiku** is not recommended for any workstream in this sprint; reserve it for trivial doc/text edits.
If H2-06 is ever split into its own branch, run that isolated hook-dedup on **Sonnet** (medium effort).

## Common rules (all agents)

1. Read `CLAUDE.md`, [`../README.md`](../README.md) conventions, and your ticket spec(s) **before touching code**. Spec line numbers are July-2026 snapshots — re-locate with grep first.
2. Branch off `integration/seah-claude`. Never commit to `main`.
3. Tests in your spec are acceptance criteria; ship them with the code. CI must be green before `done`.
4. Smallest diff that satisfies the spec. Adjacent findings → `../PROGRESS.md` Deviations, not your diff.
5. Update `../PROGRESS.md` (status, checklist ticks, measurements, deviations) at every commit; execute your spec's manual verification and record results.
6. Commit messages: imperative, ticket ID first (e.g. `H2-04: watermark grievance sync and page in batches`).
