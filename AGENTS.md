# GRM Ticketing — Agent Instructions

**Read these files before any code decision:**

| File | Contains |
|------|----------|
| `docs/PROGRESS.md` | Current build status, demo DB state, deviations from spec, commit log, integration stubs |
| `docs/SPINE.md` | **What is next** — the register. Kinds, profiles and gates: `docs/engineering/07_work_items.md` |
| `docs/engineering/00_engineering_index.md` | **How we build** — DB, service layer, API, tests, frontend, doc lifecycle. Binding on every change. |
| `docs/deployment/DOCKER.md` | How to build, start, migrate, seed, and debug the containers |
| `CLAUDE.md` | Locked architecture decisions, hard boundaries, full spec |

Read `PROGRESS.md` first (what was *actually built*), then `SPINE.md` (what's next), then the **engineering standard for the layer you're touching**, then `CLAUDE.md` (the locked architecture).
Consult `DOCKER.md` any time you need to build or restart containers.

> Paths corrected 2026-08-03: the old `docs/claude-tickets/` folder was dissolved — its operational logs moved to the `docs/` root and the Docker runbook to `docs/deployment/`.

## Model selection

Choose the model by **difficulty and blast radius, not diff size**:

- **Opus (high reasoning effort)** — security-critical work, concurrency/transaction correctness, large behavior-preserving refactors, and any edit to a live complainant/SEAH channel. A four-line change to the SEAH intake is still Opus.
- **Sonnet (medium effort)** — mechanical config, CI/YAML, UI/error-state plumbing, and test scaffolding driven by an unambiguous spec.
- **Haiku** — trivial doc/text edits only; not for feature or fix workstreams.

Each sprint records a per-ticket model recommendation in its `agents/README.md` "Model selection" table, and each runbook header carries a `**Model:**` field. When in doubt on a PII/security/concurrency touchpoint, prefer Opus.
