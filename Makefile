# Variables
PROJECT_NAME = rasa_project
PROJECT_DIRECTORY ?= nepal_chatbot

# Training Server
TRAIN_SERVER_USER = ubuntu
REMOTE_HOST_TRAINING = 13.229.238.60
REMOTE_DIR_TRAINING = /home/ubuntu/$(PROJECT_NAME)
KEY_NAME_TRAINING = /home/philg/.ssh/pg_rasa_train.pem
SSH_TRAINING = ssh -i $(KEY_NAME_TRAINING) $(TRAIN_SERVER_USER)@$(REMOTE_HOST_TRAINING)

# Running Server
RUN_SERVER_USER = ubuntu
# Replace with your running server IP
REMOTE_HOST_RUNNING = 52.76.171.73
REMOTE_DIR_RUNNING = /home/ubuntu/$(PROJECT_DIRECTORY)
KEY_NAME_RUNNING = /home/philg/.ssh/pg_rasa_train.pem
SSH_RUNNING = ssh -i $(KEY_NAME_RUNNING) $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING)
SCP_RUNNING = scp -i $(KEY_NAME_RUNNING)

# Docker Compose Command
DOCKER_COMPOSE = docker compose

# --- Local WSL (default docker-compose.yml: nginx host :8080→:80, orchestrator, backend, redis, db, celery) ---
# Run from repo root. Requires env.local. REST webchat: http://localhost:8080/
#
# Chatbot-only (no GRM): use `make chatbot-local` — starts only services in docker-compose.yml
# (db, redis, orchestrator, backend, celery workers, nginx). Does not start ticketing_api,
# grm_ui, or grm_celery*, so host ports 5002 and 3001 stay free for other worktrees/stacks.
.PHONY: compose_docker_wsl compose_docker_wsl_full compose_docker_wsl_chatbot chatbot-local compose_docker_wsl_ticketing compose_docker_wsl_down compose-down-all stop-all compose_docker_wsl_nginx compose_docker_aws compose_docker_aws_full compose_docker_aws_main check_grm_ports compose_seed_seah_catalog \
	migrate_ticketing migrate_public migrate_all reset_public_dev

# Services defined only in docker-compose.yml (chatbot + REST webchat via nginx). Explicit list
# avoids accidentally scaling the full grm overlay when iterating locally.
CHATBOT_LOCAL_SERVICES := db redis orchestrator backend celery_default celery_llm nginx

# DB migrations (two Alembic streams — run from repo root; uses POSTGRES_* from env / env.local)
migrate_ticketing:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python -m alembic -c ticketing/migrations/alembic.ini upgrade head

migrate_public:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python -m alembic -c migrations/public/alembic.ini upgrade head

migrate_all: migrate_ticketing migrate_public

# Dev-only reset of chatbot public schema (dummy data) followed by both migration streams.
# This is the canonical recovery path when public core tables are missing.
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
	$(DOCKER_COMPOSE) up -d --build

compose_docker_wsl:
	$(DOCKER_COMPOSE) up -d --build

# Local WSL full stack (chatbot + ticketing UI/API/workers)
compose_docker_wsl_full:
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.grm.yml up -d --build

# Local WSL — chatbot stack only (same as compose_docker_wsl_chatbot)
chatbot-local compose_docker_wsl_chatbot:
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d --build $(CHATBOT_LOCAL_SERVICES)

# Local WSL ticketing stack only (overlay services; expects shared deps as defined in compose files)
compose_docker_wsl_ticketing:
	$(DOCKER_COMPOSE) -f docker-compose.grm.yml up -d --build

# Seed projects + Jhapa SEAH contact points into Compose Postgres (app_db).
# Compose overrides DATABASE_URL to db:5432/app_db — host-only seeds do not apply here.
compose_seed_seah_catalog:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python scripts/database/migrate_seah_demo_catalog.py

# Stop and remove all containers for this Compose project (base + GRM). Frees host ports 8080, 3001, 5001, 5002, 8000, etc.
# Does not delete volumes unless you add: COMPOSE_DOWN_FLAGS=--volumes make compose-down-all
compose_docker_wsl_down compose-down-all stop-all:
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.grm.yml down $(COMPOSE_DOWN_FLAGS)

# Recreate only nginx after editing deployment/nginx/webchat_rest_compose_wsl.conf
compose_docker_wsl_nginx:
	$(DOCKER_COMPOSE) up -d --force-recreate nginx

