# Agent runbook — CL-04: Canonical config & env

**Branch:** land on `dev/hardening` · **Model:** Opus (high effort — cross-cutting rename + fail-closed security) · **Spec:** [`../04-canonical-config-and-env-spec.md`](../04-canonical-config-and-env-spec.md) · Read [`README.md`](README.md) + [`../AUDIT_FINDINGS.md`](../AUDIT_FINDINGS.md) §4 first. **Run first — the var scheme underpins CL-03 + CI.**

**0 records → break cleanly.** Rename/drop vars with no backward-compat or aliases. But **preserve HR-01's fail-closed security exactly** — only the mechanism becomes canonical.

## Mission

Replace the dev-phase env/config sprawl with one canonical convention per concept: one `APP_ENV`, one `AUTH_MODE`, one `KEYCLOAK_ISSUER`, one `.env.example`. After this, there is exactly one way to say each thing.

## The scheme
- `APP_ENV` ∈ `dev`|`staging`|`production` (default `production`) — replaces `TICKETING_ENV`, `BACKEND_ENV`, `ENVIRONMENT`.
- `AUTH_MODE` ∈ `keycloak` (default) | `bypass`; **bypass honored only when `APP_ENV=dev`**.
- One `KEYCLOAK_ISSUER`; frontend `NEXT_PUBLIC_OIDC_ISSUER` + bypass flag **derived** from it / `AUTH_MODE` at build.
- One root `.env.example`.
- **Invariant:** keycloak mode + missing issuer/secret ⇒ refuse start + 503; `production` can never bypass.

## Steps
1. `APP_ENV` field in shared settings (`ticketing/config/settings.py`, backend settings/`os.environ`, `ops/config.py`); `is_dev = APP_ENV=="dev"`. Replace every `TICKETING_ENV`/`BACKEND_ENV`/`ENVIRONMENT` read.
2. `AUTH_MODE` field; bypass active iff `APP_ENV=="dev" and AUTH_MODE=="bypass"`. Re-express the HR-01 guards (`dependencies.py` `_resolve_user_identity`/`verify_api_key`; backend `_assert_backend_auth_configured`/`_ticketing_auth_check`; `main._assert_auth_configured`) on `AUTH_MODE`/`APP_ENV` — behavior identical.
3. Single `KEYCLOAK_ISSUER`; derive `NEXT_PUBLIC_OIDC_ISSUER` from it (compose build arg / one source); collapse the frontend `NEXT_PUBLIC_BYPASS_AUTH` tangle to one derived switch from `AUTH_MODE`.
4. Delete `docker-compose.override.yml` (dev config now via `APP_ENV=dev` in `.env`); make every compose service read the canonical vars. (The demo/auth service split in `grm.yml` is collapsed by CL-03.)
5. One root `.env.example` documenting every var (backend/ticketing/ops/keycloak/frontend/redis/db) with defaults + comments; remove `env.local`, `backend/utils/env.grm.example`, `channels/ticketing-ui/.env.local`; fix `.gitignore` for the real `.env`.
6. Update Makefile, `.github/workflows/ci.yml` env (`APP_ENV=dev`, `AUTH_MODE=bypass`), and docs (`DOCKER.md`, `12_environment_urls.md`, `13_security.md`, `16_auth_keycloak.md`).
7. Update `tests/ticketing/test_fail_closed_auth.py` + `tests/ticketing/_host_env.py` to assert the same guarantees via `APP_ENV`/`AUTH_MODE`.

## Verify (acceptance)
- `grep -rnE "\b(TICKETING_ENV|BACKEND_ENV|ENVIRONMENT|NEXT_PUBLIC_BYPASS_AUTH)\b" backend/ ticketing/ ops/ channels/ docker-compose*.yml Makefile .github/` → **0 hits** (except intentional one-line derivations).
- One `.env.example`; the three old templates gone.
- **Fail-closed preserved:** `test_fail_closed_auth.py` green on new vars; `production`+missing-issuer refuses to start; `APP_ENV=production` can never bypass.
- **Dev bypass works:** `APP_ENV=dev AUTH_MODE=bypass` logs in without Keycloak; `keycloak` mode does real OIDC. All services boot on canonical vars; `docker compose config` resolves with the single `.env`.

## Constraints
- Preserve HR-01 fail-closed behavior exactly. One convention per concept — no compat aliases. Topology (services/nginx/chatbot-repoint) is CL-03.

## Done means
One `APP_ENV`/`AUTH_MODE`/`KEYCLOAK_ISSUER`/`.env.example`; old spellings → 0 grep hits; fail-closed tests green on new vars; dev bypass + keycloak both verified; PROGRESS updated.
