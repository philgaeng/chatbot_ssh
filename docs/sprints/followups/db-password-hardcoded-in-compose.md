# Follow-up — `POSTGRES_PASSWORD` is hardcoded in the compose files, so the encrypted copy is inert

**Logged:** 2026-08-21, during the SOPS + age migration ([`18_sops_migration_handover.md`](../../deployment/18_sops_migration_handover.md)).
**Owner:** deployment · **Severity:** the highest-value thing found by that migration, and it is **not** what
the migration set out to fix.

> ## ✅ Fixed locally, 2026-08-21 — ⚠ **and this change will stop staging and DOR prod from starting**
>
> The variable is live: every compose service now interpolates `POSTGRES_USER` / `POSTGRES_PASSWORD` /
> `POSTGRES_DB` from `env.local` with `${VAR:?}`, the credential has been **rotated**, and the literal is
> gone from all six tracked files. Verified, not assumed — the running `backend` and `ticketing_api`
> containers hold `env.local`'s value (compared by hash), all 14 services are healthy, and Keycloak
> reconnected with both realms intact.
>
> ⚠ **Read [§Deploying this to staging and DOR prod](#deploying-this-to-staging-and-dor-prod) before the
> next deploy to either host.** `${VAR:?}` fails the stack loudly when the variable is missing or wrong,
> which is the intended behaviour and is exactly what those two hosts will hit: their databases still
> answer to the old credential. **This is a coordinated change, not a pull-and-restart.**
>
> **What is still open:** the role and database rename (`user`/`app_db` → `nepal_grievance_admin`/
> `grievance_db`), which is cosmetic alignment with the documentation and carries a three-host migration
> with no security payoff; `SMTP_USERNAME`, still committed in three places; and the git history, which
> still contains the old password — rotation is what makes those historical copies worthless, and purging
> history is a separate decision about rewriting shared history.

## The finding

Every service that talks to Postgres sets the credential **in its own `environment:` block**:

```
docker-compose.yml   × 7   POSTGRES_PASSWORD: password
docker-compose.grm.yml × 4  POSTGRES_PASSWORD: password
docker-compose.yml   × 5   DATABASE_URL: postgresql://user:password@db:5432/app_db
```

Compose's `environment:` **overrides `env_file:`**. So `env.local`'s `POSTGRES_PASSWORD` — the value
this migration just moved into `secrets.enc.env` — **is read by nothing**. Verified: the running `db`
container reports `user=user db=app_db`, while `env.local` says `POSTGRES_USER=nepal_grievance_admin`.

⚠ **`docker-compose.aws.yml` and `docker-compose.prod.yml` do not override it.** They touch `nginx`
and `keycloak` only. Staging and production therefore run Postgres as **`user` / `password`**, a
credential committed in the clear, and `db` publishes **`0.0.0.0:5433`** on every host running the GRM
overlay. The only control holding is the cloud security group / firewall — the same single-control
posture already logged for `5001:5001` in TODO.md.

## Why it was invisible

Three things each looked like the reassurance:

1. **`env.local` holds a strong, non-default password** — verified by hash, it is neither `password`
   nor the committed literal below. It is simply never read.
2. **`scripts/ops/security-preflight.sh:61` asserts `POSTGRES_PASSWORD != "password"`** — and passes,
   because it reads `env.local`, i.e. the inert copy. ⚠ **The promotion gate is checking the wrong
   value.** This is the part to fix first; a gate that reports green on a variable nothing consumes is
   worse than no gate.
3. **T3-08 already found half of it** (TODO.md, 2026-07-15): *"env.local's `POSTGRES_*` are dead by
   construction — every compose service hardcodes them, so no container reads them."* It was logged as
   a **test-fixture** problem and closed there. Nobody carried it across to the security question of
   *what the password actually is on a deployed host.*

## ⚠ Worse: the live `POSTGRES_PASSWORD` is committed, in six tracked files

**`env.local`'s `POSTGRES_PASSWORD` is byte-identical to a literal committed in the repository.**
Confirmed 2026-08-21 by decrypting `secrets.enc.env` and comparing (the value is not reproduced
here, and must not be):

| Tracked file | What it is |
|---|---|
| `backend/config/constants.py:519` | `os.getenv('POSTGRES_PASSWORD', <literal>)` — a fallback default |
| `scripts/database/config.sh:32` | same, twice |
| `backend/orchestrator/config/source/legacy_rasa_config/endpoints.yml` | legacy Rasa config |
| `tests/ticketing/test_host_env.py:34` | test fixture |
| `docs/sprints/archive/claude-tickets/session-0-codebase-findings.md` | archived findings doc |
| `.claude/settings.local.json` | ⚠ **a tracked Claude Code permission rule**: `Bash(export PGPASSWORD='<literal>'…)` |

⚠ **An earlier draft of this document said the literal was *not* the live value.** That was wrong —
the comparison behind it failed to strip the quotes around the value in `env.local`. Recorded here
because the mistake pointed the wrong way: it would have told the next reader this needed no rotation.

**So encrypting `POSTGRES_PASSWORD` into `secrets.enc.env` protects nothing today.** The value is in
the working tree and in git history. It must be **rotated**, not merely encrypted — and the literal
removed from all six files in the same change. Purging git history is a separate decision (shared
history rewrite); rotation makes the historical copies worthless, which is usually the cheaper answer.

⚠ `SMTP_USERNAME` (a `gmail.com` address, the username half of the mail credential) is likewise
present in `backend/config/constants.py`, two ticketing tests and an archived doc.

`scripts/servers/create_env.sh` carries the password too but is untracked/gitignored.

## What to do

| Step | Note |
|---|---|
| 1. Point `security-preflight.sh` at the value a **container** resolves, not `env.local` | Do this first — it is small, and until it is done every later step is unverifiable |
| 2. Replace the 11 literals with `${POSTGRES_PASSWORD:?}` and the 5 `DATABASE_URL`s with the interpolated form | ⚠ `:?` (fail-if-unset), not `:-password` — restoring a default recreates the bug silently |
| 3. Set a real password on staging + DOR prod, `ALTER ROLE`, in one window | Coordinate with a stack restart; `POSTGRES_USER` differs from `env.local`'s too, so decide one identity |
| 4. Delete the `K9!…` fallbacks from the two tracked files | Rotate it wherever it turns out to be live |
| 5. Only then does `POSTGRES_PASSWORD` in `secrets.enc.env` mean anything | And only then is rotating it (handover §6 item 5) worth doing |

⚠ **Do not rotate `POSTGRES_PASSWORD` before step 2.** Rotating an inert variable changes nothing,
breaks nothing, and produces a "rotated on 2026-xx-xx" entry in
[`14_key_and_secret_lifecycle.md`](../../deployment/14_key_and_secret_lifecycle.md) §1 that is false.
False rotation records are worse than "unknown — treat as never".

## Not affected

`REDIS_PASSWORD` is wired correctly — `${REDIS_PASSWORD:-}` interpolation from `--env-file env.local`,
no hardcoded override. Verified live: `redis-cli -a "$REDIS_PASSWORD" ping` → `PONG` against the value
that came out of `secrets.enc.env`. Its encrypted copy is real.

> ⚠ **Correct about the wiring, and it was not the whole question.** A later history scan found that
> the *value* was sitting in **public git history** in 9 now-deleted files, so the encrypted copy was
> protecting a credential anyone could already read. **Rotated 2026-08-23.** The distinction is worth
> keeping: `POSTGRES_PASSWORD` was an **inert variable** (correct value, read by nothing);
> `REDIS_PASSWORD` was the opposite — **a live variable carrying an exposed value**. Checking one does
> not check the other, and this section is what happens when you check only the first.
> See [`secrets-in-public-git-history.md`](secrets-in-public-git-history.md).

---

## What was done, 2026-08-21

| # | Step | Result |
|---|---|---|
| 1 | `security-preflight.sh` no longer checks only `env.local` | Added two checks: **no compose file may pin a DB credential to a literal** (static, needs no running stack), and — when a stack is up — **the running `backend`'s value must match `env.local`**, compared by hash so no secret is printed. Both were mutation-tested: reintroducing `POSTGRES_PASSWORD: password` and an inline-credential `DATABASE_URL` each turn the gate red |
| 2 | 19 literals replaced with `${VAR:?}` | `docker-compose.yml` (7 × `POSTGRES_*` blocks + 5 `DATABASE_URL`) and `docker-compose.grm.yml` (4 blocks + Keycloak's `KC_DB_URL` / `KC_DB_USERNAME` / `KC_DB_PASSWORD`). ⭐ **Keycloak was not in the original count** — it holds its own copy and would have been missed. The `db` healthcheck now reads `pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB` rather than repeating the names |
| 3 | `.env.shared` set to the identity the volumes actually hold | `POSTGRES_DB=app_db`, `POSTGRES_USER=user`. ⚠ It said `grievance_db` / `nepal_grievance_admin` — values no database on any host has ever answered to. `POSTGRES_HOST` / `POSTGRES_PORT` stay as they were: they are container topology, not credentials, and every service overrides them |
| 4 | Password rotated | 40 alphanumeric characters. **Alphanumeric deliberately** — it is embedded in `DATABASE_URL`, so any reserved character (`@ : / # %`) would corrupt the connection string in a way that looks like a network fault. Set via `sops secrets.enc.env`, applied with `ALTER ROLE`, and TCP authentication verified before the stack was restarted |
| 5 | The literal removed from all six tracked files | `backend/config/constants.py` (no fallback password at all now), `scripts/database/config.sh` (both branches), the archived Rasa `endpoints.yml`, `tests/ticketing/test_host_env.py`, `.claude/settings.local.json`, and the archived findings doc. Verified with a repo-wide search for the old value: gone. And the **new** value appears in no tracked file |
| 6 | The host test bootstrap inverted | ⭐ **The one that was not on the list.** `tests/ticketing/_host_env.py` deliberately *ignored* `env.local` and hardcoded `user`/`password`/`app_db`, for a reason that was correct when written: env.local was dead config, so honouring it was the one way host pytest could disagree with the database (D-36). Making env.local live inverts that — the hardcoded fallback would now *cause* D-36 against a rotated database. It reads the identity from `env.local`, and raises an actionable error naming `make env-local` rather than guessing |

**Test evidence.** `tests/ticketing/test_host_env.py` rewritten to pin the new invariant, including a test
that fails if any `setdefault` credential returns to the bootstrap — mutation-checked, it turns two tests
red. `tests/repo` 82 passed; SPDX coverage 593/593. The host ticketing suite is **756 passed / 13 failed**,
and those 13 fail **identically on the pre-change commit** (verified in a throwaway worktree with the
credentials passed explicitly): they are seed-staffing debt — *"Add a Level 1 officer"* — and the last write
to `ticketing.tickets` was 2026-08-08.

## Deploying this to staging and DOR prod {#deploying-this-to-staging-and-dor-prod}

⚠ **Do not pull-and-restart.** `${POSTGRES_PASSWORD:?}` stops the stack when the value is missing, and
authentication fails when it is wrong. Both hosts will hit one or the other: their databases still answer
to the old credential, and neither host has been migrated to SOPS
([handover](../../deployment/18_sops_migration_handover.md) step 4), so `make env-local` cannot run there
until a per-server age keypair is a recipient.

**Per host, in this order — the order is the whole point:**

1. **Get the credential onto the host first.** Either complete the SOPS migration for that host (add its
   age public key with `sops updatekeys`, then `make env-local`), or set `POSTGRES_USER` / `POSTGRES_DB` /
   `POSTGRES_PASSWORD` in its existing `env.local` by hand. The values must match `.env.shared` plus the
   rotated secret.
2. **Change the database password to match, before restarting anything.** The running containers hold
   live connections and are unaffected by an `ALTER ROLE`, so this is safe to do first — and doing it
   second means an outage between the restart and the `ALTER`:
   ```bash
   printf "ALTER ROLE \"user\" WITH PASSWORD '%s';\n" "$(grep '^POSTGRES_PASSWORD=' env.local | cut -d= -f2-)" \
     | docker compose --env-file env.local -f docker-compose.yml -f docker-compose.grm.yml \
         exec -T db psql -U user -d app_db -q -v ON_ERROR_STOP=1 -f -
   ```
3. **Verify the new credential authenticates over TCP** before you restart — an `ALTER ROLE` that ran is
   not the same as a password that works.
4. **Recreate the stack**, then **recreate Keycloak separately**: it is behind the `auth` profile, so a
   plain `up -d` does not touch it and it keeps running on the old credential until it next restarts —
   a latent break that looks fine for days.
5. **Run `security-preflight.sh`.** Check 4c now compares the running container against `env.local`, which
   is the assertion that was missing.

⚠ **`OPS_DB_PASSWORD` is a separate credential** for the scoped `ops_app` role and is **not** rotated by
this change. It is empty in the local stack, so `ops` falls back to the admin credential — which now works
only because step 2 rotated that too. Giving `ops_app` its own password is
[§5 of the lifecycle doc](../../deployment/14_key_and_secret_lifecycle.md) and remains outstanding.
