# Docker Compose (local / single host)

Stack: **Nginx** → **orchestrator** (8000) + **backend** (5001) + **Celery** (default + llm_queue) + **Redis** + **Postgres**.

No Rasa server — matches the REST orchestrator architecture in `docs/BACKEND.md`.

## Prerequisites

- Docker Desktop (Windows + WSL integration) or Docker Engine on Linux.
- **`env.local`** in the repo root (same as non-Docker dev). Compose references it via `env_file`; `environment:` blocks override hostnames for Docker (`POSTGRES_HOST=db`, `REDIS_HOST=redis`, etc.).

## First-time: create DB schema

Postgres starts with an **empty** data volume until you initialize tables:

```bash
docker compose --profile init run --rm db_init
```

Then start (or restart) the app stack:

```bash
docker compose up -d --build
```

If you already ran the stack without init, run `db_init` once, then:

```bash
docker compose restart backend celery_default celery_llm
```

## Everyday commands

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

Health checks:

```bash
curl -s http://localhost/health
curl -s http://localhost/rest-webchat/ | head
```

## Troubleshooting

| Symptom | What to check |
|--------|------------------|
| `ModuleNotFoundError` | Rebuild after `requirements.txt` changes: `docker compose build --no-cache backend` |
| `relation "…" does not exist` | Run `db_init` (see above). |
| `No module named 'flask'` | Temporary: Flask is listed in `requirements.txt` until `file_server_core.py` is migrated off Flask. |
| Backend / Celery restarting | `docker compose logs --tail=100 backend celery_default` |

## Files

- [`../docker-compose.yml`](../../docker-compose.yml) — service definitions
- [`../nginx/webchat_rest_docker.conf`](../nginx/webchat_rest_docker.conf) — Nginx routes to container hostnames
- [`../../scripts/docker/init_db.sh`](../../scripts/docker/init_db.sh) — sources `scripts/database/config.sh`, runs `scripts/database/init.py`
