# QA sprint — open questions

> **How to use this file.** Every question below is one I could not settle from the code with
> confidence. Each has **my recommendation**; several also have a fact I verified so you are not
> answering blind. **Write your answer on the `> **Answer:**` line** — a one-word "recommended" is a
> complete answer where you agree.
>
> **Q-01…Q-05 block QA-02. Q-06…Q-10 block QA-04. Q-11…Q-15 can be answered later** but change scope.
> Nothing in this sprint should start before its blocking questions are answered.

---

## Blocking QA-02 — CI-built images

### Q-01 · Which registry?

**Verified:** ⚠ **this was true when written and is not any more — the repo went `PRIVATE` on 2026-09-04 ([D-010](../../DECISIONS.md)); read the amendment under the answer below.** As written: the repo is **public** (`gh repo view` → `visibility: PUBLIC`), so GHCR is free and
authenticates with the workflow's own `GITHUB_TOKEN` — no new secret. ECR would put images in the same
AWS account as the staging host (no cross-network pull) but needs AWS credentials added to CI.

⚠ **Consequence either way:** GHCR packages on a public repo default to **public**. The images contain
this repository's code, which is already public under Apache-2.0 — but they must contain **no** baked
secrets, and the UI image bakes `NEXT_PUBLIC_*` build args (see Q-04), so those must stay non-secret.

**Recommendation:** **GHCR** (`ghcr.io/philgaeng/chatbot_ssh/{app,ui}`), packages left public,
with a CI check that no `.env`/`env.local` is present in the build context.

> **Answer:** follow reco

