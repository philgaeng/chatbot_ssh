# Docker — Build & Run Reference

**Status:** As-built, July 2026 — promoted and refreshed from `docs/sprints/archive/claude-tickets/DOCKER.md` (worktree-era; paths and the Cognito-era build-args table updated). Architecture/service map: [`01_architecture.md`](01_architecture.md). Setup runbook: [`02_setup.md`](02_setup.md).

> **All commands must run from WSL (Ubuntu), never Git Bash or a Windows terminal.**
> 1. UNC paths (`\\wsl.localhost\...`) break npm builds inside containers.
> 2. A Windows terminal can resolve the **wrong project directory**, creating containers under a different compose project name — your code changes get silently ignored.
>
> Repo root: `/home/philg/projects/nepal_chatbot` (compose project `nepal_chatbot`, containers `nepal_chatbot-<service>-1`).

Convenience: define `alias dcg='docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml'` — used below.

## Port map

| Service | Host port | What it is |
|---|---|---|
| `nginx` | 8080 | REST webchat + API proxy (WSL; 80/443 with aws/prod overlays) |
| `orchestrator` | 8000 | Conversation API (`POST /message`) |
| `backend` | 5001 | Grievance/files/messaging API |
| `ticketing_api` | 5002 | Ticketing API (single consolidated instance) — auth behaviour set by `AUTH_MODE` |
| `grm_ui` | 3001 | Officer UI (single consolidated instance) — auth behaviour set by `AUTH_MODE` |
| `keycloak` *(profile `auth`)* | 18080 (`KEYCLOAK_HOST_PORT`) | OIDC provider admin UI |
| `db` | 5433 (`POSTGRES_HOST_PORT`) | Postgres `app_db` (containers use `db:5432`) |
| `redis` | — | Broker/result backend (internal) |
| `celery_llm` / `celery_default` / `celery_file` / `grm_celery` / `grm_celery_beat` / `ops` | — | Workers / scheduler / monitor |

## Start / stop

Prefer the Makefile wrappers (`make help` for the full list):

```bash
make wsl-up            # chatbot + single GRM stack (:3001 UI / :5002 API, dev bypass)
make wsl-demo-bypass   # GRM only (:3001/:5002, APP_ENV=dev AUTH_MODE=bypass, no Keycloak)
make wsl-auth          # add Keycloak :18080 (set AUTH_MODE=keycloak + KEYCLOAK_ISSUER in env.local, rebuild)
make wsl-chatbot       # chatbot base stack only
make wsl-down          # stop everything (incl. auth profile)
```

`AUTH_MODE` (in `env.local`) selects the auth behaviour of the single `ticketing_api`/`grm_ui`
pair — there is no separate `_auth` stack. Keycloak is profile-gated (`profiles: [auth]`), so
only `--profile auth` / `make wsl-auth` starts it.

Raw compose:

```bash
dcg up -d                          # chatbot + GRM demo
dcg --profile auth up -d           # + Keycloak/auth services
dcg --profile auth down            # stop all
dcg --profile auth down -v         # stop + WIPE volumes (full reset)
```

## First-time setup (fresh clone / empty volume)

See [`02_setup.md`](02_setup.md) §3 for the full sequence: `wsl-chatbot` → `db_init` → `make migrate_all` → location + SEAH-provider seed → `make wsl-seed`. Quick verify:

```bash
curl http://localhost:5002/health      # {"status":"ok"}
curl "http://localhost:5002/api/v1/tickets?limit=5"
```

## Fail-closed auth env (HR-01)

Auth fails **closed**: outside explicit dev the services refuse to boot when their auth
prerequisites are unset (a missing env var must never silently authenticate everyone as
super_admin, nor disable the API-key check). Two canonical flags (CL-03), both defaulting
to the safe value:

| Env var | Values (default) | Effect |
|---|---|---|
| `APP_ENV` | `dev` \| `staging` \| `production` (**`production`**) | Only `dev` may permit the auth bypass; replaces the old `TICKETING_ENV`/`BACKEND_ENV`/`ENVIRONMENT` |
| `AUTH_MODE` | `keycloak` \| `bypass` (**`keycloak`**) | `bypass` honoured **only** when `APP_ENV=dev`; otherwise Keycloak JWT is enforced |

Bypass requires **both** `APP_ENV=dev` **and** `AUTH_MODE=bypass`. In any other combination
(and always under `staging`/`production`), `ticketing_api` refuses to start unless
`KEYCLOAK_ISSUER` **and** `TICKETING_SECRET_KEY` are set (RuntimeError at boot; per-request
`503` as defense in depth), and the `backend` grievance API refuses to start without an
API-key configured.

The local dev stack (`dcg` / `make wsl-demo-bypass` / `make wsl-up`) sets
`APP_ENV=dev AUTH_MODE=bypass` in **`env.local`** (read via `env_file` / `--env-file`) —
copy the root [`.env.example`](../../.env.example) to `env.local` and fill it in. There is
no `docker-compose.override.yml` any more; dev-ness comes from `env.local`, not an override
file. **Never** set `APP_ENV=dev` / `AUTH_MODE=bypass` in `docker-compose.grm.yml`, `aws`,
or `prod` overlays — production must fail closed. See [`13_security.md`](13_security.md)
"Fail-closed guarantees". If `ticketing_api` exits at boot with *"Refusing to start …
auth config is unset"*, set `APP_ENV=dev AUTH_MODE=bypass` in your `env.local`.

## Rebuild after code changes

Rebuild only what changed; `--no-cache` only when `requirements*.txt` changed.

