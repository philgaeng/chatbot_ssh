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

**Verified:** the repo is **public** (`gh repo view` → `visibility: PUBLIC`), so GHCR is free and
authenticates with the workflow's own `GITHUB_TOKEN` — no new secret. ECR would put images in the same
AWS account as the staging host (no cross-network pull) but needs AWS credentials added to CI.

⚠ **Consequence either way:** GHCR packages on a public repo default to **public**. The images contain
this repository's code, which is already public under Apache-2.0 — but they must contain **no** baked
secrets, and the UI image bakes `NEXT_PUBLIC_*` build args (see Q-04), so those must stay non-secret.

**Recommendation:** **GHCR** (`ghcr.io/philgaeng/chatbot_ssh/{app,ui}`), packages left public,
with a CI check that no `.env`/`env.local` is present in the build context.

> **Answer:**

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

> **Answer (prod `uname -m` = ?):**

### Q-03 · How do we build arm64 images in CI?

GitHub-hosted **arm64 runners are free for public repositories** (`ubuntu-24.04-arm`), which would make
this nearly free — **but I am ~90% confident, not 95%: verify the label is available to this repo before
designing around it.** The fallbacks are QEMU emulation (correct but slow, and `npm run build` is the
slow part) or a self-hosted ARM runner (another box to own).

**Recommendation:** try `runs-on: ubuntu-24.04-arm` first; fall back to `docker/setup-qemu-action` only
if that label is unavailable.

> **Answer:**

### Q-04 · The UI image bakes its auth mode — do we publish two variants?

**Verified:** `channels/ticketing-ui/Dockerfile` takes `NEXT_PUBLIC_AUTH_MODE` as a **build arg** and
Next inlines it at compile time. A bypass build and a Keycloak build are therefore **different images**.
The e2e suite wants the bypass variant (no Keycloak container, cookie-based identity, see Q-07);
staging and production need the Keycloak variant.

**Recommendation:** publish **both**, tagged `ui:<sha>` (keycloak, the deployable one) and
`ui:<sha>-bypass` (test only), plus a **CI guard that fails if a `-bypass` tag is referenced by any
compose file used for staging or production**. Note the runtime already fails closed — production can
never honour `AUTH_MODE=bypass` (HR-01) — so this guard is defence in depth, not the only control.

> **Answer:**

### Q-05 · Can the **production** host pull from the registry?

Staging obviously has outbound internet. DOR production is reached over VPN and I have no way to test
whether it can reach `ghcr.io`. If it cannot, prod needs a different path — `docker save`/`load` over
the VPN, or a registry mirror inside DOR — and QA-02 should ship **staging-first**, leaving prod on the
current build-on-box flow until this is known.

**Recommendation:** scope QA-02 to **staging only**, and open a follow-up for production once someone
can run `curl -sI https://ghcr.io/v2/` from the DOR box.

> **Answer:**

---

## Blocking QA-04 — the browser harness

### Q-06 · Where do the e2e tests live?

`channels/ticketing-ui/e2e/` (Playwright is a node tool; the `ui-checks` CI job already has node + npm
and the right working directory) vs `tests/e2e/` at the repo root (next to the 172 pytest files, but
needs its own node setup).

**Recommendation:** **`channels/ticketing-ui/e2e/`**, with `playwright.config.ts` beside it. It keeps
`npx playwright test` working with no path gymnastics and leaves `vitest` (node-env, `**/*.test.ts`)
untouched — note the config's `include` would otherwise collide, so e2e specs use `*.spec.ts`.

> **Answer:**

### Q-07 · What auth mode does the suite run against?

**Verified:** a bypass build sets a `grm_bypass_user` cookie (JSON: `user_id`, `role_keys[]`,
`organization_id`) which the Next proxy turns into `X-Internal-*` headers. A test can set that cookie
directly and be any officer in the seeded roster — **no Keycloak container, no login flow, no OIDC
redirects**, which removes the single heaviest service from the CI stack.

**Recommendation:** **bypass build for the whole suite**, plus **one** Keycloak login smoke test added
later (its own job, real realm), so the login path is not entirely untested.

> **Answer:**

### Q-08 · Screenshots: artifacts only, or pixel-diffed baselines?

Playwright can commit baseline PNGs and fail on a pixel delta (`toHaveScreenshot`). That is a real
visual-regression gate — and notoriously flaky across platforms and font stacks unless every shot is
taken inside the same container image.

**Recommendation:** **v1 = capture and upload as CI artifacts, no pixel gate.** Add baselines later for
a short list of stable pages, generated inside the official Playwright image. The immediate win is that
a human — or the review-feedback triage agent — can *see* the page; the gate can come second.

> **Answer:**

### Q-09 · How much of the officer UI does v1 cover?

**Verified:** 22 `page.tsx` routes exist. A smoke pass (load each route as a seeded officer, assert no
5xx, no console error, no error boundary) is cheap and catches crashes and hydration failures. Driving
real flows is where the value is but costs a day each.

**Recommendation:** **all 22 routes smoke + 3–5 driven flows.** My proposed five, chosen because they
are what reviewers actually exercise: (1) queue → open ticket → add internal note; (2) escalate;
(3) resolve + closure summary; (4) settings → create/edit an officer; (5) reports → generate an XLSX.
**Tell me if a different five matter more** — you know what the reviewers break.

> **Answer (which flows):**

### Q-10 · Is the mobile surface in v1?

`middleware.ts` redirects mobile user-agents to a separate `/m/*` surface. In Playwright that is one
extra project (device descriptor + UA), so it is cheap — and UA-conditional routing is exactly the kind
of thing that breaks silently.

**Recommendation:** **yes — mobile smoke only** (`/m/queue`, `/m/tickets`, `/m/tasks`, one ticket
detail), no driven flows in v1.

> **Answer:**

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

> **Answer:**

### Q-12 · Does the e2e stack go through nginx, or straight to the UI container?

Direct to `grm_ui:3001` is simpler and faster. Through nginx is closer to production and would catch
proxy/routing regressions — which is how the webchat is actually served.

**Recommendation:** **direct for the officer UI; through nginx for the webchat** (QA-04d), because
nginx is part of what serves it.

> **Answer:**

### Q-13 · Report-only or required check?

**Verified via the GitHub API:** `main` has **no branch protection at all** (`Branch not protected`,
HTTP 404) — so today *no* check is required on any branch, and the HR-05 item asking for this is still
open.

**Recommendation:** land e2e as **report-only for ~2 weeks**, then enable branch protection on `main`
and `integration/**` requiring `backend-tests`, `ui-checks`, `docs-links` **and** the new e2e job.
⭐ Enabling protection for the *existing three* is a ten-minute job worth doing **now**, independent of
this sprint.

> **Answer:**

### Q-14 · Do we want an always-on test environment, or is ephemeral-per-PR enough?

Ephemeral costs nothing at rest and cannot drift. An always-on environment is nicer for humans to click
around in — and costs an instance plus an owner. This project already has one capability parked for
exactly that reason (T2 self-hosting, *"no run-cost owner"*).

**Recommendation:** **ephemeral only.** Revisit if the review-feedback sprint's agent phase actually
lands and wants a durable sandbox.

> **Answer:**

### Q-15 · Who runs the DOR-prod side of QA-02, and when?

Everything in this sprint is verifiable on staging by whoever holds the AWS key. Production needs VPN
access and a maintenance window, and per Q-05 may need a different image path entirely.

**Recommendation:** **staging in this sprint; production as a separately scheduled follow-up** with its
own runbook entry, so the sprint is not blocked on VPN availability.

> **Answer:**
