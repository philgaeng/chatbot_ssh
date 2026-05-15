# Nepal chatbot + GRM ticketing — Docker Compose shortcuts
# Run from repo root in WSL. Requires env.local for ${VAR} substitution.
#
# Quick reference:
#   make help
#
#   WSL:  wsl-up | wsl-chatbot | wsl-ticketing | wsl-nginx | wsl-down
#   AWS:  aws-up | aws-deploy
#
#   Also: migrate_all, wsl-auth, wsl-auth-ps, wsl-keycloak-ps, keycloak-setup, wsl-seed

PROJECT_NAME = rasa_project
PROJECT_DIRECTORY ?= nepal_chatbot

# Training server (Rasa)
TRAIN_SERVER_USER = ubuntu
REMOTE_HOST_TRAINING = 13.229.238.60
REMOTE_DIR_TRAINING = /home/ubuntu/$(PROJECT_NAME)
KEY_NAME_TRAINING = /home/philg/.ssh/pg_rasa_train.pem
SSH_TRAINING = ssh -i $(KEY_NAME_TRAINING) $(TRAIN_SERVER_USER)@$(REMOTE_HOST_TRAINING)

# Running server (staging / prod EC2)
RUN_SERVER_USER = ubuntu
REMOTE_HOST_RUNNING = 52.76.171.73
REMOTE_DIR_RUNNING = /home/ubuntu/$(PROJECT_DIRECTORY)
KEY_NAME_RUNNING = /home/philg/.ssh/pg_rasa_train.pem
SSH_RUNNING = ssh -i $(KEY_NAME_RUNNING) $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING)
SCP_RUNNING = scp -i $(KEY_NAME_RUNNING)

DOCKER_COMPOSE = docker compose --env-file env.local
COMPOSE_WSL = $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.grm.yml
COMPOSE_WSL_AUTH = $(COMPOSE_WSL) --profile auth
COMPOSE_AWS = $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml

CHATBOT_SERVICES := db redis orchestrator backend celery_default celery_llm nginx
TICKETING_SERVICES := db redis ticketing_api grm_celery grm_celery_beat grm_ui

.PHONY: help \
	wsl-up wsl-chatbot wsl-ticketing wsl-nginx wsl-down \
	aws-up aws-deploy \
	migrate_ticketing migrate_public migrate_all reset_public_dev \
	wsl-auth wsl-auth-ps wsl-keycloak-ps keycloak-setup wsl-seed compose_seed_seah_catalog check_grm_ports \
	compose_docker_wsl compose_docker_wsl_full compose_docker_wsl_chatbot chatbot-local \
	compose_docker_wsl_ticketing compose_docker_wsl_down compose-down-all stop-all \
	compose_docker_wsl_nginx compose_docker_wsl_grm_demo compose_docker_wsl_grm_auth \
	compose_keycloak_setup compose_docker_aws compose_docker_aws_full compose_docker_aws_main \
	ssh-training ssh-running build-remote-train build-remote-run run-remote train-remote train-local clean

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo "WSL (local Docker):"
	@echo "  make wsl-up         chatbot + GRM demo stack (:8080 webchat, :3001 GRM UI, :5002 API)"
	@echo "  make wsl-chatbot    chatbot only (db, redis, backend, orchestrator, celery, nginx)"
	@echo "  make wsl-ticketing  GRM only (db, redis, ticketing_api, celery, grm_ui)"
	@echo "  make wsl-nginx      recreate nginx after editing deployment/nginx/*.conf"
	@echo "  make wsl-down       stop all containers (base + GRM + auth profile)"
	@echo ""
	@echo "AWS (EC2):"
	@echo "  make aws-up         rebuild & up on this host (aws + GRM compose files)"
	@echo "  make aws-deploy     SSH to EC2: git pull main, migrate, rebuild UI, up all"
	@echo ""
	@echo "DB / optional:"
	@echo "  make migrate_all    both Alembic streams (ticketing.* + public.*)"
	@echo "  make wsl-seed       re-seed GRM demo tickets (first-time / reset)"
	@echo "  make wsl-auth         Keycloak + auth UI on :3002 / :18080 (--profile auth)"
	@echo "  make wsl-keycloak-ps  show Keycloak container status (after wsl-auth)"
	@echo "  make wsl-auth-ps      show Keycloak + grm_ui_auth + ticketing_api_auth"
	@echo "  make keycloak-setup   bootstrap GRM realm (once, after Keycloak is healthy)"

# ── WSL ────────────────────────────────────────────────────────────────────────
# Full stack: chatbot + GRM demo UI (bypass auth on :3001). REST webchat: http://localhost:8080/
wsl-up:
	$(COMPOSE_WSL) up -d --build

wsl-chatbot:
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d --build $(CHATBOT_SERVICES)

wsl-ticketing:
	$(COMPOSE_WSL) up -d --build $(TICKETING_SERVICES)

wsl-nginx:
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d --force-recreate nginx

wsl-down:
	$(COMPOSE_WSL_AUTH) down $(COMPOSE_DOWN_FLAGS)

# ── AWS ────────────────────────────────────────────────────────────────────────
# On the EC2 host (already in repo directory). Chatbot + GRM + TLS overlay.
aws-up:
	$(COMPOSE_AWS) up -d --build

# Full remote deploy: pull main, migrations, fresh Node UI build, full stack up, port check.
aws-deploy:
	$(SCP_RUNNING) .dockerignore $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING):$(REMOTE_DIR_RUNNING)/.dockerignore
	$(SSH_RUNNING) 'set -e; \
		cd $(REMOTE_DIR_RUNNING) && \
		git fetch origin && \
		git checkout main && \
		git pull --ff-only origin main && \
		docker compose --env-file env.local \
		  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
		  build --pull grm_ui && \
		docker compose --env-file env.local \
		  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
		  up -d --build && \
		docker compose --env-file env.local \
		  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
		  run --rm --no-deps backend python -m alembic -c ticketing/migrations/alembic.ini upgrade head && \
		docker compose --env-file env.local \
		  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
		  run --rm --no-deps backend python -m alembic -c migrations/public/alembic.ini upgrade head && \
		ui_port="$$(docker compose --env-file env.local \
		  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
		  port grm_ui 3001 2>/dev/null || true)" && \
		api_port="$$(docker compose --env-file env.local \
		  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
		  port ticketing_api 5002 2>/dev/null || true)" && \
		case "$$ui_port" in *":3001") ;; *) echo "ERROR: grm_ui not on host :3001 (actual: $$ui_port)"; exit 1;; esac; \
		case "$$api_port" in *":5002") ;; *) echo "ERROR: ticketing_api not on host :5002 (actual: $$api_port)"; exit 1;; esac; \
		echo "aws-deploy OK: grm_ui=$$ui_port ticketing_api=$$api_port"'

# ── Migrations (run from repo root; uses POSTGRES_* via backend container) ─────
migrate_ticketing:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python -m alembic -c ticketing/migrations/alembic.ini upgrade head

migrate_public:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python -m alembic -c migrations/public/alembic.ini upgrade head

migrate_all: migrate_ticketing migrate_public

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
# Keycloak OIDC (:18080) + auth UI (:3002). Not started by wsl-up.
wsl-auth:
	$(COMPOSE_WSL_AUTH) up -d --build

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
compose_docker_wsl compose_docker_wsl_full compose_docker_wsl_grm_demo: wsl-up
chatbot-local compose_docker_wsl_chatbot: wsl-chatbot
compose_docker_wsl_ticketing: wsl-ticketing
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
