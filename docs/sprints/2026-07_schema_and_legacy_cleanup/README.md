# Sprint — July 2026: Schema Truth & Legacy Cleanup

> **Status: PLANNED** · Grew out of the hardening sprint's CI verification, which exposed that `public.*` can't be rebuilt from migrations. Evidence base: [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) (three read-only audits, July 2026).
> **Why it matters:** CL-01 is the blocker for the hardening sprint's "CI green" DoD — `backend-tests` dies at the seed step because the migration streams don't reproduce the app's schema. The other two tickets retire dead weight (legacy channels, the no-Keycloak demo stack) now that Keycloak login is live.

## Product-owner decisions (locked for this sprint)

1. **SEAH vault trio dropped** — `grievance_reveal_sessions`, `grievance_sensitive_access_audit`, `grievance_vault_payloads` are removed (0 rows, never wired; the real reveal-audit lives in `ticketing.*`).
2. **Demo retirement = full consolidation** — collapse the parallel demo/auth stacks into **one** ticketing-api + one ui service; re-point the chatbot intake to it; retire `grm_ui`:3001 + `ticketing_api`:5002.
3. **Keep the offline dev/CI bypass** — the `TICKETING_ENV=dev` bypass path stays so local dev, tests, and CI don't need a live Keycloak. Only the *deployed* demo-facing bypass is retired. (Decisions 2+3 reconcile: one deployed stack that is Keycloak in prod/staging and bypass-able in dev via env.)
4. **Rasa is legacy** — exclude `events` from the Alembic-managed set; add a note flagging a future Rasa-removal, but do **not** tackle Rasa here.

## Tickets

| ID | Title | Area | Effort | Spec |
|---|---|---|---|---|
| CL-01 | Public schema single source of truth (reconcile Alembic to live, drop base_manager DDL, drop dead tables, schema-diff gate) | migrations + backend | L | [01-public-schema-source-of-truth-spec.md](01-public-schema-source-of-truth-spec.md) |
| CL-02 | Remove legacy channels (`accessible` + `monitoring-gsheet`) and their exclusive backend | backend + deploy | M | [02-remove-legacy-channels-spec.md](02-remove-legacy-channels-spec.md) |
| CL-03 | Retire the demo app / consolidate onto a single Keycloak stack | deploy + auth + UI | L | [03-retire-demo-consolidate-auth-spec.md](03-retire-demo-consolidate-auth-spec.md) |

## Execution order & workstreams

Three runbooks in [`agents/`](agents/). **CL-01 first** — it unblocks CI and is the highest-risk (touches the whole public schema).

```
CL-01 schema truth   ← FIRST. Unblocks backend-tests; must land before we trust any CI run.
CL-02 legacy channels ← independent of CL-01 (tables it touches STAY); can run after CL-01.
CL-03 demo retirement ← independent; touches compose/nginx/UI/chatbot-intake, not the schema.
```

CL-02 and CL-03 are mutually independent. All three share the `backend/api/fastapi_app.py` startup file (CL-01 may touch base_manager wiring, CL-02 removes routers, CL-03 nothing there) — coordinate small diffs, land CL-01 first.

## Parallel-safety with the other active branches

- **`dev/hardening`** (the 7 hardening tickets) is the base this builds on — CL-01 is what finally makes its CI green. Branch this sprint off `dev/hardening` (or off `integration/seah-claude` once hardening merges), not off stale `main`.
- **`dev/organisation`** (org-chart) adds `ticketing.*` migrations — a *different* Alembic stream from CL-01's `public.*` work, so no head collision. But both are schema work; sequence deliberately and keep each stream's head linear.

## Conventions (binding for all agents)

- Branch per workstream off the agreed base: `cleanup/cl-01-schema`, `cleanup/cl-02-channels`, `cleanup/cl-03-demo`.
- **Never touch `main`.** See CLAUDE.md.
- CL-01 is **`public.*` (chatbot) schema** — the "change with care" boundary. Every DDL change is idempotent (`IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS`), reconciles **to the live shape**, and is proven by the schema-diff acceptance gate. Do not "fix" the live schema to match some ideal — match what the app runs.
- Deletions (CL-02/03) must be preceded by the grep-confirmation in `AUDIT_FINDINGS.md`; re-verify before removing. **Never delete by name-match** (the accessible/voice naming trap).
- Every ticket ships tests/verification as acceptance criteria. Update [`PROGRESS.md`](PROGRESS.md) at every commit.

## Model selection

All-Opus (high effort) — rationale in [`agents/README.md`](agents/README.md). Everything here is schema-critical (CL-01), live-channel deletion-safety-critical (CL-02, the naming trap), or auth/deployment-critical (CL-03). No Fable, no Haiku.

## Definition of done (sprint level)

- [ ] CL-01: a fresh-from-migrations `public` schema is **byte-identical** (pg_dump --schema-only diff = 0) to an app-bootstrapped one; base_manager no longer owns DDL; dead tables dropped; **CI `backend-tests` reaches and passes pytest**.
- [ ] CL-02: both legacy channels + exclusive backend removed; REST_webchat voice/socket/upload paths verified still working; no dead imports.
- [ ] CL-03: single deployed Keycloak stack; chatbot intake re-pointed and verified; staging front door on the auth UI; dev/CI bypass intact.
- [ ] Hardening sprint's CI is finally green end-to-end (the real reason CL-01 exists).
- [ ] `AUDIT_FINDINGS.md` decisions all actioned; future-Rasa-removal note filed.
