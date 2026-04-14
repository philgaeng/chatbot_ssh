# Agent instructions — deployment, Nginx, and ops (nepal_chatbot)

Use this file when an automated agent (or a new chat session) is asked to **change deployment**, **Nginx**, **Docker**, **secrets**, or **infrastructure docs** for this repository.

---

## 1. Read first (mandatory)

| Order | Document | Why |
|-------|----------|-----|
| 1 | [`deployment_and_data_architecture.md`](deployment_and_data_architecture.md) | Phase 1/2 scope, secrets policy, what is in/out of deploy |
| 2 | [`../deployment_environment_urls.md`](../deployment_environment_urls.md) | Per-environment URLs, `server_name`, host paths, upstream ports for Nginx |
| 3 | [`../BACKEND.md`](../BACKEND.md) | Orchestrator vs Backend API, ports, Rasa SDK (no Rasa server) |
| 4 | [`../../deployment/nginx/webchat_rest_aws.conf`](../../deployment/nginx/webchat_rest_aws.conf) | Current production-shaped Nginx routing |

If the task touches **Phase 2** storage or crawlers, also read [`../internal_dental_system_strategy.md`](../internal_dental_system_strategy.md) when relevant.

---

## 2. Architecture constraints (do not violate)

1. **No Rasa server in production** — Conversation is **Orchestrator** (FastAPI) + **Rasa SDK** actions in-process. Do **not** add `rasa run`, a separate Rasa container, or a “classic” action server container unless the human explicitly changes product direction.
2. **Two HTTP services (typical):** Orchestrator (often **`~8000`**) and Backend API (**`~5001`**). Nginx must route to the **same** upstream names/ports the human has in their manifest.
3. **Edge proxy:** **Nginx only** — extend existing `deployment/nginx/*.conf`. Do **not** introduce Caddy, Traefik, or other edge proxies unless the human explicitly asks.
4. **Celery:** App module is **`backend.task_queue.celery_app`**. Workers use **named queues** (`-Q <queue>`). See [`../../scripts/rest_api/launch_servers_celery.sh`](../../scripts/rest_api/launch_servers_celery.sh) for patterns.
5. **Secrets:** Never commit passwords, API keys, or production URLs with embedded credentials. **Local dev:** `env.local` / local-only files. **Stage/prod:** environment variables + **AWS** (Parameter Store, Secrets Manager) as described in `deployment_and_data_architecture.md`

---

## 3. Before editing Nginx

1. Ask the human for **`docs/deployment_environment_urls.local.yaml`** (or the filled YAML block from [`../deployment_environment_urls.md`](../deployment_environment_urls.md)) for the **target environment** (`dev_wsl`, `stage`, `prod_aws`).
2. Preserve **existing** `location` blocks and behavior unless the task is explicitly to remove or replace them.
3. Use **container service names** when the stack runs under Docker Compose (e.g. `http://orchestrator:8000`); use **`127.0.0.1` or `localhost`** when processes run on the host—match the manifest.
4. After edits, **summarize** what changed (paths, upstreams, ports) so the human can sync the manifest and test.

---

## 4. Docker / Compose (when asked)

1. Do **not** copy generic tutorials that use `uvicorn main:app` from `./backend` — this repo uses **`uvicorn backend.api.fastapi_app:app`** and **`uvicorn orchestrator.main:app`** (or ASGI variant per `BACKEND.md` / launch scripts).
2. Prefer **one** `docker-compose.yml` (or a documented base + override) aligned with `deployment_and_data_architecture.md`.
3. **Migrations:** There is **no** committed `alembic.ini` today — do not assume `alembic upgrade head` works until the project adds Alembic; document manual steps if needed.

---

## 5. What not to do

- Do not add **Caddy** or **Caddyfile** unless the human explicitly requests it.
- Do not commit **`deployment_environment_urls.local.yaml`** (it should stay local; the example lives in the markdown doc).
- Do not embed **production secrets** in repo files, including `rasa_chatbot/endpoints.yml` — migrate toward env-driven config.

---

## 6. Output format for the human

When you finish a deployment-related task:

1. List **files changed** with paths.
2. Note **any follow-up** the human must do (reload Nginx, restart systemd, update Parameter Store, copy env to server).
3. If you invented placeholders, mark them **`REPLACE_ME`** and list them in a short checklist.

---

## 7. Related Cursor rules (optional)

If the repo adds a [`.cursor/rules`](../../.cursor/rules) rule for deployment, keep it **short** and point here to avoid duplication.
