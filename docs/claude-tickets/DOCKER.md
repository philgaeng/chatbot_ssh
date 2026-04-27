# GRM Ticketing — Docker Build & Run Reference

> **All commands must be run from WSL (Ubuntu), never from Git Bash or a Windows terminal.**
> Two reasons:
> 1. UNC paths like `\\wsl.localhost\...` cause npm/acorn build failures inside containers.
> 2. Running `docker compose` from a Windows terminal picks up the **wrong project directory** — containers get created as `nepal_chatbot-*` instead of `nepal_chatbot_claude-*`, meaning they use a stale image from a different repo copy and your code changes are silently ignored.
>
> Always use: `wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && docker compose ..."`

---

## Port map

| Service | Container name | Host port | What it is |
|---------|---------------|-----------|------------|
| `ticketing_api` | `nepal_chatbot_claude-ticketing_api-1` | 5002 | FastAPI — ticketing backend |
| `grm_ui` | `nepal_chatbot_claude-grm_ui-1` | 3001 | Next.js — officer UI |
| `grm_celery` | `nepal_chatbot_claude-grm_celery-1` | — | Celery worker (SLA watchdog + sync) |
| `grm_celery_beat` | `nepal_chatbot_claude-grm_celery_beat-1` | — | Celery Beat scheduler |
| `db` | `nepal_chatbot_claude-db-1` | 5433 (host) | Postgres (`app_db`) |
| `redis` | `nepal_chatbot_claude-redis-1` | 6379 | Broker + result backend |

`db` and `redis` are defined in `docker-compose.yml` (DO NOT TOUCH).
GRM services are defined in `docker-compose.grm.yml` (overlay).

---

## First-time setup (fresh clone or reset)

```bash
# 1. Open a WSL terminal
wsl -d Ubuntu

# 2. Go to repo root
cd /home/philg/projects/nepal_chatbot_claude

# 3. Build all GRM images (takes ~3-5 min first time)
docker compose -f docker-compose.yml -f docker-compose.grm.yml build

# 4. Start everything
docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d

# 5. Run Alembic migrations (ticketing.* schema only)
docker exec nepal_chatbot_claude-ticketing_api-1 \
  python -m alembic -c ticketing/migrations/alembic.ini upgrade head

# 6. Seed demo data
docker exec nepal_chatbot_claude-ticketing_api-1 \
  python -m ticketing.seed.mock_tickets --reset

# 7. Verify
curl http://localhost:5002/health
# → {"status":"ok"}
# Open http://localhost:3001 in browser
```

---

## Normal start / stop

```bash
# Start (from WSL)
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d"

# Stop (keeps volumes/data)
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml down"

# Stop + wipe all data (full reset)
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml down -v"
```

---

## Rebuild after code changes

Rebuild only the service that changed — don't rebuild everything unless deps changed.

```bash
# Rebuild ticketing API (Python changes in ticketing/)
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml build ticketing_api && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d --force-recreate ticketing_api"

# Rebuild Celery worker (same image as ticketing_api — rebuild both)
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml build ticketing_api grm_celery grm_celery_beat && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d --force-recreate grm_celery grm_celery_beat"

# Rebuild UI (Next.js changes in channels/ticketing-ui/)
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml build grm_ui && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d --force-recreate grm_ui"

# Rebuild everything (e.g. after requirements.grm.txt changes)
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml build --no-cache && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml up -d --force-recreate"
```

**When to use `--no-cache`:** only when `requirements.grm.txt` or `requirements.txt`
changes, or when a dependency is behaving unexpectedly. Otherwise omit it — it's slow.

---

## Alembic migrations

```bash
# Apply all pending migrations
docker exec nepal_chatbot_claude-ticketing_api-1 \
  python -m alembic -c ticketing/migrations/alembic.ini upgrade head

# Show current revision
docker exec nepal_chatbot_claude-ticketing_api-1 \
  python -m alembic -c ticketing/migrations/alembic.ini current

# Show migration history
docker exec nepal_chatbot_claude-ticketing_api-1 \
  python -m alembic -c ticketing/migrations/alembic.ini history

# Generate a new migration after model changes
docker exec nepal_chatbot_claude-ticketing_api-1 \
  python -m alembic -c ticketing/migrations/alembic.ini \
  revision --autogenerate -m "describe your change here"
# Then review the generated file in ticketing/migrations/versions/ before committing
```

