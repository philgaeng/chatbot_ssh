# `GRM-102` — "rollback is the same command with an older tag" is false across a migration

**Deferred 2026-09-14**, while fixing `GRM-099`. Logged here and in [`SPINE.md`](../../../SPINE.md)
per the standing deferral rule. **Kind:** `deviation` — [`03_operations.md`](../../../deployment/03_operations.md)
§6a claims something the mechanism cannot do, and the spec is the side that is wrong.

## The claim

§6a: *"`make aws-deploy IMAGE_TAG=<an-older-sha>` — ⭐ that is the rollback — no rebuild."*

## Why it is only true when no migration changed

`REMOTE_DEPLOY_CORE` runs `up -d` **first**, then the migrations. Rolling back to an image whose
code predates a migration that has already been applied:

1. `up -d` starts the **older** containers — against the **newer** schema, immediately.
2. `alembic upgrade head` then runs the older code's scripts, which do not contain the database's
   current revision. Alembic refuses: *"Can't locate revision identified by …"*. `set -e` aborts.

⚠ **That second step is expected alembic behaviour, not measured on this repository.** No rollback
across a migration boundary has been attempted here.

## What `GRM-099` changed about this — better, not solved

Before `GRM-099`, the migrations ran the host **checkout's** code, which is newer than the rolled-back
image — so they found the current revision, did nothing, and **reported success over a schema/code
mismatch.** Now they run the image's code and **fail loudly.** A loud failure is strictly better
than a silent wrong answer, and it is still not a rollback.

## The fork — which side moves

- **The spec moves.** §6a says rollback-by-tag is only valid when no migration landed between the
  two tags, and names the manual `alembic downgrade` step otherwise. Cheap and honest.
- **The code moves.** The deploy detects a revision it cannot locate and runs `downgrade` to the
  image's own head **before** `up -d`. Correct in principle; downgrades are rarely tested and a
  wrong one destroys data, which is the reason to think twice.

**Recommendation: the spec moves now; the code only with a tested downgrade for every migration.**

## ✅ Resolved 2026-09-14 — the spec moved

The owner chose the narrow fix. [`03_operations.md`](../../../deployment/03_operations.md) §6a now says a tag
rollback is valid only when no migration landed between the two tags, gives the command to check, and
describes the two alternatives. Measured while writing it: **59 of 64 migrations implement a downgrade;
the 5 that do not are all data rewrites**, so crossing one reports success and restores nothing — named
in the runbook. Automated downgrade was deliberately not built: it would be correct only if every
downgrade were tested, and none has been.

## Definition of done

- ✅ The fork is decided and recorded — the spec moves (2026-09-14).
- ✅ §6a's rollback line no longer over-claims.
- If the code moves: a rollback across one real migration is driven on a disposable stack.
