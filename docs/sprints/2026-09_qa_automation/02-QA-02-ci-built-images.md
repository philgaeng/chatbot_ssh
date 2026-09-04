# QA-02 — CI-built images, pulled by the hosts

> **Stream A · 2–3 days · depends on QA-01 and answers to [Q-01…Q-05](QUESTIONS.md) · blocks QA-03, QA-05**
> Fix **(2)** of the incident, described there as *"the actual fix"*. Also the precondition for running
> a stack anywhere a browser can test it — which is why it lives in the QA sprint rather than in ops.

## Context — what is true today

- **Eight services build from two Dockerfiles.** Seven Python services (`orchestrator`, `backend`,
  `db_init`, `celery_file`, `celery_default`, `celery_llm`, `ticketing_api`, `grm_celery`,
  `grm_celery_beat`, `ops`) all build the **same** root `Dockerfile` (`python:3.10-slim`, `COPY . /app`);
  `grm_ui` builds `channels/ticketing-ui/Dockerfile`. **So this is two images, not eight.**
- **No service declares an `image:`** in any compose file. Compose therefore names them by project +
  service, and nothing can be pulled. Adding `image:` is the core of this ticket.
- The deploy macros `REMOTE_DEPLOY_CORE` / `REMOTE_DEPLOY_LIGHT` / `REMOTE_DEPLOY_FULL` build on the
  remote host, sequentially, with `COMPOSE_PARALLEL_LIMIT=1` — a workaround for the memory ceiling this
  ticket removes.
- The UI image **bakes `NEXT_PUBLIC_AUTH_MODE` at build time** → bypass and Keycloak are different
  images ([Q-04](QUESTIONS.md#q-04--the-ui-image-bakes-its-auth-mode--do-we-publish-two-variants)).

## Scope

1. **Tag scheme + `image:` keys.** `IMAGE_TAG` defaults to `local` so a plain `docker compose build`
   still works for development; CI publishes `<short-sha>` and a moving branch tag.
   ```yaml
   image: ${IMAGE_REGISTRY:-ghcr.io/philgaeng/chatbot_ssh}/app:${IMAGE_TAG:-local}   # ×10 python services
   image: ${IMAGE_REGISTRY:-ghcr.io/philgaeng/chatbot_ssh}/ui:${IMAGE_TAG:-local}    # grm_ui
   ```
2. **A build-and-push workflow** (`.github/workflows/images.yml`): on push to `main` and
   `integration/**`, build both images, push `<sha>` + branch tag. Architecture per
   [Q-02](QUESTIONS.md#q-02--what-cpu-architectures-must-the-images-support) / runner per
   [Q-03](QUESTIONS.md#q-03--how-do-we-build-arm64-images-in-ci). Use build caching (`type=gha`) or the
   Python image rebuilds from `pip install` every run.
3. **Deploy pulls instead of building.** `REMOTE_DEPLOY_CORE` becomes fetch → checkout →
   `docker compose pull` → `up -d` → migrations. Keep an escape hatch (`DEPLOY_BUILD=1`) that restores
   the old behaviour, and say in the Makefile comment why you would ever use it.
4. **The bypass-image guard.** A CI check that no compose file used for staging or production
   references a `-bypass` tag. Defence in depth — HR-01 already makes production fail closed on
   `AUTH_MODE=bypass` — but a test-only image reaching a real environment is worth two checks.
5. **Deploy the tag, not the branch.** Once images are tagged by sha, `make aws-deploy IMAGE_TAG=<sha>`
   is a **rollback** — one command, no rebuild. Document it; this is a capability the project does not
   have today and it is worth more than the outage fix.

## Not in scope

Production rollout ([Q-05](QUESTIONS.md#q-05--can-the-production-host-pull-from-the-registry),
[Q-15](QUESTIONS.md#q-15--who-runs-the-dor-prod-side-of-qa-02-and-when)) — **staging only in this
sprint**, prod keeps building on-box until someone confirms it can reach the registry. Changing what
the images contain. Multi-stage optimisation of the Python image (log it as a follow-up if you notice
an easy win; do not take it here).

## Files

| File | Change |
|---|---|
| `docker-compose.yml`, `docker-compose.grm.yml` | `image:` on all built services |
| `.github/workflows/images.yml` | **new** — build + push both images |
| `.github/workflows/ci.yml` | the bypass-tag guard (a grep step is enough) |
| `Makefile` | deploy macros pull; `IMAGE_TAG` / `IMAGE_REGISTRY` plumbing; `DEPLOY_BUILD=1` escape hatch |
| `env.local` / `.env.example` | `IMAGE_REGISTRY`, `IMAGE_TAG` documented |
| `docs/deployment/03_operations.md`, `08_commit_strategy.md` | new deploy + rollback procedure |

## Acceptance

- [ ] Both images build and push in CI for the target architecture(s); digests recorded in `PROGRESS.md`
- [ ] `docker compose pull` on staging succeeds; `make aws-deploy` completes **without building anything on the box** — verify with `docker system events` or by confirming no `docker build` process appears
- [ ] Peak memory on staging during a deploy stays well under the ceiling (`free -m` sampled during) — the number goes in the commit message
- [ ] `make aws-deploy IMAGE_TAG=<previous-sha>` rolls back and the site serves the older build — **verified inside the container**, not from the deploy's OK line (see the DPG pack's standing lesson: *deployed is not has run*)
- [ ] A local `docker compose build` still works with no registry access (the `:local` default)
- [ ] The bypass-tag guard fails when deliberately given a bad compose file
- [ ] Migrations still run in the documented order (public → ticketing → ops) and end at head

## Risks

- **A pull-based deploy hides a stale tag.** If `IMAGE_TAG` is not bumped, `up -d` is a no-op and the
  deploy reports success having changed nothing. Print the resolved image **digest** per service after
  `up -d` — this is the same class of failure as the OK line that verified two ports and nothing else.
- **The Python image is fat** (`COPY . /app`, `python:3.10-slim` + libvips + two requirements files):
  expect slow first builds. GHA cache makes subsequent ones cheap; measure and record.
- **Public GHCR packages** — see [Q-01](QUESTIONS.md#q-01--which-registry). Confirm no secret is
  baked; the build context excludes `env.local` via `.dockerignore` — **verify that, do not assume it**.
