# Nepal chatbot + GRM ticketing — Docker Compose shortcuts
# Run from repo root in WSL. Requires env.local for ${VAR} substitution.
#
# Quick reference:
#   make help
#
#   WSL:  wsl-up | wsl-demo-bypass | wsl-auth | wsl-chatbot | wsl-nginx | wsl-down
#   AWS:  aws-up | aws-deploy
#   Prod: prod-deploy (VPN + password SSH → 103.175.193.226)
#
#   Also: migrate_all, seed_seah_providers, wsl-auth, wsl-keycloak-ps, keycloak-setup, wsl-seed

PROJECT_NAME = rasa_project
PROJECT_DIRECTORY ?= nepal_chatbot

# Training server (Rasa)
TRAIN_SERVER_USER = ubuntu
REMOTE_HOST_TRAINING = 13.229.238.60
REMOTE_DIR_TRAINING = /home/ubuntu/$(PROJECT_NAME)
KEY_NAME_TRAINING = /home/philg/.ssh/pg_rasa_train.pem
SSH_TRAINING = ssh -i $(KEY_NAME_TRAINING) $(TRAIN_SERVER_USER)@$(REMOTE_HOST_TRAINING)

# Staging server (AWS EC2 — key-based SSH)
RUN_SERVER_USER = ubuntu
REMOTE_HOST_RUNNING = 52.76.171.73
REMOTE_DIR_RUNNING = /home/ubuntu/$(PROJECT_DIRECTORY)
KEY_NAME_RUNNING = /home/philg/.ssh/pg_rasa_train.pem
SSH_RUNNING = ssh -i $(KEY_NAME_RUNNING) $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING)
SCP_RUNNING = scp -i $(KEY_NAME_RUNNING)

