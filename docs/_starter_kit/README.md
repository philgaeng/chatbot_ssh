# Starter kit — engineering standards for a new project

**What this is:** a portable, project-agnostic skeleton of the standards in [`../engineering/`](../engineering/) and [`../ticketing_system/ui/`](../ticketing_system/ui/), stripped of anything specific to this codebase. Copy it into a new repo and fill in the blanks.

**Why it exists:** the expensive part of these documents is not the writing — it is the *decisions* and the *reasons*. Both transfer between projects; the file paths and colour values don't. This kit keeps the transferable part.

**Who it is for:** a human engineer setting up a project, and the AI agents that will then build it. Every rule is written so that an agent reading it alone can comply.

---

## What's in it

```
_starter_kit/
├── README.md                 ← you are here: how to adopt, in 90 minutes
├── CLAUDE.template.md        ← the root agent file: locked architecture + entry points
├── engineering/
│   ├── 00_index.template.md              Map, the ten rules, definition of done
│   ├── 01_database.template.md           Schema ownership, migrations, naming, transactions
│   ├── 02_services.template.md           The service-layer architecture and its contracts
│   ├── 03_api_layer.template.md          HTTP contracts, authz, errors, pagination
│   ├── 04_testing.template.md            Levels, what CI enforces, pinning tests
│   ├── 05_frontend.template.md           App structure, data access, errors, a11y
│   └── 06_documentation_lifecycle.template.md   Doc tiers, promotion, versioning
└── ui/
    ├── 01_design_system.template.md      Palette, contrast, icons, tokens, components
    └── 02_copy_and_tone.template.md      Who you write for, voice, canonical vocabulary
```

---

## How to adopt (about 90 minutes)

1. **Copy** `engineering/` and `ui/` into the new repo's `docs/`, and `CLAUDE.template.md` to the repo root as `CLAUDE.md`. Drop `.template` from every filename.
2. **Fill the placeholders.** Two kinds:
   - `‹angle brackets›` — a value to substitute (a path, a name, a number).
   - **`FILL:`** callouts — a **decision** to make. Each one names the options and their trade-off. Do not delete a callout by choosing silently; write the choice down *with its reason*.
3. **Delete what doesn't apply.** No frontend? Delete `05` and `ui/`. That is better than leaving a document nobody maintains.
4. **Start the two UI documents on day one, before the first screen.** They are cheap to write and brutally expensive to retrofit — renaming a concept across sixty screens is a week nobody budgets.
5. **Wire the entry points** so agents actually find them: the root `CLAUDE.md` table, `AGENTS.md`, and `docs/README.md` all point at `docs/engineering/00_index.md`.
6. **Add the enforcement.** A rule with no gate survives about two sprints. Minimum viable set: CI runs the tests with nothing deselected, a linter, a type-checker, and a relative-link check over `docs/`.

---

## The ten rules that transfer to any project

The specifics change; these don't. They are reproduced in `engineering/00_index.template.md` for the new repo.

1. **One documented way to build and run.** Containerized, one command. "Works on my machine" is a schema drift waiting to happen.
2. **Every schema change is a migration**, in a versioned, linear, replayable-from-empty stream. One stream per schema owner; never two owners for one table.
3. **Entrypoints hold no logic.** HTTP handler, queue worker, and CLI each parse input, call one function, shape output. Anything else is unreachable from the other two.
4. **The caller owns the transaction.** Business functions take a session and don't commit; the entrypoint commits once.
5. **Authorization is declared, not scattered.** On the route, in the signature, visible to a test. Never an `if` in the middle of a handler.
6. **Name the data that must not leak, and pin the boundary with a test.** PII, secrets, tenant isolation — whichever applies. A boundary nobody tests is a boundary that has already been crossed.
7. **A rule without its reason decays into cargo cult.** When you write, move, or amend a rule, its *why* travels with it — otherwise it is obeyed pointlessly or dropped silently.
8. **Never silence a test or a lint.** A deferral not logged in a tracked follow-up, in the same commit, is a defect, not a deferral.
9. **Never write a doc claim you have not verified.** If the code doesn't do it yet, say so inline. A confident false line is trusted, built upon, and discovered only when something breaks.
10. **One word per concept, everywhere.** Pick the word in `ui/02` and use it in the UI, the code, the schema, and the docs. Synonyms are how two teams build two models of the same thing.

---

## The three ideas worth understanding before you fill anything in

### 1. Thin entrypoints over a fat service layer

Three named patterns compose into one architecture:

| Layer | Pattern | Rule it gives you |
|---|---|---|
| Route / worker / CLI | **Humble Object** (Meszaros) | The hard-to-test thing holds no logic worth testing |
| The logic | **Service Layer** (Fowler, *PoEAA*) | One plain function per use case; framework-free; session in, typed data out |
| Between services | **Shared Kernel** (Evans, *DDD*) | Generic code is shared; *domain* logic crosses only over a documented contract |

> Each service keeps only its own orchestration; everything else is a call into a shared, testable function.

**Why:** every use case ends up with at least four callers — an HTTP route, a background job, a script, and a test. Logic in a route is reachable only by HTTP, so the job re-implements it, and the two silently disagree.

### 2. The branch is the version of the documentation

Documentation lives in the repo, changes in the same pull request as the code it describes, and merges with it. Therefore `main`'s docs describe production, the staging branch's docs describe staging, and a feature branch's docs describe that branch. No version numbers in documents, no parallel "as-built vs target" pair — git already does this, exactly and for free.

The corollary that surprises people: **never edit the shared branch's spec ahead of the code.** If the work slips or is dropped, the shared branch now describes something that does not exist, and everyone builds against fiction. Full model in `engineering/06_documentation_lifecycle.template.md` §3a.

### 3. Promote documentation early, and mark honestly what is unverified

Update the specification when the code merges — not after end-to-end testing. Gating on E2E sounds safer and isn't: E2E never runs for config, permissions, admin screens, or migrations, so those would never be documented at all; and the gap between merge and E2E is exactly where staleness is born.

Safety comes from **markers, not gates**: `⏳ Changing`, `⚠ Not verified end-to-end`, `⚠ Partially built`, `⚠ Deviates from spec`. E2E then clears the marker and gates the *release* — a separate decision from documenting.

---

## Adapting the kit

- **Different language or stack?** Keep documents 01, 03, 04, 06 nearly as-is — they are about boundaries, not syntax. Rewrite 02 and 05 for your stack, keeping the *shape*: layer responsibilities, function contracts, error strategy, known-deviations table.
- **Smaller project?** Merge 01–03 into one `engineering/01_backend.md`. Keep 04 and 06 separate — testing and documentation discipline are what erode first.
- **Adding a standard later?** Only when a rule is cross-cutting *and* repeatedly re-litigated. A rule that applies to one feature belongs in that feature's spec.
- **Every standard keeps a "Known deviations — do not extend" table** with a command that finds them. An undocumented deviation reads to the next agent as permission.
