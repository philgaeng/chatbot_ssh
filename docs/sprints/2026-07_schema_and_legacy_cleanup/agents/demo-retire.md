# Agent runbook — CL-03: Consolidate deployment to one Keycloak stack

**Branch:** land on `dev/hardening` · **Model:** Opus (high effort — auth + deployment + chatbot-intake) · **Spec:** [`../03-retire-demo-consolidate-auth-spec.md`](../03-retire-demo-consolidate-auth-spec.md) · Read [`README.md`](README.md) + [`../AUDIT_FINDINGS.md`](../AUDIT_FINDINGS.md) §3 first. **After CL-04** (consumes `APP_ENV`/`AUTH_MODE`/`KEYCLOAK_ISSUER`).

**0 records → delete the demo stack outright.** This is the topology half; CL-04 owns the variable half.

## Mission
Collapse the parallel demo/auth deployment into ONE ticketing-api + one ui — Keycloak in deployed envs, bypass-able in dev via CL-04's `AUTH_MODE`. Retire `grm_ui`:3001 + `ticketing_api`:5002, re-point chatbot intake, make the auth UI the staging front door.

## Steps (de-risk order matters)
1. **Chatbot intake FIRST:** re-point `TICKETING_API_URL` (`ticketing_dispatch.py:20` + compose/env) off `ticketing_api:5002` to the single consolidated API; confirm `x-api-key` webhook works identically and **round-trip a real intake** before deleting :5002.
2. **Compose** (`docker-compose.grm.yml`, `.prod.yml`): delete `grm_ui`:3001 + `ticketing_api`:5002; promote `_auth` services to canonical `grm_ui`/`ticketing_api` (drop `_auth` suffix + `profiles:[auth]`). Deployed overlays set `APP_ENV=production`/`staging` + `AUTH_MODE=keycloak` + real `KEYCLOAK_ISSUER`; dev `.env` uses `APP_ENV=dev AUTH_MODE=bypass`. Remove the inert `grm_ui: profiles:[demo]` stub. (`override.yml` already deleted by CL-04.)
3. **nginx staging front door** (`webchat_rest_compose_aws.conf`): main-domain `/queue`,`/grm/`,`/ticketing/`,`/grm-api/` → the single Keycloak UI/API (mirror `…prod.conf`). Reconcile `…wsl.conf` to the single local stack.
4. **Makefile:** `TICKETING_SERVICES`, `AWS_DEPLOY_SERVICES(_LIGHT)`, port checks (:159-169,464-468), `wsl-*`/`test-ticketing`/`wsl-seed` → single service names/ports.
5. **Frontend bypass surface** stays (demo-login button, role switcher, cookie, proxy header injection) but driven by CL-04's single derived switch, active only in dev; no deployed build enables it.
6. **Docs:** `16_auth_keycloak.md` (two→one), `DOCKER.md`, `01_architecture.md`, ticketing_system docs → one stack, dev-only bypass.
7. **Demo data:** note (don't action) — `@grm.local` officers + `mock_tickets` purge is a separate data decision.

## Verify (acceptance)
- Chatbot intake round-trips against the consolidated API; `grep -rn "5002\|ticketing_api_auth\|grm_ui_auth\|:3001"` clean.
- `docker compose config` = one ui + one api, no `_auth`/`profiles:[auth]`/demo; a `production` build has no "Continue to demo queue".
- Dev bypass intact via `AUTH_MODE` (`APP_ENV=dev AUTH_MODE=bypass` logs in); `test_fail_closed_auth.py` passes; CI unaffected.
- Staging nginx serves auth UI on the main domain (`nginx -t` if available); `make wsl-up`/`test-ticketing`/`wsl-seed` work.

## Constraints
- Re-point chatbot BEFORE deleting :5002. Consume CL-04's canonical vars (no `TICKETING_ENV`/`KEYCLOAK_ISSUER=""` tricks). No Keycloak-realm changes.

## Done means
One deployed Keycloak stack (no `_auth`/demo); chatbot intake re-pointed + verified; staging front door on auth UI; dev bypass verified via `AUTH_MODE`; docs updated; PROGRESS updated (demo-data purge pending).
