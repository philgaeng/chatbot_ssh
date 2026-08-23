# Follow-up — which live secrets are in public git history, and what that is worth

**Logged:** 2026-08-23, while deciding whether to purge history after the `POSTGRES_PASSWORD`
rotation ([`db-password-hardcoded-in-compose.md`](db-password-hardcoded-in-compose.md)).
**Owner:** deployment · **Status:** ✅ the exposure is closed locally; the purge decision is **open,
and the recommendation is not to**.

## Why this exists

"Rotate first, then purge" is the right order, and the reason is worth writing down because the wrong
order is tempting: purging *feels* like the fix. It is not. **Rotation is unilateral, instant, and is
the step that removes risk** — it makes every historical copy worthless. **Purging is coordinated,
rewrites shared history, and cannot restore confidentiality on a repository that has been public since
2025-01-21.** Purge-before-rotate is the actively dangerous order: you pay the whole coordination cost
and come away *believing* you are clean while the credential still authenticates.

But neither step can be scoped without knowing what is actually in there, so the first move is a scan.

## The method — reproducible, and it prints no secret

Hash every **live** secret value, then hash every token in every blob ever committed and look for
collisions. This answers the only question that matters — *"is what I am using today readable by
anyone?"* — and it does so without a regex that guesses at what a secret looks like.

```
sops --decrypt secrets.enc.env        -> live values (in memory only)
git rev-list --all --objects          -> every blob ever, excluding vendored trees
git cat-file -p <sha>                 -> tokenise, sha256, compare
```

⚠ **A pattern scan is not a substitute and will mislead you in both directions.** Ours flagged 70
"secret-shaped" values; most were false positives (`COPYLEFT_TOKENS`, `ORG_NAME_TOKEN_RE`, storage-key
constants named `ACCESS_TOKEN`), and the genuinely alarming ones — an AWS key, an OpenAI key, an HF
token and a `DB_ENCRYPTION_KEY` in a committed `env.local.example` — turned out to be **superseded
values that authenticate nothing**. Only the hash comparison against live values separated the two.

## What the scan found

| Secret | In public history? | Action |
|---|---|---|
| `POSTGRES_PASSWORD` | ⚠ was — as a literal in 6 tracked files | ✅ **Rotated 2026-08-21** |
| `REDIS_PASSWORD` | ⚠ was — in 9 now-deleted files (`scripts/local/redis.conf`, `scripts/servers/launch_servers.sh`, `env.local.example`, …) | ✅ **Rotated 2026-08-23** |
| `SMTP_USERNAME` | ⚠ **yes, and it cannot be removed** — see below | ⬜ accepted |
| `DB_ENCRYPTION_KEY` | ✅ no | — |
| `SMTP_PASSWORD` · `OPENAI_API_KEY` · `HG_TOKEN` · `AWS_ACCESS_KEY_ID` · `AWS_SECRET_ACCESS_KEY` | ✅ no | — |

⭐ **`DB_ENCRYPTION_KEY` being clean is the most important line in that table.** It is the one secret
this project [cannot rotate](../../deployment/14_key_and_secret_lifecycle.md) — there is no
re-encryption script, so a leak would have been permanent PII exposure. *Older* encryption keys **are**
in history (`setup_encryption.sh`, `env.local.example`, CI), but they are not the live one, and since
no genuine grievance has ever been processed nothing of consequence was encrypted under them.

### ⚠ `SMTP_USERNAME` is unremovable, and stripping files does not change that

It is the **git author email on 865 of this repository's 1,018 commits**. Deleting it from source files
while the commit log publishes it on every commit achieves nothing; removing it from history would mean
rewriting the author of every commit, changing every SHA. It was removed from application config anyway
([`4ea8a1bf`](../../../)) because hardcoded identities are bad config, **not** because that closes an
exposure — and the lifecycle doc must not record one.

The credential that matters there is `SMTP_PASSWORD`, which is clean. Username-public /
password-private is the ordinary state for app-password SMTP; the control is 2FA on the mailbox.

## The purge decision — recommendation: **don't**, or at least don't prioritise it

With both rotations done, **nothing left in history opens a live door.** Purging would rewrite shared
history across many branches to delete values that no longer authenticate anything, and it cannot
un-publish them: the repository has been public for over a year. (0 forks helps; it does not make
anything retrievable.)

One thing genuinely argues for a rewrite, and it is not a secret: **an entire agent worktree snapshot,
`.claude/worktrees/pedantic-kapitsa-c79380/`, is committed on three branches pushed to origin** —
`feature/chatbot`, `feature/grm-ticketing`, `features/chatbot`. It is a duplicate copy of the whole
repository, which is why several secrets appear twice in any scan. That is a size-and-hygiene argument
carrying the same rewrite cost, and it should be decided on its own merits.

⚠ **Not checked: GitHub's own secret-scanning alerts.** The API returned 403 (the token lacks the
scope). Worth reading in the UI, because it also reveals whether GitHub already notified AWS or OpenAI
on our behalf for the superseded keys.

## ⬜ Also found: `TICKETING_SECRET_KEY` is empty in `secrets.enc.env`

Noticed because the scan counted 10 distinct values across 11 keys. **It is not a vulnerability here** —
the code fails closed (HR-01): `ticketing/api/main.py` **refuses to start** when it is unset outside the
dev bypass, and `verify_api_key` returns 503 rather than accepting any key. The local stack runs
`APP_ENV=dev AUTH_MODE=bypass`, so empty is the intended state.

⚠ **But it is a deployment gap with a loud failure mode**, which is worth knowing before it happens: any
host that runs `make env-local` from this `secrets.enc.env` gets an empty value, and the ticketing API
will refuse to boot. Set it — per-environment, not shared — before staging or DOR prod serves.
