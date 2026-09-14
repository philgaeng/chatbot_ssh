# Sprint — QA & build pipeline (September 2026)

**Audience:** internal — excluded from the public repository (lifecycle §10.4).

> **Status:** 📋 **Proposed — not approved.** Tier 3 per [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) §1.
> **Why:** [`DESIGN-qa-and-build-pipeline.md`](DESIGN-qa-and-build-pipeline.md) — read it first.
> 🚀 **Starting the sprint? [`KICKOFF.md`](KICKOFF.md)** — branch state, the one open decision, the three
> asks that need the owner, and the traps that are not visible from these files.
> ✅ **Q-01…Q-15 answered 2026-09-04** ([`QUESTIONS.md`](QUESTIONS.md)); every answer is folded into the
> ticket that needs it, so an agent works from its spec alone.
> ⚠ Three carry a residual check done *during* QA-02, not before it: the production host's CPU
> architecture, whether the `ubuntu-24.04-arm` runner label resolves, and whether prod can reach the
> registry. The accepted answer is the safe default in each case.
> ⚠ **A completeness review on 2026-09-04 added Q-16…Q-19 — seams between tickets.** Q-17/18/19 are
> folded in as fixes. **[Q-16](QUESTIONS.md#q-16--which-commits-get-an-image) is open** (which commits
> get an image) and **blocks QA-05, not the sprint** — QA-01 through QA-04 can all start.

## Goal, in one sentence

**Build images once in CI, run them anywhere, and put a browser in front of the result** — which is
simultaneously the fix for the 2026-09-04 deploy outage and the missing verification capability that
blocks every form of automated UI work.

## Tickets

| # | Ticket | Est. | Depends on | Stream |
|---|---|---|---|---|
| [QA-01](01-QA-01-deploy-safety.md) | Stop the next deploy being an outage (swap + build heap cap + deploy progress output) | ½ d | — | **A** |
| [QA-02](02-QA-02-ci-built-images.md) | CI-built images, pulled by the hosts | 2–3 d | QA-01 | **A** |
| [QA-03](03-QA-03-stack-isolation.md) | `COMPOSE_PROJECT_NAME` + parameterised ports | 1 d | QA-02 | **A** |
| [QA-04](04-QA-04-browser-harness.md) | Playwright harness against a seeded stack (04a) + coverage fan-out (04b routes · 04c flows · 04d webchat) | 4.5–6 d **+2–3 d** | — | **B** |
| [QA-05](05-QA-05-ci-gate-and-coverage.md) | Run it in CI; ticks HR-07’s sweep once 04d actually passes | 1–2 d | QA-02, QA-03, QA-04 | **join** |

**Total 11–15.5 days** for one person; **~7–9 elapsed days** with the two streams in parallel and 04b/c/d fanned out.

