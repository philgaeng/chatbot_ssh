# CL-04 — Canonical config & env

> Workstream: config-canonical · Branch/land on `dev/hardening` · **Run first** (the var scheme underpins CL-03 + CI).
> Evidence: [`AUDIT_FINDINGS.md`](AUDIT_FINDINGS.md) §4. **0 records** → rename/drop vars freely, no backward-compat.

---

## Goal

Replace the dev-phase env/config sprawl with one canonical convention per concept, while **preserving HR-01's fail-closed security property** (prod refuses to run without real auth; bypass only in explicit dev). After this ticket there is exactly one way to say each thing.

## The canonical scheme

| Concept | Canonical | Replaces |
|---|---|---|
| Environment | **`APP_ENV`** ∈ `dev` \| `staging` \| `production` (default `production`) | `TICKETING_ENV`, `BACKEND_ENV`, `ENVIRONMENT` |
| Auth mode | **`AUTH_MODE`** ∈ `keycloak` (default) \| `bypass`; `bypass` honored **only** when `APP_ENV=dev` | `NEXT_PUBLIC_BYPASS_AUTH` + `KEYCLOAK_ISSUER=""` + `*_ENV=dev` tangle |
| OIDC issuer | **`KEYCLOAK_ISSUER`** (one value); the frontend `NEXT_PUBLIC_OIDC_ISSUER` is **derived** from it at build, not hand-set | two hand-maintained names |
| Env template | one committed **`.env.example`** at repo root | `env.local`, `backend/utils/env.grm.example`, `channels/ticketing-ui/.env.local` |

**Security invariant (unchanged from HR-01, re-expressed):** in `keycloak` mode a missing `KEYCLOAK_ISSUER`/secret ⇒ refuse to start and 503 per request. `bypass` is impossible unless `APP_ENV=dev`. `production` can never bypass.

## Steps

1. **`APP_ENV` in the shared settings** (`ticketing/config/settings.py`, the backend settings/`os.environ` reads, `ops/config.py`): one field, default `production`, `is_dev = APP_ENV == "dev"`. Replace every `TICKETING_ENV`/`BACKEND_ENV`/`ENVIRONMENT` read. Grep must show those three gone.
2. **`AUTH_MODE`** in settings. Rewrite the dev-bypass gate: bypass is active iff `APP_ENV=="dev" and AUTH_MODE=="bypass"`. Re-express the HR-01 fail-closed guards (`dependencies.py` `_resolve_user_identity`/`verify_api_key`, `backend` `_assert_backend_auth_configured`/`_ticketing_auth_check`, `main._assert_auth_configured`) in terms of `AUTH_MODE`/`APP_ENV` instead of `KEYCLOAK_ISSUER==""`/`*_ENV`. Behavior identical; mechanism canonical.
3. **Single `KEYCLOAK_ISSUER`.** Frontend: derive `NEXT_PUBLIC_OIDC_ISSUER` from `KEYCLOAK_ISSUER` (compose build arg / a single source), don't hand-maintain a second value. Frontend bypass: one flag derived from `AUTH_MODE` at build (set `NEXT_PUBLIC_BYPASS_AUTH` from `AUTH_MODE==bypass` in one place, or rename to a single `NEXT_PUBLIC_AUTH_MODE`) — collapse the 4-var tangle to one derived switch.
4. **Compose cleanup:** delete `docker-compose.override.yml` (its only job — inject dev env — is now `APP_ENV=dev` in `.env`). Config comes from a single `.env` (copied from `.env.example`). Keep `docker-compose.yml` (base) + `docker-compose.grm.yml` + `docker-compose.prod.yml` + `docker-compose.aws.yml`; the demo/auth service split inside `grm.yml` is collapsed by **CL-03** — here just make every service read the canonical vars.
5. **One `.env.example`:** author a single root `.env.example` documenting every variable (backend, ticketing, ops, keycloak, frontend `NEXT_PUBLIC_*`, redis/db) with safe defaults and comments. Remove `env.local`, `backend/utils/env.grm.example`, `channels/ticketing-ui/.env.local` (or reduce the latter to a one-line pointer if Next requires a local file). Update `.gitignore` for the real `.env`.
6. **Makefile + CI + docs:** update Make targets, `.github/workflows/ci.yml` env (`APP_ENV=dev`, `AUTH_MODE=bypass`), and docs (`DOCKER.md`, `12_environment_urls.md`, `13_security.md`, `16_auth_keycloak.md`) to the canonical vars.
7. **Update the HR-01 tests** to the new vars: `tests/ticketing/test_fail_closed_auth.py`, `tests/ticketing/_host_env.py` — assert the same fail-closed guarantees via `APP_ENV`/`AUTH_MODE`.

## Verification (acceptance)

- [ ] `grep -rnE "\b(TICKETING_ENV|BACKEND_ENV|ENVIRONMENT|NEXT_PUBLIC_BYPASS_AUTH)\b"` across `backend/ ticketing/ ops/ channels/ docker-compose*.yml Makefile .github/` → **0 hits** (fully replaced), except intentional one-line derivations.
- [ ] `grep` shows one `.env.example`; `env.local`/`env.grm.example`/`ticketing-ui/.env.local` gone.
- [ ] **Fail-closed preserved:** `test_fail_closed_auth.py` green on `APP_ENV`/`AUTH_MODE`; a `production` + missing-issuer config refuses to start; `APP_ENV=production` can never bypass regardless of `AUTH_MODE`.
- [ ] **Dev bypass works:** `APP_ENV=dev AUTH_MODE=bypass` local bring-up logs in without Keycloak; `keycloak` mode does real OIDC.
- [ ] App + ticketing + ops all boot reading only canonical vars; `docker compose config` resolves with the single `.env`.

## Constraints

- Preserve the HR-01 fail-closed behavior exactly — only the variable names/mechanism change. Do not weaken production security.
- One convention per concept — no leaving the old var as an alias "just in case" (0 records; break cleanly).
- The deployed **topology** (which services, nginx, chatbot re-point) is CL-03 — CL-04 only makes everything read the canonical vars.

## Done means

One `APP_ENV`, one `AUTH_MODE`, one `KEYCLOAK_ISSUER`, one `.env.example`; old spellings return zero grep hits; fail-closed tests green on the new vars; dev bypass + keycloak mode both verified; [`PROGRESS.md`](PROGRESS.md) updated.
