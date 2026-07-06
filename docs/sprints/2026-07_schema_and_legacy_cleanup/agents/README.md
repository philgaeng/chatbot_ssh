# Agent runbooks — Schema & Legacy Cleanup

One runbook per workstream; each is a self-contained brief for a single agent run.

| Runbook | Ticket | Model | Branch |
|---|---|---|---|
| [schema-truth.md](schema-truth.md) | CL-01 | **Opus** | `cleanup/cl-01-schema` — **run first** |
| [legacy-channels.md](legacy-channels.md) | CL-02 | **Opus** | `cleanup/cl-02-channels` |
| [demo-retire.md](demo-retire.md) | CL-03 | **Opus** | `cleanup/cl-03-demo` |

## Model selection

All-Opus, high reasoning effort. Nothing here is safe to economize on:

| Ticket | Why Opus |
|---|---|
| CL-01 | Rewrites who owns the **live chatbot `public.*` schema** — a wrong idempotency guard or an unconditional drop is data loss on prod. Reconciling 20+ tables to an exact schema-diff is the hardest correctness task in the repo right now. |
| CL-02 | "Just deletion," but the **naming trap** (accessible/voice names that are REST_webchat's live infra) makes a wrong delete a production outage on the complainant channel. Blast radius ≫ diff size. |
| CL-03 | Auth + deployment consolidation touching chatbot intake, staging front door, and the dev/CI bypass — a misstep breaks intake or locks people out. |

No Sonnet, no Haiku, no Fable.

## Best practices (carried from the devil's-advocate + hardening sprints)

- **Reconcile to reality, prove it with a diff.** CL-01's bar is an *empty* `pg_dump` schema-diff between fresh-from-migrations and the app's real schema — not "looks right." Write that gate first.
- **Idempotent, data-preserving DDL.** `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` / shape-detection before any drop+recreate. Test against a **copy of the live DB**, not just an empty one.
- **Never delete by name-match** (CL-02). Grep for a live caller first; the audit's "must stay" set is load-bearing.
- **De-risk order** (CL-03): re-point the chatbot intake and verify it *before* deleting the old API service.
- **Tests/verification are acceptance criteria**, in the same commits. Land behind the HR-05 CI gate.
- **Durable content in `docs/` in the same PR;** update the spec/AUDIT status to as-built citing the migration/file that proves it.

## Common rules (all agents)

1. Read `CLAUDE.md` (esp. the three-stream migration policy + "change with care" service boundaries), [`../README.md`](../README.md), [`../AUDIT_FINDINGS.md`](../AUDIT_FINDINGS.md), and your spec **before touching code**. Re-verify audit line numbers with grep first.
2. Branch off the agreed base (`dev/hardening`, or `integration/seah-claude` once hardening merges). Never commit to `main`.
3. CL-01 touches **`public.*`** — the live chatbot schema. Idempotent, reconcile-to-live, proven by schema-diff. Never edit the `ticketing`/`ops` streams.
4. Deletions are preceded by grep re-confirmation; if a "safe to delete" item has a live caller, STOP and log it.
5. Update [`../PROGRESS.md`](../PROGRESS.md) at every commit (status, checklist ticks, deviations).
6. Commit messages: imperative, ticket ID first (e.g. `CL-01: make Alembic the single source of truth for public.*`).
