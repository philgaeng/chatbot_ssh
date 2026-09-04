# QA-03 — `COMPOSE_PROJECT_NAME` + parameterised ports

> **Stream A · 1 day · depends on QA-02 · blocks QA-05 (CI stack) and any future sandbox**

## Context

Two stacks cannot coexist on one host or one CI runner today:

- **`COMPOSE_PROJECT_NAME` appears nowhere** — not in the Makefile, not in `env.local`, not in any
  compose file. Compose derives the project name from the directory, so two checkouts on one host share
  container names, the default network and the named volumes (`postgres_data`, `uploads_data`,
  `backups_data`).
- **Five host ports are literals:** `5001:5001` (backend), `8000:8000` (orchestrator), `5002:5002`
  (ticketing_api), `3001:3001` (grm_ui), `8080:80` (nginx).
- **`check_grm_ports` asserts `3001` and `5002` by hand**, so it fails against any stack that moved.

This is what makes an ephemeral CI stack possible — and it is the only piece of the sandbox idea from
the review-feedback evaluation that survives on its own merits.

## Scope

1. `COMPOSE_PROJECT_NAME` set per environment in the Makefile: `grm_wsl`, `grm_aws`, `grm_prod`, and
   `grm_ci_$(GITHUB_RUN_ID)` for CI. **Volumes inherit the project prefix automatically** — that is the
   isolation, and it means a CI stack's data cannot touch a dev stack's.
2. Every published port becomes `${VAR:-<current default>}:<container port>`, so **existing behaviour is
   unchanged when nothing is set**. Defaults stay exactly what they are today.
3. `check_grm_ports` reads the same variables instead of literals.
4. A `make ephemeral-up` / `ephemeral-down` pair that brings up a fully isolated, seeded stack on
   random-ish ports and tears it down **including volumes** — this is what QA-05 calls.

## Not in scope

Any change to service configuration, networking between services (they talk by service name and are
unaffected), or the nginx config. Running two stacks on the **staging host** — ruled out by the
incident, see [`DESIGN`](DESIGN-qa-and-build-pipeline.md) §3.

## Files

| File | Change |
|---|---|
| `Makefile` | `COMPOSE_PROJECT_NAME` per target; port vars; `check_grm_ports` de-literalised; `ephemeral-up`/`ephemeral-down` |
| `docker-compose.yml`, `docker-compose.grm.yml` | five `ports:` entries parameterised |
| `env.local` / `.env.example` | the new port vars, documented with their defaults |
| `docs/deployment/02_setup.md`, `03_operations.md` | how to run a second stack |

## Acceptance

- [ ] With nothing set, every port and container name is **exactly as before** — diff the output of
      `docker compose config` before and after; the only differences should be the ones you intended
- [ ] Two stacks run simultaneously on the dev box with different `COMPOSE_PROJECT_NAME` and ports,
      each with its own volumes; `docker volume ls` shows both prefixes
- [ ] `make ephemeral-up` → seeded stack answering on its ports; `ephemeral-down` removes containers
      **and volumes**, leaving nothing behind (`docker volume ls | grep <project>` empty)
- [ ] `check_grm_ports` passes against a moved stack
- [ ] Staging deploy unaffected (run one)

## Risks

- **A stale `.env`/`env.local` port var on a real host silently moves a published port**, and nginx
  would keep proxying to the old one. Keep the defaults identical to today's literals and say so in the
  compose comment.
- Volume renaming: setting a project name on an **existing** stack orphans its current volumes. On
  staging, set `COMPOSE_PROJECT_NAME` to whatever the directory-derived name already is — check with
  `docker compose config --format json | jq .name` **before** choosing, or you will detach staging from
  its own database.
