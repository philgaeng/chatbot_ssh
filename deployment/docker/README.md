# Docker Compose (local / single host)

Stack: **Nginx** → **orchestrator** (8000) + **backend** (5001) + **Celery** (default + llm_queue) + **Redis** + **Postgres**.

No Rasa server — matches the REST orchestrator architecture in `docs/BACKEND.md`.

## Docker-only on this machine (recommended long-term)

Run the app **only** via Compose. Do **not** run a second system Nginx on the same ports.

1. **Free port 80** for the Compose `nginx` service (`80:80` in [`docker-compose.yml`](../../docker-compose.yml)):
   ```bash
   sudo systemctl stop nginx
   sudo systemctl disable nginx   # optional: do not start at boot
   ```
2. **Confirm** nothing else is bound to `:80`:
   ```bash
   sudo ss -tlnp | grep ':80'
   ```
   You should see **`docker-proxy`** (or similar) after `docker compose up -d`, not a host **`/usr/sbin/nginx`** process.
3. **Bring the stack up** (from repo root):
   ```bash
   docker compose up -d --build
   ```

If you **must** keep system Nginx for other sites, do **not** share port 80: change the Compose `nginx` service to e.g. `"8888:80"` and use `http://localhost:8888/` — but that is a mixed setup, not “everything through Docker” on `:80`.

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

Health checks (must hit **Compose** Nginx, not host Nginx — see “Docker-only” above):

```bash
curl -4 -s http://127.0.0.1/health
curl -4 -s http://127.0.0.1/rest-webchat/ | head
```

## Troubleshooting

| Symptom | What to check |
|--------|------------------|
| `ModuleNotFoundError` | Rebuild after `requirements.txt` changes: `docker compose build --no-cache backend` |
| `relation "…" does not exist` | Run `db_init` (see above). |
| `No module named 'flask'` | Temporary: Flask is listed in `requirements.txt` until `file_server_core.py` is migrated off Flask. |
| Backend / Celery restarting | `docker compose logs --tail=100 backend celery_default` |
| **404** on `/health`, footer **`nginx/… (Ubuntu)`** | Host **system Nginx** still owns `:80`. Stop/disable it (see “Docker-only”) or change Compose to another host port. |

## Files

- [`../docker-compose.yml`](../../docker-compose.yml) — service definitions
- [`../nginx/webchat_rest_docker.conf`](../nginx/webchat_rest_docker.conf) — Nginx routes to container hostnames
- [`../../scripts/docker/init_db.sh`](../../scripts/docker/init_db.sh) — sources `scripts/database/config.sh`, runs `scripts/database/init.py`
