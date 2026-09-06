# QA-02 — CI-built images, pulled by the hosts

> **Stream A · 2–3 days · depends on QA-01 · blocks QA-03, QA-05**
> ✅ **Q-01…Q-05 answered 2026-09-04** — the decisions are inline below; [`QUESTIONS.md`](QUESTIONS.md) keeps the reasoning.
> ⚠ **Revised 2026-09-04 after a completeness review** — the ticket read correctly on its own but
> contradicted QA-03/QA-05 at four seams, and one security claim in it was already false. The new
> material is Q-16…Q-19 in [`QUESTIONS.md`](QUESTIONS.md); scope items **1**, **2**, **3** and **6** carry it.
> Fix **(2)** of the incident, described there as *"the actual fix"*. Also the precondition for running
> a stack anywhere a browser can test it — which is why it lives in the QA sprint rather than in ops.

## Context — what is true today

- **Eleven services build from two Dockerfiles.** Ten (`orchestrator`, `backend`, `db_init`,
  `celery_file`, `celery_default`, `celery_llm`, `ticketing_api`, `grm_celery`, `grm_celery_beat`,
  `ops`) build the **same** root `Dockerfile` (`python:3.10-slim`, `COPY . /app`, context `.`); `grm_ui`
  builds `channels/ticketing-ui/Dockerfile` with context `./channels/ticketing-ui`.
  **So this is two images, not eleven.**
- **No service declares an `image:`** in any compose file. Compose therefore names them by project +
  service, and nothing can be pulled. Adding `image:` is the core of this ticket.
- **Four** macros build on the remote host, sequentially, with `COMPOSE_PARALLEL_LIMIT=1` — a workaround
  for the memory ceiling this ticket removes: `REMOTE_DEPLOY_CORE` (`Makefile:117`),
  `REMOTE_DEPLOY_OPS` (`:137`), `REMOTE_DEPLOY_LIGHT` (`:183`), `REMOTE_DEPLOY_FULL` (`:202`).
  ⚠ **`aws-deploy-light` builds `grm_ui` + `nginx` — that Next.js build *is* the outage**, and it is the
  target used for a UI-only release, i.e. the most frequent one. Converting only `CORE` leaves the
  incident reachable by the most-used path.
