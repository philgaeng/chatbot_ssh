# Agent runbook — CL-03: Canonical config, env & deployment

**Branch:** land on `dev/hardening` · **Model:** Opus (high effort — cross-cutting rename + fail-closed security + deployment) · **Spec:** [`../03-canonical-config-and-deployment-spec.md`](../03-canonical-config-and-deployment-spec.md) · Read [`README.md`](README.md) + [`../AUDIT_FINDINGS.md`](../AUDIT_FINDINGS.md) §3+§4 first.

**0 records → break cleanly** (rename/drop vars, delete the demo stack) but **preserve HR-01's fail-closed security exactly**. This is one ticket covering the config rename AND the stack consolidation (they touch the same compose/auth surface — do it in one pass).

## Mission
One canonical convention per concept (`APP_ENV`, `AUTH_MODE`, single `KEYCLOAK_ISSUER`, one `.env.example`) and one deployed Keycloak stack (retire the demo `grm_ui`:3001/`ticketing_api`:5002; keep a clean dev-only bypass via `AUTH_MODE`).

## Part A — config/env (do first)
1. `APP_ENV` ∈ dev/staging/production (default production) in shared settings — replace every `TICKETING_ENV`/`BACKEND_ENV`/`ENVIRONMENT`.
2. `AUTH_MODE` (keycloak default; bypass iff `APP_ENV=dev`). Re-express the HR-01 guards (`dependencies.py`, backend `_assert_backend_auth_configured`/`_ticketing_auth_check`, `main._assert_auth_configured`) on it — behavior identical. Keep the cleaned bypass surface, driven by this one flag.
3. Single `KEYCLOAK_ISSUER`; derive `NEXT_PUBLIC_OIDC_ISSUER` + the frontend bypass switch from it/`AUTH_MODE` (one source, build arg).
4. One root `.env.example`; delete `env.local`, `backend/utils/env.grm.example`, `channels/ticketing-ui/.env.local`; fix `.gitignore`.
5. Update `tests/ticketing/test_fail_closed_auth.py` + `_host_env.py` to the new vars.

## Part B — deployment (de-risk order)
6. **Chatbot intake FIRST:** re-point `TICKETING_API_URL` (`ticketing_dispatch.py:20`+compose) off `:5002` to the single API; round-trip a real intake BEFORE deleting :5002.
7. Compose: delete `grm_ui`:3001 + `ticketing_api`:5002 + `docker-compose.override.yml`; promote `_auth`→canonical `grm_ui`/`ticketing_api` (drop suffix + `profiles:[auth]`). Deployed sets `APP_ENV`/`AUTH_MODE=keycloak`/real issuer; dev `.env` = `APP_ENV=dev AUTH_MODE=bypass`.
8. nginx: `webchat_rest_compose_aws.conf` main domain → single Keycloak UI/API (mirror `…prod.conf`); reconcile `…wsl.conf`.
9. Makefile: services/ports/targets → single stack + canonical vars.
10. Docs: `16_auth_keycloak.md`/`DOCKER.md`/`13_security.md`/`12_environment_urls.md`/`01_architecture.md` → one stack, one var scheme, dev-only bypass.

## Verify (acceptance)
- `grep -rnE "\b(TICKETING_ENV|BACKEND_ENV|ENVIRONMENT|NEXT_PUBLIC_BYPASS_AUTH)\b" backend/ ticketing/ ops/ channels/ docker-compose*.yml Makefile .github/` → **0 hits**.
- One `.env.example`; old templates + `override.yml` gone. `docker compose config` = one ui + one api, no `_auth`/demo/`:5002`/`:3001`.
- Fail-closed preserved: `test_fail_closed_auth.py` green on new vars; prod+missing-issuer refuses start; `APP_ENV=production` never bypasses.
- Dev bypass works (`APP_ENV=dev AUTH_MODE=bypass` logs in); keycloak mode does real OIDC.
- Chatbot intake round-trips against the single API; staging nginx serves auth UI on the main domain; `make wsl-up`/`test-ticketing` work.

## Constraints
- Preserve HR-01 fail-closed exactly; one convention per concept, no compat aliases. Re-point chatbot before deleting :5002. No Keycloak-realm changes.

## Done means
Canonical vars (old spellings → 0 grep hits); one `.env.example`; one deployed Keycloak stack; fail-closed tests green; chatbot intake re-pointed + verified; dev bypass verified; docs updated; PROGRESS updated.