```bash
# ticketing/ Python
dcg build ticketing_api && dcg up -d --force-recreate ticketing_api
# Celery worker shares the image — rebuild together
dcg build ticketing_api grm_celery grm_celery_beat && dcg up -d --force-recreate grm_celery grm_celery_beat
# backend/ or orchestrator Python
dcg build backend orchestrator && dcg up -d --force-recreate backend orchestrator
# Officer UI (channels/ticketing-ui/)
dcg build grm_ui && dcg up -d --force-recreate grm_ui
# nginx conf edits
make wsl-nginx
```

## Migrations (three streams)

```bash
make migrate_all          # ticketing → public → ops
make migrate_ticketing    # alembic -c ticketing/migrations/alembic.ini upgrade head
make migrate_public       # alembic -c migrations/public/alembic.ini upgrade head
make migrate_ops          # alembic -c ops/migrations/alembic.ini upgrade head

# History / current / new revision (example: ticketing stream)
dcg exec ticketing_api python -m alembic -c ticketing/migrations/alembic.ini current
dcg exec ticketing_api python -m alembic -c ticketing/migrations/alembic.ini history
dcg exec ticketing_api python -m alembic -c ticketing/migrations/alembic.ini revision --autogenerate -m "change"
```

Each stream is schema-scoped (`include_object`) — see [`07_migrations_policy.md`](07_migrations_policy.md).

## Seed / demo data

```bash
make wsl-seed                 # GRM demo tickets (mock_tickets --reset): DOR/ADB orgs, roles,
                              # KL Road standard + SEAH workflows, demo tickets
make seed_seah_providers      # SEAH support centres from committed CSV
make keycloak-setup           # grm realm + demo officers (auth stack)
```

## Logs & debugging

```bash
dcg logs -f ticketing_api grm_celery grm_celery_beat grm_ui     # follow GRM services
dcg logs --tail=100 ticketing_api                               # last 100 lines
dcg exec ticketing_api bash                                     # shell in API container
dcg exec db psql -U user -d app_db                              # psql
dcg exec db psql -U user -d app_db -c "\dt ticketing.*"         # ticketing tables
dcg exec grm_celery celery -A ticketing.tasks.celery_app.celery_app inspect active
```

## UI build args (Next.js — baked at build time)

`NEXT_PUBLIC_*` vars are compiled into the bundle; changing them requires rebuilding the single `grm_ui`. They are **derived** from the canonical `AUTH_MODE` / `KEYCLOAK_ISSUER` at build time (compose build args) — there is no separate hand-kept frontend issuer var and no `NEXT_PUBLIC_BYPASS_AUTH`. Actual args (see `channels/ticketing-ui/Dockerfile` + `docker-compose.grm.yml`):

| Build arg | Source | Effect |
|---|---|---|
| `NEXT_PUBLIC_AUTH_MODE` | `${AUTH_MODE:-keycloak}` | Mirrors `AUTH_MODE`; read via `channels/ticketing-ui/lib/auth/runtime-config.ts` |
| `NEXT_PUBLIC_OIDC_ISSUER` | `${KEYCLOAK_ISSUER:-}` | Derived from `KEYCLOAK_ISSUER` (empty under dev bypass) |
| `NEXT_PUBLIC_OIDC_CLIENT_ID` | `${KEYCLOAK_CLIENT_ID:-ticketing-ui}` | OIDC public client |
| `NEXT_PUBLIC_REDIRECT_SIGN_IN` / `_OUT` | from `env.local` | Post-login/logout redirects |

There are **no Cognito vars** anymore. `TICKETING_API_URL` is a server-side **runtime** env (Next.js rewrites proxy all API calls — the browser only ever talks to :3001), so it does *not* require a rebuild.

## Tests

```bash
make test-ticketing        # pytest tests/ticketing/ inside ticketing_api container (preferred)
make test-ticketing-host   # host pytest — needs `make dev-grm-deps` + db published on :5433
make test-ticketing-unit   # host unit tests, no DB
```

Host pytest uses port **5433** (compose `db`) — a different Postgres on host :5432 will cause auth failures/hangs. Rebuild `ticketing_api` before container tests if `ticketing/` changed.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `invalid file request node_modules/.bin/acorn` | compose run from Git Bash / Windows path | Use a WSL terminal |
| Code change deployed but behaviour unchanged | Built from wrong directory / stale project name | Rebuild from the repo root in WSL; check `docker ps` container names start with `nepal_chatbot-` |
| `ticketing_api` exits immediately / `relation "ticketing.tickets" does not exist` | Migrations not applied | `make migrate_all` |
| `grm_ui` blank page / 500 | Next.js build failed (bad build args) | `dcg logs grm_ui` |
| Celery tasks not running | `grm_celery_beat` down | Ensure both `grm_celery` and `grm_celery_beat` are up |
| Seed warns about locations | Geodata not imported | Run `import_locations_json` ([`02_setup.md`](02_setup.md) §3); warning is non-fatal |
| Port already in use | Old containers running | `make wsl-down` first (nginx uses :8080, Keycloak :18080 to dodge it) |
| Keycloak / invite issues | — | See [`16_auth_keycloak.md`](16_auth_keycloak.md) §6 |
| QR scan `422 package_has_no_location` | Package has no `ticketing.package_locations` rows | Settings UI → Packages → attach a location |
| QR URL points at wrong host | `CHATBOT_WEBCHAT_URL` unset/stale in `ticketing_api` | Set in `env.local`, recreate `ticketing_api` |

*Keep this file updated when compose topology changes (new services, port changes, new env vars).*
