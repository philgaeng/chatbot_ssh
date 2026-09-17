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

# Branch that remote deploys check out + fast-forward on the server.
# Default `main` (production). AWS staging overrides this to `integration/stage`
# via target-specific vars on the aws-deploy* targets (see the AWS section).
DEPLOY_BRANCH ?= main

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
# ⚠ Defaults MEASURED on the DOR host 2026-09-16 (GRM-136). They were `ubuntu` and
# /home/ubuntu/nepal_chatbot, which exist on staging and on no production box — every prod
# target cd'd into a path that was not there. Override in env.local if a host differs.
PROD_SERVER_USER ?= $(if $(_env_prod_user),$(_env_prod_user),administrator)
PROD_HOST ?= $(if $(_env_prod_host),$(_env_prod_host),103.175.193.226)
# Expand ${PROD_SERVER_USER} in path (env.local is not shell — Make substitutes after read).
_prod_remote_dir := $(shell u='$(PROD_SERVER_USER)'; d='$(_env_prod_dir)'; \
  printf '%s' "$$d" | sed "s|\$${PROD_SERVER_USER}|$$u|g; s|\$$(PROD_SERVER_USER)|$$u|g")
PROD_REMOTE_DIR ?= $(if $(_env_prod_dir),$(_prod_remote_dir),/opt/grms)
PROD_SSH_KEY ?= $(_env_prod_ssh_key)
PROD_SSH_IDENTITY = $(if $(PROD_SSH_KEY),-i $(PROD_SSH_KEY),)
PROD_SSH_OPTS ?= -o ConnectTimeout=30 -o StrictHostKeyChecking=accept-new
SSH_PROD = ssh $(PROD_SSH_IDENTITY) $(PROD_SSH_OPTS) $(PROD_SERVER_USER)@$(PROD_HOST)
SCP_PROD = scp $(PROD_SSH_IDENTITY) $(PROD_SSH_OPTS)

DOCKER_COMPOSE = docker compose --env-file env.local
COMPOSE_WSL = $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.grm.yml
COMPOSE_WSL_AUTH = $(COMPOSE_WSL) --profile auth
COMPOSE_AWS = $(DOCKER_COMPOSE) -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml
# Deployed envs run Keycloak — bring it up via the auth profile (the single grm_ui/
# ticketing_api are always-on; only keycloak is profile-gated).
COMPOSE_AWS_AUTH = $(COMPOSE_AWS) --profile auth

# Remote hosts (AWS + prod) use the same compose overlay on the server.
# COMPOSE_PARALLEL_LIMIT=1 — EC2 stalls when multiple Next.js + Python images build at once.
REMOTE_COMPOSE = COMPOSE_PARALLEL_LIMIT=1 docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  --profile auth

# ⛔ Production runs a FOURTH overlay, and omitting it takes the site down (GRM-141, measured
# 2026-09-16 by doing it). REMOTE_COMPOSE stops at aws.yml, which sets
# NGINX_SITE_CONF=webchat_rest_compose_aws.conf — STAGING's server_name — and whose volume set
# lacks the certbot mounts. docker-compose.prod.yml restores both, and must come LAST so its
# `volumes: !override` wins. Every prod-* target below overrides REMOTE_COMPOSE with this.
PROD_REMOTE_COMPOSE = COMPOSE_PARALLEL_LIMIT=1 docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  -f docker-compose.prod.yml \
  --profile auth

# ── Stack isolation: project name + host ports (QA-03) ───────────────────────────────────
#
# ⚠ **Every default here is EMPTY, and that is the safety property.** Compose treats an empty
# variable as unset, so the `${VAR:-<literal>}` defaults already in the compose files apply and
# `env.local` still wins where it sets one — verified: exporting `KEYCLOAK_HOST_PORT=` leaves
# keycloak on env.local's 18080. Setting nothing changes nothing, which is what lets this land
# on running hosts without touching them.
#
# ⚠ **COMPOSE_PROJECT_NAME especially.** The ticket's scope said to name the environments
# `grm_wsl` / `grm_aws` / `grm_prod`; its own Risks section said to use whatever name is already
# derived, "or you will detach staging from its own database". **The Risks section is right and
# the scope line is dangerous**, and this is not hypothetical: the dev box derives
# `nepal_chatbot` and owns `nepal_chatbot_postgres_data`. Renaming the project makes compose
# look for `grm_wsl_postgres_data`, not find it, and create an empty one — the seeded database
# still on disk, silently detached. So the real environments keep deriving their name from the
# directory, exactly as they do today, and only the *ephemeral* stack (which has no data to
# lose) gets an explicit one.
#
# ⭐ Directory-derived naming has been providing isolation all along — this machine already
# carries volumes for four checkouts (`nepal_chatbot_`, `_seah_`, `_claude_`, `_integration_`).
# What was missing is a *settable* name, so CI can make a throwaway stack on purpose.
export COMPOSE_PROJECT_NAME ?=

# Published host ports. Empty = the compose file's default = today's literal.
export GRM_UI_HOST_PORT ?=
export TICKETING_API_HOST_PORT ?=
export BACKEND_HOST_PORT ?=
export ORCHESTRATOR_HOST_PORT ?=
export NGINX_HOST_PORT ?=
export POSTGRES_HOST_PORT ?=
export KEYCLOAK_HOST_PORT ?=

# What the port assertions compare against — the variable if set, else today's literal.
# Kept beside the variables so the two cannot drift.
EXPECT_GRM_UI_PORT := $(or $(GRM_UI_HOST_PORT),3001)
EXPECT_TICKETING_API_PORT := $(or $(TICKETING_API_HOST_PORT),5002)

CHATBOT_SERVICES := db redis orchestrator backend celery_default celery_llm nginx
# ops = platform monitor (broker-independent APScheduler); ships with the GRM stack.
# Single stack (CL-03): one ticketing_api (:5002) + one grm_ui (:3001).
TICKETING_SERVICES := db redis ticketing_api grm_celery grm_celery_beat grm_ui ops
# Keycloak is the only profile-gated service (needed only when AUTH_MODE=keycloak).
AUTH_SERVICES := keycloak
# Typical GRM release on EC2: officer UI + ticketing API + chatbot messaging (SMTP) + ops monitor.
# Override: make aws-deploy AWS_DEPLOY_SERVICES='...'
# Build order matters: Python/API images first (ops is a Python image), Next.js UI last (sequential loop below).
AWS_DEPLOY_SERVICES ?= ticketing_api backend celery_default grm_celery grm_celery_beat ops grm_ui
# UI-only release (no migrations, no API/backend rebuild). Add nginx for REST webchat static/conf bind-mounts.
AWS_DEPLOY_LIGHT_SERVICES ?= grm_ui nginx
PROD_DEPLOY_SERVICES ?= ticketing_api backend celery_default grm_celery grm_celery_beat ops grm_ui
PROD_DEPLOY_LIGHT_SERVICES ?= grm_ui nginx

# SEAH service provider directory (chatbot outro — public.seah_service_providers).
# Data-only import; schema via migrate_public (pub009). Commit the CSV after refreshing from xlsx.
SEAH_PROVIDERS_IMPORT_SCRIPT = scripts/database/import_seah_service_providers_xlsx.py
SEAH_PROVIDERS_CSV = scripts/database/seeds/seah_service_providers_kl_road.csv
SEAH_PROVIDERS_SEED_CMD = python $(SEAH_PROVIDERS_IMPORT_SCRIPT) --from-csv --csv $(SEAH_PROVIDERS_CSV)