⚠ **Up from 9–12.5 on 2026-09-04**, entirely in QA-04c: [Q-09](QUESTIONS.md#q-09--how-much-of-the-officer-ui-does-v1-cover)
was answered **"lets do all the flows"**, not the five the ticket had been written against. The five are
now tier 1 and the rest tier 2 — **tier 2 is the clean thing to split out** if the total is too long.

> ⚠ The QA-04 cell read *"3–4 d +1–1.5 d"* until 2026-09-04, while its own sub-ticket table summed to
> 4.5–6. The total was computed from the sub-tickets and was right; the cell was the drifted one. This
> is the drift the [`DESIGN`](DESIGN-qa-and-build-pipeline.md) §2 note predicted — **one list, in one
> file**, and the sub-ticket table is the source.

## How this splits across agents

```
 Stream A — build & deploy pipeline            Stream B — browser harness
 (Makefile · compose · CI workflow)            (channels/ticketing-ui/e2e · new files only)
 ───────────────────────────────────           ──────────────────────────────────────────
 QA-01 ─▶ QA-02 ─▶ QA-03                       QA-04a  harness + fixtures + auth
   strictly sequential:                          │
   all three edit the same                       ├─▶ QA-04b  officer-UI route smoke  ┐
   Makefile macros and                           ├─▶ QA-04c  driven flows (all, Q-09) ├ parallel,
   compose files                                 └─▶ QA-04d  webchat sweep (HR-07)   ┘ one agent each
                          │                                        │
                          └──────────────┬─────────────────────────┘
                                         ▼
                                  QA-05 — CI gate
```

**Both streams can start now.** Stream B was never blocked on Stream A. ⚠ **QA-05 is the exception** —
it needs [Q-16](QUESTIONS.md#q-16--which-commits-get-an-image) settled and `UI_IMAGE_TAG` (Q-17) built
by QA-02 before it can be written. Everything upstream of it is unblocked.

**Two rules that make the parallelism safe:**

1. **Stream A owns `Makefile`, `docker-compose*.yml` and `.github/workflows/ci.yml`. Stream B must not
   touch them** — B writes only under `channels/ticketing-ui/e2e/` (+ its own `playwright.config.ts`
   and `package.json` devDependency) until QA-05, which is the single join point where CI is edited.
   ⚠ **The `package.json` devDependency is the one place this isolation leaks.**
   `channels/ticketing-ui/Dockerfile` runs a full `npm ci` in its builder stage, so what B adds gets
   installed **inside A's image build**, on the memory-starved host QA-01 is protecting. Two lines of
   coordination, agreed once at 04a: depend on **`@playwright/test`** (never bare `playwright`, whose
   postinstall downloads browsers) and set `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1` in the builder. The
   Dockerfile edit is A's to make — see [QA-04](04-QA-04-browser-harness.md).
2. **Stream B can start immediately and does not wait for A.** It develops against the local WSL stack
   (`make wsl-up && make migrate_all && make wsl-seed-full`), which already works today. A's images are
   what let the same suite run on a CI runner — needed at QA-05, not before.

**QA-04b/c/d fan out only after QA-04a lands** — they add spec files against a harness that must
already exist. One agent per group; they do not share files.

## Branches — where each stream works

The repo's rule stands: `main` is integration-only, work happens on explicit branches
([`deployment/08_commit_strategy.md`](../../deployment/08_commit_strategy.md)). This sprint follows the
same shape the org-chart sprint used — a sprint branch, with one branch per workstream off it:

```
integration/stage
   └── dev/qa-automation                 ← the sprint branch
         ├── qa/a-build-pipeline         ← Stream A: QA-01 → QA-02 → QA-03
         ├── qa/b-harness                ← Stream B: QA-04a
         │     ├── qa/b-smoke            ← QA-04b   ┐ off qa/b-harness once it merges
         │     ├── qa/b-flows            ← QA-04c   ├ one agent each
         │     └── qa/b-webchat          ← QA-04d   ┘
         └── qa/e2e-ci                   ← QA-05, last, off a sprint branch carrying both streams
```

⭐ **The sprint branch is named `dev/qa-automation` for a mechanical reason, not a stylistic one.**
`ci.yml` triggers on pushes to `main`, `integration/**`, `dev/**` and `dpg/**` — a branch outside those
prefixes gets CI **only** through a pull request. This repo has already been bitten twice by a gate that
silently did not run (nine `dpg/**` commits, and 27 test files CI never collected). Keeping the sprint
branch under `dev/` means every push is gated; the `qa/*` workstream branches are gated by their PR.

**Merge order:** A and B are independent and merge into `dev/qa-automation` in whatever order they
finish. QA-05 branches *after* both are in, because it consumes A's images and B's specs.

## Conventions binding on every agent here

- [`engineering/04_testing.md`](../../engineering/04_testing.md) — the pyramid and the integration-marker contract.
- [`engineering/05_frontend.md`](../../engineering/05_frontend.md) — anything under `channels/ticketing-ui/`.
- [`deployment/08_commit_strategy.md`](../../deployment/08_commit_strategy.md) — branch and commit workflow.
- **The standing deferral rule** ([`../README.md`](../README.md)): anything scoped out, suppressed or
  downgraded gets a `followups/<slug>.md` **and** a `TODO.md` row **in the same commit**.
- Record every deviation in [`PROGRESS.md`](PROGRESS.md) as you go, not at the end.

## Files in this folder

| File | What |
|---|---|
| [`DESIGN-qa-and-build-pipeline.md`](DESIGN-qa-and-build-pipeline.md) | Why this sprint exists; the constraint that decides where things run |
| [`QUESTIONS.md`](QUESTIONS.md) | The 15 questions, **all answered** — kept as the record of why, and what would reverse each choice |
| `01-…` … `05-…` | One spec per ticket, written to be handed to an agent as-is |
| [`PROGRESS.md`](PROGRESS.md) | Tracker + deviations log |