Migrations only touch `ticketing.*` — `public.*` is protected by `include_object` in
`ticketing/migrations/env.py`. See `CLAUDE.md` for the two-stream migration policy.

---

## Re-seed demo data

```bash
# Full reset: drops all ticketing.* rows and re-inserts 6 demo tickets
docker exec nepal_chatbot_claude-ticketing_api-1 \
  python -m ticketing.seed.mock_tickets --reset
```

What this seeds:
- Organisations: DOR, ADB
- Locations: verified (geodata already imported — NP_P1, NP_D004, NP_D006, NP_D011)
- 12 roles + mock officer IDs (see `PROGRESS.md` → Demo DB State)
- KL Road Standard 4-level workflow + SEAH workflow
- 6 demo tickets across both scenarios

---

## Logs

```bash
# All GRM services, follow
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml logs -f \
  ticketing_api grm_celery grm_celery_beat grm_ui"

# Single service
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml logs -f ticketing_api"

# Last 100 lines (no follow)
wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && \
  docker compose -f docker-compose.yml -f docker-compose.grm.yml logs --tail=100 ticketing_api"
```

---

## Useful one-liners

```bash
# Open a shell inside the API container
docker exec -it nepal_chatbot_claude-ticketing_api-1 bash

# Open psql directly
docker exec -it nepal_chatbot_claude-db-1 psql -U user -d app_db

# Check ticketing schema tables
docker exec -it nepal_chatbot_claude-db-1 \
  psql -U user -d app_db -c "\dt ticketing.*"

# Tail Celery SLA watchdog specifically
docker exec nepal_chatbot_claude-grm_celery-1 \
  celery -A ticketing.tasks.celery_app.celery_app inspect active

# Health check
curl http://localhost:5002/health
curl http://localhost:5002/api/v1/tickets?limit=5
```

---

## UI build args (Next.js)

`NEXT_PUBLIC_*` vars are baked in at **build time** (Next.js requirement).
They are passed as `--build-arg` in `docker-compose.grm.yml` from your `env.local`.

| Var | Default (docker-compose) | What it does |
|-----|--------------------------|--------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:5002` | Ticketing API base URL |
| `NEXT_PUBLIC_BACKEND_API_URL` | `http://localhost:5001` | Grievance API base URL |
| `NEXT_PUBLIC_BYPASS_AUTH` | `true` | Skip Cognito for local dev |
| `NEXT_PUBLIC_COGNITO_DOMAIN` | *(empty)* | Set for staging/prod |
| `NEXT_PUBLIC_COGNITO_CLIENT_ID` | *(empty)* | Set for staging/prod |
| `NEXT_PUBLIC_COGNITO_REGION` | `ap-southeast-1` | AWS region |

To change any of these for local dev, set them in `env.local` and rebuild `grm_ui`.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `invalid file request node_modules/.bin/acorn` | Running docker compose from Git Bash / Windows path | Switch to WSL terminal |
| Containers named `nepal_chatbot-*` instead of `nepal_chatbot_claude-*` | `docker compose` run from Windows terminal — wrong project directory, stale image, code changes silently ignored | Stop those containers, then always use the `wsl -d Ubuntu -e bash -c "cd /home/philg/projects/nepal_chatbot_claude && ..."` form |
| Code change deployed but behaviour unchanged | Built/recreated from Windows terminal (wrong project dir) | Same as above — rebuild from WSL |
| `ticketing_api` exits immediately | Alembic migration not run yet | Run `upgrade head` (step 5 above) |
| `grm_ui` shows blank page / 500 | Next.js build failed (check build args) | `docker compose logs grm_ui` |
| Celery tasks not running | `grm_celery_beat` not started | Ensure both `grm_celery` and `grm_celery_beat` are up |
| `relation "ticketing.tickets" does not exist` | Migration not applied | Run `upgrade head` |
| Seed fails with location warning | Geodata not imported | Location verify-only — warning is safe, seed continues |
| Port 5002 already in use | Old container still running | `docker compose down` first |

---

*Keep this file updated when the compose topology changes (new services, port changes, new env vars).*