# ── How a deploy gets its images: pull, or build on the box (QA-02 scope 3) ───────────────
#
# `DEPLOY_BUILD=1` builds on the host, which is what every deploy did until QA-02 and what
# **production still does**. `DEPLOY_BUILD=0` pulls images CI already built.
#
# ⚠ **The default is 1 — build — and that is deliberate.** All four deploy macros are shared
# between the `aws-*` and `prod-*` targets, so a default of 0 would silently convert production
# to pulling from a registry nobody has confirmed it can reach: `curl -sI https://ghcr.io/v2/`
# has never been run from the DOR box (Q-05), and it is VPN-only, so the failure would land in a
# maintenance window with no quick way back. The `aws-*` targets opt **in** to pulling; prod
# opts in the day someone answers that question.
#
# Escape hatches, both directions, and both are real:
#   make aws-deploy DEPLOY_BUILD=1        # registry unreachable — fall back to building
#   make prod-deploy DEPLOY_BUILD=0       # ⚠ only once Q-05 is answered for the DOR host
DEPLOY_BUILD ?= 1

# Which images a pulling deploy asks for. Empty means `local`, which exists only on a dev box —
# so a pulling deploy demands an explicit tag rather than failing later with a registry 404.
IMAGE_TAG ?=
UI_IMAGE_TAG ?=
IMAGE_REGISTRY ?=

# Registry identity for a PULLING deploy (GRM-093 / A-11). Derived from IMAGE_REGISTRY so a
# different registry needs no second place to edit; the default mirrors docker-compose.grm.yml's.
REGISTRY_REF   = $(if $(IMAGE_REGISTRY),$(IMAGE_REGISTRY),ghcr.io/philgaeng/chatbot_ssh)
REGISTRY_HOST  = $(word 1,$(subst /, ,$(REGISTRY_REF)))
REGISTRY_OWNER = $(word 2,$(subst /, ,$(REGISTRY_REF)))

# Exported into every remote command so the compose files on the host resolve the same tags.
# `${VAR:-default}` in compose treats empty as unset, so passing these through blank is safe.
REMOTE_IMAGE_ENV = IMAGE_TAG=$(IMAGE_TAG) UI_IMAGE_TAG=$(UI_IMAGE_TAG) IMAGE_REGISTRY=$(IMAGE_REGISTRY)

# $(1)=services, $(2)=deploy label. The one place the pull/build choice is made.
# ── Registry auth for a pulling deploy (GRM-093 / A-11) ────────────────────────
# D-010 made the repository private on 2026-09-04, so its GHCR packages are private — and a host
# that PULLS a private package needs a credential. There was none, and no login step anywhere in
# this file, so the pulling deploy that `03_operations.md` §6a documents could not actually work:
# every `compose pull` on the host would end in `denied`.
#
# Reads GHCR_READ_TOKEN from env.local — the generated artefact every service already uses, 0600
# on the host — and authenticates with **--password-stdin**. Never `-p`: a token in argv is
# readable by every process on the box through `ps`, and lands in shell history.
#
# ⚠ **An absent token SKIPS, it does not fail.** `make wsl-up`, any `DEPLOY_BUILD=1` deploy and
# any host whose registry is public must keep working untouched. Turning a missing optional
# secret into a failed deploy would be a worse bug than the one this fixes — and `DEPLOY_BUILD=1`
# is precisely the documented fallback for "the registry is unreachable or uncredentialed".
#
# ⚠ **Residue, stated rather than hidden:** a successful login writes a base64 credential into
# `~/.docker/config.json` on the host, which is not encrypted. That is why A-11 specifies a
# read-only, repo-scoped token — the blast radius of that file is the whole control.
define REMOTE_REGISTRY_LOGIN
GHCR_READ_TOKEN="$$(sed -n "s/^GHCR_READ_TOKEN=//p" env.local 2>/dev/null | head -n1)"; \
GHCR_USERNAME="$$(sed -n "s/^GHCR_USERNAME=//p" env.local 2>/dev/null | head -n1)"; \
if [ -n "$$GHCR_READ_TOKEN" ]; then \
	printf "%s" "$$GHCR_READ_TOKEN" \
		| docker login $(REGISTRY_HOST) -u "$${GHCR_USERNAME:-$(REGISTRY_OWNER)}" --password-stdin >/dev/null \
		|| { echo "$(1): ERROR — docker login to $(REGISTRY_HOST) failed. Is GHCR_READ_TOKEN a valid read:packages token? Fallback: make $(1) DEPLOY_BUILD=1"; exit 1; }; \
	echo "$(1): authenticated to $(REGISTRY_HOST) as $${GHCR_USERNAME:-$(REGISTRY_OWNER)}"; \
else \
	echo "$(1): no GHCR_READ_TOKEN in env.local — pulling unauthenticated. Fine for a public registry; a private one answers: denied (A-11)"; \
fi
endef

define REMOTE_ACQUIRE_IMAGES
if [ "$(DEPLOY_BUILD)" = "1" ]; then \
	echo "$(2): DEPLOY_BUILD=1 — building on the host (sequential, COMPOSE_PARALLEL_LIMIT=1)" && \
	$(call REMOTE_BUILD_SERVICES_SEQUENTIAL,$(1),$(2)); \
else \
	if [ -z "$(IMAGE_TAG)" ] || [ "$(IMAGE_TAG)" = "local" ]; then \
		echo "ERROR: $(2) is a pulling deploy (DEPLOY_BUILD=0) but IMAGE_TAG is [$(IMAGE_TAG)]."; \
		echo "  Pass the commit to deploy:  make $(2) IMAGE_TAG=<short-sha>"; \
		echo "  That is also the rollback:  make $(2) IMAGE_TAG=<an-older-sha>"; \
		echo "  To build on the box instead: make $(2) DEPLOY_BUILD=1"; \
		exit 1; \
	fi; \
	$(call REMOTE_REGISTRY_LOGIN,$(2)); \
	echo "$(2): pulling images at IMAGE_TAG=$(IMAGE_TAG)" && \
	$(REMOTE_IMAGE_ENV) $(REMOTE_COMPOSE) pull $(1); \
fi
endef

# $(1)=services, $(2)=label. What is ACTUALLY running, after `up -d`, per service.
#
# ⚠ **This exists because a pulling deploy can succeed while changing nothing.** If IMAGE_TAG is
# not bumped, `up -d` is a no-op and the deploy prints OK having deployed the previous build —
# the same class of failure as the 2026-09-04 OK line that verified two ports and nothing else.
# A digest is the only answer to "is the running container the commit I asked for", and it is
# cheap enough to print on every deploy.
define REMOTE_REPORT_DIGESTS
echo "$(2): running images —" && \
for svc in $(1); do \
	cid="$$($(REMOTE_COMPOSE) ps -q $$svc 2>/dev/null | head -1)"; \
	if [ -n "$$cid" ]; then \
		img="$$(docker inspect --format "{{.Config.Image}}" $$cid 2>/dev/null)"; \
		dig="$$(docker inspect --format "{{index .Image}}" $$cid 2>/dev/null | cut -c1-19)"; \
		printf "  %-18s %s  %s\n" "$$svc" "$$img" "$$dig"; \
	fi; \
