# Deployment URLs and paths (dev / stage / prod)

This repo’s edge routing is defined in Nginx samples under [`deployment/nginx/`](../../deployment/nginx/). Values **differ by machine** (WSL paths vs EC2 `ubuntu` home, TLS termination, etc.). To avoid drift, maintain a **single manifest** and derive or update Nginx from it.

## Files

| File | Purpose |
|------|---------|
| This document | **Committed** — workflow + full YAML you can copy into a local file. |
| `docs/deployment/deployment_environment_urls.example.yaml` | **Committed** — template manifest. |
| `docs/deployment/deployment_environment_urls.local.yaml` | **Local override** (intended gitignored). ⚠️ **Drift note (July 2026):** despite the gitignore intent, this file is currently *tracked in git* — do not put secrets in it until that is resolved. |

## Workflow

1. Copy the **Example manifest (YAML)** block below into `docs/deployment/deployment_environment_urls.local.yaml` (or keep editing this doc’s block and paste when needed).

2. Edit your local file with your WSL `repo_root`, stage hostnames, and upstream URLs.

3. When changing Nginx or asking an assistant for config updates, **point to this file** (or paste the relevant `environments.*` block) so `server_name`, `alias` paths, and `proxy_pass` targets stay consistent.

4. After deploy path changes on AWS staging or DOR prod, update the **`stage_aws`** / **`prod_dor`** section here and the matching `webchat_rest_compose_*.conf` under `deployment/nginx/`.

## What belongs here vs elsewhere

- **Here:** Public base URL, `server_name`, **host** paths for static `alias`, HTTP upstreams for orchestrator and FastAPI, TLS termination notes.
- **Not here:** Database passwords, API keys, Redis passwords — use environment variables or a secrets manager.

## Docker Compose

If you run the stack in Compose, set `upstreams` to **service names** (e.g. `http://backend:5001`) instead of `localhost`. The manifest should document both “host-run” and “compose” variants in `notes` or duplicate blocks if you maintain two layouts.

### Compose nginx naming + defaults

To avoid local TLS breakage and make intent explicit, Compose nginx configs are now split by environment:

- `deployment/nginx/webchat_rest_compose_wsl.conf` — **WSL/local compose** (HTTP only, no certs, upstreams by service name)
- `deployment/nginx/webchat_rest_compose_aws.conf` — **AWS staging compose** (`nepal-gms-chatbot.facets-ai.com` + `grm-auth.` subdomain; HTTP→HTTPS redirect + certbot mounts + TLS cert paths)
- `deployment/nginx/webchat_rest_compose_prod.conf` / `webchat_rest_compose_prod.tls.conf` — **Nepal DOR production** (`grm-chatbot.dor.gov.np`; TLS variant mounted by `docker-compose.prod.yml`, single-host Keycloak at `/keycloak`)

Compose files:

- `docker-compose.yml` defaults to **WSL/local** behavior and maps host `8080` → container `80`.
- `docker-compose.aws.yml` is an override for AWS TLS deployment (host `80`/`443`).
- `docker-compose.prod.yml` is the DOR-prod overlay on top of aws + grm.

Run commands:

- Local WSL: `docker compose up -d --build`
- AWS/TLS compose: `docker compose -f docker-compose.yml -f docker-compose.aws.yml up -d --build`
- DOR prod: `docker compose --env-file env.local -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml -f docker-compose.prod.yml --profile auth up -d`

## Related

- Deployment and data architecture (Phase 1 → 2): [`../sprints/archive/deployment refactor/deployment_and_data_architecture.md`](../sprints/archive/deployment%20refactor/deployment_and_data_architecture.md)
- Nginx configs (the `_compose_*` variants are the live ones): [`deployment/nginx/`](../../deployment/nginx/)

---

## Example manifest (YAML)

Copy everything inside the fence into `docs/deployment/deployment_environment_urls.local.yaml` and fill in placeholders. Keep in sync when Nginx or public URLs change.

```yaml
# docs/deployment/deployment_environment_urls.local.yaml — do not commit secrets
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

  stage_aws:
    label: "AWS staging (aligned with webchat_rest_compose_aws.conf)"
    public:
      base_url: "https://nepal-gms-chatbot.facets-ai.com"
      server_name: "nepal-gms-chatbot.facets-ai.com"   # + grm-auth.nepal-gms-chatbot.facets-ai.com (Keycloak issuer host)
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
      - "Single officer UI/API in Keycloak mode (AUTH_MODE=keycloak) — main domain serves the real login, not a demo/bypass stack (mirrors prod; CL-03: :3002/:5003 retired)"

  prod_dor:
    label: "Nepal DOR production (webchat_rest_compose_prod.tls.conf, docker-compose.prod.yml)"
    public:
      base_url: "https://grm-chatbot.dor.gov.np"
      server_name: "grm-chatbot.dor.gov.np"
    tls:
      terminated_at: nginx   # certbot certs mounted into the nginx container
    nginx:
      listen_port: 443
    host_paths:
      repo_root: "/opt/grms/nepal_chatbot"   # adjust to actual checkout on the VPN host
      rest_webchat_dir: "channels/REST_webchat"
      shared_dir: "channels/shared"
    upstreams:
      orchestrator: "http://orchestrator:8000"
      fastapi_backend: "http://backend:5001"
      ticketing_ui: "http://grm_ui:3001"
      ticketing_api: "http://ticketing_api:5002"
      keycloak: "http://keycloak:8080"   # proxied at /keycloak (KC_HTTP_RELATIVE_PATH=/keycloak)
    notes:
      - "Reached via Sophos VPN only; the single grm_ui serves the main host in Keycloak mode (AUTH_MODE=keycloak) — no demo/bypass stack (CL-03: :3002/:5003 retired)"
      - "KC_HOSTNAME_URL=https://grm-chatbot.dor.gov.np/keycloak"
```
