# Database Migration Policy

## Scope

This project follows a Docker-first runtime. **Schema changes must be traceable in git** so every worktree and branch can see what ran, in what order, against which part of the database.

There are **two migration streams** on the same Postgres instance (`grievance_db` by default). They must **never** both own the same table.

---

## Two streams (LOCKED)

| Stream               | Schema                                                                 | Tooling                                                                                                                                                                                                                                                                                          | Traceability                                                                                                                   |
| -------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| **Ticketing**        | `ticketing.*`                                                          | **Alembic only** — `ticketing/migrations/alembic.ini`                                                                                                                                                                                                                                            | One linear revision chain in git; use this from **any** worktree (including Claude-only trees) when changing ticketing tables. |
| **Chatbot / public** | `public.*` (e.g. `grievances`, `complainants`, `complainants_seah`, …) | **Alembic** — `migrations/public/alembic.ini` (version table `alembic_version_public`). **Not** the ticketing Alembic project. Some tables may still be **created** on first use by app code (`CREATE TABLE IF NOT EXISTS`); **evolve** them with new files under `migrations/public/versions/`. | Linear revisions in git; same traceability model as ticketing, separate version chain.                                         |

**Principle:** Where Alembic exists for a schema, **always** use it for forward DDL there — better history across worktrees than ad-hoc SQL or silent `ALTER` in app code.

**Ticketing worktrees (e.g. Claude on ticketing):** use **only** `ticketing/migrations` for ticketing DDL. Do not put `public.*` changes in those migration files.

---

## Runtime Secrets Baseline

- `DB_ENCRYPTION_KEY` is required for encryption-enabled paths and must be provided via
  environment/secret management (for local Docker: `env.local`; for deployed environments: secret store or deployment env vars).
- Do not hardcode encryption keys in source files or migration scripts.

---

## Rules

1. **All forward schema changes for `ticketing.*` must use Alembic**
   - Config: `ticketing/migrations/alembic.ini`
   - Command: `python -m alembic -c ticketing/migrations/alembic.ini upgrade head`
   - Commit the generated revision with the feature PR so other worktrees replay the same history.

2. **Do not add ad-hoc schema mutation scripts** under `scripts/database/` for **production evolution of `ticketing.*`**
   - No new one-off `CREATE/ALTER/DROP` scripts for ticketing tables.
   - Existing legacy scripts are deprecated/removed as part of cleanup.
   - **Exception (public only):** prefer `migrations/public` revisions; a rare **documented** one-off SQL is only for emergencies and must be called out in the PR.

3. **Seed/data-loading scripts are allowed** when they are:
   - data-only (not schema-changing),
   - idempotent or documented for one-time use,
   - clearly environment-scoped.

4. **Public / SEAH (`public.*`) — use `migrations/public`**
   - **Forward DDL** (new columns, indexes, new `public` tables you want versioned): add a revision under `migrations/public/versions/`, then `upgrade head`. Use the template header: only `public.*`, never `ticketing.*`.
   - **Connection:** `env.py` reads `POSTGRES_*` via `backend.config.constants.DB_CONFIG` (same as the action server / local tools). In Docker, run e.g. `make migrate_public` or:  
     `docker compose run --rm --no-deps backend python -m alembic -c migrations/public/alembic.ini upgrade head`
   - **Bootstrap vs migrate:** Creating a table the first time may still live in Python (`_ensure_seah_tables`, `base_manager`, …). Once the table exists, **prefer Alembic** for structural changes so other worktrees apply the same `ALTER`/`CREATE INDEX` from git.
   - **Brownfield / existing DBs:** If the database predates `migrations/public`, either run `upgrade head` (applies only what is missing, e.g. `ADD COLUMN IF NOT EXISTS`) or, if the schema already matches all revisions, **`stamp head`** once:  
     `python -m alembic -c migrations/public/alembic.ini stamp pub001_seah_reporter_category`  
     (revision id unchanged; migration file is `pub001_seah_intake_public_tables.py`.)
     (Use the revision id from `alembic history` / `heads`.)
   - **Known brownfield mismatch (task_statuses):** Some older public schemas have `task_statuses.task_status_name` instead of the baseline migration's expected `status_name`. In that case, replaying `pub000_public_core_baseline` can fail during seed inserts. Treat this as a brownfield DB and follow the safe path:
     1. Confirm `complainants_seah`/`grievances_seah` already exist.
     2. `python -m alembic -c migrations/public/alembic.ini stamp pub001_seah_reporter_category`
     3. `python -m alembic -c migrations/public/alembic.ini upgrade head` (applies `pub002_contact_info_and_normalized_location`)
     4. Verify `SELECT version_num FROM alembic_version_public;` returns `pub002_contact_info_and_normalized_location`.

5. **Integration / multiple worktrees**
   - After pulling a branch, run **both** streams when relevant: `make migrate_all`, or ticketing + public commands separately.
   - Use **isolated DB volumes per worktree** where possible (see `CLAUDE.md`) to avoid revision collisions.

6. **Migration seed prerequisites must live in the same revision**
   - If a migration inserts rows that reference FK parents (for example, linking projects to organizations), the migration must also ensure the required parent rows exist first.
   - Use idempotent upserts (`INSERT ... ON CONFLICT DO NOTHING/UPDATE`) inside that revision so `upgrade head` works on fresh databases without manual pre-seeding.
   - Do not rely on external/manual SQL steps for required reference rows.

---

## Review Checklist for PRs

- `python -m alembic -c ticketing/migrations/alembic.ini heads` returns exactly one head (ticketing stream).
- `python -m alembic -c migrations/public/alembic.ini heads` returns exactly one head (public stream).
- Ticketing migration files include clear `down_revision` and the standard header: only `ticketing.*`, never `public.*`.
- Public migration files include the standard header: only `public.*`, never `ticketing.*`.
- No new schema-changing script added under `scripts/database/` for ticketing.
- If the PR changes **`public.*`** schema: include a new revision under `migrations/public/versions/` (or document why not, e.g. bootstrap-only with follow-up migration).
- Migrations that seed FK-linked rows are self-contained and idempotent (no manual pre-seed dependency).
- Upgrade path validated on both host DB and Docker DB targets where applicable.

## May5 SEAH contact/location rollout (public stream)

- Apply order:
  1. `python -m alembic -c ticketing/migrations/alembic.ini upgrade head`
  2. `python -m alembic -c migrations/public/alembic.ini upgrade head`
- New public revision for this rollout: `pub002_contact_info_and_normalized_location`.
- Rollback (public only): `python -m alembic -c migrations/public/alembic.ini downgrade pub001_seah_reporter_category`.