done
endef

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
# ── The migration image must be the deployed image, or the deploy stops (GRM-099) ──
# $(1)=label. Runs after `up -d`, before the first migration.
#
# REMOTE_DEPLOY_CORE used to prefix `up -d` with REMOTE_IMAGE_ENV and NOT the three
# `compose run --rm backend … alembic` lines. On the first real pulling deploy (2026-09-14) those
# resolved IMAGE_TAG=local, found no such image in the registry, and compose FELL BACK TO `build:`
# — a 350 MB backend build on the host, while `make` exited 0 and `aws-deploy OK` printed. Swap
# added an hour earlier absorbed 486 MB of it. Worse than the build: the migrations ran the host
# CHECKOUT's code rather than the image's, which a rollback would have turned into migrating with
# the wrong code.
#
# ⚠ Why a guard rather than a flag: `docker compose run` has NO `--no-build` (only `--build` and
# `--pull`), so its fall-back-to-build cannot be switched off from the command line. This resolves
# the exact image `run` will use — with the SAME image env — and refuses if it is not on the host.
#
# ⚠ Brace-grouped on purpose. `set -e` does not fire for a failure inside an `a && b` list; the
# chain is the control. A bare `;` in here would let a failed earlier step fall through.
define REMOTE_ASSERT_MIGRATION_IMAGE
{ MIG_IMG="$$($(REMOTE_IMAGE_ENV) $(REMOTE_COMPOSE) config --images backend 2>/dev/null | grep "/app:" | head -n1)"; \
if [ -z "$$MIG_IMG" ] || ! docker image inspect "$$MIG_IMG" >/dev/null 2>&1; then \
	echo "$(1): ERROR — migrations would run image [$$MIG_IMG], which is not on this host."; \
	echo "  Refusing: compose would silently BUILD it here, and migrate with the code in this checkout (GRM-099)."; \
	exit 1; \
fi; \
echo "$(1): migrations will run $$MIG_IMG"; }
endef

# ── Migrations — ONE definition of "run a migration on the deployed image" (GRM-099) ──
# ⚠ Extracted 2026-09-14 because the untagged-migration defect existed in THREE copies:
# REMOTE_DEPLOY_CORE, REMOTE_DEPLOY_FULL and REMOTE_DEPLOY_OPS — i.e. all six deploy targets,
# staging and production. Fixing the first copy left the other two broken, which is where three
# copies of a block always end. The IMAGE_ENV prefix now lives in exactly one line.
#
# $(1)=alembic.ini path
define REMOTE_MIGRATE_ONE
$(REMOTE_IMAGE_ENV) $(REMOTE_COMPOSE) run --rm --no-deps backend python -m alembic -c $(1) upgrade head
endef

# $(1)=label. All three streams, guarded. Order ticketing → public → ops is preserved from the
# originals; GRM-079 records that CI uses a different order, and this change does not settle that.
define REMOTE_RUN_MIGRATIONS
$(call REMOTE_ASSERT_MIGRATION_IMAGE,$(1)) && \
$(call REMOTE_MIGRATE_ONE,ticketing/migrations/alembic.ini) && \
$(call REMOTE_MIGRATE_ONE,migrations/public/alembic.ini) && \
$(call REMOTE_MIGRATE_ONE,ops/migrations/alembic.ini)
endef

# ── Apply the nginx site config on AWS staging (GRM-103) ─────────────────────────────────────
# $(1)=label. Validate → apply → reload, in that order, every aws deploy.
#
# ⚠ Why this exists at all: nginx is NOT in AWS_DEPLOY_SERVICES, so no deploy ever touched it, and
# its config was a single-file bind mount that `git pull` could not update in place. Every nginx
# change since the last manual recreate was therefore on disk and NOT in force — measured on
# staging 2026-09-14, which is how GRM-014's rate limiting sat merged-but-inert for a week.
#
#   1. VALIDATE in a throwaway container, with the exact config and mounts the real one will use
#      (`bootstrap.sh --test`). ⚠ Never `exec nginx -t` in the RUNNING container as the check: with
#      the old single-file mount it validated the stale copy and passed a config nobody had tested.
#   2. `up -d --no-deps nginx` — recreates ONLY if nginx's compose definition changed (the first time
#      this runs, it switches the mount to a directory). A no-op otherwise.
#   3. RELOAD — applies content-only changes. Retried because a freshly recreated nginx needs a
#      moment before it accepts a signal; a reload that never succeeds fails the deploy loudly.
#
# ⚠ Single quotes are forbidden in here: the whole remote command travels inside '...' over SSH.
define REMOTE_APPLY_NGINX
echo "$(1): validating the nginx site config in a throwaway container" && \
$(REMOTE_COMPOSE) run --rm --no-deps -T nginx "sh /etc/nginx/site/bootstrap.sh --test" && \
echo "$(1): applying nginx" && \
$(REMOTE_COMPOSE) up -d --no-deps nginx && \
{ ok=0; for i in $$(seq 1 30); do $(REMOTE_COMPOSE) exec -T nginx nginx -s reload >/dev/null 2>&1 && { ok=1; break; }; sleep 2; done; \
  [ "$$ok" = 1 ] || { echo "$(1): ERROR nginx did not accept a reload within 60s"; exit 1; }; } && \
echo "$(1): nginx config applied"
endef

define REMOTE_DEPLOY_CORE
set -e; \
	cd $(1) && \
	git fetch origin && \
	git checkout -- docker-compose.aws.yml .dockerignore 2>/dev/null || true && \
	git checkout $(DEPLOY_BRANCH) && \
	git checkout -- docker-compose.aws.yml .dockerignore && \
	git pull --ff-only origin $(DEPLOY_BRANCH) && \
	$(call REMOTE_ACQUIRE_IMAGES,$(2),$(3)) && \
	echo "$(3): starting $(2)" && \
	$(REMOTE_IMAGE_ENV) $(REMOTE_COMPOSE) up -d $(2) && \
	$(call REMOTE_REPORT_DIGESTS,$(2),$(3)) && \
	$(call REMOTE_RUN_MIGRATIONS,$(3))
endef

# Build + migrate + (re)start ONLY the ops monitor on a remote host.
# $(1)=remote dir, $(2)=label. Runs the ops Alembic stream (creates ops schema +
# ops_app role) so the container can connect on first deploy.
define REMOTE_DEPLOY_OPS
set -e; \
	cd $(1) && \
	git fetch origin && \
	git checkout -- docker-compose.aws.yml .dockerignore 2>/dev/null || true && \
	git checkout $(DEPLOY_BRANCH) && \
	git checkout -- docker-compose.aws.yml .dockerignore && \
	git pull --ff-only origin $(DEPLOY_BRANCH) && \
	$(call REMOTE_ACQUIRE_IMAGES,ops,$(2)) && \
	echo "$(2): ops migration (ops.* schema + ops_app role)" && \
	$(call REMOTE_ASSERT_MIGRATION_IMAGE,$(2)) && \
	$(call REMOTE_MIGRATE_ONE,ops/migrations/alembic.ini) && \
	echo "$(2): starting ops" && \
	$(REMOTE_IMAGE_ENV) $(REMOTE_COMPOSE) up -d ops && \
	$(REMOTE_COMPOSE) ps ops
endef

define REMOTE_VERIFY_GRM_PORTS_PROD
ui_port="$$(docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  -f docker-compose.prod.yml --profile auth port grm_ui 3001 2>/dev/null || true)" && \
api_port="$$(docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  -f docker-compose.prod.yml --profile auth port ticketing_api 5002 2>/dev/null || true)" && \
case "$$ui_port" in *":$(EXPECT_GRM_UI_PORT)") ;; *) echo "ERROR: grm_ui not on host :$(EXPECT_GRM_UI_PORT) (actual: $$ui_port)"; exit 1;; esac; \
case "$$api_port" in *":$(EXPECT_TICKETING_API_PORT)") ;; *) echo "ERROR: ticketing_api not on host :$(EXPECT_TICKETING_API_PORT) (actual: $$api_port)"; exit 1;; esac; \
echo "$(1) OK: grm_ui=$$ui_port ticketing_api=$$api_port"
endef

define REMOTE_VERIFY_GRM_PORTS
ui_port="$$(docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  --profile auth port grm_ui 3001 2>/dev/null || true)" && \
api_port="$$(docker compose --env-file env.local \
  -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml \
  --profile auth port ticketing_api 5002 2>/dev/null || true)" && \
