# Database standard

**Status:** ‹authoritative› (‹YYYY-MM-DD›).
**Applies to:** every model, migration, query, and seed.
**Engine: FILL:** ‹PostgreSQL ‹version›› — and say it is the **only** one. Introducing a second store is an architecture decision, not a convenience.

---

## 1. Ownership

**FILL:** the schemas/databases and who owns each. This table is the most important thing in the document — most database pain is an ownership dispute nobody wrote down.

| Schema / database | Owned by | Migration tool + config | Version table |
|---|---|---|---|
| ‹schema› | ‹service› | ‹tool, config path› | ‹table› |

**Rule 1.1 — Exactly one owner per table.** Two migration streams touching one table is unrecoverable without manual surgery.

**Rule 1.2 — One migration never touches two owners' schemas.** If a change needs both, it is two migrations, and the pull request states the run order. Streams are replayed independently on every environment; a cross-schema migration is unreplayable.

**Rule 1.3 — Cross-boundary references are soft** — store the id, no foreign key across an ownership boundary. **FILL:** state whether this applies here and why (extraction optionality, independent replay, separate deploy cadence). If it doesn't apply, say that instead of leaving the rule to be cargo-culted.

**Rule 1.4 — Reads and writes across a boundary are a closed, enumerated set.** List them, and **pin the list with a test** that fails when the list and the code disagree. An unlisted access is how a boundary silently disappears.

**Rule 1.5 — State changes owned by another service go over its API, never by direct write.** That service owns the state machine and its side effects.

**Rule 1.6 — No ‹PII / secrets / tenant-foreign data› in ‹this schema›. FILL** the specific rule, absolutely, and pin it with a test.

---

## 2. Migrations

**Rule 2.1 — All forward schema changes go through the migration tool.** No `CREATE`/`ALTER`/`DROP` in application code, scripts, or seeds. *Why:* the git history **is** the schema history; without it, two developers can hold different schemas with no way to tell.

**Rule 2.2 — Autogenerate is a draft, not an output.** Read every generated line and delete what you did not intend. Autogeneration routinely proposes drops caused by an unimported model or a stale local database.

**Rule 2.3 — Every migration replays from empty.** The test is not "it worked on my database" — it is a fresh volume, all streams, in order. CI must do exactly this.

**Rule 2.4 — `downgrade` is written or explicitly refused** with a stated reason. A silent no-op is a lie discovered during an incident.

**Rule 2.5 — Shape changes and data moves are separate migrations.** Shape changes are fast and lock-taking; data moves are slow and restartable. Mixed, a half-failure leaves neither.

**Rule 2.6 — Backfills are batched and idempotent** above ‹10k› rows.

**Rule 2.7 — Locking operations on populated tables are staged.** Adding a non-nullable column is three migrations: add nullable with default → backfill → enforce. Index creation on a live table uses the concurrent form.

**Rule 2.8 — Every migration file carries a header** stating what it touches and what it does not touch. **FILL** the exact template.

### Review checklist

- [ ] Only the owned schema is touched; header present
- [ ] Nothing unintended in the diff (no surprise drops)
- [ ] Replays from empty
- [ ] `downgrade` implemented or explicitly refused
- [ ] No unstaged lock-taking operation on a populated table
- [ ] Model and migration agree

---

## 3. Schema conventions

**FILL** the table; the point is that it exists and is followed, more than which choice you make.

| Thing | Convention | Example |
|---|---|---|
| Table | ‹plural snake_case› | ‹…› |
| Column | ‹snake_case, no table prefix› | ‹…› |
| Primary key | ‹`<singular>_id`, ‹UUID/bigint›› | ‹…› |
| Foreign key | ‹`<referenced singular>_id`› | ‹…› |
| Boolean | ‹`is_`/`has_`/`can_` prefix› | ‹…› |
| Timestamp | ‹`<verb past>_at`› | ‹…› |
| Index | ‹`ix_<table>_<cols>`› | ‹…› |
| Unique | ‹`uq_<table>_<cols>`› | ‹…› |

**Rule 3.1 — Timestamps are always timezone-aware and stored UTC.** A naive timestamp column is a bug waiting for the first user in another timezone; it surfaces as an off-by-N-hours in a report nobody trusts afterwards.

**Rule 3.2 — Exact numerics for money and measures**, never floating point.

**Rule 3.3 — Enumerations live in application code**, stored as text with a check constraint or a lookup table. *Why:* altering a database enum type is a locking, hard-to-reverse operation, so every value addition becomes outage-shaped.

**Rule 3.4 — Default to `NOT NULL`.** Nullable means "legitimately absent, and every reader handles it". If you cannot name the absent case, it is not nullable.

**Rule 3.5 — Index what you filter, sort, and join on** — every foreign key, and the column pairs behind list endpoints. Do not index speculatively: an unused index is write cost with no read benefit.

---

## 4. Transactions & queries

**Rule 4.1 — One request, one session, one transaction**, opened and closed by the framework boundary.

**Rule 4.2 — The caller owns the transaction.** Business functions receive a session and never commit. *Why:* a handler calling three functions must be able to make all three succeed or all three fail. If the second commits, the third's failure leaves a state no code path intended — and no test catches it, because each function passes alone.

**Rule 4.3 — Read-then-write on shared state takes a row lock.** Without it, two concurrent actors both read the old value and both write.

**Rule 4.4 — No N+1.** Load relations eagerly. This is the most common performance bug in any ORM codebase, and it is invisible until production data volume.

**Rule 4.5 — Never interpolate user input into SQL.** Parameterize; allowlist any user-supplied column or sort name.

**Rule 4.6 — Filter authorization in the query, not after.** A post-filter still leaks through counts, pagination, and aggregates.

---

## 5. Seeds

**Rule 5.1 — A seed is data-only, idempotent, re-runnable.** It never changes shape.

**Rule 5.2 — Reference data the application requires is seeded, not migrated** — so it can be corrected without a migration — but its **absence must fail loudly** at startup, not silently render an empty dropdown.

**Rule 5.3 — Demo data is separated from reference data by module**, and never runs by default in a production entrypoint.

---

## 6. Operations

**Rule 6.1 — Backups are verified by restore.** A backup nobody has restored is a hypothesis.
**Rule 6.2 — Secrets never appear in a migration, seed, model, or log.**
**Rule 6.3 — FILL:** retention and deletion policy, if the data is personal or regulated.

---

## 7. Known deviations — do not extend

| Deviation | Find it with | Target state |
|---|---|---|
| ‹…› | ‹command› | ‹rule number› |

## 8. Pinning tests

| Rule | Enforced by |
|---|---|
| ‹boundary rule› | ‹test path› |
| ‹all streams replay from empty› | ‹CI job› |
