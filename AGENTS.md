# GRM Ticketing — Agent Instructions

**Read these three files before any code decision:**

| File | Contains |
|------|----------|
| `docs/claude-tickets/PROGRESS.md` | Current build status, demo DB state, deviations from spec, commit log, integration stubs |
| `docs/claude-tickets/TODO.md` | Open gaps to fix, post-demo features, tech debt |
| `docs/claude-tickets/DOCKER.md` | How to build, start, migrate, seed, and debug the containers |
| `CLAUDE.md` | Locked architecture decisions, hard boundaries, full spec |

Read `PROGRESS.md` first (what was *actually built*), then `TODO.md` (what's next), then `CLAUDE.md` (the rules).
Consult `DOCKER.md` any time you need to build or restart containers.

## Model selection

Choose the model by **difficulty and blast radius, not diff size**:

- **Opus (high reasoning effort)** — security-critical work, concurrency/transaction correctness, large behavior-preserving refactors, and any edit to a live complainant/SEAH channel. A four-line change to the SEAH intake is still Opus.
- **Sonnet (medium effort)** — mechanical config, CI/YAML, UI/error-state plumbing, and test scaffolding driven by an unambiguous spec.
- **Haiku** — trivial doc/text edits only; not for feature or fix workstreams.

Each sprint records a per-ticket model recommendation in its `agents/README.md` "Model selection" table, and each runbook header carries a `**Model:**` field. When in doubt on a PII/security/concurrency touchpoint, prefer Opus.
