# The ops monitor has been unable to reach the database since 2026-08-21

**Logged:** 2026-08-24 · **Found by:** running the real daily-report queries while verifying the
Keycloak event fix · **Status:** ✅ **FIXED 2026-08-24** (local stack) — see §Fixed below

## What is wrong

[`ops/config.py:107`](../../../../ops/config.py) builds the connection string as:

```python
user     = self.ops_db_user or self.postgres_user          # → "ops_app"
password = self.ops_db_password or self.postgres_password  # → POSTGRES_PASSWORD, because…
```

`OPS_DB_PASSWORD` is **unset everywhere** — not in `env.local`, not in `.env.shared`, not in
`secrets.enc.env`, and `docker-compose.grm.yml:278` defaults it to empty. So `ops` has always
authenticated as the **`ops_app`** role using the **`user`** role's password.

That worked only for as long as the two happened to match. `POSTGRES_PASSWORD` was rotated on
**2026-08-21** ([`14_key_and_secret_lifecycle.md`](../../../deployment/14_key_and_secret_lifecycle.md) §1)
— `ALTER ROLE` on `user`. **`ops_app` is a different role and was not rotated with it.**

## Measured

| | |
|---|---|
| Last successful `ops` write | `ops.system_health_checks` **2026-08-18 07:51:53Z** (1 row); `ops.dependency_findings` same timestamp (5 rows) |
| Authentication failures in the container log | **253** |
| Daily report today | every activity and security row renders `n/a (OperationalError)` |
| Container status | `healthy` — ⚠ **the healthcheck does not test the database connection** |

```
FATAL:  password authentication failed for user "ops_app"
```

## Why it went unnoticed for three days

Three independent masks, and each one alone would have been enough:

1. **`_safe_scalar` degrades to `n/a` instead of raising.** Correct for a monitor — it must not crash —
   but `n/a` in an email nobody is diffing reads as "not applicable", not "broken".
2. **The container reports `healthy`.** Its healthcheck does not exercise the database.
3. **Nothing monitors the monitor.** The one job of `ops` is to notice things; there is no check that
   notices when `ops` itself stops noticing.

⚠ **This is the same defect class as [F-18](keycloak-recorded-no-login-events.md)** — a reporting
surface that cannot distinguish *no signal* from *no collection* — found the same day, in the same
subsystem, by the same method: running the query instead of reading the code that contains it.

## Fixed

**The credential.** `ops_app` now has its own 40-character alphanumeric password, stored as
`OPS_DB_PASSWORD` in `secrets.enc.env` with its `#@secret` marker in `.env.shared`, spliced into
`env.local` by `make env-local` (45 variables now, was 43). The accidental coupling is gone: a future
`POSTGRES_PASSWORD` rotation cannot break monitoring.

⭐ **And repairing it revealed that the report had never worked.** Authentication was only the
outermost of four layers. With `ops` finally able to connect, every activity and security row still
returned `n/a`:

| # | Defect | Fix |
|---|---|---|
| 1 | **One failed query blanked the entire report.** Postgres aborts the whole transaction on any error; `_safe_scalar` caught the exception but never rolled back, so every subsequent row raised `InFailedSqlTransaction`. The degradation was meant to be per-row and was per-report | `db.rollback()` in the handler |
| 2 | **Four queries named columns that do not exist** — `grievances.created_at` (it is `grievance_creation_date`), `tickets.status` (it is `status_code`, and the vocabulary is upper-case), `ticket_overdue_episodes.created_at` (`started_at`), `ticket_files.created_at` (`uploaded_at`) | corrected against the live schema, with a comment telling the next person to run `\d`, not to infer from the model |
| 3 | **`ops_app` lacked SELECT on five tables it reads** — `ticket_overdue_episodes`, `ticket_files`, `admin_audit_log`, and the whole `keycloak` schema. `ticketing.tickets` *was* in `ops001`'s grant list, but behind `IF to_regclass(...) IS NOT NULL`, which **silently skips** when ops migrates before ticketing | migration `ops003_report_grants` — same guard, but it now `RAISE WARNING`s what it skipped |
| 4 | **`healthy` did not mean healthy.** The healthcheck only proved the scheduler was ticking. A container that cannot reach its database is useless, and it reported healthy for three days | `ops/selfcheck.py` probes the database and names the failing role |

**So the honest summary is worse than the one this file opened with.** The credential broke on
2026-08-21; the report's own queries and grants had been wrong since it shipped. **No deployment has
ever produced a correct daily ops report.**

### Verified

Rebuilt and recreated the container, ran `ops003`, then ran the real report functions:

```
Grievances submitted (24h)  0     Open critical/high deps   0
Tickets created (24h)       0     Open total deps           5
Tickets resolved (24h)      1     Failed logins (24h)       3
Currently open tickets      5     Contact-reveal events     0
SLA-breach episodes (24h)   0     Officer logins (24h)      1
Files uploaded (24h)        0
```

Cross-checked against ground truth: open = 5 is `ESCALATED` 4 + `OPEN` 1 with `RESOLVED` 1 excluded;
the login counts are exactly the events generated while verifying [F-18](keycloak-recorded-no-login-events.md).

**Red-tested the healthcheck** by reproducing the original failure — `ALTER ROLE ops_app PASSWORD`
to a wrong value — and it now exits 1 naming the role, where before it reported `healthy`. Credential
restored, exit 0.

## Still outstanding

- [ ] ⚠ **`ops` is deployed to neither staging nor DOR production**, so every fix above is live on the
      development stack only. Deploying it needs `OPS_DB_PASSWORD` set and `ops003` run on each box.
- [ ] The other report rows should get the same treatment they just got here — **run them, do not read
      them.** `_health_rows` and the preflight status were not exercised by this pass.
- [ ] Consider whether `_safe_scalar` returning `n/a` is right at all. It is honest, but three months of
      `n/a` in an email nobody diffs is indistinguishable from three months of zeroes. An alert when a
      report row fails would have closed this in a day.