case "$$ui_port" in *":$(EXPECT_GRM_UI_PORT)") ;; *) echo "ERROR: grm_ui not on host :$(EXPECT_GRM_UI_PORT) (actual: $$ui_port)"; exit 1;; esac; \
case "$$api_port" in *":$(EXPECT_TICKETING_API_PORT)") ;; *) echo "ERROR: ticketing_api not on host :$(EXPECT_TICKETING_API_PORT) (actual: $$api_port)"; exit 1;; esac; \
echo "$(1) OK: grm_ui=$$ui_port ticketing_api=$$api_port"
endef

# nginx is brought up with --force-recreate (not a plain `up -d nginx`): the .conf is a
# single-file bind mount, and the `git reset --hard` below replaces it with a NEW inode. A
# plain `up -d nginx` sees no service-spec change and won't recreate, so the running container
# keeps the OLD inode's config — even `nginx -s reload` re-reads the stale mount. Recreating
# re-binds the mount to the current file. (wsl-nginx already does this locally for the same reason.)
define REMOTE_DEPLOY_LIGHT
set -e; \
	cd $(1) && \
	git fetch origin && \
	git checkout -- docker-compose.aws.yml .dockerignore 2>/dev/null || true && \
	git checkout $(DEPLOY_BRANCH) && \
	git reset --hard origin/$(DEPLOY_BRANCH) && \
	git checkout -- docker-compose.aws.yml 2>/dev/null || true && \
	$(call REMOTE_ACQUIRE_IMAGES,$(filter-out nginx,$(2)),$(3)) && \
	$(REMOTE_IMAGE_ENV) $(REMOTE_COMPOSE) up -d $(filter-out nginx,$(2)) && \
	$(call REMOTE_REPORT_DIGESTS,$(filter-out nginx,$(2)),$(3)) && \
	$(REMOTE_COMPOSE) up -d --force-recreate nginx && \
	ui_auth_port="$$($(REMOTE_COMPOSE) port grm_ui 3001 2>/dev/null || true)" && \
	case "$$ui_auth_port" in *":$(EXPECT_GRM_UI_PORT)") ;; *) echo "ERROR: grm_ui not on host :$(EXPECT_GRM_UI_PORT) (actual: $$ui_auth_port)"; exit 1;; esac; \
	echo "$(3) OK: grm_ui=$$ui_auth_port nginx=restarted"
endef

define REMOTE_DEPLOY_FULL
set -e; \
	cd $(1) && \
	git fetch origin && \
	git checkout -- docker-compose.aws.yml .dockerignore 2>/dev/null || true && \
	git checkout $(DEPLOY_BRANCH) && \
	git checkout -- docker-compose.aws.yml .dockerignore && \
	git pull --ff-only origin $(DEPLOY_BRANCH) && \
	$(call REMOTE_ACQUIRE_IMAGES,$$($(REMOTE_COMPOSE) config --services),full deploy) && \
	echo "full deploy: starting stack" && \
	$(REMOTE_IMAGE_ENV) $(REMOTE_COMPOSE) up -d && \
	$(call REMOTE_RUN_MIGRATIONS,full deploy)
endef

# $(1)=remote repo directory — upsert SEAH centres from committed CSV (idempotent).
# ── Keycloak realm administration ─────────────────────────────────────────────
#
# The setup script runs inside ticketing_api, which already has the package and the realm
# credentials from env.local. ⚠ **Every flag below exists so a LIVE realm can be changed one
# setting at a time.** The bare run also rewrites demo officers and every client — a bootstrap
# step, not an operation — which is why there is deliberately no aws-/prod- variant of
# `keycloak-setup`.
#
# Added 2026-09-16 (GRM-137). `keycloak-setup` already existed — the BOOTSTRAP, and the only
# one the docs ever mentioned. What had no target was every single-setting flag the script
# grew for live realms: --theme-only, --clients-only, --token-policy-only and
# --clear-invite-passwords were reachable only by hand-writing a docker exec against a named
# container, and --smtp-only did not exist at all. So the documented path to change one realm
# setting on staging was the full run, which rewrites demo officers.
KEYCLOAK_ADMIN_CMD = python -m ticketing.auth.keycloak_setup
# -T only: the image sets WORKDIR /app, so `python -m` resolves the package without PYTHONPATH.
KEYCLOAK_EXEC_OPTS = -T
# APPLY=1 turns the invite-password clean-up from a count into a change (GRM-131).
KC_APPLY = $(if $(filter 1 true yes,$(APPLY)),--apply,)

define REMOTE_KEYCLOAK_ADMIN
set -e; \
cd $(1) && \
$(REMOTE_COMPOSE) exec $(KEYCLOAK_EXEC_OPTS) ticketing_api $(KEYCLOAK_ADMIN_CMD) $(2)
endef

define REMOTE_SEED_SEAH_PROVIDERS
set -e; \
cd $(1) && \
$(REMOTE_COMPOSE) run --rm --no-deps backend $(SEAH_PROVIDERS_SEED_CMD)
endef

