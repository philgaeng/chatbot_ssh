# Sprint — July 2026: Canonical Cleanup (schema, channels, config)

**Audience:** internal — excluded from the public repository (lifecycle §10.4).

> **Status: PLANNED** · Grew out of the hardening sprint's CI verification (which exposed that `public.*` can't be rebuilt from migrations), then widened to canonicalize the dev-phase config sprawl. Evidence: [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md).
> **The unlock:** prod is **not live — 0 real records** (owner-confirmed). So we don't reconcile or preserve anything — we define the **canonical** shape and rebuild to it. Clean, canonical, bulletproof.

## What this sprint does

Remove the workarounds, fallbacks, and drift that accreted while the codebase was split across tools during the dev phase, and replace each with one canonical convention:

- **Schema (CL-01):** squash the drifted public migrations into **one** canonical Alembic baseline, delete the app-startup `CREATE TABLE` DDL, drop dead tables **and prune unused columns**.
- **Channels (CL-02):** delete the two legacy frontends (`accessible`, `monitoring-gsheet`) + their exclusive backend; REST_webchat's live voice/socket infra stays.
- **Config + deployment (CL-03):** one `APP_ENV`, one `AUTH_MODE`, one `KEYCLOAK_ISSUER`, one `.env.example`, **and** one Keycloak stack (retire the demo stack; re-point chatbot intake).

## Product-owner decisions (locked)

1. **0 records → canonical rebuild**, not reconciliation.
2. **Schema:** **squash** to one baseline **and prune unused columns/tables** (audit-justified). Dead tables incl. the **SEAH vault trio** dropped.
3. **Auth:** **keep one clean dev-only bypass** — a single `AUTH_MODE=bypass` honored only when `APP_ENV=dev`; deployed is always Keycloak, can never bypass (HR-01 fail-closed preserved). Config + deployment are **one combined ticket** (CL-03).
4. **Rasa is legacy** — exclude `events` from Alembic now; file a future Rasa-removal ticket.

## Canonical target (the end-state every ticket builds toward)

| Axis | From (mess) | To (canonical) |
|---|---|---|
| Env mode | `TICKETING_ENV` + `BACKEND_ENV` + `ENVIRONMENT` | one `APP_ENV` ∈ `dev`/`staging`/`production` |
| Auth | `NEXT_PUBLIC_BYPASS_AUTH` + `KEYCLOAK_ISSUER=""` + `*_ENV=dev` | one `AUTH_MODE` (`keycloak` default; `bypass` only if `APP_ENV=dev`) |
| OIDC issuer | `KEYCLOAK_ISSUER` + hand-kept `NEXT_PUBLIC_OIDC_ISSUER` | one `KEYCLOAK_ISSUER`; `NEXT_PUBLIC_` value derived |
| Deployed stack | demo (`:3001`/`:5002`) + auth (`:3002`/`:5003`) | one ui + one ticketing-api |
| Compose | 5 files incl. `override.yml` + `grm.yml` demo split | base + single `grm` overlay + `prod`/`aws`; no override/demo split |
| Env template | `env.local` + `env.grm.example` + `ticketing-ui/.env.local` | one committed `.env.example` |
| `public.*` schema | dual-owned + drifted, unused columns | one squashed canonical baseline, used columns only |

## Tickets

| ID | Title | Area | Effort | Spec |
|---|---|---|---|---|
| CL-01 | Canonical `public.*` schema (squashed baseline + column prune; drop DDL + dead tables) | migrations + backend | L | [01-public-schema-source-of-truth-spec.md](01-public-schema-source-of-truth-spec.md) |
| CL-02 | Remove legacy channels (`accessible` + `monitoring-gsheet`) + exclusive backend | backend + deploy | M | [02-remove-legacy-channels-spec.md](02-remove-legacy-channels-spec.md) |
| CL-03 | Canonical config, env & deployment consolidation (`APP_ENV`/`AUTH_MODE`/issuer/`.env.example` + one Keycloak stack) | backend + ui + deploy | L | [03-canonical-config-and-deployment-spec.md](03-canonical-config-and-deployment-spec.md) |

## Execution order

Two mostly-independent tracks + one anytime:

```
CL-01 schema   ← unblocks CI backend-tests (the reason this sprint exists). Independent of the var names.
CL-03 config+deploy ← the canonical var scheme + single stack. Touches auth/compose/nginx.
CL-02 channels ← independent; any time.
```

CL-01 and CL-03 are largely independent (CL-01 uses `APP_ENV` if CL-03 landed first, else the current vars + a follow-up note). Sequence by priority: **CL-01 first if getting CI green is the priority**, **CL-03 first if locking the canonical config is**. They can also run in parallel with coordination on the shared CI file.

## Parallel-safety with other branches

- Built on **`dev/hardening`** — this *is* the core-codebase cleanup, so it lands there (owner's call). CL-01 also finally makes hardening's CI green.
- **`dev/organisation`** (org-chart) adds `ticketing.*` migrations — a different Alembic stream from CL-01's `public.*`, no head collision. CL-03's `APP_ENV` rename touches shared settings modules — coordinate if org work reads them.
- **Branch size:** `dev/hardening` will carry 7 hardening + 3 cleanup tickets before merging. Plan a merge to `integration` once CL-01 makes CI green, rather than piling higher.

## Conventions (binding)

- Land on `dev/hardening`. Never `main`.
- **0 records = rebuild, don't reconcile.** Still prove a fresh migrate → seed → pytest works.
- **One convention per concept.** After a ticket, `grep` must show the old spelling *gone* (e.g. `TICKETING_ENV` → 0 hits after CL-03), not coexisting.
- **Prune only the provably-unused** (CL-01): when a column's usage is ambiguous (`SELECT *`, serializers, seed-by-position), keep it. The full test + smoke run is the safety net.
- Deletions preceded by grep re-confirmation (the accessible/voice naming trap, AUDIT §2).
- Tests/verification as acceptance criteria; update [`PROGRESS.md`](PROGRESS.md) at every commit.

## Model selection

All-Opus — schema-critical + column-prune correctness (CL-01), live-channel deletion-safety (CL-02), cross-cutting config with fail-closed security + deployment (CL-03). See [`agents/README.md`](agents/README.md). No Fable, no Haiku.

## Definition of done (sprint level)

- [ ] CL-01: fresh empty DB → migrations → **seed succeeds → pytest + smoke green**; one squashed baseline, used columns only, `prune_audit.md` committed; base_manager owns no DDL; self-consistency gate in CI.
- [ ] CL-03: `grep` shows one `APP_ENV`/`AUTH_MODE`/`KEYCLOAK_ISSUER`/`.env.example` (old spellings → 0 hits); fail-closed preserved (prod refuses bypass); one deployed Keycloak stack; chatbot intake re-pointed + verified.
- [ ] CL-02: both legacy channels + exclusive backend removed; REST_webchat voice/socket/upload verified intact.
- [ ] Hardening CI green end-to-end; future Rasa-removal ticket filed.
