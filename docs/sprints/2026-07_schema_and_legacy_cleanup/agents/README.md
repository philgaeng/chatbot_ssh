# Agent runbooks — Canonical Cleanup

One runbook per workstream. **Land on `dev/hardening`** (this is core-codebase cleanup). **0 records → rebuild canonically, don't reconcile.**

| Runbook | Ticket | Model | Notes |
|---|---|---|---|
| [schema-truth.md](schema-truth.md) | CL-01 | **Opus** | unblocks CI; squash + prune |
| [config-and-deploy.md](config-and-deploy.md) | CL-03 | **Opus** | config rename + single Keycloak stack (merged) |
| [legacy-channels.md](legacy-channels.md) | CL-02 | **Opus** | any time; naming-trap safety |

CL-01 and CL-03 are largely independent (order by priority — CI-green vs canonical-config); CL-02 any time.

## Model selection

All-Opus, high effort:

| Ticket | Why Opus |
|---|---|
| CL-01 | Squashes the canonical `public.*` baseline **and prunes columns** — the app boots against it and a wrong prune (a `SELECT *`/serializer dep) is a runtime break. Highest correctness stakes. |
| CL-03 | Cross-cutting config rename touching every settings module + the **fail-closed auth invariant**, plus deployment consolidation (chatbot intake, staging front door). |
| CL-02 | The accessible/voice **naming trap** — a wrong delete is a production outage on the complainant channel. |

No Sonnet, Haiku, or Fable.

## Best practices (carried forward)

- **One convention per concept.** After each ticket, `grep` proves the old spelling is *gone* (e.g. `TICKETING_ENV` → 0 hits post-CL-03).
- **Rebuild, don't reconcile** (0 records). CL-01 is a clean squashed baseline; still prove fresh migrate → seed → pytest → smoke works.
- **Prune only the provably-unused** (CL-01): ambiguous column usage (`SELECT *`, serializers, seed-by-position) → keep it; the full test + smoke run is the safety net.
- **Preserve security through the rename** (CL-03): HR-01 fail-closed is behavior-identical; only the variable/mechanism is canonical.
- **Never delete by name-match** (CL-02); grep for a live caller first.
- **De-risk order** (CL-03): re-point chatbot intake and verify *before* deleting the old API.
- Tests/verification as acceptance criteria; update [`../PROGRESS.md`](../PROGRESS.md) each commit.

## Common rules (all agents)

1. Read `CLAUDE.md` (migration policy + "change with care" boundaries), [`../README.md`](../README.md) (the canonical target table), [`../AUDIT_FINDINGS.md`](../AUDIT_FINDINGS.md), and your spec **before touching code**. Re-verify audit line numbers with grep.
2. Land on `dev/hardening`. Never `main`. Leave changes for orchestrator review unless told otherwise.
3. CL-01 = `migrations/public/` stream only. CL-03 must not weaken production security. Test on scratch DBs.
4. Deletions/prunes preceded by grep re-confirmation; if a "safe to delete/rename/prune" item has an unexpected live caller, STOP and log it.
5. Update [`../PROGRESS.md`](../PROGRESS.md) at every commit.
6. Commit messages: imperative, ticket ID first (e.g. `CL-03: collapse env-mode vars to a single APP_ENV`).
