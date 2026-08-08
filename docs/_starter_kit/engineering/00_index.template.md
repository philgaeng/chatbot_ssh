# Engineering standards — index

**Status:** ‹authoritative› (‹YYYY-MM-DD›). The **single source for _how_ we build**.
**Relationship to the rest of the tree:** `docs/‹domain›/` says **what** we build. This folder says **how**. The root `CLAUDE.md` holds the **locked architecture decisions**; this folder holds the craft rules that follow from them.
**Audience:** a human engineer joining the project, and every AI agent that touches the codebase.

> **Reading order for any code change:** `‹PROGRESS log›` (what exists) → `‹TODO›` (what's next) → **the standard for the layer you're touching** → the domain spec for the feature.

---

## The standards

| # | Standard | Read before you touch |
|---|---|---|
| [01](01_database.template.md) | **Database** — schema ownership, migrations, naming, transactions, seeds | any model, migration, or query |
| [02](02_services.template.md) | **Services** — the architecture, module layout, function contracts, errors | any business logic |
| [03](03_api_layer.template.md) | **API layer** — contracts, authorization, errors, pagination | any HTTP surface |
| [04](04_testing.template.md) | **Testing** — levels, fixtures, pinning tests, what CI enforces | any test, and any change that needs one |
| [05](05_frontend.template.md) | **Frontend** — structure, data access, state, errors, a11y | any UI code |
| [06](06_documentation_lifecycle.template.md) | **Documentation lifecycle** — tiers, promotion, versioning | any doc, and the end of every task |

**FILL:** add rows for the visual and copy standards once they exist — `‹docs/…/ui/01_design_system.md›` and `‹docs/…/ui/02_copy_and_tone.md›` — plus any runbooks (deployment, migrations, on-call).

---

## The ten rules, on one page

The rules that get violated most and cost most.

1. **One documented way to build and run** — ‹containerized, one command›. Never build or serve from an ad-hoc local install; that is how version and schema drift start.
2. **Every schema change is a migration**, in the stream that owns that schema, replayable from empty. → [01](01_database.template.md)
3. **Entrypoints hold no logic.** A route, a worker, and a CLI each parse input, call one function, shape output. → [02](02_services.template.md)
4. **The caller owns the transaction.** Business functions take a session and never commit. → [02](02_services.template.md)
5. **Authorization is declared on the route, not scattered in handlers — and it is tested.** → [03](03_api_layer.template.md)
6. **FILL: the data boundary that must never be crossed** — ‹PII / secrets / tenant isolation›, stated absolutely, and **pinned by a test**.
7. **A rule without its reason decays into cargo cult.** Move the *why* whenever you move the rule. → [06](06_documentation_lifecycle.template.md)
8. **Never silence a test or a lint.** A deferral not logged in ‹the follow-up doc› **and** ‹the TODO backlog›, same commit, is a defect.
9. **Never write a doc claim you have not verified.** If the code doesn't do it yet, the spec says so. → [06](06_documentation_lifecycle.template.md)
10. **One word per concept**, in the UI, the code, the schema, and the docs. → ‹the copy guide›

---

## What "done" means

The shared definition used by every standard in this folder.

- [ ] Code merged on a feature branch (never directly on the integration branch)
- [ ] Migrations, if any, in the right stream and replayable from empty
- [ ] Tests at the right level; CI green **without** deselecting, downgrading, or suppressing anything
- [ ] The **live spec** reflects the new behaviour, with an honest verification marker
- [ ] Every deferral logged, same commit
- [ ] ‹The build log› updated

---

## How to extend this folder

Add a standard when a rule is **cross-cutting** and **repeatedly re-litigated**. A rule for one feature belongs in that feature's spec. Keep the house shape:

1. A **status header** — date, and what it supersedes.
2. **Numbered imperative rules**, each with a one-line *why*.
3. A **"Known deviations — do not extend"** table with a command that finds them.
4. **A link to the enforcement** — the pinning test or CI gate — or an explicit admission there is none.
