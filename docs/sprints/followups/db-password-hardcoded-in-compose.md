# Follow-up — `POSTGRES_PASSWORD` is hardcoded in the compose files, so the encrypted copy is inert

**Logged:** 2026-08-21, during the SOPS + age migration ([`18_sops_migration_handover.md`](../../deployment/18_sops_migration_handover.md)).
**Owner:** deployment · **Size:** medium (11 compose sites + a coordinated DB password change on two hosts)
**Severity:** the highest-value thing found by that migration, and it is **not** what the migration set out to fix.

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