# Production server (Nepal — VPN required, password SSH; no -i key)
#
# Configure in env.local (gitignored), not in this file:
#   PROD_SERVER_USER=your_username
#   PROD_HOST=103.175.193.226
#   # optional — omit PROD_REMOTE_DIR to default to /home/<user>/nepal_chatbot
#   PROD_REMOTE_DIR=/home/${PROD_SERVER_USER}/nepal_chatbot
#   PROD_SSH_KEY=/home/philg/.ssh/nepal_gms_prod   # optional — skips password prompt
#
# Without PROD_SSH_KEY, ssh/scp prompt for password.
#
# CLI override: make prod-deploy PROD_SERVER_USER=other
_get_env = $(strip $(shell grep -E '^$(1)=' env.local 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'"))
_env_prod_user := $(call _get_env,PROD_SERVER_USER)
_env_prod_host := $(call _get_env,PROD_HOST)
_env_prod_dir := $(call _get_env,PROD_REMOTE_DIR)
_env_prod_ssh_key := $(call _get_env,PROD_SSH_KEY)
PROD_SERVER_USER ?= $(if $(_env_prod_user),$(_env_prod_user),ubuntu)
PROD_HOST ?= $(if $(_env_prod_host),$(_env_prod_host),103.175.193.226)
# Expand ${PROD_SERVER_USER} in path (env.local is not shell — Make substitutes after read).
_prod_remote_dir := $(shell u='$(PROD_SERVER_USER)'; d='$(_env_prod_dir)'; \
  printf '%s' "$$d" | sed "s|\$${PROD_SERVER_USER}|$$u|g; s|\$$(PROD_SERVER_USER)|$$u|g")
PROD_REMOTE_DIR ?= $(if $(_env_prod_dir),$(_prod_remote_dir),/home/$(PROD_SERVER_USER)/$(PROJECT_DIRECTORY))
PROD_SSH_KEY ?= $(_env_prod_ssh_key)
PROD_SSH_IDENTITY = $(if $(PROD_SSH_KEY),-i $(PROD_SSH_KEY),)
PROD_SSH_OPTS ?= -o ConnectTimeout=30 -o StrictHostKeyChecking=accept-new
SSH_PROD = ssh $(PROD_SSH_IDENTITY) $(PROD_SSH_OPTS) $(PROD_SERVER_USER)@$(PROD_HOST)
SCP_PROD = scp $(PROD_SSH_IDENTITY) $(PROD_SSH_OPTS)

DOCKER_COMPOSE = docker compose --env-file env.local
COMPOSE_WSL = $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.grm.yml
COMPOSE_WSL_AUTH = $(COMPOSE_WSL) --profile auth
COMPOSE_AWS = $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml
# Production officer UI at grm-auth.* uses grm_ui_auth (:3002), not demo grm_ui (:3001).
COMPOSE_AWS_AUTH = $(COMPOSE_AWS) --profile auth

# Remote hosts (AWS + prod) use the same compose overlay on the server.
# COMPOSE_PARALLEL_LIMIT=1 — EC2 stalls when multiple Next.js + Python images build at once.
REMOTE_COMPOSE = COMPOSE_PARALLEL_LIMIT=1 docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  --profile auth

CHATBOT_SERVICES := db redis orchestrator backend celery_default celery_llm nginx
TICKETING_SERVICES := db redis ticketing_api grm_celery grm_celery_beat grm_ui
AUTH_SERVICES := keycloak ticketing_api_auth grm_ui_auth
# Typical GRM release on EC2: officer UI + ticketing APIs + chatbot messaging (SMTP). Override: make aws-deploy AWS_DEPLOY_SERVICES='...'
# Build order matters: Python/API images first, Next.js UIs last (sequential loop below).
AWS_DEPLOY_SERVICES ?= ticketing_api ticketing_api_auth backend celery_default grm_celery grm_celery_beat grm_ui_auth grm_ui
# UI-only release (no migrations, no API/backend rebuild). Add nginx for REST webchat static/conf bind-mounts.
AWS_DEPLOY_LIGHT_SERVICES ?= grm_ui grm_ui_auth nginx
PROD_DEPLOY_SERVICES ?= ticketing_api ticketing_api_auth backend celery_default grm_celery grm_celery_beat grm_ui_auth
PROD_DEPLOY_LIGHT_SERVICES ?= grm_ui_auth nginx

# SEAH service provider directory (chatbot outro — public.seah_service_providers).
# Data-only import; schema via migrate_public (pub009). Commit the CSV after refreshing from xlsx.
SEAH_PROVIDERS_IMPORT_SCRIPT = scripts/database/import_seah_service_providers_xlsx.py
SEAH_PROVIDERS_CSV = scripts/database/seeds/seah_service_providers_kl_road.csv
SEAH_PROVIDERS_SEED_CMD = python $(SEAH_PROVIDERS_IMPORT_SCRIPT) --from-csv --csv $(SEAH_PROVIDERS_CSV)

# $(1)=space-separated service names, $(2)=deploy label — one image at a time (no parallel build).
define REMOTE_BUILD_SERVICES_SEQUENTIAL
for svc in $(1); do \
	echo "$(2): build $$svc" && \
	$(REMOTE_COMPOSE) build --pull "$$svc" || exit 1; \
done
endef

# Same without --pull (light UI-only deploy).
define REMOTE_BUILD_SERVICES_SEQUENTIAL_NO_PULL
for svc in $(1); do \
	echo "$(2): build $$svc" && \
	$(REMOTE_COMPOSE) build "$$svc" || exit 1; \
done
endef

# Shared remote deploy steps (Make expands $(1)=remote dir, $(2)=services, $(3)=label).
define REMOTE_DEPLOY_CORE
set -e; \
	cd $(1) && \
	git fetch origin && \
	git checkout main && \
	git checkout -- docker-compose.aws.yml .dockerignore && \
	git pull --ff-only origin main && \
	echo "$(3): rebuilding $(2) (sequential, COMPOSE_PARALLEL_LIMIT=1)" && \
	$(call REMOTE_BUILD_SERVICES_SEQUENTIAL,$(2),$(3)) && \
	echo "$(3): starting $(2)" && \
	$(REMOTE_COMPOSE) up -d $(2) && \
	$(REMOTE_COMPOSE) run --rm --no-deps backend python -m alembic -c ticketing/migrations/alembic.ini upgrade head && \
	$(REMOTE_COMPOSE) run --rm --no-deps backend python -m alembic -c migrations/public/alembic.ini upgrade head
endef

define REMOTE_VERIFY_GRM_PORTS_PROD
ui_auth_port="$$(docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  -f docker-compose.prod.yml --profile auth port grm_ui_auth 3001 2>/dev/null || true)" && \
api_port="$$(docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  -f docker-compose.prod.yml port ticketing_api 5002 2>/dev/null || true)" && \
case "$$ui_auth_port" in *":3002") ;; *) echo "ERROR: grm_ui_auth not on host :3002 (actual: $$ui_auth_port)"; exit 1;; esac; \
case "$$api_port" in *":5002") ;; *) echo "ERROR: ticketing_api not on host :5002 (actual: $$api_port)"; exit 1;; esac; \
echo "$(1) OK: grm_ui_auth=$$ui_auth_port ticketing_api=$$api_port (no demo grm_ui on prod)"
endef

