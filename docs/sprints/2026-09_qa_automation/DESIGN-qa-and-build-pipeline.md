# DESIGN — Build pipeline and UI verification (the QA sprint)

> **Status:** Proposed, **2026-09-04**, branch `integration/stage`. **Not an approved sprint. No code
> written.** Tier 3 per [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) §1.
> **Split out of** the review-feedback evaluation ([`../2026-09_review_feedback_loop/DESIGN-review-feedback-loop.md`](../2026-09_review_feedback_loop/DESIGN-review-feedback-loop.md)),
> which found this to be the larger and more foundational half — and independent of it.
> **Start here, then:** [`README.md`](README.md) (ticket graph + how it splits across agents) and
> [`QUESTIONS.md`](QUESTIONS.md) (Q-01…Q-15 **answered 2026-09-04**, plus Q-16…Q-19 from the
> completeness review in §6 — kept as the record of why). **§6 is the newest material; read it before
> handing any ticket to an agent.**

---

## 1. Why this is its own sprint, and why it stopped being optional this morning

Two unrelated forces land on the **same** piece of infrastructure:

**Force 1 — nothing in this project can look at the UI.** There is no browser automation anywhere:
no Playwright, Puppeteer, Cypress or Selenium in any `package.json` or `requirements*.txt`. The gates
that exist — `tsc --noEmit`, `eslint`, `next build`, 897 backend tests — prove a UI change *compiles*.
None of them can see a button overlapping its label. The officer UI is **180 TS/TSX files, 22 routes**,
with **no end-to-end coverage at all**. (It was 172 files when this was first written on 2026-09-04 —
the number moves; the zero does not.)

The clearest evidence that this is a real gap rather than a theoretical one: HR-07's 7-item regression
sweep is **still an open checkbox** a sprint after its code merged, explicitly because *"no browser
automation available in this environment"* ([`2026-07_hardening/PROGRESS.md`](../2026-07_hardening/PROGRESS.md)).
⚠ **That sweep covers the REST webchat, not the officer UI** — a different surface. It is the same root
cause showing up somewhere else. Automating it was *additional* scope, not a freebie; it was **taken
into scope** as QA-04d (+1–1.5 d).

**Force 2 — building on the deploy host took staging down for 40 minutes.** Incident `2431da51`
(2026-09-04): `REMOTE_DEPLOY_CORE` runs `docker compose build --pull` **on the box**, the Next.js
build exhausted a **t4g.medium — 2 vCPU, 3825 MB, no swap** running 14 containers, and the host stopped
accepting new SSH, ping and Tailscale for 41 minutes while every AWS-side signal read healthy.
96 MB free, load average 54.92. Its own logged fix, second of three: *"stop building on the box and
pull a CI-built image (the actual fix)."*

**Three facts found while scoping, which make QA-02 much cheaper than "containerise the deploy" sounds:**

