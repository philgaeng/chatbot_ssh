# Sprint — QA & build pipeline (September 2026)

> **Status:** 📋 **Proposed — not approved.** Tier 3 per [`engineering/06_documentation_lifecycle.md`](../../engineering/06_documentation_lifecycle.md) §1.
> **Why:** [`DESIGN-qa-and-build-pipeline.md`](DESIGN-qa-and-build-pipeline.md) — read it first.
> **Blocking input:** [`QUESTIONS.md`](QUESTIONS.md) — **15 open questions, most with a recommendation.**
> Q-01…Q-05 block QA-02; Q-06…Q-10 block QA-04. Nothing should start until those are answered.

## Goal, in one sentence

**Build images once in CI, run them anywhere, and put a browser in front of the result** — which is
simultaneously the fix for the 2026-09-04 deploy outage and the missing verification capability that
blocks every form of automated UI work.

## Tickets

| # | Ticket | Est. | Depends on | Stream |
|---|---|---|---|---|
| [QA-01](01-QA-01-deploy-safety.md) | Stop the next deploy being an outage (swap + build heap cap + deploy progress output) | ½ d | — | **A** |
| [QA-02](02-QA-02-ci-built-images.md) | CI-built images, pulled by the hosts | 2–3 d | QA-01, Q-01…Q-05 | **A** |
| [QA-03](03-QA-03-stack-isolation.md) | `COMPOSE_PROJECT_NAME` + parameterised ports | 1 d | QA-02 | **A** |
| [QA-04](04-QA-04-browser-harness.md) | Playwright harness against a seeded stack | 3–4 d | Q-06…Q-10 | **B** |
| [QA-05](05-QA-05-ci-gate-and-coverage.md) | Run it in CI, fan out coverage, close HR-07's sweep | 1–2 d + fan-out | QA-02, QA-03, QA-04 | **join** |

**Total 8–11 days** for one person; **~5–6 elapsed days** with the two streams in parallel.

## How this splits across agents

```
 Stream A — build & deploy pipeline            Stream B — browser harness
 (Makefile · compose · CI workflow)            (channels/ticketing-ui/e2e · new files only)
 ───────────────────────────────────           ──────────────────────────────────────────
 QA-01 ─▶ QA-02 ─▶ QA-03                       QA-04a  harness + fixtures + auth
   strictly sequential:                          │
   all three edit the same                       ├─▶ QA-04b  officer-UI route smoke  ┐
   Makefile macros and                           ├─▶ QA-04c  the 3–5 real flows      ├ parallel,
   compose files                                 └─▶ QA-04d  webchat sweep (HR-07)   ┘ one agent each
                          │                                        │
                          └──────────────┬─────────────────────────┘
                                         ▼
                                  QA-05 — CI gate
```

**Two rules that make the parallelism safe:**

1. **Stream A owns `Makefile`, `docker-compose*.yml` and `.github/workflows/ci.yml`. Stream B must not
   touch them** — B writes only under `channels/ticketing-ui/e2e/` (+ its own `playwright.config.ts`
   and `package.json` devDependency) until QA-05, which is the single join point where CI is edited.
2. **Stream B can start immediately and does not wait for A.** It develops against the local WSL stack
   (`make wsl-up && make migrate_all && make wsl-seed-full`), which already works today. A's images are
   what let the same suite run on a CI runner — needed at QA-05, not before.

**QA-04b/c/d fan out only after QA-04a lands** — they add spec files against a harness that must
already exist. One agent per group; they do not share files.

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
| [`QUESTIONS.md`](QUESTIONS.md) | **15 open questions — answer here** |
| `01-…` … `05-…` | One spec per ticket, written to be handed to an agent as-is |
| [`PROGRESS.md`](PROGRESS.md) | Tracker + deviations log |