define REMOTE_VERIFY_GRM_PORTS
ui_port="$$(docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  port grm_ui 3001 2>/dev/null || true)" && \
ui_auth_port="$$(docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  --profile auth port grm_ui_auth 3001 2>/dev/null || true)" && \
api_port="$$(docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  port ticketing_api 5002 2>/dev/null || true)" && \
case "$$ui_port" in *":3001") ;; *) echo "ERROR: grm_ui not on host :3001 (actual: $$ui_port)"; exit 1;; esac; \
case "$$ui_auth_port" in *":3002") ;; *) echo "ERROR: grm_ui_auth not on host :3002 (actual: $$ui_auth_port)"; exit 1;; esac; \
case "$$api_port" in *":5002") ;; *) echo "ERROR: ticketing_api not on host :5002 (actual: $$api_port)"; exit 1;; esac; \
echo "$(1) OK: grm_ui=$$ui_port grm_ui_auth=$$ui_auth_port ticketing_api=$$api_port"
endef

define REMOTE_DEPLOY_LIGHT
set -e; \
	cd $(1) && \
	git fetch origin && \
	git checkout main && \
	git reset --hard origin/main && \
	git checkout -- docker-compose.aws.yml 2>/dev/null || true && \
	echo "$(3): rebuilding $(2) (sequential)" && \
	$(call REMOTE_BUILD_SERVICES_SEQUENTIAL_NO_PULL,$(filter-out nginx,$(2)),$(3)) && \
	$(REMOTE_COMPOSE) up -d $(filter-out nginx,$(2)) && \
	$(REMOTE_COMPOSE) up -d nginx && \
	ui_auth_port="$$(docker compose --env-file env.local \
	  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
	  --profile auth port grm_ui_auth 3001 2>/dev/null || true)" && \
	case "$$ui_auth_port" in *":3002") ;; *) echo "ERROR: grm_ui_auth not on host :3002 (actual: $$ui_auth_port)"; exit 1;; esac; \
	echo "$(3) OK: grm_ui_auth=$$ui_auth_port nginx=restarted"
endef

define REMOTE_DEPLOY_FULL
set -e; \
	cd $(1) && \
	git fetch origin && \
	git checkout main && \
	git checkout -- docker-compose.aws.yml .dockerignore && \
	git pull --ff-only origin main && \
	echo "full deploy: building all compose services sequentially" && \
	for svc in $$($(REMOTE_COMPOSE) config --services); do \
		echo "full deploy: build $$svc" && \
		$(REMOTE_COMPOSE) build --pull "$$svc" || exit 1; \
	done && \
	echo "full deploy: starting stack" && \
	$(REMOTE_COMPOSE) up -d && \
	$(REMOTE_COMPOSE) run --rm --no-deps backend python -m alembic -c ticketing/migrations/alembic.ini upgrade head && \
	$(REMOTE_COMPOSE) run --rm --no-deps backend python -m alembic -c migrations/public/alembic.ini upgrade head
endef

# $(1)=remote repo directory — upsert SEAH centres from committed CSV (idempotent).
define REMOTE_SEED_SEAH_PROVIDERS
set -e; \
cd $(1) && \
$(REMOTE_COMPOSE) run --rm --no-deps backend $(SEAH_PROVIDERS_SEED_CMD)
endef