- ⚠ **`REMOTE_DEPLOY_CORE` is shared with production.** `Makefile:355` (`aws-deploy`) and `Makefile:380`
  (`prod-deploy`) call the *same* macro. Rewriting it in place silently converts prod to pulling from
  GHCR — which is exactly what [Q-05](QUESTIONS.md#q-05--can-the-production-host-pull-from-the-registry)
  scoped out, because nobody has yet run `curl -sI https://ghcr.io/v2/` from the DOR box. **The macro
  must be split or parameterised, not edited in place** (scope 3).
- ⚠ **The root `.dockerignore` does not exclude `.env` or `env.local`**, and the root `Dockerfile:25` is
  `COPY . /app`. An earlier draft of this ticket said the exclusion "is supposed to" exist and asked
  the agent to verify it — it does not exist. On a host that has `env.local` (every deploy host, and
  every dev box), the app image **already contains the decrypted secrets file**. That is survivable
  only while the images are never pushed; this ticket pushes them, to a **public** package. See scope 6.
- The UI image **bakes `NEXT_PUBLIC_AUTH_MODE` at build time** → bypass and Keycloak are different
  images — hence the two published variants. ⚠ Today the variant is selected by `${AUTH_MODE}` as a
  **build arg** (`docker-compose.grm.yml:318`). Pulling removes that mechanism, so the variant needs a
  tag-side replacement — scope 1.

## Scope

**The five decisions this ticket executes** (record of why: [`QUESTIONS.md`](QUESTIONS.md)):

| | Decided |
|---|---|
| Registry | **GHCR** — `ghcr.io/philgaeng/chatbot_ssh/{app,ui}`, packages public. Authenticates with the workflow's own `GITHUB_TOKEN`; **no new secret**. ⚠ **Fix `.dockerignore` first** (scope 6) — a CI-only build-context check passes vacuously, because CI's checkout never has an `env.local` to catch |
| Architecture | **Multi-arch: arm64 + amd64.** ⚠ Chosen as the *safe default* because the DOR production host's `uname -m` is still unknown. **First thing to do:** get it. If it is `aarch64`, drop amd64 and halve every build — and record the value in [`PROGRESS.md`](PROGRESS.md) so nobody pays that cost twice |
| Runner | **Try `runs-on: ubuntu-24.04-arm` first** (free for public repos). ⚠ Verify the label resolves on the *first* run; fall back to `docker/setup-qemu-action` only if it does not, and say so in `PROGRESS.md` before tuning QEMU |
| UI variants | **Two** — `ui:<sha>` (keycloak, deployable) and `ui:<sha>-bypass` (test only), plus the guard below. ⚠ **They need their own tag variable** — see scope 1, or QA-05 cannot pull the bypass one |
| Blast radius | **Staging only.** Production keeps building on-box until someone runs `curl -sI https://ghcr.io/v2/` from the DOR box — that check and the prod rollout are a scheduled follow-up, not this ticket. ⚠ **This is a constraint on `prod-deploy`, which shares the macro** — scope 3 |

1. **Tag scheme + `image:` keys.** `IMAGE_TAG` defaults to `local` so a plain `docker compose build`
   still works for development; CI publishes `<short-sha>` and a moving branch tag.
   ```yaml
   image: ${IMAGE_REGISTRY:-ghcr.io/philgaeng/chatbot_ssh}/app:${IMAGE_TAG:-local}      # ×10 python services
   image: ${IMAGE_REGISTRY:-ghcr.io/philgaeng/chatbot_ssh}/ui:${UI_IMAGE_TAG:-${IMAGE_TAG:-local}}   # grm_ui
   ```
   ⭐ **`UI_IMAGE_TAG` is not decoration — without it the sprint does not join up.** The UI is the one
   image with two variants for the *same* commit, and QA-05 needs `ui:<sha>-bypass` while the rest of
   the stack runs `app:<sha>`. One shared `IMAGE_TAG` can only ever name one of them. Defaulting
   `UI_IMAGE_TAG` to `IMAGE_TAG` keeps every existing invocation unchanged; QA-03's `ephemeral-up` and
   QA-05's job set `UI_IMAGE_TAG=<sha>-bypass` and nothing else moves. **This variable is QA-02's
   deliverable** — QA-05 must not have to touch a compose file to get it ([Q-17](QUESTIONS.md#q-17--how-does-a-stack-select-the-bypass-ui-variant)).
2. **A build-and-push workflow** (`.github/workflows/images.yml`): build both images multi-arch, push
   `<sha>` + branch tag. Use build caching (`type=gha`) or the Python image rebuilds from `pip install`
   every run — with two architectures that cost doubles, so the cache is not optional.
   ⚠ **The trigger set must match `ci.yml`'s, plus `pull_request`** — `main`, `integration/**`,
   `dev/**`, `dpg/**`. A narrower set is the defect that breaks QA-05: that job pulls
   `IMAGE_TAG=<this commit's sha>`, so on any branch or PR this workflow does not build, **no such tag
   exists and the e2e job fails for a reason unrelated to the change**. That includes this sprint's own
   `qa/*` → `dev/qa-automation` PRs. If building on every PR proves too expensive, the alternative is a
   documented fallback order (exact sha → branch tag → PR base sha) — **decide it here, in this ticket,
   not in QA-05** ([Q-16](QUESTIONS.md#q-16--which-commits-get-an-image)).
3. **Deploy pulls instead of building — on staging only, which means the macro must be split.**
   `REMOTE_DEPLOY_CORE` is called by both `aws-deploy` (`Makefile:355`) and `prod-deploy`
   (`Makefile:380`), so an in-place rewrite silently converts production too. Take the pull/build
   choice as a macro parameter (or a `DEPLOY_BUILD` variable defaulted per target: `0` for `aws-*`,
   `1` for `prod-*`) so **`make prod-deploy` behaves exactly as it does today** until Q-05 is answered.
   Keep the escape hatch working in both directions and say in the Makefile comment why you would use it.
   ⚠ **Convert all four build paths, not just `CORE`.** `REMOTE_DEPLOY_LIGHT` (`grm_ui` + `nginx`) is
   the target that rebuilds the Next.js app for a UI-only release — leaving it building on-box leaves
   the outage class open on the most frequently used deploy. `REMOTE_DEPLOY_FULL` and
   `REMOTE_DEPLOY_OPS` get the same treatment; `nginx` is `image: nginx:stable` and never built, so
   `aws-deploy-light` reduces to a pull plus the existing `--force-recreate`.
4. **The bypass-image guard.** A CI check that no compose file used for staging or production
   references a `-bypass` tag. Defence in depth — HR-01 already makes production fail closed on
   `AUTH_MODE=bypass` — but a test-only image reaching a real environment is worth two checks.
   ⚠ With scope 1 the guard must also read **`UI_IMAGE_TAG`**, not just the `image:` lines — that is
   now where a `-bypass` reference would actually come from.
5. **Deploy the tag, not the branch.** Once images are tagged by sha, `make aws-deploy IMAGE_TAG=<sha>`
   is a **rollback** — one command, no rebuild. Document it; this is a capability the project does not
   have today and it is worth more than the outage fix.
6. **Add `.env*` and `env.local` to the root `.dockerignore`. This is a fix, not a verification.**
   The file today excludes caches, `node_modules`, `models`, `uploads` and `deployment/certbot` — and
   no env file. With `Dockerfile:25` = `COPY . /app`, any build on a host that has `env.local` bakes
   the decrypted secrets into `/app/env.local` in the image. Add the exclusion, then add the CI
   build-context check as the *second* control, and state in the commit message that the check alone
   would have been theatre: CI's own checkout has no `env.local`, so it can only ever pass.
   ⭐ **Rebuild and push after the exclusion lands, never before**, and confirm with
   `docker run --rm <image> ls -la /app | grep -i env` that the published image is clean. The
   `.dockerignore` is also scp'd to the host by `aws-deploy` (`Makefile:354`) and then restored from
   git by the macro — so the git copy is the one that matters. ([Q-18](QUESTIONS.md#q-18--does-the-image-contain-envlocal))

## Not in scope

Production rollout — **staging only in this sprint**; prod keeps building on-box until someone
confirms it can reach the registry. **Log it as a `followups/` doc + a `TODO.md` row when this ticket
lands**, per the standing deferral rule, or it becomes invisible debt. Changing what
the images contain. Multi-stage optimisation of the Python image (log it as a follow-up if you notice
an easy win; do not take it here). The UI Dockerfile's **dead `deps` stage** — that belongs to
[QA-01](01-QA-01-deploy-safety.md), which has to measure the build anyway.

## Files

| File | Change |
|---|---|
| `docker-compose.yml`, `docker-compose.grm.yml` | `image:` on all built services; `grm_ui` uses `UI_IMAGE_TAG` |
| `.dockerignore` | ⚠ **add `.env*` / `env.local`** — scope 6. Do this **before** the first push |
| `.github/workflows/images.yml` | **new** — build + push both images; trigger set matches `ci.yml` + `pull_request` |
| `.github/workflows/ci.yml` | the bypass-tag guard (a grep step is enough), reading `UI_IMAGE_TAG` too |
| `Makefile` | **all four** deploy macros pull; `IMAGE_TAG` / `UI_IMAGE_TAG` / `IMAGE_REGISTRY` plumbing; `DEPLOY_BUILD` defaulted per target (`0` for `aws-*`, `1` for `prod-*`) |
| `env.local` / `.env.example` | `IMAGE_REGISTRY`, `IMAGE_TAG`, `UI_IMAGE_TAG` documented |
| `docs/deployment/03_operations.md`, `08_commit_strategy.md` | new deploy + rollback procedure |
| `docs/deployment/01_architecture.md` | ⚠ **it documents the as-built deploy model and the UI's build-time auth baking** — both change here. The spec edit rides this PR (`06` §3.1), it is not a later chore |

## Acceptance

- [ ] Both images build and push in CI for the target architecture(s); digests recorded in `PROGRESS.md`
- [ ] `docker compose pull` on staging succeeds; `make aws-deploy` completes **without building anything on the box** — verify with `docker system events` or by confirming no `docker build` process appears
- [ ] Peak memory on staging during a deploy stays well under the ceiling (`free -m` sampled during) — the number goes in the commit message
- [ ] `make aws-deploy IMAGE_TAG=<previous-sha>` rolls back and the site serves the older build — **verified inside the container**, not from the deploy's OK line (see the DPG pack's standing lesson: *deployed is not has run*)
- [ ] A local `docker compose build` still works with no registry access (the `:local` default)
- [ ] The bypass-tag guard fails when deliberately given a bad compose file
- [ ] **`make prod-deploy` still builds on the box** — the prod path is byte-for-byte unchanged in
      behaviour. Prove it by diffing `make -n prod-deploy` before and after
- [ ] **`make aws-deploy-light` builds nothing on the box either** — the UI-only path is the one that
      caused the incident, so it is not enough to fix `aws-deploy`
- [ ] **`UI_IMAGE_TAG=<sha>-bypass docker compose … config`** resolves `grm_ui` to the bypass image and
      leaves every other service on `app:<sha>` — this is the line QA-05 depends on
- [ ] **The published image contains no env file**: `docker run --rm <image> sh -c 'ls -a /app | grep -i "^\.env\|env.local"'` returns nothing
- [ ] **An image exists for a PR head commit** (or the documented fallback resolves one) — test it on a
      throwaway PR before QA-05 is written against it
- [ ] Migrations still run and end at head, **in the order the Makefile uses today —
      ticketing → public → ops** (`Makefile:129-131`). ⚠ Do **not** "correct" this to the order in
      `ci.yml`: the two differ, this ticket is not the place to reconcile them, and reordering a
      deploy's migrations as a side effect of an image change is how a schema surprise ships
      ([Q-19](QUESTIONS.md#q-19--which-migration-order-is-the-documented-one))

## Risks

- **A pull-based deploy hides a stale tag.** If `IMAGE_TAG` is not bumped, `up -d` is a no-op and the
  deploy reports success having changed nothing. Print the resolved image **digest** per service after
  `up -d` — this is the same class of failure as the OK line that verified two ports and nothing else.
- **The Python image is fat** (`COPY . /app`, `python:3.10-slim` + libvips + two requirements files):
  expect slow first builds. GHA cache makes subsequent ones cheap; measure and record.
- **Public GHCR packages.** ⚠ **The `.dockerignore` does not exclude `env.local` today** — this was
  written as "verify, do not assume", and the verification came back negative. Scope 6 is the fix, and
  it must land before the first push. A published image is not un-publishable: if one goes out dirty,
  the secrets are burned and `secrets.enc.env` has to be rotated
  ([`14_key_and_secret_lifecycle.md`](../../deployment/14_key_and_secret_lifecycle.md)), not just the
  package deleted.
- **A pull-based prod deploy that nobody asked for.** The macro is shared; see scope 3. The failure
  would land on the VPN-only host, in a maintenance window, with no way to fall back quickly.
