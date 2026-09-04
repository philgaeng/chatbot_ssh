# Engineering standards — index

**Status:** authoritative (2026-08-03). This folder is the **single source for _how_ we build**.
**Relationship to the rest of the tree:** `docs/<domain>/` says **what** we build (product specs, as-built behaviour). This folder says **how** — the rules any change must satisfy regardless of feature. [`CLAUDE.md`](../../CLAUDE.md) holds the **locked architecture decisions** (schema ownership, service boundaries, PII rules); this folder holds the **craft rules** that follow from them.
**Audience:** a human engineer joining the project, and every AI agent that touches the codebase. Written to be read start-to-finish in about 40 minutes.

> **The reading order for any code change:** [`../PROGRESS.md`](../PROGRESS.md) (what exists) → [`../TODO.md`](../TODO.md) (what's next) → **the standard for the layer you're touching** (below) → the domain spec for the feature.

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

Layer-specific standards that live elsewhere because they were written first and are heavily cross-linked:

| Standard | Home | Covers |
|---|---|---|
| **Visual design system** | [`../ticketing_system/ui/02_design_system.md`](../ticketing_system/ui/02_design_system.md) | palette, WCAG floors, icons, tokens, badges |
| **UI copy & plain language** | [`../ticketing_system/ui/05_ui_copy_style.md`](../ticketing_system/ui/05_ui_copy_style.md) | every user-facing string; canonical vocabulary |
| **Migration policy (long form)** | [`../deployment/07_migrations_policy.md`](../deployment/07_migrations_policy.md) | stream ownership, brownfield recovery, runbook |
| **Commit & branch strategy** | [`../deployment/08_commit_strategy.md`](../deployment/08_commit_strategy.md) | branches, staging deploys |
| **Docker runbook** | [`../deployment/DOCKER.md`](../deployment/DOCKER.md) | build, up, migrate, seed, debug |

---

## The ten rules, on one page

If you read nothing else, these are the rules that get violated most and cost most.

1. **Docker only.** Never `pip install`, `npm run build`, `uvicorn`, `redis-server`, or run a migration natively to build or serve. Host CLIs are for reading. → [`DOCKER.md`](../deployment/DOCKER.md)
2. **Every schema change is an Alembic revision**, in the stream that owns the schema. Three streams, never overlapping: `ticketing/migrations`, `migrations/public`, `ops/migrations`. → [01](01_database.md)
3. **Entrypoints hold no logic.** A router, a Celery task, and a CLI script all do the same three things: parse input, call one service function, shape the response. → [02](02_python_services.md)
4. **The caller owns the transaction.** Service functions take `db: Session` and never `commit()`. → [02](02_python_services.md#4-transactions)
5. **Authorization is a dependency, not an `if`.** It is declared on the route, and it is tested. → [03](03_api_layer.md#4-authorization)
6. **No complainant PII in `ticketing.*`**, ever, in any form — column, cache, or log. Ticketing cannot decrypt and must not learn how. → [`CLAUDE.md`](../../CLAUDE.md) data rules, pinned by `tests/ticketing/test_pii_boundary.py`
7. **A rule without its reason decays into cargo cult.** When you write, amend, or move a rule, move its *why* with it. → [06](06_documentation_lifecycle.md#5-how-to-write-a-rule)
8. **Never silence a test or a lint.** A deferral that is not logged in `sprints/<sprint>/followups/` **and** `TODO.md` in the same commit is a defect, not a deferral.
9. **Never write a doc claim you have not verified.** If the code doesn't do it yet, the spec says `⚠ Not built`. → [06](06_documentation_lifecycle.md#4-honesty-markers)
10. **Every user-facing string** goes through the copy guide and the canonical vocabulary. → [`ui/05`](../ticketing_system/ui/05_ui_copy_style.md)

---

## What "done" means

A ticket is done when **all** of these are true. This list is the shared definition used by every standard in this folder.

- [ ] Code merged on a feature branch (never `main`) — [`08_commit_strategy.md`](../deployment/08_commit_strategy.md)
- [ ] Migrations, if any, in the right stream and replayable from empty — [01](01_database.md)
- [ ] Tests written at the right level, and CI is green **without** deselecting anything — [04](04_testing.md)
- [ ] The **live spec** reflects the new behaviour, with an honest verification marker — [06](06_documentation_lifecycle.md)
- [ ] Every deferral logged in `followups/` + `TODO.md`, same commit
- [ ] `PROGRESS.md` updated

---

## How to extend this folder

Add a standard when a rule is **cross-cutting** (applies to many features) and **repeatedly re-litigated**. Do not add one for a single feature — that belongs in the domain spec. Keep the house shape:

1. A **status header** (`**Status:**` + date + what it supersedes).
2. **Rules as numbered imperatives**, each with a one-line *why*.
3. A **"Known deviations — do not extend"** section listing where the codebase disagrees with the standard, with a grep to find them. An undocumented deviation reads as permission.
4. **Links to the pinning test**, if the rule has one. A rule nobody enforces is a wish.
