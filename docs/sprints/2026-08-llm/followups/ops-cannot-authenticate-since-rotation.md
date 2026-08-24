# The ops monitor has been unable to reach the database since 2026-08-21

**Logged:** 2026-08-24 · **Found by:** running the real daily-report queries while verifying the
Keycloak event fix · **Status:** 🔴 open, not fixed — a credential change nobody has authorised yet

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

## The fix, and why it is not applied here

Two options, and the second is better:

- **(a)** `ALTER ROLE ops_app PASSWORD '<POSTGRES_PASSWORD>'` — restores the accidental coupling that
  caused this. **Do not.**
- **(b)** Give `ops_app` its **own** password, set `OPS_DB_PASSWORD` in `secrets.enc.env`, regenerate
  `env.local`, recreate the `ops` container. This is what the inventory row already describes, and it
  makes a future `POSTGRES_PASSWORD` rotation unable to break monitoring.

Not applied because it changes a database role's credential and adds a secret to the encrypted store —
the project owner's call, not an incidental fix during a verification run.

## Outstanding

- [ ] Apply fix (b) on the local stack; add `OPS_DB_PASSWORD` to `secrets.enc.env` and to
      [`14_key_and_secret_lifecycle.md`](../../../deployment/14_key_and_secret_lifecycle.md) §1 as its
      own rotation procedure rather than "as `POSTGRES_PASSWORD`".
- [ ] ⚠ **Remove the fallback in `ops/config.py:107`, or make it warn loudly.** A silent fallback to a
      different role's password is what turned a routine rotation into three days of blind monitoring.
- [ ] Make the `ops` healthcheck exercise the database, so `healthy` means what it says.
- [ ] Add a check that fails when `ops` has not written a health row in N hours — the monitor for the
      monitor. Without it this recurs on the next rotation.
- [ ] ⚠ **Staging and DOR production have not been rotated at all**, so `ops` there would still connect
      — if `ops` were deployed there, which it is not. Both facts need to change together, in that order.
