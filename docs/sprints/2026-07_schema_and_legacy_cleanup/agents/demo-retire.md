# Agent runbook — CL-03: Retire demo app / consolidate auth

**Branch:** `cleanup/cl-03-demo` off the agreed base · **Model:** Opus (high effort — auth + deployment + chatbot-intake) · **Spec:** [`../03-retire-demo-consolidate-auth-spec.md`](../03-retire-demo-consolidate-auth-spec.md) · Read [`README.md`](README.md) + [`../AUDIT_FINDINGS.md`](../AUDIT_FINDINGS.md) §3 first.

## Mission

Collapse the parallel demo/auth stacks into ONE ticketing-api + ui service that is **Keycloak in prod/staging** and **bypass-able in dev/CI** (`TICKETING_ENV=dev`). Retire the deployed demo (`grm_ui`:3001 + `ticketing_api`:5002), re-point chatbot intake, make the auth UI the staging front door. **Keep** the dev/CI bypass code.

## Steps (de-risk order matters)

1. **Chatbot intake FIRST:** re-point `TICKETING_API_URL` (`ticketing_dispatch.py:20` + compose/env) from `ticketing_api:5002` to the consolidated API. Confirm it accepts the `x-api-key` webhook identically (`create_ticket`→`verify_api_key`, auth-mode-independent) and **round-trip a real intake** BEFORE removing :5002.
2. **Compose consolidation** (`docker-compose.grm.yml`, `.prod.yml`, `.override.yml`): remove `grm_ui`:3001 + `ticketing_api`:5002; promote `grm_ui_auth`→canonical `grm_ui`, `ticketing_api_auth`→`ticketing_api`, drop `profiles:[auth]`. Dev override keeps `TICKETING_ENV=dev` (+ `NEXT_PUBLIC_BYPASS_AUTH=true`); prod/staging set real `KEYCLOAK_ISSUER` + `TICKETING_ENV≠dev`. Remove the inert `grm_ui: profiles:[demo]` stub.
3. **nginx staging front door** (`webchat_rest_compose_aws.conf`): main-domain `/queue`,`/grm/`,`/ticketing/`,`/grm-api/` → consolidated Keycloak UI/API (mirror `…prod.conf`). Reconcile `…wsl.conf` to the single local stack.
4. **Makefile:** update `TICKETING_SERVICES`, `AWS_DEPLOY_SERVICES(_LIGHT)`, port checks (:159-169,464-468), `wsl-*`/`test-ticketing`/`wsl-seed` to the consolidated names/ports; preserve a wsl bypass path.
5. **Keep bypass code (dev/CI):** leave `dependencies.py` dev-bypass (HR-01-gated), the frontend bypass surface (`app/login/page.tsx`, `AuthProvider`, `AppShell`/`MobileAppHeader` switchers, `app/api/v1/[...path]/route.ts`), `NEXT_PUBLIC_BYPASS_AUTH`. Ensure **no deployed build** enables bypass. Optionally hide the demo-login button unless bypass is on — but don't remove the path.
6. **Docs:** `16_auth_keycloak.md` (two→one instance), `DOCKER.md`, `13_security.md`, `01_architecture.md`, ticketing_system docs → single stack + dev-only bypass.
7. **Demo data:** note (don't action) that `@grm.local` officers + `mock_tickets` purge from deployed envs is a separate data decision (they're also in real Keycloak).

## Verify (acceptance)
- Chatbot intake round-trips against the consolidated API; `grep -rn "ticketing_api:5002\|:5002"` clean (no live pointers).
- `docker compose config` shows one ui + one api, no `_auth`/`profiles:[auth]`/`grm_ui:3001`; a prod/staging build has no "Continue to demo queue".
- Dev/CI bypass intact: `TICKETING_ENV=dev` local login works; `test_fail_closed_auth.py` + `_host_env.py` pass; CI unaffected.
- Staging nginx serves auth UI on the main domain (`nginx -t` if available); `make wsl-up`/`test-ticketing`/`wsl-seed` work.

## Constraints
- Re-point chatbot BEFORE deleting :5002. Keep the dev/CI bypass working (decision 3 — this is NOT "remove all bypass"). No Keycloak-realm/setup changes.

## Done means
One deployed Keycloak stack; chatbot intake re-pointed + verified; staging front door on auth UI; `grm_ui`:3001/`ticketing_api`:5002 gone; dev/CI bypass verified intact; docs updated; PROGRESS updated (demo-data purge as pending decision).