.PHONY: help \
	wsl-up wsl-demo-bypass wsl-auth wsl-chatbot wsl-ticketing wsl-nginx wsl-down \
	aws-up aws-deploy aws-deploy-light aws-deploy-full \
	prod-deploy prod-deploy-light prod-deploy-full prod-sync-db-from-aws ssh-prod \
	test-ticketing test-ticketing-host test-ticketing-unit dev-grm-deps \
	migrate_ticketing migrate_public migrate_all reset_public_dev \
	seed_seah_providers seed_seah_providers_xlsx seed_seah_providers_dry_run \
	aws-seed-seah-providers prod-seed-seah-providers \
	wsl-auth wsl-auth-ps wsl-keycloak-ps keycloak-setup wsl-seed compose_seed_seah_catalog check_grm_ports \
	compose_docker_wsl compose_docker_wsl_full compose_docker_wsl_chatbot chatbot-local \
	compose_docker_wsl_ticketing compose_docker_wsl_down compose-down-all stop-all \
	compose_docker_wsl_nginx compose_docker_wsl_grm_demo compose_docker_wsl_grm_auth \
	compose_keycloak_setup compose_docker_aws compose_docker_aws_full compose_docker_aws_main \
	ssh-training ssh-running build-remote-train build-remote-run run-remote train-remote train-local clean

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo "WSL (local Docker):"
	@echo "  make wsl-up           chatbot + GRM :3001 demo bypass + :3002 Keycloak auth"
	@echo "  make wsl-demo-bypass  GRM demo only — :3001 UI, :5002 API (no Keycloak)"
	@echo "  make wsl-auth         GRM auth only — :3002 UI, :5003 API, Keycloak :18080"
	@echo "  make wsl-chatbot      chatbot only (db, redis, backend, orchestrator, celery, nginx)"
	@echo "  make wsl-ticketing    alias for wsl-demo-bypass"
	@echo "  make wsl-nginx        recreate nginx after editing deployment/nginx/*.conf"
	@echo "  make wsl-down         stop all containers (base + GRM + auth profile)"
	@echo ""
	@echo "AWS staging (EC2 key SSH — $(REMOTE_HOST_RUNNING)):"
	@echo "  make aws-up           rebuild & up on this host (aws + GRM compose files)"
	@echo "  make aws-deploy       pull main, migrate, rebuild AWS_DEPLOY_SERVICES (one image at a time)"
	@echo "  make aws-deploy-light pull main, rebuild UI (+ nginx); no migrations (sequential builds)"
	@echo "  make aws-deploy-full  pull main, migrate, rebuild entire stack (sequential builds)"
	@echo "  make ssh-running      open SSH session to staging"
	@echo ""
	@echo "Production (VPN + password SSH — $(PROD_HOST)):"
	@echo "  make ssh-prod         open SSH session (prompts for password)"
	@echo "  make prod-deploy      pull main, migrate, rebuild PROD_DEPLOY_SERVICES"
	@echo "  make prod-deploy-light UI-only rebuild (+ nginx); no migrations"
	@echo "  make prod-deploy-full pull main, migrate, rebuild entire stack"
	@echo "  make prod-sync-db-from-aws CONFIRM=1  replace prod DB from AWS (VPN; downtime OK)"
	@echo "  Override user/dir: PROD_SERVER_USER=... PROD_REMOTE_DIR=/path/to/nepal_chatbot"
	@echo "  Or set PROD_SERVER_USER, PROD_HOST, PROD_REMOTE_DIR, PROD_SSH_KEY in env.local"
	@echo ""
	@echo "DB / optional:"
	@echo "  make migrate_all              both Alembic streams (ticketing.* + public.*)"
	@echo "  make seed_seah_providers      upsert SEAH centres from committed CSV (local Docker)"
	@echo "  make seed_seah_providers_xlsx refresh CSV from Excel + upsert (after workbook update)"
	@echo "  make aws-seed-seah-providers  upsert SEAH centres on staging EC2"
	@echo "  make prod-seed-seah-providers upsert SEAH centres on prod (VPN)"
	@echo "  make wsl-seed                 re-seed GRM demo tickets (first-time / reset)"
	@echo "  make test-ticketing     pytest tests/ticketing in ticketing_api container"
	@echo "  make test-ticketing-host pytest on WSL host (needs dev-grm-deps + db :5433)"
	@echo "  make dev-grm-deps   pip install -r requirements.grm.txt (host conda env)"
	@echo "  make wsl-keycloak-ps  show Keycloak container status (after wsl-auth)"
	@echo "  make wsl-auth-ps      show Keycloak + grm_ui_auth + ticketing_api_auth"
	@echo "  make keycloak-setup   bootstrap GRM realm (once, after Keycloak is healthy)"

