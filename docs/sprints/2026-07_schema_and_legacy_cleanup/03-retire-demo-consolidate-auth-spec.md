# CL-03 — Retire the demo app / consolidate onto one Keycloak stack

> Workstream: demo-retire · Branch `cleanup/cl-03-demo` · Independent of CL-01/02.
> Evidence: [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) §3. Decisions: **full consolidation** (one stack) + **keep the offline dev/CI bypass**.

---

## Goal

Collapse the parallel demo/auth stacks into a **single** ticketing-api + ui service that runs **Keycloak in prod/staging** and stays **bypass-able in dev/CI** via `TICKETING_ENV=dev`. Retire the deployed no-Keycloak demo (`grm_ui`:3001 + `ticketing_api`:5002), re-point the chatbot's ticket intake, and make the auth UI the staging front door. Keep the dev/CI bypass code so local dev, tests, and CI don't need a live Keycloak.

## The reconciliation (decisions 2 + 3)

- **Deployed:** one stack, Keycloak only. The former `_auth` services become **the** services (drop the `_auth` suffix and `profiles:[auth]`); the former `grm_ui`:3001 / `ticketing_api`:5002 demo services are removed.
- **Dev/CI:** the same single service, run with `TICKETING_ENV=dev` (and `NEXT_PUBLIC_BYPASS_AUTH=true` for the UI build/runtime), gives the offline bypass. The bypass **code** stays; only the always-on deployed demo instances go.

## Steps

1. **Chatbot intake first (de-risk):** re-point `TICKETING_API_URL` from `http://ticketing_api:5002` to the consolidated API (`ticketing_dispatch.py:20` default + any compose/env). Confirm the consolidated API accepts the `x-api-key` webhook identically (`create_ticket` → `verify_api_key`, independent of auth mode — same code, so yes) **before** removing :5002. Verify a chatbot→ticketing intake round-trip.

2. **Compose consolidation** (`docker-compose.grm.yml`, `docker-compose.prod.yml`, `docker-compose.override.yml`):
   - Remove the `grm_ui`:3001 and `ticketing_api`:5002 demo services.
   - Promote `grm_ui_auth`→`grm_ui` (or the canonical name), `ticketing_api_auth`→`ticketing_api`; drop `profiles:[auth]` so it's the default stack. Keep a single port each.
   - Dev override keeps `TICKETING_ENV=dev` (+ `NEXT_PUBLIC_BYPASS_AUTH=true`) so local runs bypass; prod/staging overlays set real `KEYCLOAK_ISSUER` and `TICKETING_ENV≠dev`.
   - Remove the now-inert `grm_ui: profiles:[demo]` stub in prod.

3. **nginx — staging front door** (`deployment/nginx/webchat_rest_compose_aws.conf`): re-point the main-domain GRM routes (`/queue`, `/grm/`, `/ticketing/`, `/grm-api/`) from `grm_ui:3001`/`ticketing_api:5002` to the consolidated Keycloak UI/API — mirroring what `webchat_rest_compose_prod.conf` already does. Reconcile the `wsl` conf to the single local stack.

4. **Makefile:** update `TICKETING_SERVICES`, `AWS_DEPLOY_SERVICES`, `AWS_DEPLOY_LIGHT_SERVICES`, port checks (:159-169,464-468), and the `wsl-*`/`test-ticketing`/`wsl-seed` targets to the consolidated service names/ports. Preserve a `wsl` bypass path for offline dev.

5. **Keep the bypass code (dev/CI), retire only deployed usage:** leave `dependencies.py` dev-bypass (already HR-01-gated to `TICKETING_ENV=dev`), the frontend bypass surface (`app/login/page.tsx` demo button, `AuthProvider` cookie/roster/switcher, `AppShell`/`MobileAppHeader` role switchers, `app/api/v1/[...path]/route.ts` header injection), and `NEXT_PUBLIC_BYPASS_AUTH`. Ensure **no deployed build** sets `NEXT_PUBLIC_BYPASS_AUTH=true` or `TICKETING_ENV=dev`. (If you can cheaply hide the demo-login button unless bypass is on, do — but don't rip out the path.)

6. **Docs:** update `docs/deployment/16_auth_keycloak.md` ("two API/UI instances" → one), `DOCKER.md:138`, `13_security.md`, `01_architecture.md`, and the ticketing_system docs to describe the single stack + the dev-only bypass.

7. **Demo data (separate, optional):** the `@grm.local` officers + `mock_tickets` are also in real Keycloak — purging them from staging/prod is a **data** decision, not code. Note it in PROGRESS; do not action unless asked.

## Verification (acceptance)

- [ ] **Chatbot intake** works against the consolidated API (round-trip a submitted grievance → ticket created); the old :5002 is gone and nothing still points at it (`grep -rn "5002\|ticketing_api:" ` clean except history).
- [ ] **Deployed = Keycloak:** the consolidated UI requires real login (no "Continue to demo queue" in a prod/staging build); `docker compose config` shows one ui + one api, no `_auth`/`profiles:[auth]`/`grm_ui:3001`.
- [ ] **Dev/CI bypass intact:** `TICKETING_ENV=dev` local bring-up still logs in without Keycloak; `tests/ticketing/test_fail_closed_auth.py` + `_host_env.py` still pass; CI unaffected.
- [ ] Staging nginx serves the auth UI on the main domain (config reviewed; `nginx -t` if available).
- [ ] `make wsl-up` / `test-ticketing` / `wsl-seed` work against the renamed service.

## Constraints

- Re-point the chatbot BEFORE deleting :5002. Do not break intake or the pytest container.
- Keep the dev/CI bypass path working (decision 3) — this is not "remove all bypass," it's "remove the deployed demo stack."
- No change to the Keycloak realm/setup itself (`keycloak_setup.py`) — it already works.

## Done means

One deployed Keycloak stack; chatbot intake re-pointed + verified; staging front door on the auth UI; `grm_ui`:3001/`ticketing_api`:5002 gone; dev/CI bypass verified intact; docs updated; [`PROGRESS.md`](PROGRESS.md) updated (incl. the demo-data purge note as pending decision).
