# CL-03 — Canonical config, env & deployment consolidation

> Workstream: config-and-deploy · Branch/land on `dev/hardening` · Merged CL-04+CL-03 (they rewrite the same compose/auth surface — one pass, no inter-ticket rebase).
> Evidence: [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) §3 + §4. **0 records** → rename/drop vars and delete the demo stack outright. **Preserve HR-01's fail-closed security exactly.**

---

## Goal

One canonical convention per concept **and** one deployed Keycloak stack. After this: exactly one way to say each config thing, and exactly one ui + one ticketing-api (Keycloak in deployed envs, cleanly bypass-able in dev).

## The canonical scheme

| Concept | Canonical | Replaces |
|---|---|---|
| Environment | **`APP_ENV`** ∈ `dev`/`staging`/`production` (default `production`) | `TICKETING_ENV`, `BACKEND_ENV`, `ENVIRONMENT` |
| Auth mode | **`AUTH_MODE`** ∈ `keycloak` (default) \| `bypass`; bypass honored **only** when `APP_ENV=dev` | `NEXT_PUBLIC_BYPASS_AUTH` + `KEYCLOAK_ISSUER=""` + `*_ENV=dev` |
| OIDC issuer | one **`KEYCLOAK_ISSUER`**; frontend `NEXT_PUBLIC_OIDC_ISSUER` derived from it at build | two hand-kept names |
| Env template | one root **`.env.example`** | `env.local`, `env.grm.example`, `ticketing-ui/.env.local` |
| Deployed stack | one ui + one ticketing-api | demo (`:3001`/`:5002`) + auth (`:3002`/`:5003`) |
| Compose | base + single `grm` overlay + `prod`/`aws` | 5 files incl. `override.yml` + demo/auth split |

**Security invariant (unchanged from HR-01):** keycloak mode + missing issuer/secret ⇒ refuse start + 503; `production` can never bypass; bypass requires `APP_ENV=dev`.

## Part A — Config/env canonicalization

1. **`APP_ENV`** in shared settings (`ticketing/config/settings.py`, backend settings/`os.environ`, `ops/config.py`); `is_dev = APP_ENV=="dev"`. Replace every `TICKETING_ENV`/`BACKEND_ENV`/`ENVIRONMENT` read.
2. **`AUTH_MODE`**: bypass active iff `APP_ENV=="dev" and AUTH_MODE=="bypass"`. Re-express HR-01 guards (`dependencies.py` `_resolve_user_identity`/`verify_api_key`; backend `_assert_backend_auth_configured`/`_ticketing_auth_check`; `main._assert_auth_configured`) on `AUTH_MODE`/`APP_ENV` — behavior identical. Keep the (cleaned) bypass surface; it's now driven by this one flag.
3. **Single `KEYCLOAK_ISSUER`**; derive `NEXT_PUBLIC_OIDC_ISSUER` + the frontend bypass switch from it / `AUTH_MODE` (one source, compose build arg) — collapse the `NEXT_PUBLIC_BYPASS_AUTH` tangle.
4. **One root `.env.example`** documenting every var (backend/ticketing/ops/keycloak/frontend/redis/db) with defaults + comments; remove `env.local`, `backend/utils/env.grm.example`, `channels/ticketing-ui/.env.local`; fix `.gitignore`.
5. Update the HR-01 tests to new vars: `tests/ticketing/test_fail_closed_auth.py`, `_host_env.py`.

## Part B — Deployment consolidation

6. **Chatbot intake FIRST (de-risk):** re-point `TICKETING_API_URL` (`ticketing_dispatch.py:20` + compose/env) off `ticketing_api:5002` to the single consolidated API; confirm the `x-api-key` webhook works and **round-trip a real intake** before deleting :5002.
7. **Compose** (`docker-compose.grm.yml`, `.prod.yml`): delete `grm_ui`:3001 + `ticketing_api`:5002; promote `_auth` services to canonical `grm_ui`/`ticketing_api` (drop `_auth` suffix + `profiles:[auth]`) — one ui, one api. Delete `docker-compose.override.yml`. Deployed overlays set `APP_ENV=production`/`staging` + `AUTH_MODE=keycloak` + real `KEYCLOAK_ISSUER`; dev `.env` uses `APP_ENV=dev AUTH_MODE=bypass`. Remove the inert `grm_ui: profiles:[demo]` stub.
8. **nginx staging front door** (`webchat_rest_compose_aws.conf`): main-domain `/queue`,`/grm/`,`/ticketing/`,`/grm-api/` → the single Keycloak UI/API (mirror `…prod.conf`). Reconcile `…wsl.conf` to the single local stack.
9. **Makefile:** `TICKETING_SERVICES`, `AWS_DEPLOY_SERVICES(_LIGHT)`, port checks (:159-169,464-468), `wsl-*`/`test-ticketing`/`wsl-seed` → single service names/ports + canonical vars.
10. **Docs:** `DOCKER.md`, `12_environment_urls.md`, `13_security.md`, `16_auth_keycloak.md`, `01_architecture.md`, ticketing_system docs → one stack, one var scheme, dev-only bypass.
11. **Demo data (note, don't action):** `@grm.local` officers + `mock_tickets` purge is a separate data decision.

## Verification (acceptance)

- [ ] `grep -rnE "\b(TICKETING_ENV|BACKEND_ENV|ENVIRONMENT|NEXT_PUBLIC_BYPASS_AUTH)\b" backend/ ticketing/ ops/ channels/ docker-compose*.yml Makefile .github/` → **0 hits** (except intentional one-line derivations).
- [ ] One `.env.example`; the three old templates + `override.yml` gone.
- [ ] **Fail-closed preserved:** `test_fail_closed_auth.py` green on new vars; `production`+missing-issuer refuses to start; `APP_ENV=production` can never bypass.
- [ ] **Dev bypass works:** `APP_ENV=dev AUTH_MODE=bypass` logs in without Keycloak; `keycloak` mode does real OIDC.
- [ ] **One stack:** `docker compose config` shows one ui + one api, no `_auth`/`profiles:[auth]`/demo services, no `:5002`/`:3001`; a `production` build has no "Continue to demo queue".
- [ ] **Chatbot intake** round-trips against the consolidated API; `grep -rn "5002\|ticketing_api_auth\|grm_ui_auth\|:3001"` clean.
- [ ] Staging nginx serves the auth UI on the main domain (`nginx -t` if available); `make wsl-up`/`test-ticketing`/`wsl-seed` work.

## Constraints

- Preserve HR-01 fail-closed behavior exactly; one convention per concept, no compat aliases.
- Re-point chatbot BEFORE deleting :5002. No Keycloak-realm changes (`keycloak_setup.py` already works).

## Done means
One `APP_ENV`/`AUTH_MODE`/`KEYCLOAK_ISSUER`/`.env.example` (old spellings → 0 grep hits); fail-closed tests green on new vars; one deployed Keycloak stack; chatbot intake re-pointed + verified; dev bypass verified; docs updated; [`PROGRESS.md`](PROGRESS.md) updated (demo-data purge pending).
