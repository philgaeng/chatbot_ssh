# Claude Handoff — SEAH Privacy Split (Public vs Ticketing Worktrees)

## Purpose

Provide implementation-ready boundaries so ticketing can be developed in a separate worktree while keeping original grievance safety controls authoritative in the public/chatbot domain.

This handoff is aligned with:

- `docs/PRIVACY.md`
- `docs/Refactor specs/May5_seah/05_vault_and_summary_operating_model.md`
- `docs/Refactor specs/May5_seah/06_vault_reveal_audit_and_ui_controls.md`
- `docs/MIGRATIONS_POLICY.md`

## Non-negotiable ownership

### Public/chatbot worktree owns

- `public.*` schema changes (via `migrations/public/alembic.ini`)
- canonical grievance and complainant storage
- vault/original content protection and key policy
- reveal authorization decisioning and authoritative sensitive-access audit

### Ticketing worktree owns

- `ticketing.*` schema changes (via `ticketing/migrations/alembic.ini`)
- officer workflow metadata/events
- derived summary and anomaly detection artifacts
- ticketing UI behavior for summary-first operations and reveal UX

### Forbidden coupling

- No direct SQL joins from `ticketing.*` to `public.*`
- No ticketing storage of raw vault narrative or direct PII fields
- No duplicate reveal policy logic in ticketing that bypasses public API checks

## Required cross-worktree API contracts

### Public/chatbot API (authoritative)

1. Reveal start endpoint (reason required) returning short-lived token.
2. Reveal close endpoint (session closure and duration).
3. Safe grievance view endpoint (masked complainant + policy-safe summary/source fields).
4. Optional policy-safe excerpt endpoint for summary regeneration inputs.

### Ticketing API/UI responsibilities

1. Trigger reveal request with reason codes and context metadata.
2. Render controlled reveal pane (watermark, copy deterrence, timeout).
3. Submit close/expire callbacks and preserve correlation IDs.
4. Keep default officer screens summary-first.

## Suggested delivery sequence

1. Public/chatbot: finalize reveal endpoints + policy checks + immutable audit events.
2. Ticketing: implement summary-first case detail and metadata event schema.
3. Ticketing: add reveal UX wiring to public endpoints.
4. Ticketing: add summary generation pipeline and leakage/coverage blockers.
5. Joint: run end-to-end SEAH access matrix and audit correlation tests.

## Minimum test matrix for Claude

### Public/chatbot tests

- in-scope reveal grant with valid reason
- out-of-scope reveal denial
- token expiry and close lifecycle
- SEAH stricter quota/rate policy behavior
- immutable audit event completeness

### Ticketing tests

- no raw PII/raw narrative in ticketing API payloads by default
- stale summary indicator behavior during async regeneration
- leakage blocker prevents unsafe summary publication
- reveal pane timeout and re-request behavior
- correlation IDs propagated to public reveal API

## Acceptance criteria

Work is complete only when all are true:

1. Officer default journey is fully summary-first.
2. Original-content access is policy-gated in public/chatbot API only.
3. Public and ticketing audit streams can be correlated deterministically.
4. `ticketing.*` remains free of raw grievance narrative and direct complainant PII.
5. Migrations remain in correct stream ownership with no schema crossover.

## Notes for parallel worktrees

- Use separate local DB instances per worktree.
- Avoid cross-branch migration drift by keeping revision streams linear.
- Merge to integration worktree for end-to-end validation before promotion.
