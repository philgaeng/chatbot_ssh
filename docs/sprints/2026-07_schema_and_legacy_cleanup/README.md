# Sprint — July 2026: Canonical Cleanup (schema, channels, config)

> **Status: PLANNED** · Grew out of the hardening sprint's CI verification (which exposed that `public.*` can't be rebuilt from migrations), then widened to canonicalize the dev-phase config sprawl. Evidence: [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md).
> **The unlock:** prod is **not live — 0 real records** (owner-confirmed). So we don't reconcile or preserve anything — we define the **canonical** shape and rebuild to it. Clean, canonical, bulletproof.

## What this sprint does

Remove the workarounds, fallbacks, and drift that accreted while the codebase was split across tools during the dev phase, and replace them with one canonical convention each:

- **Schema:** `public.*` becomes a single canonical Alembic baseline; the app-startup `CREATE TABLE` DDL (`base_manager.py`) is deleted; dead tables gone. (CL-01)
- **Channels:** the two legacy frontends (`accessible`, `monitoring-gsheet`) and their exclusive backend are deleted; REST_webchat's live voice/socket infra stays. (CL-02)
- **Deployment:** one Keycloak stack (retire the no-auth demo stack); chatbot intake re-pointed; staging front door on the auth UI. (CL-03)
- **Config/env:** one `APP_ENV`, one `AUTH_MODE`, one `KEYCLOAK_ISSUER`, one `.env.example`, clean compose — replacing the `TICKETING_ENV`/`BACKEND_ENV`/`NEXT_PUBLIC_BYPASS_AUTH`/`override.yml` tangle. (CL-04)

## Product-owner decisions (locked)

1. **0 records → canonical rebuild**, not reconciliation. Breaking changes are fine.
2. **SEAH vault trio dropped** (`grievance_reveal_sessions`, `grievance_sensitive_access_audit`, `grievance_vault_payloads`).
3. **One deployed Keycloak stack**; chatbot intake re-pointed off the demo API.
4. **Keep a single, clean dev/CI bypass** — one explicit `AUTH_MODE=bypass` honored only when `APP_ENV=dev`; deployed envs are always Keycloak and can never bypass (fail-closed preserved).
5. **Rasa is legacy** — exclude `events` from Alembic now; file a future Rasa-removal ticket.

## Canonical target (the end-state every ticket builds toward)

| Axis | From (mess) | To (canonical) |
|---|---|---|
| Env mode | `TICKETING_ENV` + `BACKEND_ENV` + `ENVIRONMENT` | one `APP_ENV` ∈ `dev`/`staging`/`production` |
| Auth | `NEXT_PUBLIC_BYPASS_AUTH` + `KEYCLOAK_ISSUER=""` + `*_ENV=dev` | one `AUTH_MODE` (`keycloak` default; `bypass` only if `APP_ENV=dev`) |
| OIDC issuer | `KEYCLOAK_ISSUER` + hand-kept `NEXT_PUBLIC_OIDC_ISSUER` | one `KEYCLOAK_ISSUER`; `NEXT_PUBLIC_` value derived |
| Deployed stack | demo (`:3001`/`:5002`) + auth (`:3002`/`:5003`) | one ui + one ticketing-api |
| Compose | 5 files incl. `override.yml` + `grm.yml` demo split | base + single `grm` overlay + `prod`/`aws`; no override/demo split |
| Env template | `env.local` + `env.grm.example` + `ticketing-ui/.env.local` | one committed `.env.example` |
| `public.*` schema | dual-owned + drifted | one canonical Alembic baseline; no app-startup DDL |

## Tickets

| ID | Title | Area | Effort | Spec |
|---|---|---|---|---|
| CL-01 | Canonical `public.*` schema (single Alembic baseline; drop base_manager DDL + dead tables) | migrations + backend | L | [01-public-schema-source-of-truth-spec.md](01-public-schema-source-of-truth-spec.md) |
| CL-02 | Remove legacy channels (`accessible` + `monitoring-gsheet`) + exclusive backend | backend + deploy | M | [02-remove-legacy-channels-spec.md](02-remove-legacy-channels-spec.md) |
| CL-03 | Consolidate deployment to one Keycloak stack (compose/nginx/chatbot-intake) | deploy | M | [03-retire-demo-consolidate-auth-spec.md](03-retire-demo-consolidate-auth-spec.md) |
| CL-04 | Canonical config & env (`APP_ENV`, `AUTH_MODE`, single issuer, one `.env.example`) | backend + ui + config | L | [04-canonical-config-and-env-spec.md](04-canonical-config-and-env-spec.md) |

## Execution order

```
CL-04 config/env   ← FIRST. The canonical APP_ENV/AUTH_MODE/issuer scheme underpins CL-03 (and CI).
CL-01 schema       ← unblocks CI backend-tests; independent of CL-04 (do in parallel or right after).
CL-03 deployment   ← after CL-04 (consumes APP_ENV/AUTH_MODE + single stack).
CL-02 channels     ← independent; any time.
```

Rationale for CL-04 first: the compose/stack/nginx work in CL-03 and the CI env both depend on the canonical variable scheme, so lock that in first to avoid re-touching compose twice.

## Parallel-safety with other branches

- Built on **`dev/hardening`** — this *is* the core-codebase cleanup, so it lands there (the schema/config are hardening concerns). CL-01 also finally makes hardening's CI green.
- **`dev/organisation`** (org-chart) adds `ticketing.*` migrations — a different Alembic stream from CL-01's `public.*`, no head collision. CL-04's `APP_ENV` rename touches shared settings modules — coordinate if org work reads them.

## Conventions (binding)

- Branch/land on `dev/hardening` (owner's call — this is core hardening). Never `main`.
- **0 records = rebuild, don't reconcile.** CL-01 is a clean canonical baseline, not an idempotent drift-patch. Still test that a fresh migrate → seed → pytest works.
- **One convention per concept.** After a ticket, `grep` must show the old spelling gone (e.g. `TICKETING_ENV`/`BACKEND_ENV` → 0 hits after CL-04), not coexisting with the new one.
- Deletions preceded by grep re-confirmation (the accessible/voice naming trap in AUDIT §2).
- Tests/verification as acceptance criteria; update [`PROGRESS.md`](PROGRESS.md) at every commit.

## Model selection

All-Opus — schema-critical (CL-01), live-channel deletion-safety (CL-02), deployment/auth-critical (CL-03), and cross-cutting config correctness with fail-closed security (CL-04). See [`agents/README.md`](agents/README.md). No Fable, no Haiku.

## Definition of done (sprint level)

- [ ] CL-01: fresh empty DB → migrations → **seed succeeds → pytest runs**; base_manager owns no DDL; one canonical public baseline; dead tables gone; schema-diff gate in CI.
- [ ] CL-04: `grep` shows one `APP_ENV`, one `AUTH_MODE`, one `KEYCLOAK_ISSUER`, one `.env.example`; the old spellings return zero hits; fail-closed preserved (prod refuses to bypass).
- [ ] CL-03: one deployed Keycloak stack; chatbot intake re-pointed + verified; staging front door on the auth UI.
- [ ] CL-02: both legacy channels + exclusive backend removed; REST_webchat voice/socket/upload verified intact.
- [ ] Hardening CI green end-to-end; future Rasa-removal ticket filed.
