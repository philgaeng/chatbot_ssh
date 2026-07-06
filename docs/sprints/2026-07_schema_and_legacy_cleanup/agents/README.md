# Agent runbooks — Canonical Cleanup

One runbook per workstream. **Land on `dev/hardening`** (this is core-codebase cleanup). **0 records → rebuild canonically, don't reconcile.**

| Runbook | Ticket | Model | Order |
|---|---|---|---|
| [config-canonical.md](config-canonical.md) | CL-04 | **Opus** | **first** — var scheme underpins CL-03 + CI |
| [schema-truth.md](schema-truth.md) | CL-01 | **Opus** | unblocks CI; parallel to CL-04 |
| [demo-retire.md](demo-retire.md) | CL-03 | **Opus** | after CL-04 |
| [legacy-channels.md](legacy-channels.md) | CL-02 | **Opus** | any time |

## Model selection

All-Opus, high effort:

| Ticket | Why Opus |
|---|---|
| CL-04 | Cross-cutting config rename touching every settings module + the **fail-closed auth security invariant** — a wrong guard re-expression re-opens the HR-01 hole. |
| CL-01 | Rebuilds the canonical `public.*` schema; the app boots against it. Getting the canonical shape exactly right (schema-diff = 0) is the hardest correctness task here. |
| CL-03 | Deployment/auth consolidation touching chatbot intake, staging front door, and the dev bypass. |
| CL-02 | The accessible/voice **naming trap** — a wrong delete is a production outage on the complainant channel. |

No Sonnet, Haiku, or Fable.

## Best practices (carried forward)

- **One convention per concept.** After each ticket, `grep` proves the old spelling is *gone*, not coexisting (e.g. `TICKETING_ENV` → 0 hits post-CL-04).
- **Rebuild, don't reconcile** (0 records). CL-01 is a clean canonical baseline; still prove fresh migrate → seed → pytest works.
- **Preserve security through the rename** (CL-04): the HR-01 fail-closed guarantee is behavior-identical; only the variable/mechanism is canonical. Keep the tests green on the new vars.
- **Never delete by name-match** (CL-02); grep for a live caller first.
- **De-risk order** (CL-03): re-point chatbot intake and verify *before* deleting the old API.
- Tests/verification as acceptance criteria; update [`../PROGRESS.md`](../PROGRESS.md) each commit.

## Common rules (all agents)

1. Read `CLAUDE.md` (migration policy + "change with care" boundaries), [`../README.md`](../README.md) (the canonical target table), [`../AUDIT_FINDINGS.md`](../AUDIT_FINDINGS.md), and your spec **before touching code**. Re-verify audit line numbers with grep.
2. Land on `dev/hardening`. Never `main`. Do NOT commit or push unless told — leave changes for orchestrator review (unless your runbook says otherwise).
3. CL-01 = `migrations/public/` stream only. CL-04 must not weaken production security. Test on scratch DBs.
4. Deletions preceded by grep re-confirmation; if a "safe to delete/rename" item has an unexpected live caller, STOP and log it.
5. Update [`../PROGRESS.md`](../PROGRESS.md) at every commit.
6. Commit messages: imperative, ticket ID first (e.g. `CL-04: collapse env-mode vars to a single APP_ENV`).
