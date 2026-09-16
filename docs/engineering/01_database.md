# Database standard

**Status:** authoritative (2026-08-03). Craft rules for anything that touches Postgres.
**Reads with:** [`CLAUDE.md`](../../CLAUDE.md) "DATABASE ARCHITECTURE (LOCKED)" — the *ownership* decisions — and [`../deployment/07_migrations_policy.md`](../deployment/07_migrations_policy.md) — the *runbook* (commands, brownfield recovery, stamping).
**This doc adds:** the rules that neither of those covers — naming, transactions, indexes, nullability, enums, seeds, and how to review a migration.

---

## 1. Postgres is the default, and the only one

**Rule 1.1 — Postgres for anything durable.** One instance (`grievance_db`), three schemas (`public`, `ticketing`, `ops`). Do not introduce SQLite, MySQL, Mongo, or a document store for new work.
*Why:* one backup path, one migration story, one set of credentials to rotate. The legacy MySQL GRM sync ([`09_grm_integration_service.md`](../services/09_grm_integration_service.md)) is dormant and is not a precedent.

**Rule 1.2 — Redis is a broker and a cache, never a store of record.** Anything that must survive a restart is a Postgres row.

**Rule 1.3 — SQLite in tests is forbidden.** Tests run against real Postgres (see [04 §3](04_testing.md#3-integration-tests-are-not-optional)). Schema-qualified tables, `JSONB`, `gen_random_uuid()`, and partial indexes do not exist in SQLite; a green SQLite suite is a false green.

---

## 2. Three migration streams, never overlapping (LOCKED)

| Stream | Owns | Config | Version table |
|---|---|---|---|
| **Ticketing** | `ticketing.*` | `ticketing/migrations/alembic.ini` | `alembic_version` (in `ticketing`) |
| **Public / chatbot** | `public.*` | `migrations/public/alembic.ini` | `alembic_version_public` |
| **Ops** | `ops.*` + the `ops_app` role/grants | `ops/migrations/alembic.ini` | `alembic_version_ops` |

**Rule 2.1 — Forward DDL always goes through Alembic**, in the stream that owns the schema. No `CREATE`/`ALTER`/`DROP` in application code, service functions, seeds, or `scripts/`.
*Why:* the git history *is* the schema history. Ad-hoc DDL means two developers (or two worktrees) can hold different schemas with no way to tell.

**Rule 2.2 — One revision never touches two schemas.** If a change needs both, it is two revisions in two streams, and the PR says which order they run in.
*Why:* streams have independent version chains and are replayed independently on every environment. A cross-schema revision is unreplayable.

**Rule 2.3 — Every ticketing migration starts with the header:**

```python
# Safe to run: only creates/modifies ticketing.* tables
# Does NOT touch: grievances, complainants, or any existing public.* table
```

**Rule 2.4 — `include_object` + `version_table_schema` must stay scoped.** Ticketing's `env.py` filters to `object.schema == "ticketing"`; ops to `"ops"`. Do not "fix" an autogenerate diff by widening the filter — a widened filter will happily propose dropping every chatbot table.

**Rule 2.5 — Bootstrap-in-code is legacy, not a pattern.** A few `public.*` tables are still first-created by app code (`CREATE TABLE IF NOT EXISTS`). That is grandfathered. Any *structural change* to them goes in `migrations/public/versions/`. New tables are never created in app code.

---

## 3. Writing a migration

**Rule 3.1 — Autogenerate is a draft, not an output.** Always run `alembic revision --autogenerate`, then read every line. Delete what you didn't intend. Autogenerate routinely proposes drops caused by an unimported model or a stale local DB.

**Rule 3.2 — Every revision must be replayable from empty.** The test is not "it worked on my DB". It is:

```bash
make wsl-down-v && make wsl-up && make migrate_all   # from nothing, all three streams
```

CI does exactly this (`.github/workflows/ci.yml`, "Run migrations (public -> ticketing -> ops)"), which is why a revision that only works against your local snapshot fails there and not locally.

**Rule 3.3 — `downgrade()` is written or explicitly refused.** Either implement it, or leave `raise NotImplementedError("forward-only: <reason>")`. A silent `pass` is a lie that will be discovered during an incident.

**Rule 3.4 — Data migrations are separate revisions from DDL.** A revision either changes shape or moves data, never both.
*Why:* shape changes are fast and lock-taking; data moves are slow and restartable. Mixed, a failure halfway leaves you with neither.

**Rule 3.5 — Backfills must be batched and idempotent** if they can touch more than ~10k rows: `UPDATE … WHERE <not yet migrated> LIMIT n` in a loop, safe to re-run.

**Rule 3.6 — Adding a `NOT NULL` column to a populated table is three revisions**, never one: (1) add nullable with a default, (2) backfill, (3) set `NOT NULL`. Doing it in one takes an `ACCESS EXCLUSIVE` lock for the length of the rewrite.

**Rule 3.7 — Index creation on a populated table uses `CREATE INDEX CONCURRENTLY`**, which requires the revision to run outside a transaction:

```python
def upgrade():
    with op.get_context().autocommit_block():
        op.create_index("ix_tickets_status_code", "tickets", ["status_code"],
                        schema="ticketing", postgresql_concurrently=True)
```

### Reviewing a migration — the checklist

- [ ] Header comment present; only the owned schema is touched
- [ ] Diff contains nothing you didn't intend (no surprise `drop_table`, `drop_column`)
- [ ] Replays from empty (`migrate_all` on a fresh volume)
- [ ] `downgrade()` implemented or explicitly refused with a reason
- [ ] No lock-taking rewrite on a populated table without the three-step dance
- [ ] Model and migration agree (run the app; SQLAlchemy fails loudly on a column mismatch)

---

## 4. Schema conventions

**Rule 4.1 — Every ticketing model carries `__table_args__ = {"schema": "ticketing"}`.** No exceptions. A model without it silently lands in `public` and becomes a cross-stream ownership violation.

**Rule 4.2 — No foreign keys from `ticketing.*` into `public.*`.** Cross-schema links are soft `String(64)` refs (`grievance_id`, `complainant_id`). **Pinned by a test.**
*Why:* it preserves the option to extract ticketing to its own database, and keeps the three migration streams independently replayable. It costs nothing — the join is the same either way.

**Rule 4.3 — Foreign keys *within* `ticketing.*` are required**, with an explicit `ondelete`. Never rely on application code to clean up children.

**Rule 4.4 — Naming.**

| Thing | Convention | Example |
|---|---|---|
| Table | plural, `snake_case` | `workflow_steps` |
| Column | `snake_case`, no table prefix | `status_code`, not `ticket_status_code` |
| Primary key | `<singular>_id`, UUID4 | `ticket_id` |
| Foreign key | `<referenced singular>_id` | `workflow_id` |
| Boolean | `is_` / `has_` / `can_` prefix | `is_seah`, `has_attachments` |
| Timestamp | `<verb past>_at` | `created_at`, `resolved_at`, `step_started_at` |
| Soft-delete / lifecycle | `is_active` + `deactivated_at` | — |
| Index | `ix_<table>_<cols>` | `ix_tickets_status_code` |
| Unique constraint | `uq_<table>_<cols>` | `uq_officer_scope_user_project` |
| Check constraint | `ck_<table>_<rule>` | `ck_tickets_priority_valid` |

**Rule 4.5 — Types.**
- IDs: `UUID` (`gen_random_uuid()` server-side, `uuid4()` in Python).
- Timestamps: **always** `TIMESTAMP WITH TIME ZONE`, always stored UTC. A naive timestamp column is a bug — Nepal is UTC+05:45 and the off-by-5h45m only shows up in an SLA breach report.
- Money/measures: `NUMERIC`, never `FLOAT`.
- Free text: `TEXT`. Use `String(n)` only where the length is a real constraint (codes, keys).
- Structured blobs: `JSONB`, never `JSON` — `JSONB` indexes and dedupes keys.

**Rule 4.6 — Enums live in Python, not Postgres.** Store the value as `String`/`TEXT` with a `CHECK` constraint or a lookup table; keep the allowed values in `ticketing/constants/`.
*Why:* `ALTER TYPE … ADD VALUE` cannot run in a transaction and cannot be reversed. Every enum change would otherwise be an outage-shaped migration.

**Rule 4.7 — Default to `NOT NULL`.** Nullable means "this can legitimately be absent, and every reader must handle it". If you can't name the absent case, it isn't nullable.

**Rule 4.8 — Index what you filter, sort, and join on.** In particular: every FK column, every column in a queue filter, and the `(status, created_at)`-shaped pairs behind list endpoints. Do not index speculatively — an unused index is write cost with no read benefit.

---

## 5. Transactions and sessions

**Rule 5.1 — One request, one session, one transaction.** The session comes from the `get_db()` dependency and is closed by it.

**Rule 5.2 — The caller owns the transaction.** Service functions accept `db: Session`, do their work, and **do not `commit()`**. The router (or task, or CLI) commits once, after all the service calls succeed. Full rationale in [02 §4](02_python_services.md#4-transactions).

**Rule 5.3 — Never `commit()` inside a loop** over rows you are mutating. Either one commit at the end, or explicit batches with a stated batch size.

**Rule 5.4 — Concurrent state transitions take a row lock.** Anything that reads-then-writes a ticket's state (assign, escalate, resolve) must `SELECT … FOR UPDATE` the ticket row inside the transaction. Without it two officers acting at once both read `OPEN` and both write.

**Rule 5.5 — No N+1.** Loading a collection and then touching a relation per item is the single most common performance bug here. Use `selectinload()` / `joinedload()`. If you can't tell, log the SQL count in a test.

---

## 6. Reading and writing `public.*` from ticketing

The permitted set is **closed** and lives in [`CLAUDE.md`](../../CLAUDE.md) (data rule 1), **pinned by** `tests/ticketing/test_boundary_policy.py`, which parses that table and fails when it and the code disagree.

**Rule 6.1 — Adding a `public.*` table to ticketing's reach is a decision, not a default.** Edit the CLAUDE.md table *and* the code in the same commit; the test enforces the pair.

**Rule 6.2 — Grievance *state* changes go over HTTP** (`POST /api/grievance/{id}/status`), never SQL. This is a real invariant: the backend owns the state machine and its side effects (notifications, audit).

**Rule 6.3 — Complainant PII is never selected into ticketing.** Not into a column, not into a cache, not into a log line, not into an LLM prompt. Ticketing holds no `DB_ENCRYPTION_KEY` and there is no accessor — **pinned by** `tests/ticketing/test_pii_boundary.py`. Fetch fresh via `GET /api/grievance/{id}`, which returns plaintext because the backend decrypts server-side.

---

## 7. Seeds vs migrations

**Rule 7.1 — A seed is data-only, idempotent, and re-runnable.** Seeds live in `ticketing/seed/` and run as modules (`python -m ticketing.seed.mock_tickets --reset`). They never change shape.

**Rule 7.2 — Reference data that the app requires to function** (statuses, taxonomies, location codes) is seeded, not migrated — so it can be corrected without a revision — but its *absence must fail loudly* at startup rather than silently produce an empty dropdown.

**Rule 7.3 — Demo/mock data is separated from reference data** by module, and demo seeds carry `--reset`. Never ship a demo seed that runs by default in a production entrypoint.

---

## 8. Operations

**Rule 8.1 — All DB commands run in Docker.** `make migrate_all`, `make wsl-seed-full`. Host `psql` is for *reading only*.

**Rule 8.2 — Backups are verified by restore, not by existence.** A backup nobody has restored is a hypothesis. → [`11_health_and_monitoring_service.md`](../services/11_health_and_monitoring_service.md)

**Rule 8.3 — Secrets never appear in a migration, a seed, or a model.** `DB_ENCRYPTION_KEY` is owned solely by `backend`. → [`14_key_and_secret_lifecycle.md`](../deployment/14_key_and_secret_lifecycle.md)

---

## 9. Known deviations — do not extend

| Deviation | Where | Note |
|---|---|---|
| `commit()` inside service functions | 18 call sites in `ticketing/services/` — `grep -rn "\.commit()" ticketing/services/` | Rule 5.2 is the target state. Do not add more; unwind opportunistically when you touch the file. |
| `public.*` tables first created in app code | `_ensure_seah_tables`, `base_manager` | Grandfathered (Rule 2.5). New tables never. |
| Brownfield `task_statuses.task_status_name` mismatch | older public schemas | Recovery procedure in [`07_migrations_policy.md`](../deployment/07_migrations_policy.md). |

---

## 10. Pinning tests

| Rule | Enforced by |
|---|---|
| No FK from `ticketing.*` → `public.*` | `tests/ticketing/test_boundary_policy.py` |
| Closed set of `public.*` tables + which are written | `tests/ticketing/test_boundary_policy.py` (parses the CLAUDE.md table) |
| No complainant PII in `ticketing.*`; no decryption accessor | `tests/ticketing/test_pii_boundary.py` |
| All three streams replay from empty | `.github/workflows/ci.yml` |
| Public schema self-consistency | `scripts/ci/check_public_schema_baseline.sh` |
