# Agent Instructions — Refactor Work (Common)

Use this file for any refactor-related task under `docs/Refactor specs/`.

This is the shared baseline for all agents and chat sessions working on refactor planning or implementation support.

---

## 1. Read first (mandatory)

1. [`../COMMIT_STRATEGY.md`](../COMMIT_STRATEGY.md)
2. Relevant spec in this folder (for example `March 5/*` or `April20_seah/*`)
3. [`../ARCHITECTURE.md`](../ARCHITECTURE.md)
4. [`../BACKEND.md`](../BACKEND.md)

If there is a conflict between an old spec and current architecture docs, call it out explicitly and ask for direction.

---

## 2. Branch and commit workflow

- Never do feature/refactor work directly on `main`.
- Create a focused branch (`feat/*`, `fix/*`, `chore/*`, `docs/*`).
- Keep commits small and intent-focused.
- Validate behavior in Docker before opening/merging PR when feasible.
- Merge to `main` only after review and green checks.

See [`../COMMIT_STRATEGY.md`](../COMMIT_STRATEGY.md) for full command flow.

---

## 3. Refactor execution principles

1. Preserve behavior unless the spec explicitly changes behavior.
2. Prefer incremental changes over large rewrites.
3. Keep interfaces stable when possible; if not, document migration impact.
4. Add or update tests alongside behavior-impacting changes.
5. Avoid hidden coupling: call out assumptions and cross-module dependencies.

---

## 4. Safety constraints

- Do not commit secrets, credentials, or local environment files.
- Do not force-push to `main`.
- Do not revert unrelated local changes you did not create.
- If unexpected repository changes appear during work, pause and ask the human how to proceed.

---

## 5. Expected delivery format

When completing a refactor task, include:

1. Files changed.
2. What changed and why.
3. Test/validation commands run (prefer Docker path).
4. Any follow-up required by the human.

If placeholders are introduced, label them as `REPLACE_ME`.

---

## 6. Scope notes

- `March 5/` and `April20_seah/` may contain historical planning docs. Treat them as guidance, not guaranteed source of truth.
- Use architecture and backend docs to confirm current system behavior before implementing breaking changes.