.PHONY: help env-local secrets-edit \
	wsl-up wsl-demo-bypass wsl-auth wsl-chatbot wsl-ticketing wsl-nginx wsl-ops wsl-down \
	aws-up aws-deploy aws-deploy-light aws-deploy-full aws-deploy-ops \
	prod-deploy prod-deploy-light prod-deploy-full prod-deploy-ops prod-sync-db-from-aws ssh-prod \
	release-check release-tag hooks \
	test-ticketing test-ticketing-host test-ticketing-unit dev-grm-deps \
	migrate_ticketing migrate_public migrate_ops migrate_all reset_public_dev security-preflight \
	seed_seah_providers seed_seah_providers_xlsx seed_seah_providers_dry_run \
	aws-seed-seah-providers prod-seed-seah-providers \
	keycloak-smtp keycloak-themes keycloak-clients keycloak-token-policy \
	keycloak-clear-invite-passwords \
	aws-keycloak-smtp aws-keycloak-themes aws-keycloak-clients aws-keycloak-token-policy \
	aws-keycloak-clear-invite-passwords \
	prod-keycloak-smtp prod-keycloak-themes prod-keycloak-clients prod-keycloak-token-policy \
	prod-keycloak-clear-invite-passwords \
	wsl-auth wsl-auth-ps wsl-keycloak-ps keycloak-setup wsl-seed wsl-seed-locations wsl-seed-full compose_seed_seah_catalog check_grm_ports \
	compose_docker_wsl compose_docker_wsl_full compose_docker_wsl_chatbot chatbot-local \
	compose_docker_wsl_ticketing compose_docker_wsl_down compose-down-all stop-all \
	compose_docker_wsl_nginx compose_docker_wsl_grm_demo compose_docker_wsl_grm_auth \
	compose_keycloak_setup compose_docker_aws compose_docker_aws_full compose_docker_aws_main \
	ssh-training ssh-running build-remote-train build-remote-run run-remote train-remote train-local clean

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo "Secrets:"
	@echo "  make env-local        regenerate env.local from .env.shared + secrets.enc.env"
	@echo "  make secrets-edit     edit secrets.enc.env in place (SOPS), then run make env-local"
	@echo ""
	@echo "WSL (local Docker):"
	@echo "  make wsl-up           chatbot + GRM single stack — :3001 UI, :5002 API (dev bypass)"
	@echo "  make wsl-demo-bypass  GRM only — :3001 UI, :5002 API (dev bypass, no Keycloak)"
	@echo "  make wsl-auth         add Keycloak :18080 (set AUTH_MODE=keycloak + KEYCLOAK_ISSUER in env.local, rebuild)"
	@echo "  make wsl-chatbot      chatbot only (db, redis, backend, orchestrator, celery, nginx)"
	@echo "  make wsl-ticketing    alias for wsl-demo-bypass"
	@echo "  make wsl-nginx        recreate nginx after editing deployment/nginx/*.conf"
	@echo "  make wsl-ops          build & (re)start ONLY the ops monitor (run migrate_ops first on fresh DB)"
	@echo "  make wsl-down         stop all containers (base + GRM + auth profile)"
	@echo ""
	@echo "AWS staging (EC2 key SSH — $(REMOTE_HOST_RUNNING)) — deploys branch integration/stage:"
	@echo "  ⚠ 'make env-local' on staging/prod is the dangerous one, NOT aws-deploy."
	@echo "     It overwrites that host's env.local with the ROTATED POSTGRES_PASSWORD while its"
	@echo "     database still holds the pre-rotation one — and deletes ~30 host-only variables,"
	@echo "     incl. DOIT_SMS_BEARER_TOKEN (the Nepal Govt SMS gateway credential)."
	@echo "     Read docs/deployment/18_sops_migration_handover.md §5a first. It has a step with no undo."
	@echo "     aws-deploy does NOT run env-local: it pulls, rebuilds and migrates only."
	@echo "  make aws-up           rebuild & up on this host (aws + GRM compose files)"
	@echo "  make aws-deploy       pull integration/stage, migrate (incl. ops), rebuild AWS_DEPLOY_SERVICES (one image at a time)"
	@echo "  make aws-deploy-light pull integration/stage, rebuild UI (+ nginx); no migrations (sequential builds)"
	@echo "  make aws-deploy-full  pull integration/stage, migrate, rebuild entire stack (sequential builds)"
	@echo "  make aws-deploy-ops   build + ops migration + restart ONLY the ops monitor"
	@echo "  make ssh-running      open SSH session to staging"
	@echo ""
	@echo "Production (VPN + password SSH — $(PROD_HOST)):"
	@echo "  make ssh-prod         open SSH session (prompts for password)"
	@echo "  make prod-deploy      pull main, migrate (incl. ops), rebuild PROD_DEPLOY_SERVICES"
	@echo "  make prod-deploy-light UI-only rebuild (+ nginx); no migrations"
	@echo "  make prod-deploy-full pull main, migrate, rebuild entire stack"
	@echo "  make prod-deploy-ops  build + ops migration + restart ONLY the ops monitor (VPN)"
	@echo "  make prod-sync-db-from-aws CONFIRM=1  replace prod DB from AWS (VPN; downtime OK)"
	@echo "  Override user/dir: PROD_SERVER_USER=... PROD_REMOTE_DIR=/path/to/nepal_chatbot"
	@echo "  Or set PROD_SERVER_USER, PROD_HOST, PROD_REMOTE_DIR, PROD_SSH_KEY in env.local"
	@echo ""
	@echo "Keycloak realm (runs inside ticketing_api; prefix aws- or prod- for those hosts):"
	@echo "  make keycloak-setup          BOOTSTRAP a fresh realm — LOCAL ONLY (also rewrites demo officers)"
	@echo "  make keycloak-smtp           realm mail settings only"
	@echo "  make keycloak-themes         login + email themes only (Keycloak caches themes until it restarts)"
	@echo "  make keycloak-clients        redirect + post-logout URIs only (after a hostname change)"
	@echo "  make keycloak-token-policy   token lifespans only"
	@echo "  make keycloak-clear-invite-passwords [APPLY=1]   GRM-131; counts unless APPLY=1"
	@echo "  e.g. make aws-keycloak-smtp · make prod-keycloak-themes"
	@echo "  ⚠ There is no aws-/prod- keycloak-setup: on a live realm the full run rewrites"
	@echo "     demo officers and every client. Change one setting at a time."
	@echo ""
	@echo "DB / optional:"
	@echo "  make migrate_all              all Alembic streams (ticketing.* + public.* + ops.*)"
	@echo "  make seed_seah_providers      upsert SEAH centres from committed CSV (local Docker)"
	@echo "  make seed_seah_providers_xlsx refresh CSV from Excel + upsert (after workbook update)"
	@echo "  make aws-seed-seah-providers  upsert SEAH centres on staging EC2"
	@echo "  make prod-seed-seah-providers upsert SEAH centres on prod (VPN)"
	@echo "  make wsl-seed                 re-seed GRM demo tickets (first-time / reset)"
	@echo "  make test-ticketing     pytest tests/ticketing in ticketing_api container"
	@echo "  make test-ticketing-host pytest on WSL host (needs dev-grm-deps + db :5433)"
	@echo "  make dev-grm-deps   pip install -r requirements.grm.txt (host conda env)"
	@echo "  make wsl-keycloak-ps  show Keycloak container status (after wsl-auth)"
	@echo "  make wsl-auth-ps      show Keycloak + grm_ui + ticketing_api"
	@echo "  make keycloak-setup   bootstrap GRM realm (once, after Keycloak is healthy)"

# ── Secrets (SOPS + age) — docs/deployment/13_security.md §5 ───────────────────
# env.local is a GENERATED artefact:
#     .env.shared (committed, plaintext) + secrets.enc.env (committed, SOPS) -> env.local
# Never hand-edit env.local: the next regeneration discards the edit, and a secret typed
# there never reaches staging or production.
env-local:
	scripts/ops/gen_env_local.sh

# Edit the encrypted half. Decrypts to a temp file, re-encrypts on save — plaintext
# never touches the working tree. Run `make env-local` afterwards to apply.
secrets-edit:
	sops secrets.enc.env
	@echo ""
	@echo "Now run: make env-local"

# ── WSL ────────────────────────────────────────────────────────────────────────
# Full local stack: chatbot + single GRM stack (dev bypass). REST webchat: http://localhost:8080/
# Uses env.local APP_ENV=dev AUTH_MODE=bypass — no Keycloak. For real OIDC use wsl-auth.
wsl-up:
	$(COMPOSE_WSL) up -d --build
	@echo ""
	@echo "GRM (dev bypass): http://localhost:3001  → ticketing_api :5002"
	@echo "For real OIDC: set AUTH_MODE=keycloak + KEYCLOAK_ISSUER in env.local, then make wsl-auth"

# GRM single stack only — :3001 UI + :5002 API (dev bypass, no Keycloak).
wsl-demo-bypass:
	$(COMPOSE_WSL) up -d --build $(TICKETING_SERVICES)
	@echo ""
	@echo "GRM (dev bypass): http://localhost:3001  → ticketing_api :5002"

wsl-chatbot:
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d --build $(CHATBOT_SERVICES)

wsl-ticketing: wsl-demo-bypass

wsl-nginx:
	$(DOCKER_COMPOSE) -f docker-compose.yml up -d --force-recreate nginx

# Build & (re)start ONLY the ops monitor locally (run `make migrate_ops` first on a fresh DB).
wsl-ops:
	$(COMPOSE_WSL) up -d --build ops
	$(COMPOSE_WSL) ps ops

wsl-down:
	$(COMPOSE_WSL_AUTH) down $(COMPOSE_DOWN_FLAGS)

# ── AWS ────────────────────────────────────────────────────────────────────────
# AWS staging is our stage box: it tracks the integration branch, not main.
# Prod deploys keep DEPLOY_BRANCH=main (the default) — this override is scoped to
# the aws-deploy* targets only.
aws-deploy aws-deploy-light aws-deploy-full aws-deploy-ops: DEPLOY_BRANCH := integration/stage

# On the EC2 host (already in repo directory). Chatbot + GRM + Keycloak (auth profile).
aws-up:
	$(COMPOSE_AWS_AUTH) up -d --build

