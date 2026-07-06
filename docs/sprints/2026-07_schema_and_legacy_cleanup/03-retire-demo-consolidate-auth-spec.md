# CL-03 — Consolidate deployment to one Keycloak stack

> Workstream: demo-retire · Branch/land on `dev/hardening` · **After CL-04** (consumes the canonical `APP_ENV`/`AUTH_MODE`/`KEYCLOAK_ISSUER`).
> Evidence: [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) §3. **0 records** → delete the demo stack outright, no data/back-compat.

---

## Goal

Collapse the parallel demo/auth deployment into **one** ticketing-api + one ui service — Keycloak in deployed envs, bypass-able in dev via CL-04's `AUTH_MODE`. Retire the no-auth demo (`grm_ui`:3001 + `ticketing_api`:5002), re-point the chatbot's ticket intake, and make the auth UI the staging front door. This is the **topology** half of the auth cleanup; CL-04 owns the **variable/settings** half.

## Steps (de-risk order matters)

1. **Chatbot intake first:** re-point `TICKETING_API_URL` (`ticketing_dispatch.py:20` + compose/env) off `ticketing_api:5002` to the single consolidated API. Confirm it accepts the `x-api-key` webhook identically (`create_ticket`→`verify_api_key`, auth-mode-independent) and **round-trip a real intake** before deleting :5002.
2. **Compose consolidation** (`docker-compose.grm.yml`, `.prod.yml`): delete the `grm_ui`:3001 and `ticketing_api`:5002 demo services; promote the former `_auth` services to the canonical `grm_ui` / `ticketing_api` (drop the `_auth` suffix and `profiles:[auth]`) — one ui, one api. Deployed overlays set `APP_ENV=production`/`staging` + `AUTH_MODE=keycloak` + real `KEYCLOAK_ISSUER` (CL-04 vars); the dev `.env` uses `APP_ENV=dev AUTH_MODE=bypass`. Remove the now-inert `grm_ui: profiles:[demo]` stub. (`docker-compose.override.yml` is already deleted by CL-04.)
3. **nginx — staging front door** (`webchat_rest_compose_aws.conf`): re-point the main-domain GRM routes (`/queue`, `/grm/`, `/ticketing/`, `/grm-api/`) from the demo `grm_ui:3001`/`ticketing_api:5002` to the single Keycloak UI/API — mirroring `webchat_rest_compose_prod.conf`. Reconcile `…wsl.conf` to the single local stack.
4. **Makefile:** update `TICKETING_SERVICES`, `AWS_DEPLOY_SERVICES(_LIGHT)`, port checks (:159-169,464-468), and `wsl-*`/`test-ticketing`/`wsl-seed` to the single service names/ports.
5. **Frontend bypass surface:** the bypass **code** (demo-login button, role switcher, cookie, proxy header injection) stays but is driven by CL-04's single derived switch and only active in `dev`. Ensure no deployed build enables bypass. Optionally hide the demo-login button unless bypass is on.
6. **Docs:** `16_auth_keycloak.md` (two instances → one), `DOCKER.md`, `01_architecture.md`, ticketing_system docs → one stack, dev-only bypass.
7. **Demo data (note, don't action):** `@grm.local` officers + `mock_tickets` are also in real Keycloak — purging them from deployed envs is a separate data decision.

## Verification (acceptance)

- [ ] **Chatbot intake** round-trips against the consolidated API; `grep -rn "5002\|ticketing_api_auth\|grm_ui_auth\|:3001"` clean (no live pointers/`_auth` names left).
- [ ] **One stack:** `docker compose config` shows one ui + one api, no `_auth`/`profiles:[auth]`/demo services; a `production`/`staging` build has no "Continue to demo queue".
- [ ] **Dev bypass intact** (via CL-04): `APP_ENV=dev AUTH_MODE=bypass` local bring-up logs in; `test_fail_closed_auth.py` passes; CI unaffected.
- [ ] Staging nginx serves the auth UI on the main domain (`nginx -t` if available); `make wsl-up`/`test-ticketing`/`wsl-seed` work against the single service.

## Constraints

- Re-point the chatbot BEFORE deleting :5002 (don't break intake or the pytest container).
- Consume CL-04's canonical vars — don't reintroduce `TICKETING_ENV`/`KEYCLOAK_ISSUER=""` bypass tricks.
- No Keycloak-realm/setup changes (`keycloak_setup.py` already works).

## Done means

One deployed Keycloak stack (no `_auth`/demo duplicates); chatbot intake re-pointed + verified; staging front door on the auth UI; dev bypass verified via `AUTH_MODE`; docs updated; [`PROGRESS.md`](PROGRESS.md) updated (demo-data purge as a pending decision).