| Verified | Consequence |
|---|---|
| **Eleven built services, two Dockerfiles** — ten build the root `Dockerfile` (context `.`); only `grm_ui` differs (context `./channels/ticketing-ui`) | This is **two images**, not eleven |
| **No service declares an `image:`** in any compose file | Adding them is the core of the work, and it is mechanical |
| ~~**The repo is public** (`gh repo view` → `PUBLIC`)~~ ⚠ **REVERSED 2026-09-04** — it is now `PRIVATE` ([D-010](../../DECISIONS.md)) | `GITHUB_TOKEN` still authenticates with no new secret, but **packages are now private**: metered storage, and metered egress to anything outside Actions — which the staging host pulling an image is. **Re-decide [Q-01](QUESTIONS.md#q-01--which-registry) before QA-02 starts**, together with [Q-16](QUESTIONS.md#q-16--which-commits-get-an-image), which is now the cost dial |

⭐ **Those two fixes are the same build.** "Images are built in CI and pulled by whoever runs them" is
simultaneously the incident's real remedy and the precondition for standing a stack up anywhere a test
harness can reach it. **This sprint is therefore not overhead invented by the feedback feature** — it is
an operations fix and a test capability that happen to be one piece of work.

---

## 2. What is in the sprint

**Five tickets:** QA-01 deploy safety · QA-02 CI-built images · QA-03 stack isolation ·
QA-04 browser harness (04a harness, then 04b routes / 04c flows / 04d webchat) · QA-05 CI gate.

> **▶ The plan is [`README.md`](README.md)** — estimates, dependencies, the two agent streams, the
> branch tree and the merge order. Each ticket then has its own spec, `01-…05-`, written to be handed
> to an agent on its own.
>
> ⚠ **Deliberately no estimates or dependency table here.** There was one until 2026-09-04, and it
> drifted from the tickets twice in a single day — a stale total and a ticket title that no longer
> matched. **One list, in one file.** This document answers *why the sprint exists*; it does not
> restate what it contains.

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

- **The officer UI gets its first end-to-end coverage** — 22 routes, 12 unit-test files today (all pure
  logic under `lib/` and `components/settings/`, none of them touching a rendered page), zero e2e.
- **Deploys stop being an outage risk**, which is the incident's actual ask — and gain a **rollback**
  they do not currently have: `make aws-deploy IMAGE_TAG=<older-sha>`, no rebuild.
- **HR-07's sweep is finally retired** — on the webchat surface, as QA-04d, and its checkbox is ticked
  only against a run that actually passed.
- **The review-feedback sprint's agent phase becomes possible** — an agent can apply a change, look at
  the result, and attach a before/after pair to a PR. Without this sprint that agent is guessing.
  See [`../2026-09_review_feedback_loop/DESIGN-review-feedback-loop.md`](../2026-09_review_feedback_loop/DESIGN-review-feedback-loop.md) §3.

## 5. Open questions

✅ **Q-01…Q-15 were answered on 2026-09-04 and folded into the ticket specs** — [`QUESTIONS.md`](QUESTIONS.md)
survives as the record of *why* each choice was made and what would reverse it. The three that shaped
the work most, and what they settled:

| # | Question | Why it decides something |
|---|---|---|
| [Q-02](QUESTIONS.md#q-02--what-cpu-architectures-must-the-images-support) | **What architecture is DOR production?** Staging is ARM64 (t4g.medium); the prod spec says *"ARM64 **or** x86_64"*, and the box is VPN-only, so it is still unknown | → **build multi-arch**, the safe branch. ⚠ Get `uname -m` from the prod box early: if it is `aarch64`, every build halves |
| [Q-09](QUESTIONS.md#q-09--how-much-of-the-officer-ui-does-v1-cover) | **Which flows does v1 drive?** 22 routes smoke cheaply; driven flows cost ~a day each | → **22 routes smoke + five named flows**, deliberately provisional: swapping one after watching real feedback is the plan, not a change of plan |
| [Q-13](QUESTIONS.md#q-13--report-only-or-required-check) | **Report-only or required?** ⚠ Verified via the API: `main` has **no branch protection at all** today | → **report-only with an expiry date in the job header**, then required. ⭐ Protecting the three *existing* checks is a ten-minute action worth doing now, outside this sprint |

---

## 6. What a completeness review found (2026-09-04)

The tickets were reviewed against the tree, claim by claim, before any code was written. **Every
factual claim in this document checked out** — eleven built services from two Dockerfiles, no `image:`
key anywhere, no `COMPOSE_PROJECT_NAME`, 22 `page.tsx` routes, no browser automation in any
`package.json` or `requirements*.txt`, HR-07's diffs present in `channels/REST_webchat/app.js`, and the
`grm_bypass_user` cookie doing what Q-07 says it does.

**What did not hold was the joins.** Each ticket read correctly alone; four pairs contradicted each
other when executed in order, and one security claim was already false:

| Seam | What broke | Now in |
|---|---|---|
| QA-02 → QA-05 | The image workflow built on `main`/`integration/**`; the e2e job pulls *this commit's* sha. No PR would have an image — including this sprint's own | [Q-16](QUESTIONS.md#q-16--which-commits-get-an-image) — **open, a real fork** |
| QA-02 → QA-05 | One `IMAGE_TAG` cannot name both `ui:<sha>` and `ui:<sha>-bypass`; the build-arg mechanism that selects the variant today is exactly what pulling removes | [Q-17](QUESTIONS.md#q-17--how-does-a-stack-select-the-bypass-ui-variant) — `UI_IMAGE_TAG`, owned by QA-02 |
| QA-02 → prod | `REMOTE_DEPLOY_CORE` is called by **both** `aws-deploy` and `prod-deploy`, so "staging only" and "rewrite the macro" cannot both hold | QA-02 scope 3 — split, not edit |
| QA-02 (self) | "The `.dockerignore` is supposed to exclude `env.local` — verify it." It does not, and the images become **public** | [Q-18](QUESTIONS.md#q-18--does-the-image-contain-envlocal) — a fix, not a check |
| QA-02 (self) | Only `REMOTE_DEPLOY_CORE` was converted. `aws-deploy-light` rebuilds the Next.js app on the box — **that build is the incident**, on the most-used path | QA-02 scope 3 |
| QA-02/05 → repo | Both cited "the documented order (public → ticketing → ops)". Two orders exist in the repo and disagree | [Q-19](QUESTIONS.md#q-19--which-migration-order-is-the-documented-one) — change neither, log it |
| QA-04b → seed | Three of five parameterised routes have **no seeded token**; a closure token requires running the LLM summary builder | QA-04b — a fixture, and an honest skip if not free |
| QA-04d → CI | Voice-note automation means a **paid ASR call**, which `backend-tests` deliberately excludes; the dead-backend item takes the stack down under any concurrent spec | QA-04d — stub ASR, simulate the dead backend at the network layer |
| Stream B → Stream A | The "B only touches `e2e/` + a devDependency" isolation leaks: the UI builder runs `npm ci` with dev deps | [README](README.md) rule 1 |

⭐ **The pattern worth keeping.** Every one of these lives in the *space between* two documents that
are each correct. The DESIGN warned about exactly this failure mode for estimates — *"one list, in one
file"* (§2) — and the same discipline was missing for interfaces: nothing said which ticket **owns**
`UI_IMAGE_TAG`, or what QA-05 is entitled to assume exists. The tickets now name their handoffs
explicitly, and QA-05 is told **not to work around a missing one**, because a join point that quietly
absorbs two other tickets' work is how a sprint's estimate goes wrong without anyone noticing.