# ── WSL ────────────────────────────────────────────────────────────────────────
# Full stack: chatbot + GRM demo (:3001) + GRM auth (:3002). REST webchat: http://localhost:8080/
wsl-up:
	$(COMPOSE_WSL_AUTH) up -d --build
	@echo ""
	@echo "GRM demo (bypass): http://localhost:3001  → ticketing_api :5002"
	@echo "GRM auth (OIDC):   http://localhost:3002  → ticketing_api_auth :5003"
	@echo "Keycloak admin:    http://localhost:18080"

# Demo bypass only — :3001 UI + :5002 API (no Keycloak / :3002).
wsl-demo-bypass:
	$(COMPOSE_WSL) up -d --build $(TICKETING_SERVICES)
	@echo ""
	@echo "GRM demo (bypass): http://localhost:3001  → ticketing_api :5002"

wsl-chatbot:
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d --build $(CHATBOT_SERVICES)

wsl-ticketing: wsl-demo-bypass

wsl-nginx:
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d --force-recreate nginx

wsl-down:
	$(COMPOSE_WSL_AUTH) down $(COMPOSE_DOWN_FLAGS)

# ── AWS ────────────────────────────────────────────────────────────────────────
# On the EC2 host (already in repo directory). Chatbot + GRM + TLS overlay.
aws-up:
	$(COMPOSE_AWS) up -d --build

# Remote deploy: pull main, migrations, rebuild selected services (default GRM UI/API + messaging backend).
aws-deploy:
	$(SCP_RUNNING) .dockerignore $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING):$(REMOTE_DIR_RUNNING)/.dockerignore
	$(SSH_RUNNING) '$(call REMOTE_DEPLOY_CORE,$(REMOTE_DIR_RUNNING),$(AWS_DEPLOY_SERVICES),aws-deploy) && $(call REMOTE_VERIFY_GRM_PORTS,aws-deploy)'

# Light remote deploy: officer UI (+ optional nginx for bind-mounted webchat). Skips migrations and API/backend.
aws-deploy-light:
	$(SSH_RUNNING) '$(call REMOTE_DEPLOY_LIGHT,$(REMOTE_DIR_RUNNING),$(AWS_DEPLOY_LIGHT_SERVICES),aws-deploy-light)'

# Full remote deploy: entire stack (Rasa, orchestrator, all celery, etc.).
aws-deploy-full:
	$(SCP_RUNNING) .dockerignore $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING):$(REMOTE_DIR_RUNNING)/.dockerignore
	$(SSH_RUNNING) '$(call REMOTE_DEPLOY_FULL,$(REMOTE_DIR_RUNNING)) && $(call REMOTE_VERIFY_GRM_PORTS,aws-deploy-full)'

# ── Production (VPN + password SSH) ───────────────────────────────────────────
# Requires VPN. No -i key: ssh/scp prompt for PROD_SERVER_USER password.
ssh-prod:
	@echo "VPN required. Connecting to $(PROD_SERVER_USER)@$(PROD_HOST) (password prompt)..."
	$(SSH_PROD)

prod-deploy:
	@echo "VPN required. Deploying to $(PROD_HOST) as $(PROD_SERVER_USER) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_DEPLOY_CORE,$(PROD_REMOTE_DIR),$(PROD_DEPLOY_SERVICES),prod-deploy) && $(call REMOTE_VERIFY_GRM_PORTS_PROD,prod-deploy)'

prod-deploy-light:
	@echo "VPN required. Light deploy to $(PROD_HOST) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_DEPLOY_LIGHT,$(PROD_REMOTE_DIR),$(PROD_DEPLOY_LIGHT_SERVICES),prod-deploy-light)'

prod-deploy-full:
	@echo "VPN required. Full deploy to $(PROD_HOST) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_DEPLOY_FULL,$(PROD_REMOTE_DIR)) && $(call REMOTE_VERIFY_GRM_PORTS_PROD,prod-deploy-full)'

