# Database Migration Policy

## Scope

This project follows a Docker-first runtime and Alembic-first migration workflow.

## Runtime Secrets Baseline

- `DB_ENCRYPTION_KEY` is required for encryption-enabled paths and must be provided via
  environment/secret management (for local Docker: `env.local`; for deployed environments: secret store or deployment env vars).
- Do not hardcode encryption keys in source files or migration scripts.

## Rules

1. **All forward schema changes for ticketing must use Alembic**
   - Config: `ticketing/migrations/alembic.ini`
   - Command: `python -m alembic -c ticketing/migrations/alembic.ini upgrade head`

2. **Do not add ad-hoc schema mutation scripts** under `scripts/database/`
   - No new one-off `CREATE/ALTER/DROP` scripts for production schema evolution.
   - Existing legacy scripts are deprecated/removed as part of cleanup.

3. **Seed/data-loading scripts are allowed** when they are:
   - data-only (not schema-changing),
   - idempotent or documented for one-time use,
   - clearly environment-scoped.

4. **SEAH schema transition note**
   - SEAH tables currently have bootstrap/runtime creation paths.
   - Any *new* SEAH schema evolution should move to formal migrations.

## Review Checklist for PRs

- `alembic heads` returns exactly one head.
- Migration includes clear `down_revision`.
- No new schema-changing script added under `scripts/database/`.
- Upgrade path validated on both host DB and Docker DB targets where applicable.
