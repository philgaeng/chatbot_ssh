# Variables
PROJECT_NAME = rasa_project

# Training Server
TRAIN_SERVER_USER = ubuntu
REMOTE_HOST_TRAINING = 13.229.238.60
REMOTE_DIR_TRAINING = /home/ubuntu/$(PROJECT_NAME)
KEY_NAME_TRAINING = pg_rasa_train.pem
SSH_TRAINING = ssh -i $(KEY_NAME_TRAINING) $(TRAIN_SERVER_USER)@$(REMOTE_HOST_TRAINING)

# Running Server
RUN_SERVER_USER = ubuntu
REMOTE_HOST_RUNNING = 13.228.123.45  # Replace with your running server IP
REMOTE_DIR_RUNNING = /home/ubuntu/$(PROJECT_DIRECTORY)
KEY_NAME_RUNNING = pg_rasa_train.pem
SSH_RUNNING = ssh -i $(KEY_NAME_RUNNING) $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING)

# Docker Compose Command
DOCKER_COMPOSE = docker compose

# --- Local WSL (default docker-compose.yml: nginx :80, orchestrator, backend, redis, db, celery) ---
# Run from repo root. Requires env.local; free host port 80 if nginx binds 80:80.
.PHONY: compose_docker_wsl compose_docker_wsl_down compose_docker_wsl_nginx compose_docker_aws compose_seed_seah_catalog

compose_docker_wsl:
	$(DOCKER_COMPOSE) up -d --build

# Seed projects + Jhapa SEAH contact points into Compose Postgres (app_db).
# Compose overrides DATABASE_URL to db:5432/app_db — host-only seeds do not apply here.
compose_seed_seah_catalog:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python scripts/database/migrate_seah_demo_catalog.py

compose_docker_wsl_down:
	$(DOCKER_COMPOSE) down

# Recreate only nginx after editing deployment/nginx/webchat_rest_compose_wsl.conf
compose_docker_wsl_nginx:
	$(DOCKER_COMPOSE) up -d --force-recreate nginx

# AWS / TLS: uses docker-compose.aws.yml override (443, cert mounts)
compose_docker_aws:
	$(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.aws.yml up -d --build

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

# Test the Rasa server locally
run-local:
	docker-compose up -d

# Clean up temporary files locally
clean:
	rm -rf $(PROJECT_NAME).tar.gz

kill_action_server:
	pkill -f "rasa run actions"

# Systemd service management commands
systemd-start:
	sudo systemctl start rasa.service rasa-actions.service nginx

systemd-stop:
	sudo systemctl stop rasa.service rasa-actions.service

systemd-restart:
	sudo systemctl restart rasa.service rasa-actions.service nginx

systemd-status:
	sudo systemctl status rasa.service rasa-actions.service nginx | cat

systemd-logs:
	sudo tail -n 50 /home/ubuntu/nepal_chatbot/rasa.log