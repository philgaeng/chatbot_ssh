# Contributing

Thank you for considering a contribution. This is a Grievance Redress Mechanism for people affected
by road construction in Nepal: real complainants, real officers, and a stream that handles SEAH
(sexual exploitation, abuse and harassment) disclosures. Bugs here have consequences for people who
have no other channel, so this guide is a little stricter than most.

**This file points at the rules; it does not restate them.** A contributing guide that paraphrases
the build steps drifts out of date and then contradicts them, which is worse than not having one.

---

## Before you start

| Read | For |
|---|---|
| [`docs/engineering/00_engineering_index.md`](docs/engineering/00_engineering_index.md) | **The ten rules and the definition of done.** Start here. |
| [`CLAUDE.md`](CLAUDE.md) | Locked architecture: schema ownership, service boundaries, the PII rules and *why* each exists |
| [`docs/deployment/DOCKER.md`](docs/deployment/DOCKER.md) | Build, start, migrate, seed, debug |
| [`docs/deployment/08_commit_strategy.md`](docs/deployment/08_commit_strategy.md) | Branch names, commit style, PR expectations |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) → [`docs/TODO.md`](docs/TODO.md) | What exists, and what is already queued |
| [`docs/README.md`](docs/README.md) | The index of the whole specification tree |

If you are proposing something substantial, **open an issue first**. A design that conflicts with a
locked decision in `CLAUDE.md` costs you a rewrite, and those decisions carry their reasons — read
the reason before arguing with the rule.

---

## Ground rules

### 1. Build and run only with Docker

Never `pip install`, `npm run build`, `uvicorn`, `redis-server`, or run a migration natively to build
or serve. Host CLIs are for reading and inspection only. Native runs cause port, version and schema
drift that then shows up as a mystery bug for someone else. Commands:
[`docs/deployment/DOCKER.md`](docs/deployment/DOCKER.md).

### 2. Never work on `main`

`main` is an integration target, reached by pull request. Branch as
`feat/…`, `fix/…`, `chore/…` or `docs/…`
([`08_commit_strategy.md`](docs/deployment/08_commit_strategy.md) §Branching Rules).

### 3. Tests ship in the same commit as the code

Not a follow-up commit, not a follow-up PR. Which level a test belongs at, which markers to use, and
what CI runs: [`docs/engineering/04_testing.md`](docs/engineering/04_testing.md). A test that pins an
architectural rule is as valuable as the rule.

### 4. Never silence a test or a lint

If you genuinely must defer something — downgrade a rule, skip a test, scope a finding out — it is
logged in **two** places in the **same commit**: a follow-up doc under
`docs/sprints/<sprint>/followups/<slug>.md`, and a pointer row in
[`docs/TODO.md`](docs/TODO.md) under 🔵 TECH DEBT. An unlogged deferral is treated as a defect, not a
deferral. The rule and its rationale: [`docs/sprints/README.md`](docs/sprints/README.md).

### 5. Never write a documentation claim you have not verified

If the code does not do it yet, the doc says `⚠ Not built`. This project has been bitten repeatedly
by confident documentation that was false for months — including a README that advertised a service
which never existed. When you amend a rule, move its *reason* with it; a rule without its reason
decays into cargo cult.

### 6. Respect the PII boundary

No complainant PII in `ticketing.*` — not as a column, not as a cache, not in a log line. Ticketing
cannot decrypt and must not learn how. Complainant PII is fetched on demand from the authenticated,
audited grievance endpoint. This is pinned by `tests/ticketing/test_pii_boundary.py` and
`tests/ticketing/test_boundary_policy.py`; if your change makes one of those fail, the change is
wrong, not the test.

### 7. Schema changes go through the owning Alembic stream

Three streams, three schemas, never overlapping: `ticketing/migrations/` → `ticketing.*`,
`migrations/public/` → `public.*`, `ops/migrations/` → `ops.*`.
See [`docs/deployment/07_migrations_policy.md`](docs/deployment/07_migrations_policy.md).

### 8. Every source file carries an SPDX header

`SPDX-License-Identifier: Apache-2.0`, added by `scripts/ops/add_spdx_headers.py` (idempotent; run
it, do not hand-edit). `tests/repo/test_spdx_headers.py` fails the build if a file drifts out of
coverage. By contributing, you agree your contribution is licensed under Apache-2.0 — see
[`LICENSE`](LICENSE) and the pending-ownership note in [`NOTICE`](NOTICE).

### 9. User-facing strings go through the copy guide

Every on-screen word is governed by
[`docs/ticketing_system/ui/05_ui_copy_style.md`](docs/ticketing_system/ui/05_ui_copy_style.md) and its
canonical vocabulary. Officers use this under time pressure, in a second language; wording is not a
matter of taste here.

---

## Working on the sensitive paths

Some areas need more care than a normal review, and it is fair to say so up front:

- **SEAH / sensitive workflows.** Access is cast-based: administrators configure these workflows but
  must never be able to read the cases. If your change touches queue filtering, role resolution, or
  ticket visibility, say so explicitly in the PR description so it gets reviewed for isolation, not
  just for correctness. Specs: [`docs/seah/`](docs/seah/).
- **Anything that sends data to a model provider.** Grievance narratives go to a third-party LLM
  today. Do not add a call site without reading
  [`docs/deployment/11_llm_pipeline_policy.md`](docs/deployment/11_llm_pipeline_policy.md) and
  [`docs/dpg/privacy-assessment.md`](docs/dpg/privacy-assessment.md).
- **Logging.** Do not log grievance text, contact fields, or model inputs and outputs. Several
  existing leaks are known and tracked; please do not add more.

---

## Submitting a change

1. Branch from `main` (or the current integration branch, if you are working alongside a sprint).
2. Build and run in Docker; run the tests in the container.
3. Commit in small logical units, with intention-revealing messages
   (`feat: …`, `fix: …`, `chore: …`, `docs: …`).
4. Update the live spec, `docs/PROGRESS.md`, and `docs/TODO.md` as the change requires — this is part
   of the definition of done, not an optional extra.
5. Open a pull request describing **what** changed, **why**, **how you tested it** (commands and
   results, not "tested locally"), and the **risks or rollback** if relevant.

CI runs backend tests, UI checks, webchat checks, a documentation link check, and the repository
policy tests (`tests/repo/`). A PR merges when review passes and CI is green **without** anything
deselected.

---

## Reporting bugs and requesting features

Use the issue templates in [`.github/ISSUE_TEMPLATE/`](.github/ISSUE_TEMPLATE/).

**Security vulnerabilities do not go in an issue.** This platform holds SEAH disclosures; a public
issue describing a data-exposure path is a map for anyone who wants that data. Use the private
channel in [`SECURITY.md`](SECURITY.md).

Never paste real grievance data, complainant contact details, or production credentials into an
issue, a pull request, or a test fixture. Invent an example.

---

## Community

Participation is governed by [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

## Roadmap

The current programme of work is the DPG compliance and LLM-independence sprint plan:
[`docs/sprints/2026-08-llm/README.md`](docs/sprints/2026-08-llm/README.md), with per-ticket status in
its [`PROGRESS.md`](docs/sprints/2026-08-llm/PROGRESS.md). Longer-range items and tracked technical
debt are in [`docs/TODO.md`](docs/TODO.md). Completed work is summarised in
[`docs/sprints/README.md`](docs/sprints/README.md).
