# Deployment URLs and paths (dev / stage / prod)

This repo’s edge routing is defined in Nginx samples under [`deployment/nginx/`](../deployment/nginx/). Values **differ by machine** (WSL paths vs EC2 `ubuntu` home, TLS termination, etc.). To avoid drift, maintain a **single manifest** and derive or update Nginx from it.

## Files

| File | Purpose |
|------|---------|
| This document | **Committed** — workflow + full YAML you can copy into a local file. |
| `docs/deployment_environment_urls.local.yaml` | **Optional local override** (recommended gitignored) — save the example block below after filling in `REPLACE_ME` / `YOU` paths. |

## Workflow

1. Copy the **Example manifest (YAML)** block below into `docs/deployment_environment_urls.local.yaml` (or keep editing this doc’s block and paste when needed).

2. Edit your local file with your WSL `repo_root`, stage hostnames, and upstream URLs.

3. When changing Nginx or asking an assistant for config updates, **point to this file** (or paste the relevant `environments.*` block) so `server_name`, `alias` paths, and `proxy_pass` targets stay consistent.

4. After deploy path changes on AWS, update the **`prod_aws`** (or equivalent) section here and the matching file under `deployment/nginx/`.

## What belongs here vs elsewhere

- **Here:** Public base URL, `server_name`, **host** paths for static `alias`, HTTP upstreams for orchestrator and FastAPI, TLS termination notes.
- **Not here:** Database passwords, API keys, Redis passwords — use environment variables or a secrets manager.

## Docker Compose

If you run the stack in Compose, set `upstreams` to **service names** (e.g. `http://backend:5001`) instead of `localhost`. The manifest should document both “host-run” and “compose” variants in `notes` or duplicate blocks if you maintain two layouts.

### Compose nginx naming + defaults

To avoid local TLS breakage and make intent explicit, Compose nginx configs are now split by environment:

- `deployment/nginx/webchat_rest_compose_wsl.conf` — **WSL/local compose** (HTTP only, no certs, upstreams by service name)
- `deployment/nginx/webchat_rest_compose_aws.conf` — **AWS compose** (HTTP->HTTPS redirect + certbot mounts + TLS cert paths)

Compose files:

- `docker-compose.yml` defaults to **WSL/local** behavior and maps only `80:80`.
- `docker-compose.aws.yml` is an override for AWS TLS deployment.

Run commands:

- Local WSL: `docker compose up -d --build`
- AWS/TLS compose: `docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d --build`

## Related

- Deployment and data architecture (Phase 1 → 2): [`deployment refactor/deployment_and_data_architecture.md`](deployment%20refactor/deployment_and_data_architecture.md)
- AWS-oriented sample: [`deployment/nginx/webchat_rest_aws.conf`](../deployment/nginx/webchat_rest_aws.conf)
- Local sample: [`deployment/nginx/webchat_rest.conf`](../deployment/nginx/webchat_rest.conf)

---

## Example manifest (YAML)

Copy everything inside the fence into `docs/deployment_environment_urls.local.yaml` (gitignored) and fill in placeholders. Keep in sync when Nginx or public URLs change.

```yaml
# docs/deployment_environment_urls.local.yaml — do not commit secrets
meta:
  project: nepal_chatbot
  purpose: >-
    Public URLs, server names, host filesystem paths, and upstream targets
    for dev / stage / prod. Keep in sync with deployment/nginx/*.conf.

nginx_location_prefixes:
  rest_webchat: /rest-webchat/
  shared_assets: /shared/
  ticketing_ui: /ticketing/
  ticketing_mobile_api: /ticketing-mobile/
  orchestrator_message: /message
  orchestrator_health: /health
  accessible_socketio: /accessible-socket.io
  upload_files: /upload-files
  files_api: /files/
  file_status: /file-status/
  task_status: /task-status/
  gsheet_get_grievances: /gsheet-get-grievances

environments:

  dev_wsl:
    label: "Local dev (WSL)"
    public:
      base_url: "http://localhost"
      server_name: "localhost"
    tls:
      terminated_at: none # none | nginx | alb
    nginx:
      listen_port: 80
    host_paths:
      repo_root: "/home/YOU/projects/nepal_chatbot"
      rest_webchat_dir: REPLACE_ME
      shared_dir: REPLACE_ME
    upstreams:
      orchestrator: "http://127.0.0.1:8000"
      fastapi_backend: "http://127.0.0.1:5001"
    notes: []

  stage:
    label: "Staging"
    public:
      base_url: "https://REPLACE_STAGE_HOST"
      server_name: "REPLACE_STAGE_HOST"
    tls:
      terminated_at: alb
    nginx:
      listen_port: 80
    host_paths:
      repo_root: "/home/ubuntu/nepal_chatbot"
      rest_webchat_dir: "/home/ubuntu/nepal_chatbot/channels/REST_webchat"
      shared_dir: "/home/ubuntu/nepal_chatbot/channels/shared"
    upstreams:
      orchestrator: "http://127.0.0.1:8000"
      fastapi_backend: "http://127.0.0.1:5001"
    notes: []

  prod_aws:
    label: "Production (aligned with webchat_rest_aws.conf)"
    public:
      base_url: "https://nepal-gms-chatbot.facets-ai.com"
      server_name: "nepal-gms-chatbot.facets-ai.com"
    tls:
      terminated_at: alb
    nginx:
      listen_port: 80
    host_paths:
      repo_root: "/home/ubuntu/nepal_chatbot"
      rest_webchat_dir: "/home/ubuntu/nepal_chatbot/channels/REST_webchat"
      shared_dir: "/home/ubuntu/nepal_chatbot/channels/shared"
    upstreams:
      orchestrator: "http://127.0.0.1:8000"
      fastapi_backend: "http://127.0.0.1:5001"
      ticketing_ui: "http://127.0.0.1:3001"
      ticketing_mobile_api: "http://127.0.0.1:5001"
    notes:
      - "Docker Compose: use service names, e.g. http://orchestrator:8000"
      - "Nginx aliases: /ticketing/ -> grm_ui:3001 and /ticketing-mobile/ -> backend:5001"

# other_services:
#   rasa: "http://127.0.0.1:5005"
#   rasa_actions: "http://127.0.0.1:5055"
```
