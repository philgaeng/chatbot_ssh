# Engineering standards — index

**Status:** authoritative (2026-08-03). This folder is the **single source for _how_ we build**.
**Last updated:** 2026-09-06 — **reference packs** added (a folder and one entry point, never a file list), and an **eleventh rule**: work is classified before it starts. The reading order now passes through [`07_work_items.md`](07_work_items.md). Earlier: `07_work_items.md` added; the reading order and rule 8 point at [`../SPINE.md`](../SPINE.md) rather than the retired `TODO.md`.
**Relationship to the rest of the tree:** `docs/<domain>/` says **what** we build (product specs, as-built behaviour). This folder says **how** — the rules any change must satisfy regardless of feature. [`CLAUDE.md`](../../CLAUDE.md) holds the **locked architecture decisions** (schema ownership, service boundaries, PII rules); this folder holds the **craft rules** that follow from them.
**Audience:** a human engineer joining the project, and every AI agent that touches the codebase. Written to be read start-to-finish in about 40 minutes.

> **The reading order for any code change:** [`../PROGRESS.md`](../PROGRESS.md) (what exists) → [`../SPINE.md`](../SPINE.md) (what's next) → [`07_work_items.md`](07_work_items.md) (**what kind of work this is, and which gates it fires** — before you start, not at merge) → **the standard for the layer you're touching** (below) → the domain spec for the feature.
>
> **Then read the pack for the area you are touching** (below). A pack is *a folder and one entry point* — not a list of files.

---

## The standards

| # | Standard | Read before you touch |
|---|---|---|
| [01](01_database.md) | **Database** — Postgres, Alembic, three migration streams, schema ownership, naming, transactions, seeds | any `models/`, `migrations/`, or SQL |
| [02](02_python_services.md) | **Python & the service layer** — the architecture pattern, module layout, function contracts, errors, config, logging | any `ticketing/services/`, `engine/`, `tasks/`, `backend/services/` |
| [03](03_api_layer.md) | **API layer** — FastAPI routers, Pydantic v2 schemas, auth dependencies, status codes, errors, pagination | any `api/routers/`, `api/schemas/` |
| [04](04_testing.md) | **Testing** — the pyramid, markers, fixtures, pinning tests, what CI runs, definition of done | any test, and any change that needs one (all of them) |
| [05](05_frontend.md) | **Frontend** — Next.js App Router, data access, state, errors, i18n, accessibility | any `channels/ticketing-ui/` |
| [06](06_documentation_lifecycle.md) | **Documentation lifecycle** — live specs vs reviews vs sprints vs archive, and **when a sprint spec is promoted** | any doc, and the end of every ticket |
| [07](07_work_items.md) | **Work items** — how work is born, classified and gated: five kinds, a four-question triage test, nine gates, six derived profiles, definition of ready | any new piece of work, before it starts |

Layer-specific standards that live elsewhere because they were written first and are heavily cross-linked:

| Standard | Home | Covers |
|---|---|---|
| **Visual design system** | [`../ticketing_system/ui/02_design_system.md`](../ticketing_system/ui/02_design_system.md) | palette, WCAG floors, icons, tokens, badges |
| **UI copy & plain language** | [`../ticketing_system/ui/05_ui_copy_style.md`](../ticketing_system/ui/05_ui_copy_style.md) | every user-facing string; canonical vocabulary |
| **Migration policy (long form)** | [`../deployment/07_migrations_policy.md`](../deployment/07_migrations_policy.md) | stream ownership, brownfield recovery, runbook |
| **Commit & branch strategy** | [`../deployment/08_commit_strategy.md`](../deployment/08_commit_strategy.md) | branches, staging deploys |
| **Docker runbook** | [`../deployment/DOCKER.md`](../deployment/DOCKER.md) | build, up, migrate, seed, debug |

---

## Reference packs — what to read for a given area

**A pack names a folder and one entry point. It never lists files.** *Why: a file list is wrong the
week after it is written — files get added, split and renamed, and a stale list quietly sends people
to the wrong place while looking authoritative. A folder plus an entry point survives a growing tree,
because keeping the entry point current is already somebody's job.*

Read the pack **in addition to** the layer standard, not instead of it.

| Pack | Read from | Entry point | Governs |
|---|---|---|---|
| **Ticketing** | [`../ticketing_system/`](../ticketing_system/) | [`00_ticketing_decisions.md`](../ticketing_system/00_ticketing_decisions.md) | `ticketing/` — schema, workflow engine, queue, resolution |
| **Officer portal** | [`../ticketing_system/ui/`](../ticketing_system/ui/) | [`01_ui_spec.md`](../ticketing_system/ui/01_ui_spec.md) | `channels/ticketing-ui/` — read with [05](05_frontend.md), [`ui/02`](../ticketing_system/ui/02_design_system.md) and [`ui/05`](../ticketing_system/ui/05_ui_copy_style.md) |
| **Chatbot intake** | [`../rest_chatbot/`](../rest_chatbot/) | [`00_rest_chatbot_index.md`](../rest_chatbot/00_rest_chatbot_index.md) | `backend/actions/`, `backend/orchestrator/`, `channels/` |
| **Sensitive path** | [`../seah/`](../seah/) | [`02_vault_privacy_and_reveal.md`](../seah/02_vault_privacy_and_reveal.md) | anything touching PII, SEAH visibility, or the complainant channel — **plus the data rules in [`CLAUDE.md`](../../CLAUDE.md)**. ⭐ Entering this pack means the work is `+SENSITIVE` ([07](07_work_items.md) §4.2) |
| **Deploy & ops** | [`../deployment/`](../deployment/) | [`DOCKER.md`](../deployment/DOCKER.md) | `docker-compose*.yml`, `Makefile`, `deployment/nginx/`, `ops/` |
| **Compliance (DPG)** | [`../dpg/`](../dpg/) | [`00_compliance_status.md`](../dpg/00_compliance_status.md) | licensing, model independence, the evidence pack an assessor reads |

⚠ **The Sensitive-path pack is the one that changes how the work is done, not just what you read.**
If your change lands in it, the profile carries `+SENSITIVE`, which selects Opus and requires the
boundary tests to be named in the item before the work starts — mechanically, whatever the diff size.

---

## The eleven rules, on one page

If you read nothing else, these are the rules that get violated most and cost most.

1. **Docker only.** Never `pip install`, `npm run build`, `uvicorn`, `redis-server`, or run a migration natively to build or serve. Host CLIs are for reading. → [`DOCKER.md`](../deployment/DOCKER.md)
2. **Every schema change is an Alembic revision**, in the stream that owns the schema. Three streams, never overlapping: `ticketing/migrations`, `migrations/public`, `ops/migrations`. → [01](01_database.md)
3. **Entrypoints hold no logic.** A router, a Celery task, and a CLI script all do the same three things: parse input, call one service function, shape the response. → [02](02_python_services.md)
4. **The caller owns the transaction.** Service functions take `db: Session` and never `commit()`. → [02](02_python_services.md#4-transactions)
5. **Authorization is a dependency, not an `if`.** It is declared on the route, and it is tested. → [03](03_api_layer.md#4-authorization)
6. **No complainant PII in `ticketing.*`**, ever, in any form — column, cache, or log. Ticketing cannot decrypt and must not learn how. → [`CLAUDE.md`](../../CLAUDE.md) data rules, pinned by `tests/ticketing/test_pii_boundary.py`
7. **A rule without its reason decays into cargo cult.** When you write, amend, or move a rule, move its *why* with it. → [06](06_documentation_lifecycle.md#5-how-to-write-a-rule)
8. **Never silence a test or a lint.** A deferral that is not logged in `sprints/<sprint>/followups/` **and** a `SPINE.md` row in the same commit is a defect, not a deferral.
9. **Never write a doc claim you have not verified.** If the code doesn't do it yet, the spec says `⚠ Not built`. → [06](06_documentation_lifecycle.md#4-honesty-markers)
10. **Every user-facing string** goes through the copy guide and the canonical vocabulary. → [`ui/05`](../ticketing_system/ui/05_ui_copy_style.md)
11. **Work is classified before it starts, not at merge.** Kind and profile are derived at intake from six questions; the **profile** — not judgment at the keyboard — selects the model, the reviewer, the tests and the gates. A `ready` item with no profile is a test failure, not a style point. → [07](07_work_items.md), form: [`../items/TEMPLATE.md`](../items/TEMPLATE.md), pinned by `tests/repo/test_spine.py`

---

## What "done" means

A ticket is done when **all** of these are true. This list is the shared definition used by every standard in this folder.

- [ ] Code merged on a feature branch (never `main`) — [`08_commit_strategy.md`](../deployment/08_commit_strategy.md)
- [ ] Migrations, if any, in the right stream and replayable from empty — [01](01_database.md)
- [ ] Tests written at the right level, and CI is green **without** deselecting anything — [04](04_testing.md)
- [ ] The **live spec** reflects the new behaviour, with an honest verification marker — [06](06_documentation_lifecycle.md)
- [ ] Every deferral logged in `followups/` + `SPINE.md`, same commit
- [ ] `PROGRESS.md` updated

---

## How to extend this folder

Add a standard when a rule is **cross-cutting** (applies to many features) and **repeatedly re-litigated**. Do not add one for a single feature — that belongs in the domain spec. Keep the house shape:

1. A **status header** (`**Status:**` + date + what it supersedes).
2. **Rules as numbered imperatives**, each with a one-line *why*.
3. A **"Known deviations — do not extend"** section listing where the codebase disagrees with the standard, with a grep to find them. An undocumented deviation reads as permission.
4. **Links to the pinning test**, if the rule has one. A rule nobody enforces is a wish.