# Remote deploy: pull integration/stage, migrations, rebuild selected services (default GRM UI/API + messaging backend).
# ── Staging pulls; production still builds (QA-02 scope 3) ───────────────────────────────
# These four opt IN to pulling CI-built images. `prod-*` deliberately does not: nobody has run
# `curl -sI https://ghcr.io/v2/` from the VPN-only DOR host yet (Q-05), so converting it would
# be a change nobody has tested landing in a maintenance window. Override per invocation —
# `make aws-deploy DEPLOY_BUILD=1` falls back to building if the registry is unreachable.
aws-deploy: DEPLOY_BUILD = 0
aws-deploy:
	$(SCP_RUNNING) .dockerignore $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING):$(REMOTE_DIR_RUNNING)/.dockerignore
	$(SSH_RUNNING) '$(call REMOTE_DEPLOY_CORE,$(REMOTE_DIR_RUNNING),$(AWS_DEPLOY_SERVICES),aws-deploy) && $(call REMOTE_APPLY_NGINX,aws-deploy) && $(call REMOTE_VERIFY_GRM_PORTS,aws-deploy)'

# Light remote deploy: officer UI (+ optional nginx for bind-mounted webchat). Skips migrations and API/backend.
aws-deploy-light: DEPLOY_BUILD = 0
aws-deploy-light:
	$(SSH_RUNNING) '$(call REMOTE_DEPLOY_LIGHT,$(REMOTE_DIR_RUNNING),$(AWS_DEPLOY_LIGHT_SERVICES),aws-deploy-light)'

# Full remote deploy: entire stack (Rasa, orchestrator, all celery, etc.).
aws-deploy-full: DEPLOY_BUILD = 0
aws-deploy-full:
	$(SCP_RUNNING) .dockerignore $(RUN_SERVER_USER)@$(REMOTE_HOST_RUNNING):$(REMOTE_DIR_RUNNING)/.dockerignore
	$(SSH_RUNNING) '$(call REMOTE_DEPLOY_FULL,$(REMOTE_DIR_RUNNING)) && $(call REMOTE_APPLY_NGINX,aws-deploy-full) && $(call REMOTE_VERIFY_GRM_PORTS,aws-deploy-full)'

# Ops-only deploy: build + migrate (ops stream) + restart just the ops monitor on staging.
aws-deploy-ops: DEPLOY_BUILD = 0
aws-deploy-ops:
	$(SSH_RUNNING) '$(call REMOTE_DEPLOY_OPS,$(REMOTE_DIR_RUNNING),aws-deploy-ops)'

# ── Git hooks ─────────────────────────────────────────────────────────────────
# Hooks live in .githooks/ (committed, reviewable) rather than .git/hooks (per-clone,
# invisible, unversioned). One command per clone points git at them.
hooks:
	@git config core.hooksPath .githooks
	@echo "hooks enabled: core.hooksPath = .githooks"
	@echo "  pre-commit  a spec edit and its date ride the same commit (doc_headers.py --check-staged)"
	@echo "  bypass:     git commit --no-verify   (loudly, and say why in the message)"

# ── Release gate (D-009 · docs/deployment/20_release_and_versioning.md) ───────
# A version is cut when, and only when, a build is deployed to production. The tag
# is REQUIRED, not cut by the deploy: a deploy that tags on entry leaves a tag for a
# release that then failed halfway, and one that tags on success cannot tag a commit
# if the deploy died. Requiring it first means the tag names a commit somebody chose.
RELEASE_TAG_RE := ^v[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[0-9]+)?$$

release-check:
	@tag="$$(git tag --points-at HEAD | grep -E '$(RELEASE_TAG_RE)' | head -1)"; \
	if [ -n "$$tag" ]; then \
	  echo "release gate OK — HEAD is $$tag"; \
	elif [ "$(HOTFIX)" = "1" ]; then \
	  echo ""; \
	  echo "  ############################################################"; \
	  echo "  ##  HOTFIX DEPLOY — NO RELEASE TAG ON HEAD                ##"; \
	  echo "  ##  A tag is OWED, today. Cut it as soon as the fire is   ##"; \
	  echo "  ##  out:   make release-tag && git push origin <tag>      ##"; \
	  echo "  ##  Policy: docs/deployment/20_release_and_versioning.md  ##"; \
	  echo "  ############################################################"; \
	  echo ""; \
	else \
	  echo ""; \
	  echo "REFUSING TO DEPLOY: HEAD carries no release tag."; \
	  echo ""; \
	  echo "  A version is cut when, and only when, a build is deployed to"; \
	  echo "  production (D-009). Cut it, then deploy:"; \
	  echo ""; \
	  echo "      make release-tag"; \
	  echo "      make $(MAKECMDGOALS)"; \
	  echo ""; \
	  echo "  Genuine emergency? Bypass LOUDLY and tag the same day:"; \
	  echo ""; \
	  echo "      make $(MAKECMDGOALS) HOTFIX=1"; \
	  echo ""; \
	  echo "  Policy: docs/deployment/20_release_and_versioning.md"; \
	  echo ""; \
	  exit 1; \
	fi

# Cut today's release tag. vYYYY.MM.DD, with .N for a second release the same day.
release-tag:
	@existing="$$(git tag --points-at HEAD | grep -E '$(RELEASE_TAG_RE)' | head -1)"; \
	if [ -n "$$existing" ]; then \
	  echo "HEAD already carries $$existing — nothing to cut."; exit 1; \
	fi; \
	base="v$$(date +%Y.%m.%d)"; tag="$$base"; n=0; \
	while git rev-parse -q --verify "refs/tags/$$tag" >/dev/null 2>&1; do \
	  n=$$((n+1)); tag="$$base.$$n"; \
	done; \
	git tag -a "$$tag" -m "Release $$tag"; \
	echo "cut $$tag at $$(git rev-parse --short HEAD)"; \
	echo "push it:  git push origin $$tag"; \
	prev="$$(git tag --list --merged HEAD^ | grep -E '$(RELEASE_TAG_RE)' | sort | tail -1)"; \
	if [ -n "$$prev" ]; then \
	  echo "changelog: seed with  git log --oneline $$prev..$$tag"; \
	else \
	  echo "changelog: first release — seed with  git log --oneline $$tag"; \
	fi

# ── Production (VPN + password SSH) ───────────────────────────────────────────
# Requires VPN. No -i key: ssh/scp prompt for PROD_SERVER_USER password.
ssh-prod:
	@echo "VPN required. Connecting to $(PROD_SERVER_USER)@$(PROD_HOST) (password prompt)..."
	$(SSH_PROD)

prod-deploy: REMOTE_COMPOSE = $(PROD_REMOTE_COMPOSE)
prod-deploy: release-check
	@echo "VPN required. Deploying to $(PROD_HOST) as $(PROD_SERVER_USER) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_DEPLOY_CORE,$(PROD_REMOTE_DIR),$(PROD_DEPLOY_SERVICES),prod-deploy) && $(call REMOTE_VERIFY_GRM_PORTS_PROD,prod-deploy)'

prod-deploy-light: REMOTE_COMPOSE = $(PROD_REMOTE_COMPOSE)
prod-deploy-light: release-check
	@echo "VPN required. Light deploy to $(PROD_HOST) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_DEPLOY_LIGHT,$(PROD_REMOTE_DIR),$(PROD_DEPLOY_LIGHT_SERVICES),prod-deploy-light)'

prod-deploy-full: REMOTE_COMPOSE = $(PROD_REMOTE_COMPOSE)
prod-deploy-full: release-check
	@echo "VPN required. Full deploy to $(PROD_HOST) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_DEPLOY_FULL,$(PROD_REMOTE_DIR)) && $(call REMOTE_VERIFY_GRM_PORTS_PROD,prod-deploy-full)'

