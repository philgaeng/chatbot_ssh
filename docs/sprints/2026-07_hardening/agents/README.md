# Agent runbooks — Tier-1 Hardening

One runbook per workstream; each is a self-contained brief for a single agent run. Give the agent the runbook plus repo access — it should not need anything else.

| Runbook | Tickets | Model | Branch |
|---|---|---|---|
| [ci.md](ci.md) | HR-05 | **Sonnet** | `hardening/hr-05-ci` — **run first** |
| [backend-auth.md](backend-auth.md) | HR-01, HR-02 | **Opus** | `hardening/hr-01-02-auth` |
| [backend-data.md](backend-data.md) | HR-03, HR-04 | **Opus** | `hardening/hr-03-04-data` — after auth lands (shared files) |
| [portal.md](portal.md) | HR-06 | **Sonnet** | `hardening/hr-06-portal` |
| [webchat.md](webchat.md) | HR-07 | **Opus** | `hardening/hr-07-webchat` |

## Model selection (per workstream)

Pick the model by **difficulty and blast radius, not diff size**. Rationale per ticket:

| Ticket(s) | Model / reasoning effort | Why |
|---|---|---|
| HR-05 (CI) | **Sonnet**, medium effort | Mechanical CI YAML + migration-order + eslint baseline against an unambiguous spec. Low correctness ambiguity. |
| HR-01 / HR-02 (auth) | **Opus**, high effort | Security-critical: fail-closed startup and a per-ticket authz class fix on a government PII system. A subtle miss reopens the worst findings in the review. |
| HR-03 / HR-04 (data) | **Opus**, high effort | DB-enforced invariant + lock-free escalation made crash- and concurrency-safe (savepoints, `FOR UPDATE SKIP LOCKED`). Concurrency-correctness reasoning. |
| HR-06 (portal) | **Sonnet**, medium effort | React hooks-order fix, error boundaries, list error states, vitest seed — mechanical UI plumbing with a detailed spec. |
| HR-07 (webchat) | **Opus**, high effort | Only four tiny diffs, **but the live complainant/SEAH intake channel** — judgment about not regressing outweighs line count. Small diff ≠ low risk. |

**Haiku** is not recommended for any workstream in this sprint; reserve it for trivial doc/text edits.

## Common rules (all agents)

1. Read `CLAUDE.md` (git workflow, schema ownership, service-boundary care) and your ticket spec(s) in this folder's parent **before touching code**. Line numbers in specs are July-2026 snapshots — re-locate with grep first.
2. Branch off `integration/seah-claude`. Never commit to `main`.
3. Tests listed in your spec are **acceptance criteria** — ship them in the same commits as the code. Run the full relevant suite (`pytest tests/ticketing tests/orchestrator -q` / `npx tsc --noEmit` + `npx eslint .`) before declaring done.
4. Smallest possible diff. No drive-by refactors, no formatting sweeps. Adjacent bugs go to `../PROGRESS.md` → Deviations, not into your diff.
5. Update `../PROGRESS.md` (status, checklist ticks, deviations) at every commit; execute your spec's **manual verification** section and record results there.
6. Commit messages: imperative one-liner, mention the ticket ID (e.g. `HR-03: enforce one active ticket per grievance with partial unique index`).