# Replace prod Postgres + uploads from AWS staging. Requires CONFIRM=1 (destructive).
prod-sync-db-from-aws:
ifndef CONFIRM
	$(error Set CONFIRM=1 to replace prod DB from AWS — stops prod stack, wipes public/ticketing/keycloak, restores from 52.76.171.73)
endif
	@echo "VPN required. Syncing prod DB from AWS ($(REMOTE_HOST_RUNNING)) → $(PROD_HOST)..."
	@chmod +x scripts/ops/aws_to_prod_db_sync.sh
	./scripts/ops/aws_to_prod_db_sync.sh

# ── Migrations (run from repo root; uses POSTGRES_* via backend container) ─────
migrate_ticketing:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python -m alembic -c ticketing/migrations/alembic.ini upgrade head

migrate_public:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python -m alembic -c migrations/public/alembic.ini upgrade head

migrate_all: migrate_ticketing migrate_public

# SEAH service providers (public.seah_service_providers) — data import, not schema.
# Run after migrate_public on fresh DBs. Idempotent upsert from git-tracked CSV.
seed_seah_providers:
	$(DOCKER_COMPOSE) run --rm --no-deps backend $(SEAH_PROVIDERS_SEED_CMD)

# Parse backend/dev-resources/SEAH Service Providers_NEP.xlsx, rewrite CSV, then upsert.
seed_seah_providers_xlsx:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python $(SEAH_PROVIDERS_IMPORT_SCRIPT)

seed_seah_providers_dry_run:
	$(DOCKER_COMPOSE) run --rm --no-deps backend $(SEAH_PROVIDERS_SEED_CMD) --dry-run

aws-seed-seah-providers:
	$(SSH_RUNNING) '$(call REMOTE_SEED_SEAH_PROVIDERS,$(REMOTE_DIR_RUNNING))'

prod-seed-seah-providers:
	@echo "VPN required. Seeding SEAH providers on $(PROD_HOST) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_SEED_SEAH_PROVIDERS,$(PROD_REMOTE_DIR))'

# Dev-only: wipe public schema then re-migrate both streams.
reset_public_dev:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python - <<-'PY'
	import os
	import psycopg2
	conn = psycopg2.connect(
	    host=os.environ["POSTGRES_HOST"],
	    port=os.environ["POSTGRES_PORT"],
	    dbname=os.environ["POSTGRES_DB"],
	    user=os.environ["POSTGRES_USER"],
	    password=os.environ["POSTGRES_PASSWORD"],
	)
	conn.autocommit = True
	with conn.cursor() as cur:
	    cur.execute("DROP SCHEMA IF EXISTS public CASCADE;")
	    cur.execute("CREATE SCHEMA public;")
	    cur.execute("GRANT ALL ON SCHEMA public TO public;")
	print("public schema recreated")
	conn.close()
	PY
	$(MAKE) migrate_public
	$(MAKE) migrate_ticketing
	$(MAKE) wsl-up

# ── Optional stacks / one-shot setup ───────────────────────────────────────────
# Auth stack only — :3002 UI, :5003 API, Keycloak :18080 (starts db/redis via depends_on).
wsl-auth:
	$(COMPOSE_WSL_AUTH) up -d --build $(AUTH_SERVICES)
	@echo ""
	@echo "GRM auth (OIDC): http://localhost:3002  → ticketing_api_auth :5003"
	@echo "Keycloak admin:  http://localhost:18080"

# Auth stack status (requires `make wsl-auth` first).
wsl-keycloak-ps:
	$(COMPOSE_WSL_AUTH) ps keycloak

wsl-auth-ps:
	$(COMPOSE_WSL_AUTH) ps keycloak grm_ui_auth ticketing_api_auth

keycloak-setup compose_keycloak_setup:
	$(COMPOSE_WSL_AUTH) exec -T ticketing_api_auth python -m ticketing.auth.keycloak_setup

# GRM demo tickets in ticketing.* (idempotent with --reset).
wsl-seed:
	$(COMPOSE_WSL) exec -T ticketing_api python -m ticketing.seed.mock_tickets --reset

