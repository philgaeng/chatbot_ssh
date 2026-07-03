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
| `ticketing_api` | 5002 | Ticketing API — demo/bypass |
| `grm_ui` | 3001 | Officer UI — demo/bypass |
| `ticketing_api_auth` *(auth)* | 5003 | Ticketing API — Keycloak JWT |
| `grm_ui_auth` *(auth)* | 3002 | Officer UI — real OIDC |
| `keycloak` *(auth)* | 18080 (`KEYCLOAK_HOST_PORT`) | OIDC provider admin UI |
| `db` | 5433 (`POSTGRES_HOST_PORT`) | Postgres `app_db` (containers use `db:5432`) |
| `redis` | — | Broker/result backend (internal) |
| `celery_llm` / `celery_default` / `celery_file` / `grm_celery` / `grm_celery_beat` / `ops` | — | Workers / scheduler / monitor |

## Start / stop

Prefer the Makefile wrappers (`make help` for the full list):

```bash
make wsl-up            # chatbot + GRM demo :3001 + auth :3002
make wsl-demo-bypass   # GRM demo only (:3001/:5002, no Keycloak)
make wsl-auth          # auth stack only (:3002/:5003, Keycloak :18080)
make wsl-chatbot       # chatbot base stack only
make wsl-down          # stop everything (incl. auth profile)
```

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

`NEXT_PUBLIC_*` vars are compiled into the bundle; changing them requires rebuilding `grm_ui`/`grm_ui_auth`. Actual args (see `channels/ticketing-ui/Dockerfile` + `docker-compose.grm.yml`):

| Build arg | `grm_ui` (:3001) | `grm_ui_auth` (:3002) |
|---|---|---|
| `NEXT_PUBLIC_BYPASS_AUTH` | `"true"` (forced) | `"false"` |
| `NEXT_PUBLIC_OIDC_ISSUER` | `""` | `${NEXT_PUBLIC_OIDC_ISSUER:-http://localhost:18080/realms/grm}` |
| `NEXT_PUBLIC_OIDC_CLIENT_ID` | `ticketing-ui` | `${NEXT_PUBLIC_OIDC_CLIENT_ID:-ticketing-ui}` |
| `NEXT_PUBLIC_REDIRECT_SIGN_IN` / `_OUT` | `""` | from `env.local` |

There are **no Cognito vars** anymore. `TICKETING_API_URL` is a server-side **runtime** env (Next.js rewrites proxy all API calls — the browser only ever talks to :3001/:3002), so it does *not* require a rebuild.

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