# Ops-only deploy: build + migrate (ops stream) + restart just the ops monitor on prod.
prod-deploy-ops: REMOTE_COMPOSE = $(PROD_REMOTE_COMPOSE)
prod-deploy-ops: release-check
	@echo "VPN required. Deploying ops monitor to $(PROD_HOST) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_DEPLOY_OPS,$(PROD_REMOTE_DIR),prod-deploy-ops)'

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

migrate_ops:
	$(DOCKER_COMPOSE) run --rm --no-deps backend python -m alembic -c ops/migrations/alembic.ini upgrade head

# Security pre-promotion gate (docs/services/12_security_monitoring_service.md §4).
# Runs on the HOST (reads env.local, TLS cert, backup status). Non-zero exit blocks promotion.
security-preflight:
	./scripts/ops/security-preflight.sh $(CURDIR)

migrate_all: migrate_ticketing migrate_public migrate_ops

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

prod-seed-seah-providers: REMOTE_COMPOSE = $(PROD_REMOTE_COMPOSE)
prod-seed-seah-providers:
	@echo "VPN required. Seeding SEAH providers on $(PROD_HOST) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_SEED_SEAH_PROVIDERS,$(PROD_REMOTE_DIR))'

# ── Keycloak: local (WSL) ─────────────────────────────────────────────────────
# The bootstrap itself is `keycloak-setup`, further down beside the other wsl-* targets.
# ⚠ It also rewrites demo officers, which is why it has no aws-/prod- variant.
keycloak-smtp:
	$(COMPOSE_WSL_AUTH) exec $(KEYCLOAK_EXEC_OPTS) ticketing_api $(KEYCLOAK_ADMIN_CMD) --smtp-only

keycloak-themes:
	$(COMPOSE_WSL_AUTH) exec $(KEYCLOAK_EXEC_OPTS) ticketing_api $(KEYCLOAK_ADMIN_CMD) --theme-only

keycloak-clients:
	$(COMPOSE_WSL_AUTH) exec $(KEYCLOAK_EXEC_OPTS) ticketing_api $(KEYCLOAK_ADMIN_CMD) --clients-only

keycloak-token-policy:
	$(COMPOSE_WSL_AUTH) exec $(KEYCLOAK_EXEC_OPTS) ticketing_api $(KEYCLOAK_ADMIN_CMD) --token-policy-only

keycloak-clear-invite-passwords:
	$(COMPOSE_WSL_AUTH) exec $(KEYCLOAK_EXEC_OPTS) ticketing_api $(KEYCLOAK_ADMIN_CMD) --clear-invite-passwords $(KC_APPLY)

# ── Keycloak: AWS staging ─────────────────────────────────────────────────────
aws-keycloak-smtp:
	$(SSH_RUNNING) '$(call REMOTE_KEYCLOAK_ADMIN,$(REMOTE_DIR_RUNNING),--smtp-only)'

aws-keycloak-themes:
	$(SSH_RUNNING) '$(call REMOTE_KEYCLOAK_ADMIN,$(REMOTE_DIR_RUNNING),--theme-only)'

aws-keycloak-clients:
	$(SSH_RUNNING) '$(call REMOTE_KEYCLOAK_ADMIN,$(REMOTE_DIR_RUNNING),--clients-only)'

aws-keycloak-token-policy:
	$(SSH_RUNNING) '$(call REMOTE_KEYCLOAK_ADMIN,$(REMOTE_DIR_RUNNING),--token-policy-only)'

aws-keycloak-clear-invite-passwords:
	$(SSH_RUNNING) '$(call REMOTE_KEYCLOAK_ADMIN,$(REMOTE_DIR_RUNNING),--clear-invite-passwords $(KC_APPLY))'

# ── Keycloak: DOR production (VPN + password SSH) ─────────────────────────────
prod-keycloak-smtp: REMOTE_COMPOSE = $(PROD_REMOTE_COMPOSE)
prod-keycloak-smtp:
	@echo "VPN required. Applying realm SMTP on $(PROD_HOST) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_KEYCLOAK_ADMIN,$(PROD_REMOTE_DIR),--smtp-only)'

prod-keycloak-themes: REMOTE_COMPOSE = $(PROD_REMOTE_COMPOSE)
prod-keycloak-themes:
	@echo "VPN required. Applying realm themes on $(PROD_HOST) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_KEYCLOAK_ADMIN,$(PROD_REMOTE_DIR),--theme-only)'

prod-keycloak-clients: REMOTE_COMPOSE = $(PROD_REMOTE_COMPOSE)
prod-keycloak-clients:
	@echo "VPN required. Applying realm clients on $(PROD_HOST) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_KEYCLOAK_ADMIN,$(PROD_REMOTE_DIR),--clients-only)'

prod-keycloak-token-policy: REMOTE_COMPOSE = $(PROD_REMOTE_COMPOSE)
prod-keycloak-token-policy:
	@echo "VPN required. Applying realm token policy on $(PROD_HOST) (password prompt)..."
	$(SSH_PROD) '$(call REMOTE_KEYCLOAK_ADMIN,$(PROD_REMOTE_DIR),--token-policy-only)'

prod-keycloak-clear-invite-passwords: REMOTE_COMPOSE = $(PROD_REMOTE_COMPOSE)
prod-keycloak-clear-invite-passwords:
	@echo "VPN required. Invite-password clean-up on $(PROD_HOST) — counts only unless APPLY=1..."
	$(SSH_PROD) '$(call REMOTE_KEYCLOAK_ADMIN,$(PROD_REMOTE_DIR),--clear-invite-passwords $(KC_APPLY))'

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

# ── Optional: real Keycloak auth (local) ──────────────────────────────────────
# Brings up Keycloak :18080 and rebuilds the single grm_ui/ticketing_api under the
# auth profile. For a REAL-auth build, first set in env.local:
#   AUTH_MODE=keycloak  KEYCLOAK_ISSUER=http://localhost:18080/realms/grm
# (otherwise the UI/API rebuild in dev-bypass mode). :3001 UI, :5002 API.
wsl-auth:
	$(COMPOSE_WSL_AUTH) up -d --build $(AUTH_SERVICES) ticketing_api grm_ui
	@echo ""
	@echo "GRM (OIDC): http://localhost:3001  → ticketing_api :5002"
	@echo "Keycloak admin:  http://localhost:18080"

# Keycloak status (requires `make wsl-auth` first).
wsl-keycloak-ps:
	$(COMPOSE_WSL_AUTH) ps keycloak

wsl-auth-ps:
	$(COMPOSE_WSL_AUTH) ps keycloak grm_ui ticketing_api

keycloak-setup compose_keycloak_setup:
	$(COMPOSE_WSL_AUTH) exec -T ticketing_api python -m ticketing.auth.keycloak_setup

# GRM demo tickets in ticketing.* (idempotent with --reset).
wsl-seed:
	$(COMPOSE_WSL) exec -T ticketing_api python -m ticketing.seed.mock_tickets --reset

# Import Nepal geodata into ticketing.locations (idempotent upsert, ~837 nodes). Required by
# mock_tickets + the test suite for location-hierarchy resolution; empty locations is a
# recurring setup gap (org territory FK + auto-assign hierarchy silently break).
wsl-seed-locations:
	$(COMPOSE_WSL) exec -T ticketing_api python -m ticketing.seed.import_locations_json \
	  --country NP --en backend/dev-resources/location_dataset/en_cleaned.json \
	  --ne backend/dev-resources/location_dataset/ne_cleaned.json --max-level 3

# Full dev seed in dependency order (geodata first, then workflows/officers/tickets). One
# command so the location import is never skipped. Run after `make migrate_all`.
wsl-seed-full: wsl-seed-locations wsl-seed

