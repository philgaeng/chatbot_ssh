# QA sprint — progress

> **Status: not started.** Q-01…Q-15 answered 2026-09-04; **QA-01 through QA-04 can begin.**
> ⚠ **QA-05 is blocked on [Q-16](QUESTIONS.md#q-16--which-commits-get-an-image)** (which commits get an
> image) — a seam found by the 2026-09-04 completeness review, [`DESIGN`](DESIGN-qa-and-build-pipeline.md) §6.
> It is QA-02's decision to record; QA-05 must not improvise around it.
> Tracker skeleton — fill as work lands, not at the end.
> Sprint: [`README.md`](README.md) · Why: [`DESIGN-qa-and-build-pipeline.md`](DESIGN-qa-and-build-pipeline.md) · Decisions: [`QUESTIONS.md`](QUESTIONS.md)

## Ticket status

| Ticket | Stream | Status | Branch | Commit | Notes |
|---|---|---|---|---|---|
| QA-01 deploy safety | A | ⬜ not started | — | — | Blocked on nothing. Measure the real Next build peak before picking the heap cap. |
| QA-02 CI-built images | A | ⬜ not started | — | — | GHCR · multi-arch (pending the prod `uname -m` below) · two UI variants · staging only |
| QA-03 stack isolation | A | ⬜ not started | — | — | Blocked on QA-02 |
| QA-04a harness | B | ⬜ not started | — | — | `channels/ticketing-ui/e2e/`, bypass build, `*.spec.ts`. **Can start today** |
| QA-04b route smoke | B | ⬜ not started | — | — | After 04a |
| QA-04c driven flows | B | ⬜ not started | — | — | After 04a. ⚠ **Q-09 answered "all the flows"** — five as tier 1, the rest as tier 2 (+2–3 d). Tier 2 is the clean split if the sprint is too long |
| QA-04d webchat sweep | B | ⬜ not started | — | — | ✅ in scope (+1–1.5 d). Through nginx |
| QA-05 CI gate | join | ⬜ not started | — | — | After QA-02, QA-03, QA-04a. ⚠ Blocked on Q-16; needs `UI_IMAGE_TAG` (Q-17) from QA-02 |

## Open actions that are not tickets

These came out of the answers and have no home in a ticket. **They are listed here so they are not lost** —
each is small, and two of them change how much QA-02 costs.

| # | Action | Owner | Why it matters |
|---|---|---|---|
| A-1 | **Get `uname -m` from the DOR production host** | owner (Q-15: *"I have access to prod but access is intermittent"*) | If `aarch64`, QA-02 drops amd64 and **every image build halves**. Until then multi-arch is the safe default |
| A-2 | **`curl -sI https://ghcr.io/v2/` from the DOR production host** | owner (same intermittent access — pair it with A-1, one session) | Decides whether prod can ever pull, or needs `docker save`/`load` or an internal mirror |
| A-3 | ~~**Enable branch protection**~~ 🟡 **Settings done and active 2026-09-04; the proof is not** | repo admin | The repo went private ([D-010](../../DECISIONS.md)), which is what made this possible — protection rules need a paid plan on a private repo. Created: a repository **ruleset** (`Main`, id 22278949) targeting `refs/heads/main` and `refs/heads/integration/*`, with all five CI jobs as required checks (`backend-tests`, `ui-checks`, `webchat-checks`, `docs-links`, `dpg-platform-independence`), pull-request-required, deletions and force-pushes blocked, and **no bypass actors**. ✅ **Verified active 2026-09-04** via `gh api /repos/philgaeng/chatbot_ssh/rulesets` — `enforcement: active`, targets `refs/heads/main` + `refs/heads/integration/*`, five required checks, zero bypass actors, `required_approving_review_count: 0`. ⭐ **And it settles an open unknown:** rulesets *do* enforce on a private repo owned by a personal account on a paid plan — the community reports of a "won't be enforced" banner did not apply here. ⚠ `strict_required_status_checks_policy` is **false**, so a PR can merge on checks that passed against a stale base. **The second half of A-3 — proving a red build actually blocks — is untouched** ([HR-05](../../deployment/17_manual_browser_sweep.md)) |
| A-4 | **Confirm `ubuntu-24.04-arm` resolves** on the first CI run | QA-02 agent | If not, fall back to QEMU — and record it here before spending time tuning it |
| A-5 | **Log the prod-rollout follow-up** (`followups/` + `TODO.md` row) when QA-02 lands | QA-02 agent | Standing deferral rule — prod staying on build-on-box is deferred debt, not a silent omission |
| A-6 | **Settle [Q-16](QUESTIONS.md#q-16--which-commits-get-an-image) — which commits get an image** | owner + QA-02 agent | ⚠ **The one open decision.** QA-05 pulls `IMAGE_TAG=<this sha>`; if `images.yml` does not build for the branch under test, no PR has an image and the e2e job fails for an unrelated reason. Recommendation in QUESTIONS.md |
| A-7 | **Log the migration-order reconciliation** ([Q-19](QUESTIONS.md#q-19--which-migration-order-is-the-documented-one)) as `followups/` + `TODO.md` | QA-02 agent | `ci.yml` and the Makefile run the three streams in **different** orders. Neither ticket changes either; the discrepancy needs a migrations ticket, not a guess inside a test harness |
| A-8 | **Rotate secrets if any image is pushed before the `.dockerignore` fix** ([Q-18](QUESTIONS.md#q-18--does-the-image-contain-envlocal)) | QA-02 agent | The root `.dockerignore` excludes no env file and the image is `COPY . /app` → a build on any host holding `env.local` bakes it in. A published image cannot be unpublished |

## Measurements to record (the sprint is not done without these)

| What | Why it matters | Value |
|---|---|---|
| Peak RSS of `npm run build` | Sets QA-01's heap cap honestly | — |
| Staging peak memory during a **pulled** deploy | Proves QA-02 removed the OOM class | — |
| Image build time, cold and cached | Tells us whether the cache is working | — |
| e2e wall-clock in CI | Decides whether it can ever be a required check | — |
| Routes covered / 22 | The honest coverage number, not a claim | — |
| Parameterised routes skipped, and why | Three of five have no seeded token (QA-04b) — a suite that silently omits them while reporting 22 is the failure this sprint exists to stop | — |

## Deviations log

| Date | Ticket | Deviation / adjacent finding | Action |
|---|---|---|---|
| 2026-09-04 | sprint | **Completeness review before any code.** Every factual claim in the specs verified against the tree (all held); **nine seams between tickets did not**, and one security claim was already false — the root `.dockerignore` excludes no env file. Full table: [`DESIGN`](DESIGN-qa-and-build-pipeline.md) §6 | Specs revised same-day; Q-16…Q-19 added to [`QUESTIONS.md`](QUESTIONS.md); A-6…A-8 opened above. Q-16 left **open** — it is a fork, not a fix |

## Acceptance — sprint level

- [ ] A deploy to staging builds nothing on the host, and it is verified inside the container that the running code is the intended commit
- [ ] **`make aws-deploy-light` builds nothing on the host either** — the UI-only path is the one that caused the incident
- [ ] **`make prod-deploy` still behaves exactly as it does today** — the shared macro did not drag production onto an untested registry path
- [ ] **No published image contains an env file** — checked on the image, not inferred from the `.dockerignore`
- [ ] `make aws-deploy IMAGE_TAG=<older-sha>` is a working rollback
- [ ] Two isolated stacks run side by side on one machine
- [ ] A browser drives the officer UI in CI, and a deliberate regression turns the build red
- [ ] Every number in the table above is filled in with a measured value