# AWS / TLS: uses docker-compose.aws.yml override (443, cert mounts)
compose_docker_aws:
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.aws.yml up -d --build

# AWS / TLS full stack with ticketing overlay.
compose_docker_aws_full:
	$(SCP_RUNNING) .dockerignore $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING):$(REMOTE_DIR_RUNNING)/.dockerignore
	$(SSH_RUNNING) 'set -e; \
		cd $(REMOTE_DIR_RUNNING) && \
		git fetch origin && \
		git checkout main && \
		git pull --ff-only origin main && \
		$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml up -d --build && \
		ui_port="$$($(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml port grm_ui 3001 2>/dev/null || true)" && \
		api_port="$$($(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml port ticketing_api 5002 2>/dev/null || true)" && \
		case "$$ui_port" in *":3001") ;; *) echo "ERROR: grm_ui is not published on host :3001 (actual: $$ui_port)"; exit 1;; esac; \
		case "$$api_port" in *":5002") ;; *) echo "ERROR: ticketing_api is not published on host :5002 (actual: $$api_port)"; exit 1;; esac; \
		echo "GRM port check passed: grm_ui=$$ui_port ticketing_api=$$api_port"'

# Validate GRM port mappings are exactly host 3001->3001 and 5002->5002.
check_grm_ports:
	@set -e; \
	ui_port="$$(docker compose -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml port grm_ui 3001 2>/dev/null || true)"; \
	api_port="$$(docker compose -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml port ticketing_api 5002 2>/dev/null || true)"; \
	case "$$ui_port" in \
		*":3001") ;; \
		*) echo "ERROR: grm_ui is not published on host :3001 (actual: '$$ui_port')"; exit 1;; \
	esac; \
	case "$$api_port" in \
		*":5002") ;; \
		*) echo "ERROR: ticketing_api is not published on host :5002 (actual: '$$api_port')"; exit 1;; \
	esac; \
	echo "GRM port check passed: grm_ui=$$ui_port ticketing_api=$$api_port"

# AWS / TLS build from the main worktree to avoid branch/worktree confusion.
compose_docker_aws_main:
	cd /home/philg/projects/nepal_chatbot && $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.aws.yml up -d --build

# SSH into the training remote host
ssh-training:
	$(SSH_TRAINING)

# SSH into the running remote host
ssh-running:
	$(SSH_RUNNING)

# Build and upload the project to the training remote server
build-remote-train-old:
	tar --exclude=$(PROJECT_NAME).tar.gz --exclude=.DS_Store --exclude=__MACOSX -czf $(PROJECT_NAME).tar.gz . && \
	scp -i $(KEY_NAME_TRAINING) $(PROJECT_NAME).tar.gz $(TRAIN_SERVER_USER)@$(REMOTE_HOST_TRAINING):/home/ubuntu && \
	$(SSH_TRAINING) "rm -rf /home/ubuntu/$(masPROJECT_NAME) && mkdir -p /home/ubuntu/$(PROJECT_NAME) && cd /home/ubuntu/$(PROJECT_NAME) && tar -xzf /home/ubuntu/$(PROJECT_NAME).tar.gz && rm /home/ubuntu/$(PROJECT_NAME).tar.gz && docker compose build"

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


# Run the training process on the training remote server
train-remote:
	$(SSH_TRAINING) "cd $(REMOTE_DIR_TRAINING) && \
	docker compose run --entrypoint bash rasa-server /app/start_train.sh"


# Build and upload the project to the running remote server
build-remote-run:
	tar -czf $(PROJECT_NAME).tar.gz . && \
	scp -i $(KEY_NAME_RUNNING) $(PROJECT_NAME).tar.gz $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING):$(REMOTE_DIR_RUNNING) && \
	$(SSH_RUNNING) "cd $(REMOTE_DIR_RUNNING) && tar -xzf $(PROJECT_NAME).tar.gz && rm $(PROJECT_NAME).tar.gz && $(DOCKER_COMPOSE) build"

# Run the project on the running remote server
run-remote:
	$(SSH_RUNNING) "cd $(REMOTE_DIR_RUNNING) && $(DOCKER_COMPOSE) up -d"

# Test training locally
train-local:
	bash /app/start_train.sh

# Clean up temporary files locally
clean:
	rm -rf $(PROJECT_NAME).tar.gz

# Docker-only runtime: host-level process/systemd controls removed.