# ── Ticketing tests ───────────────────────────────────────────────────────────
# Container: same image/deps/DB as production stack (preferred).
test-ticketing:
	$(COMPOSE_WSL) exec -T ticketing_api python -m pytest tests/ticketing/ -v

# Host WSL: requires `make dev-grm-deps`, Docker db published on :5433, migrations + seed.
test-ticketing-host:
	PYTHONPATH=. python -m pytest tests/ticketing/ -v

# Host unit tests only (no DB): admin_access matrix helpers.
test-ticketing-unit:
	PYTHONPATH=. python -m pytest tests/ticketing/test_admin_access.py -v

dev-grm-deps:
	pip install -r requirements.grm.txt

compose_seed_seah_catalog:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python scripts/database/migrate_seah_demo_catalog.py

check_grm_ports:
	@set -e; \
	ui_port="$$(docker compose -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml port grm_ui 3001 2>/dev/null || true)"; \
	api_port="$$(docker compose -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml port ticketing_api 5002 2>/dev/null || true)"; \
	case "$$ui_port" in *":3001") ;; *) echo "ERROR: grm_ui not on :3001 (actual: $$ui_port)"; exit 1;; esac; \
	case "$$api_port" in *":5002") ;; *) echo "ERROR: ticketing_api not on :5002 (actual: $$api_port)"; exit 1;; esac; \
	echo "GRM port check passed: grm_ui=$$ui_port ticketing_api=$$api_port"

# ── Back-compat aliases (old target names) ───────────────────────────────────────
compose_docker_wsl compose_docker_wsl_full: wsl-up
compose_docker_wsl_grm_demo: wsl-demo-bypass
chatbot-local compose_docker_wsl_chatbot: wsl-chatbot
compose_docker_wsl_ticketing: wsl-demo-bypass
compose_docker_wsl_nginx: wsl-nginx
compose_docker_wsl_down compose-down-all stop-all: wsl-down
compose_docker_wsl_grm_auth: wsl-auth
compose_docker_aws: aws-up
compose_docker_aws_full: aws-deploy
compose_docker_aws_main:
	cd /home/philg/projects/nepal_chatbot && $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.aws.yml up -d --build

# ── Remote Rasa training (unchanged) ───────────────────────────────────────────
ssh-training:
	$(SSH_TRAINING)

ssh-running:
	$(SSH_RUNNING)

build-remote-train:
	tar --exclude=$(PROJECT_NAME).tar.gz --exclude=.DS_Store --exclude=__MACOSX -czf $(PROJECT_NAME).tar.gz . && \
	scp -i $(KEY_NAME_TRAINING) $(PROJECT_NAME).tar.gz $(TRAIN_SERVER_USER)@$(REMOTE_HOST_TRAINING):/home/ubuntu && \
	$(SSH_TRAINING) "\
		rm -rf /home/ubuntu/$(PROJECT_NAME) && \
		mkdir -p /home/ubuntu/$(PROJECT_NAME) && \
		cd /home/ubuntu/$(PROJECT_NAME) && \
		tar -xzf /home/ubuntu/$(PROJECT_NAME).tar.gz && \
		rm /home/ubuntu/$(PROJECT_NAME).tar.gz && \
		docker compose up --build --remove-orphans"

train-remote:
	$(SSH_TRAINING) "cd $(REMOTE_DIR_TRAINING) && \
	docker compose run --entrypoint bash rasa-server /app/start_train.sh"

build-remote-run:
	tar -czf $(PROJECT_NAME).tar.gz . && \
	scp -i $(KEY_NAME_RUNNING) $(PROJECT_NAME).tar.gz $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING):$(REMOTE_DIR_RUNNING) && \
	$(SSH_RUNNING) "cd $(REMOTE_DIR_RUNNING) && tar -xzf $(PROJECT_NAME).tar.gz && rm $(PROJECT_NAME).tar.gz && $(DOCKER_COMPOSE) build"

run-remote:
	$(SSH_RUNNING) "cd $(REMOTE_DIR_RUNNING) && $(DOCKER_COMPOSE) up -d"

train-local:
	bash /app/start_train.sh

clean:
	rm -rf $(PROJECT_NAME).tar.gz
