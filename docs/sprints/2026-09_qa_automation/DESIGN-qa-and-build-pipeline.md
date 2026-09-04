# DESIGN — Build pipeline and UI verification (the QA sprint)

> **Status:** Proposed, **2026-09-04**, branch `integration/stage`. **Not an approved sprint. No code
> written.** Tier 3 per [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) §1.
> **Split out of** the review-feedback evaluation ([`../2026-09_review_feedback_loop/DESIGN-review-feedback-loop.md`](../2026-09_review_feedback_loop/DESIGN-review-feedback-loop.md)),
> which found this to be the larger and more foundational half — and independent of it.
> **Start here, then:** [`README.md`](README.md) (ticket graph + how it splits across agents) and
> [`QUESTIONS.md`](QUESTIONS.md) (**15 open questions — nothing starts before its blockers are answered**).

---

## 1. Why this is its own sprint, and why it stopped being optional this morning

Two unrelated forces land on the **same** piece of infrastructure:

**Force 1 — nothing in this project can look at the UI.** There is no browser automation anywhere:
no Playwright, Puppeteer, Cypress or Selenium in any `package.json` or `requirements*.txt`. The gates
that exist — `tsc --noEmit`, `eslint`, `next build`, 897 backend tests — prove a UI change *compiles*.
None of them can see a button overlapping its label. The officer UI is **172 TS/TSX files, ~35.6k lines,
22 routes**, with **no end-to-end coverage at all**.

