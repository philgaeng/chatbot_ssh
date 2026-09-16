# QA-03 — `COMPOSE_PROJECT_NAME` + parameterised ports

> **Stream A · 1 day · depends on QA-02 · blocks QA-05 (CI stack) and any future sandbox**

## Context

Two stacks cannot coexist on one host or one CI runner today:

- **`COMPOSE_PROJECT_NAME` appears nowhere** — not in the Makefile, not in `env.local`, not in any
  compose file. Compose derives the project name from the directory, so two checkouts on one host share
  container names, the default network and the named volumes (`postgres_data`, `uploads_data`,
  `backups_data`).
- **Five host ports are literals:** `5001:5001` (backend), `8000:8000` (orchestrator), `5002:5002`
  (ticketing_api), `3001:3001` (grm_ui) — all four in `docker-compose.grm.yml` — and `8080:80` (nginx)
  in `docker-compose.yml`.
  ⭐ **Two are already parameterised and are the pattern to copy:**
  `${KEYCLOAK_HOST_PORT:-18080}:8080` and `${POSTGRES_HOST_PORT:-5433}:5432`
  (`docker-compose.grm.yml:87,109`). Match their shape exactly — this is not a new convention.
- **Four places assert ports by hand, not one.** `check_grm_ports` (`Makefile:520`) is the obvious one;
  `REMOTE_VERIFY_GRM_PORTS` (`:165`), `REMOTE_VERIFY_GRM_PORTS_PROD` (`:153`) and an **inline copy
  inside `REMOTE_DEPLOY_LIGHT`** (`:195-199`) each hardcode `3001`/`5002` as well. Staging and prod keep
  the defaults so they will still pass, but a moved stack fails three checks the ticket did not name.
- ⚠ `docker-compose.aws.yml` publishes `80:80` and `443:443` for nginx. **Deliberately left as
  literals** — they are the real host's real ports, and running a second stack on the staging host is
  ruled out anyway ([`DESIGN`](DESIGN-qa-and-build-pipeline.md) §3). Say so in the file rather than
  leaving the next reader to wonder whether they were missed.

This is what makes an ephemeral CI stack possible — and it is the only piece of the sandbox idea from
the review-feedback evaluation that survives on its own merits.

## Scope

1. `COMPOSE_PROJECT_NAME` set per environment in the Makefile: `grm_wsl`, `grm_aws`, `grm_prod`, and
   `grm_ci_$(GITHUB_RUN_ID)` for CI. **Volumes inherit the project prefix automatically** — that is the
   isolation, and it means a CI stack's data cannot touch a dev stack's.
2. Every published port becomes `${VAR:-<current default>}:<container port>`, so **existing behaviour is
   unchanged when nothing is set**. Defaults stay exactly what they are today.
3. `check_grm_ports` **and the three other hardcoded assertions** read the same variables instead of
   literals — see the context list; fixing only `check_grm_ports` leaves three.
4. A `make ephemeral-up` / `ephemeral-down` pair that brings up a fully isolated, seeded stack on
   random-ish ports and tears it down **including volumes** — this is what QA-05 calls.
   **Name the service set explicitly in the target; do not leave it to `up -d` with no arguments.**
   QA-04 drives two surfaces, and they do not need the same stack:
   | Needed by | Services |
   |---|---|
   | QA-04b/c — officer UI | `db redis ticketing_api grm_celery grm_celery_beat grm_ui` (= `TICKETING_SERVICES` minus `ops`) |
   | QA-04d — webchat | **plus** `orchestrator backend celery_default celery_llm nginx` (= `CHATBOT_SERVICES`) |
   ⚠ **`nginx` bind-mounts `./channels/REST_webchat`, `./channels/shared` and its `.conf` from the
   checkout** — it is `image: nginx:stable` and is never built, so the webchat is served from the
   working tree, not from a pulled image. An ephemeral stack therefore needs the **repo present**, not
   just the images. That is free on a CI runner, but it must be said, because it is the one place where
   "pull, don't build" does not describe what happens.
   ⭐ `ephemeral-up` must also accept **`UI_IMAGE_TAG`** (QA-02 scope 1) so the stack can run the
   bypass UI variant. Without it QA-05 has a stack it cannot log into.

## Not in scope

Any change to service configuration, networking between services (they talk by service name and are
unaffected), or the nginx config. Running two stacks on the **staging host** — ruled out by the
incident, see [`DESIGN`](DESIGN-qa-and-build-pipeline.md) §3.

## Files

| File | Change |
|---|---|
| `Makefile` | `COMPOSE_PROJECT_NAME` per target; port vars; **all four** port assertions de-literalised (`check_grm_ports`, `REMOTE_VERIFY_GRM_PORTS`, `_PROD`, and the inline copy in `REMOTE_DEPLOY_LIGHT`); `ephemeral-up`/`ephemeral-down` with an explicit service set + `UI_IMAGE_TAG` |
| `docker-compose.yml`, `docker-compose.grm.yml` | five `ports:` entries parameterised |
| `env.local` / `.env.example` | the new port vars, documented with their defaults |
| `docs/deployment/02_setup.md`, `03_operations.md` | how to run a second stack |
| `docs/deployment/01_architecture.md` | ⚠ its service table lists the host ports **as literals** (`3001`, `5002`, host `8080`) — they become defaults, and the table must say so |
| `docs/deployment/12_environment_urls.md` | ⚠ the URL manifest hardcodes the same ports; it is the file people copy from, so a stale port here propagates |

## Acceptance

- [ ] With nothing set, every port and container name is **exactly as before** — diff the output of
      `docker compose config` before and after; the only differences should be the ones you intended
- [ ] Two stacks run simultaneously on the dev box with different `COMPOSE_PROJECT_NAME` and ports,
      each with its own volumes; `docker volume ls` shows both prefixes
- [ ] `make ephemeral-up` → seeded stack answering on its ports; `ephemeral-down` removes containers
      **and volumes**, leaving nothing behind (`docker volume ls | grep <project>` empty)
- [ ] `check_grm_ports` passes against a moved stack — **and so do the three deploy-side assertions**
- [ ] `make ephemeral-up` with `UI_IMAGE_TAG=<sha>-bypass` yields a stack whose UI is the bypass build
      (a request with a `grm_bypass_user` cookie is accepted) — this is QA-05's precondition
- [ ] The webchat answers through the ephemeral stack's nginx port — proves the QA-04d service set is right
- [ ] Staging deploy unaffected (run one)

## Risks

- **A stale `.env`/`env.local` port var on a real host silently moves a published port**, and nginx
  would keep proxying to the old one. Keep the defaults identical to today's literals and say so in the
  compose comment.
- Volume renaming: setting a project name on an **existing** stack orphans its current volumes. On
  staging, set `COMPOSE_PROJECT_NAME` to whatever the directory-derived name already is — check with
  `docker compose config --format json | jq .name` **before** choosing, or you will detach staging from
  its own database.