# ── Ephemeral stack (QA-03 scope 4) — what QA-05's e2e job brings up ─────────────────────
#
# A fully isolated stack: its own project name, its own volumes, its own ports. Tearing it
# down takes the volumes with it, so nothing survives a run.
#
# ⭐ **Ports are a fixed alternate block, not random.** The ticket said "random-ish"; the
# *purpose* is not colliding with a dev stack, and a fixed block achieves that while staying
# something a human can point a browser at and a test suite can be configured with. Random
# ports would have to be discovered and passed around, which is machinery in exchange for
# nothing — a CI runner hosts one stack.
#
# ⚠ **The repo must be present, not just the images.** `nginx` is `image: nginx:stable` and is
# never built: it bind-mounts `./channels/REST_webchat`, `./channels/shared` and its `.conf`
# from the checkout, so the webchat is served from the working tree. This is the one place
# where "pull, don't build" does not describe what happens. Free on a CI runner; worth saying.
#
#   make ephemeral-up                                  # officer UI only (QA-04b/c)
#   make ephemeral-up-full                             # + the webchat half (QA-04d)
#   make ephemeral-up UI_IMAGE_TAG=<sha>-bypass IMAGE_TAG=<sha>   # what QA-05 runs
#   make ephemeral-down                                # containers AND volumes
#
EPHEMERAL_PROJECT ?= grm_ci_$(or $(GITHUB_RUN_ID),local)

# QA-04b/c need the officer UI; QA-04d needs the chatbot half as well. Named explicitly rather
# than left to a bare `up -d`, so a suite cannot silently depend on a service nobody meant to run.
EPHEMERAL_UI_SERVICES      := db redis ticketing_api grm_celery grm_celery_beat grm_ui
EPHEMERAL_WEBCHAT_SERVICES := orchestrator backend celery_default celery_llm nginx
EPHEMERAL_SERVICES         ?= $(EPHEMERAL_UI_SERVICES)

# One block away from the dev stack's 3001/5002/8080/5433, so both can run at once.
#
# ⚠ KEYCLOAK_ADMIN_URL points at a port that REFUSES, on purpose (GRM-107). This stack runs no
# Keycloak, but compose defaults the URL to http://keycloak:8080, and a lookup of a host that does
# not exist is not fast: measured, 3.6 s per DNS miss plus a client retry, ~13 s per roster request.
# The Staffing pane waited on it and a spec went flaky. A refused connection fails in milliseconds.
EPHEMERAL_ENV = COMPOSE_PROJECT_NAME=$(EPHEMERAL_PROJECT) \
  KEYCLOAK_ADMIN_URL=http://127.0.0.1:9 \
  GRM_UI_HOST_PORT=$(or $(EPH_UI_PORT),13001) \
  TICKETING_API_HOST_PORT=$(or $(EPH_API_PORT),15002) \
  NGINX_HOST_PORT=$(or $(EPH_NGINX_PORT),18081) \
  POSTGRES_HOST_PORT=$(or $(EPH_DB_PORT),15433) \
  BACKEND_HOST_PORT=$(or $(EPH_BACKEND_PORT),15001) \
  ORCHESTRATOR_HOST_PORT=$(or $(EPH_ORCH_PORT),18000) \
  IMAGE_TAG=$(IMAGE_TAG) UI_IMAGE_TAG=$(UI_IMAGE_TAG) IMAGE_REGISTRY=$(IMAGE_REGISTRY)

.PHONY: ephemeral-up ephemeral-up-full ephemeral-down

ephemeral-up:
	@echo "ephemeral: project=$(EPHEMERAL_PROJECT) services=$(EPHEMERAL_SERVICES)"
	@echo "ephemeral: ui=http://localhost:$(or $(EPH_UI_PORT),13001) api=http://localhost:$(or $(EPH_API_PORT),15002) webchat=http://localhost:$(or $(EPH_NGINX_PORT),18081)/rest-webchat/"
	$(EPHEMERAL_ENV) $(COMPOSE_WSL) up -d $(EPHEMERAL_SERVICES)
	@echo "ephemeral: waiting for the database"
	@until $(EPHEMERAL_ENV) $(COMPOSE_WSL) exec -T db pg_isready -q; do sleep 2; done
	@echo "ephemeral: migrations (ticketing -> public -> ops, the Makefile's order — see GRM-079)"
	$(EPHEMERAL_ENV) $(COMPOSE_WSL) run --rm --no-deps ticketing_api python -m alembic -c ticketing/migrations/alembic.ini upgrade head
	$(EPHEMERAL_ENV) $(COMPOSE_WSL) run --rm --no-deps ticketing_api python -m alembic -c migrations/public/alembic.ini upgrade head
	$(EPHEMERAL_ENV) $(COMPOSE_WSL) run --rm --no-deps ticketing_api python -m alembic -c ops/migrations/alembic.ini upgrade head
	@echo "ephemeral: seeding (the same two commands backend-tests uses — see ci.yml)"
	$(EPHEMERAL_ENV) $(COMPOSE_WSL) run --rm --no-deps ticketing_api python -m ticketing.seed.import_locations_json \
	  --country NP \
	  --en backend/dev-resources/location_dataset/en_cleaned.json \
	  --ne backend/dev-resources/location_dataset/ne_cleaned.json \
	  --max-level 3
	$(EPHEMERAL_ENV) $(COMPOSE_WSL) run --rm --no-deps ticketing_api python -m ticketing.seed.mock_tickets --reset
	@echo "ephemeral: up"

ephemeral-up-full: EPHEMERAL_SERVICES = $(EPHEMERAL_UI_SERVICES) $(EPHEMERAL_WEBCHAT_SERVICES)
ephemeral-up-full: ephemeral-up

# ⚠ `-v` is the point: without it the volumes outlive the stack and the next run inherits a
# database that is neither empty nor freshly seeded — the single most confusing state a test
# harness can be in.
ephemeral-down:
	@echo "ephemeral: tearing down $(EPHEMERAL_PROJECT) — containers, networks AND volumes"
	-$(EPHEMERAL_ENV) $(COMPOSE_WSL) down -v --remove-orphans
	@left="$$(docker volume ls -q | grep -c '^$(EPHEMERAL_PROJECT)_' || true)"; \
	if [ "$$left" != "0" ]; then echo "WARNING: $$left volume(s) still named $(EPHEMERAL_PROJECT)_*"; \
	else echo "ephemeral: nothing left behind"; fi

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

# ⚠ **`--env-file env.local` added 2026-09-07 — without it this target could only ever FAIL.**
# Every other compose invocation in this file passes it; this one did not, so interpolation died
# on `POSTGRES_USER is missing a value`, `port` returned nothing, and the check reported
# "grm_ui not on :3001 (actual: )" on any host that keeps its config in env.local — which is all
# of them. Verified pre-existing: identical output from the Makefile at HEAD before QA-03
# touched it. ⭐ A check that cannot pass is the mirror of a check that cannot fail; both are
# decoration, and this one had been reporting a port problem that was never there.
check_grm_ports:
	@set -e; \
	ui_port="$$(docker compose --env-file env.local -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml port grm_ui 3001 2>/dev/null || true)"; \
	api_port="$$(docker compose --env-file env.local -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml port ticketing_api 5002 2>/dev/null || true)"; \
	case "$$ui_port" in *":$(EXPECT_GRM_UI_PORT)") ;; *) echo "ERROR: grm_ui not on :$(EXPECT_GRM_UI_PORT) (actual: $$ui_port)"; exit 1;; esac; \
	case "$$api_port" in *":$(EXPECT_TICKETING_API_PORT)") ;; *) echo "ERROR: ticketing_api not on :$(EXPECT_TICKETING_API_PORT) (actual: $$api_port)"; exit 1;; esac; \
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