The clearest evidence that this is a real gap rather than a theoretical one: HR-07's 7-item regression
sweep is **still an open checkbox** a sprint after its code merged, explicitly because *"no browser
automation available in this environment"* ([`2026-07_hardening/PROGRESS.md`](../2026-07_hardening/PROGRESS.md)).
⚠ **That sweep covers the REST webchat, not the officer UI** — a different surface. It is the same root
cause showing up somewhere else, and automating it is *additional* scope here, not a freebie
([Q-11](QUESTIONS.md#q-11--does-closing-hr-07s-sweep-belong-in-this-sprint)).

**Force 2 — building on the deploy host took staging down for 40 minutes.** Incident `2431da51`
(2026-09-04): `REMOTE_DEPLOY_CORE` runs `docker compose build --pull` **on the box**, the Next.js
build exhausted a **t4g.medium — 2 vCPU, 3825 MB, no swap** running 14 containers, and the host stopped
accepting new SSH, ping and Tailscale for 41 minutes while every AWS-side signal read healthy.
96 MB free, load average 54.92. Its own logged fix, second of three: *"stop building on the box and
pull a CI-built image (the actual fix)."*

**Three facts found while scoping, which make QA-02 much cheaper than "containerise the deploy" sounds:**

| Verified | Consequence |
|---|---|
| **Eight built services, two Dockerfiles** — ten Python services all build the same root `Dockerfile`; only `grm_ui` differs | This is **two images**, not eight |
| **No service declares an `image:`** in any compose file | Adding them is the core of the work, and it is mechanical |
| **The repo is public** (`gh repo view` → `PUBLIC`) | GHCR is free and authenticates with CI's own `GITHUB_TOKEN` — no new secret ([Q-01](QUESTIONS.md#q-01--which-registry)) |

⭐ **Those two fixes are the same build.** "Images are built in CI and pulled by whoever runs them" is
simultaneously the incident's real remedy and the precondition for standing a stack up anywhere a test
harness can reach it. **This sprint is therefore not overhead invented by the feedback feature** — it is
an operations fix and a test capability that happen to be one piece of work.

---

## 2. Scope

| # | Ticket | What | Est. |
|---|---|---|---|
| **QA-01** | **Stop the next deploy being an outage** | The incident's fixes **(1)** add swap — a 4 GB file turns a livelock into a slowdown — and **(3)** cap the Next build's heap (`NODE_OPTIONS=--max-old-space-size`) so it fails loudly instead of taking the host with it. Stopgaps, not substitutes for QA-02. | ½ d |
| **QA-02** | **CI-built images** | The incident's fix **(2)**, *"the actual fix"*: build in GitHub Actions, push to a registry, tag by commit; `aws-deploy` / `prod-deploy` **pull** instead of building. Removes the OOM class entirely and makes an image runnable anywhere. ⚠ Also worth fixing alongside: `aws-deploy` prints nothing until it exits, so a 40-minute stall looks like a 4-minute one. | 2–3 d |
| **QA-03** | **Stack isolation** | `COMPOSE_PROJECT_NAME` (absent from every compose file, the Makefile and `env.local` today) + parameterised host ports — `5001`, `8000`, `5002`, `3001`, `8080:80` are literals, and `check_grm_ports` asserts `3001`/`5002` by hand. Without this, two stacks cannot coexist on one host or one runner. | 1 d |
| **QA-04** | **Browser harness** | Playwright against a seeded stack: load each officer-UI route, drive a named reproduction, capture a screenshot. Seeding is already solved — `make wsl-seed-full` + `ticketing/seed/mock_tickets.py` build the corpus from nothing. | 3–4 d |
| **QA-05** | **Wire into CI + close HR-07** | Run QA-04 on PRs; publish screenshots as artifacts. Converts the pending-human browser sweep into a gate. | 1–2 d |

**Total: 8–11 days.** QA-01 is worth doing this week regardless of whether the rest is approved.

⭐ **QA-01 and QA-02 are not new scope.** They are fixes (1)(3) and (2) of the three already logged
against the incident in [`TODO.md`](../../TODO.md) (🔴 row, *"A routine `make aws-deploy` took staging
OFF THE NETWORK for ~40 minutes"*). This sprint is where they get done — and the point of putting them
here rather than leaving them as ops chores is that **QA-02 is the same work as "run a stack somewhere
a browser can test it"**.

---

## 3. The constraint that decides where anything runs

**Co-locating a second stack on the staging host is off the table.** Not "needs headroom" — there is
none. Measured during the incident: **3825 MB, no swap, 14 containers, 96 MB free at failure**, and a
single Next.js build was enough to livelock it. A second stack means a second Postgres, a second
Keycloak and a second UI build.

This kills the cheapest option and makes **QA-02 the load-bearing ticket**: once images are built in CI,
the thing that runs a stack no longer needs to be able to *build* one, and it can be an ephemeral CI
runner rather than a paid always-on instance.

| Where a test/sandbox stack could run | Verdict |
|---|---|
| Second compose project on the staging EC2 | 🔴 **Ruled out by the incident.** |
| Ephemeral stack on a CI runner, from pulled images | ✅ **Recommended** — free at rest, disposable by construction, needs QA-02 + QA-03 |
| A small dedicated instance | 🟡 Viable, costs money, only if an always-on environment is genuinely wanted |
| The dev WSL box | 🟡 Already runs the full stack — fine for local QA-04 runs, not for unattended use |

---

## 4. What this sprint unlocks elsewhere

- **The officer UI gets its first end-to-end coverage** — 22 routes, 11 unit tests today, zero e2e.
- **Deploys stop being an outage risk**, which is the incident's actual ask — and gain a **rollback**
  they do not currently have: `make aws-deploy IMAGE_TAG=<older-sha>`, no rebuild.
- **HR-07's sweep can finally be retired** — conditionally, and on the webchat surface
  ([Q-11](QUESTIONS.md#q-11--does-closing-hr-07s-sweep-belong-in-this-sprint)).
- **The review-feedback sprint's agent phase becomes possible** — an agent can apply a change, look at
  the result, and attach a before/after pair to a PR. Without this sprint that agent is guessing.
  See [`../2026-09_review_feedback_loop/DESIGN-review-feedback-loop.md`](../2026-09_review_feedback_loop/DESIGN-review-feedback-loop.md) §3.

## 5. Open questions

**All 15 live in [`QUESTIONS.md`](QUESTIONS.md), each with a recommendation and an answer slot.** The
three that most change the shape of the work:

| # | Question | Why it decides something |
|---|---|---|
| [Q-02](QUESTIONS.md#q-02--what-cpu-architectures-must-the-images-support) | **What architecture is DOR production?** Staging is ARM64 (t4g.medium); the prod spec says *"ARM64 **or** x86_64"*, and the box is VPN-only so I could not check | arm64-only vs multi-arch roughly doubles QA-02's build time |
| [Q-09](QUESTIONS.md#q-09--how-much-of-the-officer-ui-does-v1-cover) | **Which 3–5 flows does v1 drive?** 22 routes smoke cheaply; driven flows cost ~a day each | Scope of the largest ticket, and you know what reviewers break better than the code does |
| [Q-13](QUESTIONS.md#q-13--report-only-or-required-check) | **Report-only or required?** ⚠ Verified via the API: `main` has **no branch protection at all** today | Whether any of this becomes a gate or stays decoration |