> ⚠ **AMENDED 2026-09-04 — the verified premise above has inverted; re-decide before QA-02 starts.**
> [D-010](../../DECISIONS.md) made the working repository **private** — done 2026-09-04, verified
> `gh repo view` → `PRIVATE`. The reasoning in this question
> rests on it being public (*"the repo is **public**, so GHCR is free"*, and *"packages default to
> public"*). Neither holds now: private repository → **private packages**, metered for storage and for
> egress to anything outside GitHub Actions — and the staging host pulling an image **is** outside.
> Two consequences: the "leave packages public" recommendation no longer means what it said, and image
> size × pull frequency becomes a cost question.
> ⭐ **[Q-16](#q-16--which-commits-get-an-image) is now also the cost dial** — building on every
> `dev/**` push versus only `integration/**` + `main` is the difference between staying inside the free
> tier and paying overage. Settle the two together.

### Q-02 · What CPU architecture(s) must the images support?

**Verified:** staging is a **t4g.medium — ARM64 (Graviton)**. `docs/deployment/10_production_server_spec.md`
states the DOR production requirement as *"ARM64 **or** x86_64"*, which is a requirement, not an
as-built fact — **and I cannot check the prod host** (VPN-only).

This is the single biggest driver of QA-02's cost:
- **arm64 only** — simplest, matches staging, breaks if DOR prod is x86_64.
- **multi-arch (arm64 + amd64)** — safe, roughly doubles build time, needs `docker buildx` + a manifest list.

**Recommendation:** **ask DOR / check the prod host for `uname -m`, then build only what is needed.**
If the answer cannot be obtained quickly, build **multi-arch** — the extra CI minutes are cheaper than
discovering it during a production deploy.

> **Answer (prod `uname -m` = ?):** multi arch

> ⭐ **REVISED 2026-09-06 by the owner, before `images.yml` was written:** *"it is more likely
> that the opposite is true, in which case I can easily move stage to amd64"* — the expectation
> is that DOR prod is **x86_64**, and that staging (currently a t4g.medium, ARM64) moves to match.
> **If both hosts land on amd64, build a single architecture.** That is not merely cheaper, it is
> *simpler*: no `buildx` manifest list, no QEMU, and [Q-03](#q-03--how-do-we-build-arm64-images-in-ci)
> stops mattering entirely, because a standard `ubuntu-latest` runner is amd64 and builds it natively.
> ⚠ **Multi-arch was chosen as the safe default under uncertainty, not on its merits** — so a
> better guess is a good enough reason to revisit it. What is still open is **sequencing**, not
> architecture: staging is ARM64 *today* and cannot run an amd64-only image until it moves.
> Tracked as A-10 in [`PROGRESS.md`](PROGRESS.md). ⭐ Note the e2e story is unaffected either way —
> QA-05 runs on an amd64 GitHub runner.

### Q-03 · How do we build arm64 images in CI?

GitHub-hosted **arm64 runners are free for public repositories** (`ubuntu-24.04-arm`), which would make
this nearly free — **but I am ~90% confident, not 95%: verify the label is available to this repo before
designing around it.** The fallbacks are QEMU emulation (correct but slow, and `npm run build` is the
slow part) or a self-hosted ARM runner (another box to own).

**Recommendation:** try `runs-on: ubuntu-24.04-arm` first; fall back to `docker/setup-qemu-action` only
if that label is unavailable.

> **Answer:** follow reco

### Q-04 · The UI image bakes its auth mode — do we publish two variants?

**Verified:** `channels/ticketing-ui/Dockerfile` takes `NEXT_PUBLIC_AUTH_MODE` as a **build arg** and
Next inlines it at compile time. A bypass build and a Keycloak build are therefore **different images**.
The e2e suite wants the bypass variant (no Keycloak container, cookie-based identity, see Q-07);
staging and production need the Keycloak variant.

**Recommendation:** publish **both**, tagged `ui:<sha>` (keycloak, the deployable one) and
`ui:<sha>-bypass` (test only), plus a **CI guard that fails if a `-bypass` tag is referenced by any
compose file used for staging or production**. Note the runtime already fails closed — production can
never honour `AUTH_MODE=bypass` (HR-01) — so this guard is defence in depth, not the only control.

> **Answer:**follow reco

### Q-05 · Can the **production** host pull from the registry?

Staging obviously has outbound internet. DOR production is reached over VPN and I have no way to test
whether it can reach `ghcr.io`. If it cannot, prod needs a different path — `docker save`/`load` over
the VPN, or a registry mirror inside DOR — and QA-02 should ship **staging-first**, leaving prod on the
current build-on-box flow until this is known.

**Recommendation:** scope QA-02 to **staging only**, and open a follow-up for production once someone
can run `curl -sI https://ghcr.io/v2/` from the DOR box.

> **Answer:**follow reco

---

## Blocking QA-04 — the browser harness

### Q-06 · Where do the e2e tests live?

`channels/ticketing-ui/e2e/` (Playwright is a node tool; the `ui-checks` CI job already has node + npm
and the right working directory) vs `tests/e2e/` at the repo root (next to the 172 pytest files, but
needs its own node setup).

**Recommendation:** **`channels/ticketing-ui/e2e/`**, with `playwright.config.ts` beside it. It keeps
`npx playwright test` working with no path gymnastics and leaves `vitest` (node-env, `**/*.test.ts`)
untouched — note the config's `include` would otherwise collide, so e2e specs use `*.spec.ts`.

> **Answer:**follow reco

### Q-07 · What auth mode does the suite run against?

**Verified:** a bypass build sets a `grm_bypass_user` cookie (JSON: `user_id`, `role_keys[]`,
`organization_id`) which the Next proxy turns into `X-Internal-*` headers. A test can set that cookie
directly and be any officer in the seeded roster — **no Keycloak container, no login flow, no OIDC
redirects**, which removes the single heaviest service from the CI stack.

**Recommendation:** **bypass build for the whole suite**, plus **one** Keycloak login smoke test added
later (its own job, real realm), so the login path is not entirely untested.

> **Answer:**follow reco

### Q-08 · Screenshots: artifacts only, or pixel-diffed baselines?

Playwright can commit baseline PNGs and fail on a pixel delta (`toHaveScreenshot`). That is a real
visual-regression gate — and notoriously flaky across platforms and font stacks unless every shot is
taken inside the same container image.

**Recommendation:** **v1 = capture and upload as CI artifacts, no pixel gate.** Add baselines later for
a short list of stable pages, generated inside the official Playwright image. The immediate win is that
a human — or the review-feedback triage agent — can *see* the page; the gate can come second.

> **Answer:**follow reco

### Q-09 · How much of the officer UI does v1 cover?

**Verified:** 22 `page.tsx` routes exist. A smoke pass (load each route as a seeded officer, assert no
5xx, no console error, no error boundary) is cheap and catches crashes and hydration failures. Driving
real flows is where the value is but costs a day each.

**Recommendation:** **all 22 routes smoke + 3–5 driven flows.** My proposed five, chosen because they
are what reviewers actually exercise: (1) queue → open ticket → add internal note; (2) escalate;
(3) resolve + closure summary; (4) settings → create/edit an officer; (5) reports → generate an XLSX.
**Tell me if a different five matter more** — you know what the reviewers break.

> **Answer (which flows):**lets do all the flows

### Q-10 · Is the mobile surface in v1?

`middleware.ts` redirects mobile user-agents to a separate `/m/*` surface. In Playwright that is one
extra project (device descriptor + UA), so it is cheap — and UA-conditional routing is exactly the kind
of thing that breaks silently.

**Recommendation:** **yes — mobile smoke only** (`/m/queue`, `/m/tickets`, `/m/tasks`, one ticket
detail), no driven flows in v1.

> **Answer:**yes

---

## Scope questions — answer before QA-05

### Q-11 · Does closing HR-07's sweep belong in this sprint?

⚠ **I stated in an earlier draft that this sprint "closes HR-07". That was imprecise, and the
correction matters for scope.** HR-07 is the **REST webchat** (`channels/REST_webchat/` — plain JS +
socket.io), a *different surface* from the officer UI. Its code is merged and in the tree, but its
**7-item manual sweep was never run** — checkbox still open in `2026-07_hardening/PROGRESS.md`, and the
sweep was what "blocks merge" was conditioned on. The items: EN/NE switch, image upload, voice note,
map pin, status check, send-lock double-Enter under a dead backend, filed-banner rendering, SEAH route
entry, session-id persistence + `/clear_session` rotation.

**Recommendation:** **yes, as QA-04d** — it is the same harness pointed at a second surface, and it
retires a real open item. But it is **additional scope, roughly +1–1.5 d**, not a freebie.

> **Answer:**Yes we need it

### Q-12 · Does the e2e stack go through nginx, or straight to the UI container?

Direct to `grm_ui:3001` is simpler and faster. Through nginx is closer to production and would catch
proxy/routing regressions — which is how the webchat is actually served.

**Recommendation:** **direct for the officer UI; through nginx for the webchat** (QA-04d), because
nginx is part of what serves it.

> **Answer:**follow reco

### Q-13 · Report-only or required check?

**Verified via the GitHub API:** `main` had **no branch protection at all** (`Branch not protected`,
HTTP 404) — so no check was required on any branch, and the HR-05 item asking for this was still open.

> ✅ **RESOLVED 2026-09-04.** A repository ruleset (`Main`) is **active** on `refs/heads/main` and
> `refs/heads/integration/*` — all five CI jobs required, PR required at 0 approvals, deletions and
> force-pushes blocked, no bypass actors. Verified through the API. **The recommendation below is now
> half-done**: the existing checks are required; the e2e job is the only context left to add when its
> report-only period expires.

**Recommendation:** land e2e as **report-only for ~2 weeks**, then enable branch protection on `main`
and `integration/**` requiring `backend-tests`, `ui-checks`, `docs-links` **and** the new e2e job.
⭐ Enabling protection for the *existing three* is a ten-minute job worth doing **now**, independent of
this sprint.

> **Answer:**follow reco

### Q-14 · Do we want an always-on test environment, or is ephemeral-per-PR enough?

Ephemeral costs nothing at rest and cannot drift. An always-on environment is nicer for humans to click
around in — and costs an instance plus an owner. This project already has one capability parked for
exactly that reason (T2 self-hosting, *"no run-cost owner"*).

**Recommendation:** **ephemeral only.** Revisit if the review-feedback sprint's agent phase actually
lands and wants a durable sandbox.

> **Answer:** follow reco

### Q-15 · Who runs the DOR-prod side of QA-02, and when?

Everything in this sprint is verifiable on staging by whoever holds the AWS key. Production needs VPN
access and a maintenance window, and per Q-05 may need a different image path entirely.

**Recommendation:** **staging in this sprint; production as a separately scheduled follow-up** with its
own runbook entry, so the sprint is not blocked on VPN availability.

> **Answer:**i HAVE ACCESS to prod but access is intermittent

---

## Second pass — seams between tickets (2026-09-04)

> **Why these exist, and why they are different from Q-01…Q-15.** The first fifteen were asked of the
> *sprint*. These four came out of checking each finished ticket **against the tree**, and they all live
> in the space *between* two tickets that are each correct on their own — the gap you only see by asking
> what QA-05 receives from QA-02.
>
> **Q-17, Q-18 and Q-19 are corrections of fact, not preferences** — they are already folded into the
> tickets, because leaving them would mean shipping something known to be wrong. Read them, but there
> is nothing to decide unless you disagree.
> **[Q-16](#q-16--which-commits-get-an-image) is a genuine fork and needs your call.**

### Q-16 · Which commits get an image?

QA-02 proposed building images on push to `main` and `integration/**`. QA-05 pulls
`IMAGE_TAG=<this commit's sha>`. **Those cannot both hold:** on a pull request — including this sprint's
own `qa/*` → `dev/qa-automation` PRs — no such tag exists, so the e2e job fails for a reason unrelated
to the change. `ci.yml` already gates `main`, `integration/**`, `dev/**` and `dpg/**`, so the narrow
image trigger would also be a fresh instance of the defect recorded in `ci.yml`'s own header: a gate
that does not run on the branches people actually work on.

- **(a) Build on everything `ci.yml` gates, plus `pull_request`.** Every commit under test has its own
  image. Costs CI minutes on every PR — and with multi-arch (your Q-02 answer) that is the expensive
  branch until the prod `uname -m` comes back `aarch64`.
- **(b) Keep the narrow trigger, give the e2e job a documented fallback** — exact sha → branch tag →
  PR base sha. Cheap, but the suite then sometimes tests *the base commit's* image against the PR's
  specs. That is a subtly false green, which is the class of thing this sprint exists to stop.

**Recommendation: (a), narrowed by path** — build on PRs that touch build inputs (`Dockerfile`,
`channels/ticketing-ui/**`, `requirements*.txt`, `docker-compose*.yml`, the workflows), and use (b)'s
fallback for the rest. A docs-only PR stays free; nothing ever silently tests the wrong image.
⚠ Whichever you pick, **it is written down in QA-02** — QA-05 must not improvise it.

> **Answer:**a

### Q-17 · How does a stack select the bypass UI variant?

QA-02's tag scheme was one variable, `ui:${IMAGE_TAG:-local}`. QA-05 needs `ui:<sha>-bypass` running
**beside** `app:<sha>`. One variable cannot name both. Today the variant is chosen by `${AUTH_MODE}` as
a **build arg** (`docker-compose.grm.yml:318`) — the mechanism that pulling removes.

**Recommendation:** a second variable, `UI_IMAGE_TAG`, defaulting to `IMAGE_TAG`
(`ui:${UI_IMAGE_TAG:-${IMAGE_TAG:-local}}`). Every existing invocation is unchanged; QA-03's
`ephemeral-up` and QA-05's job set it and nothing else moves. **Owned by QA-02.**

> **Answer:** *(folded in — a missing mechanism, not a preference; say so if you want it done differently)*

### Q-18 · Does the image contain `env.local`?

**Yes, today.** QA-02 said the build context "is supposed to exclude `env.local` via `.dockerignore` —
verify that, do not assume it". Verified: **it does not.** The root `.dockerignore` excludes caches,
`node_modules`, `models`, `uploads` and `deployment/certbot`, and no env file; the root `Dockerfile:25`
is `COPY . /app`. Any build on a host holding `env.local` — every deploy host, every dev box — bakes the
decrypted secrets into the image. Survivable only while images are never pushed. **This sprint pushes
them, to a public package** (your Q-01 answer).

The proposed control was a CI build-context check. Alone it is theatre: CI's checkout has no
`env.local`, so it can only ever pass, while `DEPLOY_BUILD=1` on a host and every local
`docker compose build` stay dirty.

**Recommendation:** fix the `.dockerignore` first (`.env*`, `env.local`), keep the CI check as the
second control, and verify the published image directly (`ls -a /app`). ⚠ A published image cannot be
unpublished — if a dirty one ships the remedy is secret **rotation**, not deleting the package.

> **Answer:** *(folded in as a fix — this one is not optional)*

### Q-19 · Which migration order is "the documented one"?

QA-02's acceptance and QA-05's scope both said *"the documented order (public → ticketing → ops)"*.
**Two orders exist in the repo and they disagree:**

| Source | Order |
|---|---|
| `ci.yml:206-208` | public → ticketing → ops |
| `Makefile:129-131` (`REMOTE_DEPLOY_CORE`), `Makefile:419` (`migrate_all`) | **ticketing → public → ops** |
| [`07_migrations_policy.md`](../../deployment/07_migrations_policy.md) §"May5 SEAH rollout" | ticketing → public (ops not mentioned) |

An agent rewriting `REMOTE_DEPLOY_CORE` to match the ticket's wording would **reorder a live deploy's
migrations as a side effect of an image change**.

**Recommendation:** **neither ticket touches it.** QA-02 preserves the Makefile's order; QA-05 copies
`backend-tests`' steps verbatim, since those demonstrably work against the same seed. Whether the
streams have a real ordering dependency deserves a migrations ticket with evidence — the schema rules
say the three never share ownership of a table, which suggests both orders are fine, but "suggests" is
not a basis for changing a deploy. Logged as a follow-up per the standing deferral rule.

> **Answer:** *(folded in — change neither order, log the reconciliation)*
