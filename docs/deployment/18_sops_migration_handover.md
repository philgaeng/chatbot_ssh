# Handover — migrate this project's secrets to SOPS + age, and rotate

> **For:** an agent or engineer picking this up cold.
> **Scope:** **`nepal_chatbot` only.** The policy in
> [`13_security.md`](13_security.md) §5 covers every repository under `~/projects/`; this document is
> the slice for this one, so the issue can be closed here without waiting on the others.
> **Written:** 2026-08-20. **Status:** 🟨 **steps 0–5 done 2026-08-21; step 6 (rotation) and the
> staging/production migration are not.** See *What actually happened* below before doing anything.
> **Prerequisite that is not yours:** the owner answers the `TBC` cells in `13_security.md` §5.3.1.
> You can do steps 1–4 without them; step 6 needs them.

---

## ⬛ What actually happened — 2026-08-21

**Done, locally:**

| Step | Outcome |
|---|---|
| 0 · Task zero | Reconciled. [`14_…`](14_key_and_secret_lifecycle.md) §1 is now the **single authority** (16 rows, one per secret, with impact + cadence + procedure + `Last rotated`); [`13_security.md`](13_security.md) §5.3.1 keeps location columns only and points at it |
| 1 · Tooling | `sops` 3.13.3 + `age` 1.1.1 in `~/.local/bin` (no sudo). **Provenance verified** — sops against its published `checksums.txt`, age against the **GPG-signed Ubuntu archive index** |
| 2 · Keypair | `~/.config/sops/age/keys.txt`, mode 0600, dir 0700, on **ext4** (checked `df -T`, and that the path does not resolve under `/mnt`). Public key `age1ke0hk5e…rz95h` |
| 3 · `.gitignore` | Verified, plus `env.local.extra` added (see below) |
| 4 · Split | `.env.shared` (32 vars, committed plaintext) + `secrets.enc.env` (11 vars, SOPS) + `.sops.yaml`; `make env-local` / `make secrets-edit`; generator `scripts/ops/gen_env_local.sh`. ⚠ **Counts are as at 2026-08-21. Current: 33 + 12 = 45** — `OPS_DB_PASSWORD` was added 2026-08-24. Do not treat any number in this table as today's; run the generator, it prints them |
| 5 · Verify | `make wsl-up` green — **14/14 containers healthy**, 0 compose "variable is not set" warnings; regenerated `env.local` has **all 43 names and every value identical** to the pre-migration file; regeneration is idempotent. *(45 names as of 2026-08-24.)* |

### ⚠ Four places this document was wrong, and what was done instead

1. **`.env` cannot be the plaintext half — it is gitignored on purpose** (`.gitignore:29`, CL-03, with
   a comment saying it was checked deliberately). Committing it needs a `!.env` negation, which
   deletes the safety net that stops the universal "secrets go in `.env`" reflex from committing a
   secret. **The plaintext half is `.env.shared`**, which matches the tracked `.env.*` family
   (`.env.example`, `.env.open`, `.env.openai`). Everything else in §4 stands.
2. **"8 of them secret-class" undercounts. It is 11.** The encrypted half was defined as *this
   project's own secret inventory* (§5.3.1) intersected with `env.local` — a rule that can be
   restated, rather than a hand-picked list. That adds `TICKETING_SECRET_KEY` (empty locally, but
   secret-class everywhere else — leaving it in the committed plaintext half is a trap for whoever
   sets it on a host) and `HG_USERNAME` (§5.3.1 groups it with `HG_TOKEN` exactly as it groups
   `SMTP_USERNAME` with `SMTP_PASSWORD`, which §4 *did* catch). `POSTGRES_USER` and
   `PINPOINT_APPLICATION_ID` were left in the plaintext half: they are resource addresses, not
   authentication principals. ⚠ **`PINPOINT_APPLICATION_ID` was deleted on 2026-08-24** — it was read
   by no code at all, and the AWS SMS path it belonged to is gone (privacy assessment F-12).
3. **Task zero says five rows are missing from §14. It is six** — `KEYCLOAK_CLIENT_SECRET` was absent
   from both lists' reconciliation notes. This is the defect the section is about, one level down.
4. **The DoD asked for `Last rotated` in §5.3.1 *and* for §5.3.1 to stop owning rotation.** Those
   contradict. `Last rotated` is rotation state, so it went to §14 §1 with the rest.

### ⚠ And one thing that was worse than anything this migration fixed — ✅ now fixed locally

> **Resolved 2026-08-21**, after this section was written and because of it. All 19 compose literals
> (including **Keycloak's `KC_DB_*`**, which the count below misses) now interpolate from `env.local`
> with `${VAR:?}`; the credential is **rotated**; the literal is gone from the source and config files; and
> `security-preflight.sh` checks what a **container** resolves rather than the inert copy. ⚠ **Staging
> and DOR prod are not done and will fail to start on the next deploy** — see the coordinated runbook in
> [`db-password-hardcoded-in-compose.md`](../sprints/followups/db-password-hardcoded-in-compose.md).
> The description below is kept as the finding, in its original terms.
>
> ### ⚠ Re-checked 2026-08-24: "gone from all six tracked files" was too strong
>
> `git grep POSTGRES_PASSWORD=password` still returns **three tracked files**:
>
> | File | What it is | Verdict |
> |---|---|---|
> | `.claude/settings.local.json` (×3, lines 106/110/115) | Claude Code permission allowlist — the literal is embedded in pre-approved `export … POSTGRES_PASSWORD=password …` commands | ⚠ **Real leftover.** Removing it makes those exact commands prompt again, which is a workflow choice, not a mechanical edit |
> | `.env.example:29` | ⚠ Carries a **value**, not a name — while §7 of this document tells readers it is "names only". Both cannot be true | ⚠ **Correct §7 or change the placeholder.** `changeme` would be as useful and would not collide |
> | `docs/sprints/archive/.../PROGRESS.md` | Archived history describing the defect | ✅ Leave. Rewriting history to hide a finding is worse than the finding |
>
> ⭐ **Why this still matters even though the value was rotated locally:** `14_…` §1 records that
> **staging and DOR prod were never rotated and still hold the pre-rotation credential**. So `password`
> is not a stale string in those files — it is **the live database credential for both servers**, sitting
> in the working tree of a repository slated for public release. The fix is the rotation in item 4
> below, not a `sed`; this document's own conclusion applies unchanged — *encrypting (or deleting) a
> value that is already in git history protects nothing; it has to be rotated.*

**`POSTGRES_PASSWORD` is hardcoded as `password` in 11 compose sites and is not overridden by the
staging or production overlays.** Compose's `environment:` beats `env_file:`, so the value this
migration encrypted **is read by nothing**, and `db` publishes `0.0.0.0:5433` on every host running
the GRM overlay. `security-preflight.sh` asserts the password is non-default — against the inert
copy — so the promotion gate reports green on a variable nothing consumes.

**And the value itself is already public.** `env.local`'s `POSTGRES_PASSWORD` is byte-identical to a
literal committed in **six tracked files** — `backend/config/constants.py:519`,
`scripts/database/config.sh:32`, `legacy_rasa_config/endpoints.yml`, `tests/ticketing/test_host_env.py:34`,
an archived findings doc, and ⚠ **`.claude/settings.local.json`**, a tracked Claude Code permission
rule that embeds it in a `PGPASSWORD=` command. `SMTP_USERNAME` is committed in three places.
**Encrypting a value that is already in the working tree and in git history protects nothing** — it
has to be *rotated*, and the literals removed in the same change.

⚠ **Do not rotate `POSTGRES_PASSWORD` (step 6 item 5) as a lone edit to `secrets.enc.env`** — nothing
reads that copy, so it would change nothing while writing a false `Last rotated` date. Fix the compose
hardcoding first, then rotate, then purge the literals.
Full analysis and the fix order: [`../sprints/followups/db-password-hardcoded-in-compose.md`](../sprints/followups/db-password-hardcoded-in-compose.md).

### New: `env.local.extra`

`env.local` is now generated, so anything hand-added to it is discarded on the next `make env-local`
— and the Makefile itself tells you to put `PROD_SERVER_USER` / `PROD_HOST` / `PROD_SSH_KEY` there.
Those go in **`env.local.extra`** (gitignored), which the generator appends verbatim.

### Still open — and who owns it

| # | Outstanding | Owner |
|---|---|---|
| 1 | ⚠ **Back up the age private key** to Proton Pass + a paper copy. **Until this is done, one disk failure makes `secrets.enc.env` permanently unreadable.** Nothing else here is urgent; this is | you, today |
| 2 | Fill the `Owner` `TBC` cells in §5.3.1 | you |
| 3 | The rotation pass (§6) — every credential is "unknown, treat as never" | you (external consoles) |
| 4 | Migrate **staging** and **DOR prod**: install sops+age (⚠ **neither is installed on staging** — verified 2026-08-24), generate a **per-server keypair**, add it as a recipient (`sops updatekeys`), then `make env-local`. ⭐ **Measured on staging 2026-08-24: `make env-local` there would delete THIRTY variables**, including `DOIT_SMS_BEARER_TOKEN` — a credential in neither inventory — and the whole Keycloak configuration. §5a Hazard 2 has the list. **DOR prod is unmeasured.** ⚠ **And `OPS_DB_PASSWORD` (row 4) is the opposite hazard**: it arrives correctly and still does nothing until `ALTER ROLE ops_app PASSWORD` runs on that box — §5a Hazard 3 | you |
| 7 | ⭐ **`DOIT_SMS_BEARER_TOKEN` is tracked by no inventory** — read by `backend/config/sms_config.py:47`, live on staging, absent from §5.3.1, `14_…` §1 and every committed env file. It authenticates to the **Government of Nepal SMS gateway**, which is the *production* complainant-notification path. Added to both inventories 2026-08-24; ⚠ **it still needs an owner and a rotation route, neither of which we control** | you |
| 6 | ⚠ **`POSTGRES_PASSWORD=password` is still in 3 tracked files** — `.claude/settings.local.json` (×3) and `.env.example:29`, plus archived history that should stay. ⚠ **Confirmed live on AWS staging by digest comparison, 2026-08-24** — that host still holds the pre-rotation value. In a repo slated for public release. Rotate there (item 4), then purge; or purge now and accept the prompts | you |
| 5 | ~~The compose-password fix above~~ ✅ **done locally 2026-08-21** — ⚠ but it makes item 4 a **prerequisite for the next deploy**, not a nice-to-have: `${VAR:?}` stops the stack when the value is missing, and neither host can run `make env-local` until its age key is a recipient | deployment |

⚠⚠ **UPDATED 2026-09-03 — the code IS now on `integration/stage`. Nothing has been DEPLOYED.**

This paragraph used to read *"nothing has been pushed to staging or production"*. That is no longer
true and the distinction is the whole point:

| | State |
|---|---|
| **`origin/integration/stage`** | ✅ Carries all of it — Sprints 2 and 3, and this secrets work |
| **The AWS staging host** | ⚠ **No longer untouched — deployed 2026-09-03.** Three `make aws-deploy` runs shipped Sprints 2 and 3 there (the default service list, then `celery_llm`/`celery_file`, then `orchestrator`). The compose credential path held exactly as the correction below predicted: nothing halted, no migration failed. ⭐ **But the deploy carried `ops` to a server for the first time, and that tripped §5a Hazard 3** — fixed the same day, §5a below. Deploys are still manual; there is no CD on this branch |

### ⚠ Corrected 2026-09-03 — `aws-deploy` is NOT blocked. `env-local` is the dangerous command.

An earlier version of this paragraph, and a banner in `make help`, said the next `make aws-deploy`
would break staging at the database. **That was wrong, and it was checked against the host rather
than reasoned about a second time:**

| Check, on the staging host 2026-09-03 | Result |
|---|---|
| `POSTGRES_PASSWORD` present in its `env.local` | ✅ yes — so `${VAR:?}` resolves, nothing halts at compose time |
| Digest of that value | `5e884898da280471` = **the pre-rotation value** |
| The host's own database | holds the same pre-rotation value (§5a row 4) — **so they match** |
| How compose is invoked there | `REMOTE_COMPOSE` passes **`--env-file env.local`**, so interpolation reads the host's file |
| Does `.env.shared` (new, committed) redefine it? | ✅ no — it carries `POSTGRES_DB` and `POSTGRES_USER` only |
| Does `REMOTE_DEPLOY_CORE` run `make env-local`? | ✅ **no** — it pulls, rebuilds and migrates |

**The credential path is self-consistent on that host**, so the compose change is inert there.

🔴 **The hazard is real but it belongs to a different command.** `make env-local` on staging
overwrites its `env.local` from `secrets.enc.env` — installing the **rotated** password against a
database that still holds the old one, and **deleting thirty host-only variables** including
`DOIT_SMS_BEARER_TOKEN`, the Government of Nepal SMS gateway credential. That is item 4, unchanged,
and §5a is still required reading before anyone runs it.

⚠ **Why the correction is worth this much space:** a banner saying *"BLOCKED, the deploy will fail"*
in front of a deploy that works is not a harmless excess of caution. It is the same failure as a
permanently red build (D-26) — people learn that the warning is wrong, and then they are trained to
walk past the next one, which will not be.

⚠ **DOR production is unmeasured and nothing here has been verified against it.** Hazard 1 —
overwriting `DB_ENCRYPTION_KEY` and rendering every encrypted PII column permanently unreadable,
silently, because decryption fails open — is **open for prod and only for prod**.

---

## 0. Read these first, in this order

1. [`13_security.md`](13_security.md) **§5** — the decided approach. **Do not re-litigate it.** SOPS +
   age, no hosted vault, platform-native stores where the platform issues the credential.
2. [`14_key_and_secret_lifecycle.md`](14_key_and_secret_lifecycle.md) — the **operational** doc for
   this project's secrets: impact-if-lost, impact-if-leaked, rotation cadence, backup.
3. [`../../CLAUDE.md`](../../CLAUDE.md) §Docker-only, §Environment variables.

### ✅ Task zero — DONE 2026-08-21. Kept as the reasoning, not as a task

> The reconciliation described below **has been carried out** — see the *What actually happened* table,
> row 0. [`14_…`](14_key_and_secret_lifecycle.md) §1 is the single authority (16 rows as of 2026-08-24 —
> `DOIT_SMS_BEARER_TOKEN` was added that day, having been in neither inventory) and [`13_security.md`](13_security.md) §5.3.1 keeps location columns only. **Do not redo
> it.** The section stays because the *reason* it was done is the reason not to undo it.

#### ⚠ Why there were TWO inventories, and why that was a defect

`13_security.md` §5.3.1 and `14_key_and_secret_lifecycle.md` §1 both list this project's secrets.
They were written months apart, they **disagree**, and neither is complete:

| | `13_security.md` §5.3.1 | `14_key_and_secret_lifecycle.md` §1 |
|---|---|---|
| Strength | *where* each secret lives and every copy | *impact* if lost or leaked, and rotation cadence |
| Missing | impact analysis | `SEARCH_TOKEN_PEPPER`, `SMTP_PASSWORD`, the AWS pair, `OPENAI_API_KEY`, `HG_TOKEN` |
| Has that the other lacks | the above five | ⚠ **`GITHUB_TOKEN`** (Dependabot) — absent from §5.3.1 entirely |

**Reconcile them before migrating anything, and do it by pointing rather than copying:**

- `14_key_and_secret_lifecycle.md` §1 becomes the **single authority** for this project's secrets —
  add the five missing rows to it.
- `13_security.md` §5.3.1 keeps only its **location** columns (Authoritative store · Other copies)
  and **replaces its rotation column with a pointer** to §14.

⚠ **Two rotation procedures for one credential is how a wrong one gets followed during an incident.**
Do not solve this by keeping both and "keeping them in sync" — that is the thing that has already
failed once here.

---

## 1. Install the tooling

> ✅ **Done 2026-08-21 on this workstation** — `sops` 3.13.3 + `age` 1.1.1 in `~/.local/bin`, verified
> present 2026-08-24. **Still to do on staging and DOR prod**, which is where this section now applies.

Verify with `which sops age`.

⚠ **Host install is correct here.** CLAUDE.md's Docker-only rule governs *building and running the
stack*; `sops` is a developer tool that never runs in a container and never serves a request.

## 2. Generate the age keypair — the one step with an irreversible mistake in it

```bash
mkdir -p ~/.config/sops/age
age-keygen -o ~/.config/sops/age/keys.txt
chmod 600 ~/.config/sops/age/keys.txt
```

⚠⚠ **It must be in the WSL filesystem. Never `/mnt/c/`, `/mnt/g/`, or anywhere inside
`G:\My Drive\`.** Google Drive mirror mode would sync the **private key in plaintext** to Google —
silently, as a backup feature working exactly as designed. Confirm with `df ~/.config/sops/age`; if
it shows a `drvfs` mount, stop and move it.

**Back it up** to Proton Pass as a secure note, plus a paper copy. Losing this key makes every
`secrets.enc.env` unreadable.

## 3. ✅ `.gitignore` — already done

Done 2026-08-20: `*.decrypted` added to this repository (and to the six other repos under
`~/projects/`, closing gaps where `.env` itself was unignored). `env.local` and `.env.local` were
already covered. **Verify rather than trust:**

```bash
git check-ignore -q .env .env.local '*.decrypted' && echo covered
```

⚠ The ordering still matters for anyone repeating this elsewhere: **ignore first, create second**, so
the window in which a decrypted file is committable never opens.

## 4. Split `env.local`

Per `13_security.md` §5.2. Current `env.local` holds **43 variables, 8 of them secret-class**.

> ⚠ **Superseded in two ways on 2026-08-21** — the plaintext half is **`.env.shared`** (`.env` is
> gitignored on purpose), and the encrypted half holds **11** variables, not 8 (**12 since 2026-08-24**,
> with `OPS_DB_PASSWORD`). The reasoning is in *What actually happened* above; the table below is kept
> as the original intent.

| Destination | Contents |
|---|---|
| `.env` — **committed, plaintext** | The other 35: `APP_ENV`, `AUTH_MODE`, `LOG_LEVEL`, ports, paths, `POSTGRES_HOST/DB/PORT/USER`, `REDIS_HOST/PORT/DB`, `FLASK_*`, `*_DIR`, `AWS_REGION`, `SMTP_SERVER/PORT` — **plus every comment and section header** |
| `secrets.enc.env` — **committed, SOPS-encrypted** | `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `OPENAI_API_KEY`, `HG_TOKEN`, `SMTP_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `DB_ENCRYPTION_KEY` |

⚠ **`SMTP_USERNAME` is secret-class**, per §5.2's rule — a username paired with a credential for the
same service. It goes in the encrypted half despite looking like configuration.

`.sops.yaml`:
```yaml
creation_rules:
  - path_regex: \.enc\.env$
    age: <your age public key>
```

### ⚠ 4a. `env.local` cannot be deleted — ten services read it

`docker-compose.yml` (×6) and `docker-compose.grm.yml` (×4) declare `env_file: env.local`. Containers
read that **file**, not the shell environment. So the end state is:

```
.env (committed)  +  secrets.enc.env (committed, encrypted)  →  generate env.local (gitignored, 0600)
```

`env.local` becomes a **build artefact**, not a source. Add a `make env-local` target that
regenerates it, and **do not** convert the ten `env_file:` declarations to `environment:` as part of
this work — that is a separate change with its own regression risk.

## 5. Verify before you touch staging or production

```bash
make wsl-up            # the stack must come up on a generated env.local
```

Then confirm the two things a split most commonly breaks:

1. **Nothing lost.** Diff the variable *names* of the generated file against the original — the
   count must match **what that host had before you started**, which is why step 1 of §5a backs it up.
   ⚠ **Do not hard-code a number here.** It was 43 on 2026-08-21 and is 45 today; a memorised count is
   how a dropped variable gets waved through. Compare **names**, never values, and never print a value.
2. **The encrypted file is actually encrypted.** `grep -c 'ENC\[' secrets.enc.env` must be non-zero,
   and `git show HEAD:secrets.enc.env` must not contain a readable value.

⚠ **Do not push to staging or production until the local stack is green.** Deploys there are
`git pull` + `compose up` on the box, so a broken `env.local` contract breaks the running system.

### ⚠⚠ 5a. Migrating staging and production — the step with no undo

**A single `secrets.enc.env` asserts that every host holds the same value for every secret.** That
is fine, even desirable, for most of them. For **one** it is **irreversible if the assertion is false**,
for **an unknown number of others** it is destructive in a different way — measured at **thirty** on
staging, unmeasured on prod — and for one it is inert-but-silent. None of the three raises an error.

#### Hazard 1 — one file carries one value

`make env-local` on a host **overwrites** that host's `DB_ENCRYPTION_KEY` with the one in
`secrets.enc.env`. If DOR prod's key differs from yours, every encrypted PII column on that box
becomes unreadable **permanently** — pgcrypto does not fail loudly here, and `base_manager.py`
**fails open** when decryption raises (DPG-04 finding). It looks like empty fields, not an outage.

`SEARCH_TOKEN_PEPPER` was listed here as having the same shape. ⚠ **Corrected 2026-08-24 — it is a
different and sneakier problem, because the variable does not exist.** It is absent from `env.local`,
`.env.shared` and `secrets.enc.env`, and `base_manager.py:557` reads
`os.getenv("SEARCH_TOKEN_PEPPER") or self.encryption_key` — **the same silent-fallback pattern that
blinded the ops monitor** (Hazard 3). So every stored lookup token today is derived from
`DB_ENCRYPTION_KEY`.

**The danger is therefore *introducing* the variable, not rotating it.** The first host that sets
`SEARCH_TOKEN_PEPPER` re-derives nothing: every existing token was built from the encryption key, so
phone and email lookup return **nothing, silently, raising no error** — it reads as "no such
complainant". Only `scripts/database/rehash_search_tokens.py`, run on that box in the same window,
repairs it. Treat setting it for the first time exactly like rotating it.

> ### ✅ VERIFIED FOR STAGING, 2026-08-24 — and this was the one that could not be undone
>
> Run over SSH against `ubuntu@52.76.171.73` (`integration/stage`) and compared with the local box:
>
> | Secret | Local | AWS staging | Verdict |
> |---|---|---|---|
> | `DB_ENCRYPTION_KEY` | `0be56b09e6dc3c62` | `0be56b09e6dc3c62` | ✅ **Identical.** The irreversible hazard is cleared **for staging** |
> | `SEARCH_TOKEN_PEPPER` | ⛔ absent | ⛔ absent | ✅ Consistent — see the correction below |
> | `OPS_DB_PASSWORD` | present | ⛔ absent | ~~Expected; staging runs no `ops` container~~ ⚠ **This row's justification expired on 2026-09-03**, when `ops` was deployed there and the absence stopped being harmless. **Now present on staging** (appended 2026-09-03, digest `1a5b66412c05bdc9` on both sides) — Hazard 3, closed for staging |
> | `POSTGRES_PASSWORD` | rotated 2026-08-21 | ⚠ **still the pre-rotation value**, confirmed by digest | Matches what `14_…` §1 records. This is open item 6 |
>
> ⚠ **DOR prod has NOT been checked** — no access from the development box. Until the same comparison
> is run there, Hazard 1 is open for prod and **only** for prod. Nothing below is safe to run on that
> host first.

⚠ **Prod remains unverified.** §5.3.1 records *that* copies exist on staging and prod; its own
header says values were never compared, and that check was across **repositories**, not across
these hosts. **Verify by hash on each host before deploying anything** — never by printing, pasting
or eyeballing a value:

⚠ **The command that used to be here was unsafe, and this is worth understanding before you trust
the replacement.** It piped `grep -oP '^VAR=\K.*'` into `sha256sum`. When the variable is **absent**,
grep matches nothing, `sha256sum` hashes the empty string, and you get `e3b0c442…` — *the same value
on every host that also lacks it*. Two hosts with no `SEARCH_TOKEN_PEPPER` produce identical hashes
and the table below says **"Safe to proceed"**. Verified 2026-08-24: that is exactly what it returned
locally. A check that cannot distinguish *matching* from *missing* is worse than no check, because it
is read as reassurance before a step with no undo.

Use this instead — it refuses to hash nothing. Run it **on each host and locally**, then compare:

```bash
# Paste this function on each host, then run the three lines under it.
hash_secret() {
  local name="$1" file="${2:-env.local}" val
  val="$(sed -n "s/^${name}=//p" "$file" | tr -d '"' | tr -d '\n')"
  if [ -z "$val" ]; then
    printf '%-22s ⛔ ABSENT OR EMPTY in %s — nothing to compare\n' "$name" "$file"
    return 1
  fi
  printf '%-22s %s\n' "$name" "$(printf '%s' "$val" | sha256sum | cut -c1-16)"
}

hash_secret DB_ENCRYPTION_KEY      # ⭐ irreversible if these differ
hash_secret SEARCH_TOKEN_PEPPER    # ⚠ expect ABSENT locally — see above
hash_secret OPS_DB_PASSWORD        # Hazard 3; recoverable, but check it
```

⚠ **Every host must run the identical function**, or you are comparing hashing conventions rather than
values — trailing newlines and quote stripping both change the digest.

| Result | Action |
|---|---|
| All hashes present **and** matching | Safe to proceed |
| **Any differ** | ⛔ **Stop.** One shared file cannot hold two values. You need a per-host encrypted file (`secrets.prod.enc.env`, its own recipient, its own `path_regex`) — **or** a planned re-encryption migration. Do **not** "just use the local one" |
| **`⛔ ABSENT` on some hosts but not others** | ⛔ **Stop, and do not read this as a match.** Whichever host *has* the value is the one whose behaviour differs; deciding which way to converge is a data question, not a config one. For `SEARCH_TOKEN_PEPPER` specifically, see the note above — introducing it anywhere requires the rehash script |
| **`⛔ ABSENT` everywhere** | Expected for `SEARCH_TOKEN_PEPPER` today. Record it and move on — but **do not add the variable as part of this migration** |

#### Hazard 2 — the generator writes `env.local` from scratch

`gen_env_local.sh` builds `env.local` from `.env.shared` + `secrets.enc.env` **only**. Anything
present in a host's current `env.local` and absent from those two halves is **silently dropped**.

> ### ⭐ MEASURED ON STAGING, 2026-08-24 — the number was not five, it was thirty
>
> This section previously named five host-only secrets from §5.3.1 and said `make env-local` would
> delete them. **That was inferred from an inventory, not measured against a host.** Read over SSH
> (names only, no values): staging's `env.local` holds **67 variables**; the two committed halves
> generate **45**. **Thirty names exist on staging and in neither half**, and two of the five this
> document named are **not on staging at all**.
>
> **`make env-local` on staging today would delete thirty variables**, of which four are credentials:
>
> | Deleted | What breaks |
> |---|---|
> | ⭐ **`DOIT_SMS_BEARER_TOKEN`** | **The production Nepal SMS gateway** (`sms.doit.gov.np`, `backend/config/sms_config.py:47`). ⚠ **This credential is in NEITHER inventory** — not §5.3.1, not `14_…` §1, not in any committed env file. Task zero's defect, recurring: a secret nobody is tracking |
> | `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_CLIENT_SECRET`, `KEYCLOAK_WEBHOOK_SECRET` | Officer login and onboarding. The three this document did get right |
> | `KEYCLOAK_ISSUER`, `KEYCLOAK_JWKS_URL`, `KEYCLOAK_ADMIN_URL`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_INVITE_*`, `KC_HOSTNAME_URL`, `KC_HTTP_RELATIVE_PATH`, `KEYCLOAK_HOST_PORT`, `NEXT_PUBLIC_OIDC_*`, `NEXT_PUBLIC_BYPASS_AUTH` | Not secrets — but auth stops working without them, and a "secrets migration" that silently deletes non-secret config is the same outage |
> | `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `SOCKETIO_REDIS_URL`, `DATABASE_*` (×5), `CHATBOT_WEBCHAT_URL`, `TICKETING_API_URL`-adjacent wiring, `SMS_ENABLED`, `SMS_PROVIDER`, `DOIT_SMS_BASE_URL`, `SMTP_FROM`, `SMTP_FROM_DISPLAY` | Runtime wiring |
>
> **Not on staging, though this document said they were:** `SEARCH_TOKEN_PEPPER` (absent everywhere —
> Hazard 1) and `MESSAGING_API_KEY` (absent). §5.3.1 rows 2 and 7 are wrong about staging.
>
> ⚠ **Do not replace "five" with "thirty" and move on.** The number is a property of that host on that
> day, and DOR prod has **not** been measured. The durable instruction is step 5 of *the order that is
> safe*: **run the name-parity dry run on the host you are about to touch, and read its output.**
>
> ### ✅ FOLDED IN, 2026-08-24 — staging's gap is 30 → 18, and the remaining 18 are deliberate
>
> `secrets.enc.env` went 12 → **17 keys**; `.env.shared` 33 → **40**; the generator now writes **57**
> variables. What moved, and what deliberately did not:
>
> | Bucket | Variables | Where |
> |---|---|---|
> | **Secret, shared** (5 new) | `DOIT_SMS_BEARER_TOKEN`, `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_CLIENT_SECRET`, `KEYCLOAK_WEBHOOK_SECRET`, `SMTP_FROM` | `secrets.enc.env` + `#@secret` marker |
> | **Secret, overwritten** (2) | `SMTP_USERNAME`, `SMTP_PASSWORD` — staging's mail config is authoritative, on the owner's instruction | `secrets.enc.env` |
> | **Non-secret, shared** (8) | `SMTP_SERVER` (overwritten), `SMTP_FROM_DISPLAY`, `SMS_PROVIDER`, `DOIT_SMS_BASE_URL`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_INVITE_CLIENT_ID`, `NEXT_PUBLIC_OIDC_CLIENT_ID`, `KEYCLOAK_HOST_PORT` | `.env.shared` |
> | ⛔ **Host-specific — must NOT be shared** (10) | `KEYCLOAK_ISSUER`, `KC_HOSTNAME_URL`, `KC_HTTP_RELATIVE_PATH`, `KEYCLOAK_ADMIN_URL`, `KEYCLOAK_JWKS_URL`, `KEYCLOAK_INVITE_REDIRECT_URI`, `NEXT_PUBLIC_OIDC_ISSUER`, `NEXT_PUBLIC_BYPASS_AUTH`, `SMS_ENABLED`, `CHATBOT_WEBCHAT_URL` | **`env.local.extra` on each host** — they encode that deployment's own hostname and auth mode. Putting staging's `nepal-gms-chatbot.facets-ai.com` in a shared file breaks local and prod |
> | ⛔ **Dead — do not propagate** (8) | `DATABASE_HOST/NAME/PASSWORD/PORT/USER`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `SOCKETIO_REDIS_URL` | Nowhere. ⚠ **`DATABASE_*` is read by no code** (`git grep` over `backend/ ticketing/ ops/ channels/ scripts/` is empty) and carries the stale `password` credential. The three Redis URLs are set by compose `environment:`, **which wins over `env_file:`** — and staging's copies carry **no** `REDIS_PASSWORD`, so propagating them would be a downgrade. Delete them from the host's `env.local` during the migration |
>
> ⚠ **`SMS_ENABLED` is host-specific for a reason worth stating:** staging has it `true`. A shared
> `true` would make every developer's stack send real SMS to Nepali phone numbers. Absent, the code
> falls back to `backend/config/constants.SMS_ENABLED` (`sms_config.py:58-63`).
>
> **Verified after the fold:** every folded value's digest matches staging's; `POSTGRES_PASSWORD` kept
> its **locally rotated** value and was *not* clobbered by staging's pre-rotation one;
> `make keycloak-setup` runs clean; 14/14 containers healthy.
>
> ⚠ **One consequence to decide on, not an accident:** `KEYCLOAK_ADMIN_PASSWORD`,
> `KEYCLOAK_CLIENT_SECRET` and `KEYCLOAK_WEBHOOK_SECRET` are now **one value across local, staging and
> prod**, because that is what a single `secrets.enc.env` means. For an IdP admin credential that is a
> real blast-radius question — a leak anywhere grants everywhere. The alternative is Hazard 1's
> per-host encrypted file. **This needs an owner's decision before prod.**

⚠ **Some variables live only on staging and prod and are NOT in `secrets.enc.env`.** Running
`make env-local` on those hosts deletes every one of them, silently. The measured list for staging is
above; **prod is unmeasured**. ⚠ `MESSAGING_API_KEY` — which guards `GET /api/grievance/{id}`, serving
plaintext PII — is in §5.3.1 as a host-only secret but is **absent from staging**, so it is presumably
prod-only or stale; find out before you generate anything there.

> **`OPS_DB_PASSWORD` is not in this hazard.** It is now **in** `secrets.enc.env`, so it cannot be
> dropped here — it moved to Hazard 3, which is a different problem with the opposite sign. Counting it
> in both places would be worse than counting it in neither.

#### Hazard 3 — a secret can arrive without the thing it unlocks (`OPS_DB_PASSWORD`, new 2026-08-24)

Hazards 1 and 2 are about **values being overwritten or dropped**. This one is the inverse: the value
arrives correctly and still does nothing, because **a database role's password lives in the database,
per host** — publishing the secret does not set the role.

`make env-local` will put `OPS_DB_PASSWORD` on staging and prod. Until someone also runs
`ALTER ROLE ops_app PASSWORD` **on that box** to the same value, `ops` there cannot authenticate.

⚠ **This is not theoretical — it is exactly what happened locally**, for the adjacent reason: `ops`
had no secret of its own and silently fell back to `POSTGRES_PASSWORD`, that was rotated without
`ops_app`, and monitoring went blind for three days while the container reported `healthy`. See
[`ops-cannot-authenticate-since-rotation.md`](../sprints/2026-08-llm/followups/ops-cannot-authenticate-since-rotation.md).

**Two things make this much less dangerous than Hazards 1 and 2, and one makes it easy to miss:**

- ✅ **Fully recoverable** — re-run the `ALTER ROLE`. No data is lost, only unmonitored time.
- ~~✅ **`ops` runs on neither server today**, so nothing breaks on the next deploy.~~
  🔴 **FALSE from 2026-09-03, and this is the line that let it through.** `ops` is in
  `AWS_DEPLOY_SERVICES`, so the ordinary `make aws-deploy` shipped it to staging — no separate
  decision, no prompt. The reassurance was written as a statement of fact about the world, and the
  world changed without anyone editing it. ⭐ **A precondition that no test enforces is a comment
  with a shelf life.** DOR prod still does not run `ops`; that is the only half still standing.
- ⚠ **And nothing told anyone.** Step 7 below was never run — because this bullet said it did not
  apply. Measured on staging after five hours: **309 consecutive healthcheck failures,
  `ops.system_health_checks` with `health_rows=0`**, every job logging `executed successfully`.
  A monitor that cannot see is indistinguishable from a monitor with nothing to report — and that is
  not a hypothetical in this document any more, it is the second time it has happened here.

Full procedure: [`14_… §5.1`](14_key_and_secret_lifecycle.md).

#### The order that is safe

1. **Back up the host's `env.local` first** — `cp env.local env.local.pre-sops && chmod 600 …`, off-box too. It is gitignored, so there is no other copy.
2. Compare the two hashes above. Stop if they differ.
3. Add **every host-only variable the step-5 dry run reports as missing** to `secrets.enc.env` (secrets) or `.env.shared` (non-secrets), via `make secrets-edit` / an edit, **before** generating anything. ⚠ **Do not work from a list in this document** — it said five, and staging measured thirty.
4. Give the host **its own age keypair** and add it as a recipient — `sops updatekeys secrets.enc.env`. ⚠ Do not copy your personal key onto a server (§5.2).
5. **Dry-run the parity check** — generate into a scratch directory and diff the variable **names**
   against the live file. Zero missing names, or stop.

   ⚠ **The command printed here until 2026-08-24 did not work.** It was
   `scripts/ops/gen_env_local.sh /tmp/drill`, but that argument is the **repo directory** the script
   reads its two halves *from*, not an output directory — so it died with
   `missing /tmp/drill/.env.shared` and the `&&` swallowed the diff. Copy the halves in first:

   ```bash
   rm -rf /tmp/drill && mkdir -p /tmp/drill
   cp .env.shared secrets.enc.env /tmp/drill/
   scripts/ops/gen_env_local.sh /tmp/drill

   diff <(grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' env.local        | sort) \
        <(grep -oE '^[A-Za-z_][A-Za-z0-9_]*=' /tmp/drill/env.local | sort)
   ```

   Empty diff = no name gained or lost. ⚠ **Then delete the scratch copy** — it holds a plaintext
   `env.local`: `rm -rf /tmp/drill`.
6. Only then `make env-local`, then restart the stack.
7. **If (and only if) this host runs `ops`** — today neither does: set the role to match the secret,
   run the ops migrations, and **verify**. Three commands, in
   [`14_… §5.1`](14_key_and_secret_lifecycle.md).
   `python -m ops.selfcheck` exiting 0 is the only evidence that it worked; the container reporting
   `healthy` was not, until 2026-08-24.

## 6. The rotation pass

Every credential's "last rotated" date is **unknown**, which means treat as never. Do this **after**
the migration, so each rotation is a single edit to `secrets.enc.env`.

Order by value at risk, and **check `14_key_and_secret_lifecycle.md` §1 for impact-if-lost before
each one**:

1. `AWS_SECRET_ACCESS_KEY` — IAM → create new → update → **delete old**
2. `HG_TOKEN` — ⚠ also re-paste the **GitHub Actions secret `HF_TOKEN`**; it is the same credential
3. `OPENAI_API_KEY`
4. `SMTP_PASSWORD`
5. ~~`POSTGRES_PASSWORD`, `REDIS_PASSWORD`~~ ✅ **rotated locally — 2026-08-21 and 2026-08-23** (`14_…` §1 carries the dates and the reason each was rotated). ⚠ **Staging and DOR prod still hold both old values, and `REDIS_PASSWORD`'s previous value is in public git history** — rotating them there is part of the host migration, not of this pass. Coordinate with a stack restart. ⚠ **`ops_app` is a separate role with a separate password** (`OPS_DB_PASSWORD`) and is **not** carried along by this rotation. That coupling used to exist implicitly, and rotating `POSTGRES_PASSWORD` on 2026-08-21 blinded the monitor for three days because of it — see §5a Hazard 3. It is fixed; do not recreate it by leaving `OPS_DB_PASSWORD` unset on a host that runs `ops`.

### ⚠ Two that are NOT in the pass

- **`DB_ENCRYPTION_KEY` has no rotation path.** Every pgcrypto value must be decrypted with the old
  key and re-encrypted with the new, and **no script exists**. It is a migration, not a rotation.
  Leave it. Losing it means permanent PII loss (§14 §2).
- **`SEARCH_TOKEN_PEPPER` invalidates every stored lookup token** — and ⚠ **it is not set anywhere,
  so the operation to fear is *setting* it, not rotating it** (§5a Hazard 1, corrected 2026-08-24).
  `base_manager.py:557` falls back to `DB_ENCRYPTION_KEY`, so every token in the database today was
  derived from that key. The first host to define `SEARCH_TOKEN_PEPPER` orphans all of them.
  Either way `scripts/database/rehash_search_tokens.py` **must** run on that box in the same
  maintenance window. Skipping it makes phone and email lookup return nothing — **silently, raising
  nothing**. It reads as "no such complainant".

## 7. ⚠ Things that look like defects and are not — do not "fix" them

| Looks wrong | It is correct |
|---|---|
| `TICKETING_SECRET_KEY` is **empty** in `env.local` | The dev bypass (`APP_ENV=dev` + `AUTH_MODE=bypass`) is active locally. It **fails closed** elsewhere — `backend/api/routers/grievance.py` raises without a key. Checked 2026-08-20 |
| `.env.open` and `.env.openai` are **tracked** | Deliberate (DPG-16). They are secret-free templates and the `diff` between them is the DPG indicator-4 evidence. A test asserts neither carries a key |
| `.env.example` is **tracked** and lists secret names | Generated from `declared_env_vars()` and pinned both ways by a test. ⚠ **If you add a variable, that test fails until `.env.example` is updated.** ⚠ **"Names only" is not quite true — corrected 2026-08-24:** line 29 is `POSTGRES_PASSWORD=password`, a *value*, and it is byte-identical to the credential still live on staging and DOR prod. It reads as an innocuous template default, which is exactly why it survived. See the re-check note in *What actually happened* |
| `NEXT_PUBLIC_*` in `channels/ticketing-ui/.env.local` | Public by contract — they ship to the browser. They belong in the plaintext half |

## 8. Definition of done

- [x] The two inventories reconciled — one authority, the other points at it (Task zero)
- [x] `sops` + `age` installed, **provenance verified**; keypair in the **WSL/ext4** filesystem
- [ ] ⚠ **age private key backed up to Proton Pass + paper** — *the one urgent item*
- [x] `.gitignore` covers `*.decrypted` (and now `env.local.extra`)
- [x] `.env.shared` (plaintext, committed) + `secrets.enc.env` (encrypted, committed) + `.sops.yaml`
      — ⚠ **`.env.shared`, not `.env`**; see *What actually happened*
- [x] `make env-local` regenerates a working `env.local`; `make wsl-up` green on it (14/14 healthy)
- [x] All 43 variable names present after the split — and every value byte-identical, verified by
      comparison, never printed *(45 as of 2026-08-24; the number moves, the check does not)*
- [x] `secrets.enc.env` verified encrypted **in the committed object**, not just on disk
- [ ] Rotation pass complete for the five in §6, with dates recorded in `14_…` §1
      — ✅ **`POSTGRES_PASSWORD` (08-21) and `REDIS_PASSWORD` (08-23) done locally**; the compose-password
      blocker that held them is fixed. ⚠ **The four external-console credentials (AWS, HG, OPENAI, SMTP)
      are still "unknown — treat as never"**, and neither server is rotated at all
- [x] `DB_ENCRYPTION_KEY` and `SEARCH_TOKEN_PEPPER` **deliberately skipped**, and that recorded
      (`14_…` §3)
- [ ] Staging and production migrated only after local is green — **local is green; hosts not started**
- [x] ✅ **§5a Hazard 1 run on AWS staging, 2026-08-24** — `DB_ENCRYPTION_KEY` identical to local, so the
      irreversible hazard is cleared **for staging**. ⚠ **DOR prod not run — no access from the dev box**
- [ ] ⚠ **§5a run on each host before any deploy**: host `env.local` backed up; `hash_secret` run for
      `DB_ENCRYPTION_KEY`, `SEARCH_TOKEN_PEPPER` and `OPS_DB_PASSWORD` — ⚠ **using the fail-loud
      function, not the old grep-into-sha256sum, which reported a match on absent variables**; the
      **every variable the dry run reports missing** added to `secrets.enc.env` (secrets) or `.env.shared`
      (non-secrets) — ⚠ **measured at thirty on staging, not the five this document used to claim**; and the
      name-parity dry run re-run clean afterwards
- [x] ⚠ **If `ops` is ever deployed to a host**: `ALTER ROLE ops_app`, ops migrations, and
      `python -m ops.selfcheck` exiting 0 — §5a Hazard 3 and [`14_…`](14_key_and_secret_lifecycle.md) §5.1
      — ⭐ **done on AWS staging 2026-09-03**, *after* the deploy had already put `ops` there and left it
      blind for five hours (`health_rows=0`, 309 failing checks). `selfcheck` exit 0; first five rows all
      `ok` three minutes later. ⚠ **Open for DOR prod**, which does not run `ops` yet — the same sentence
      that was true of staging until the morning of the day it wasn't
- [x] `Last rotated` recorded as *"unknown — treat as never"* — in **`14_…` §1**, not §5.3.1

## 9. ⚠ Never

- Print, echo, log or commit a secret **value** — including in a commit message or a test fixture
- Put the age private key on `/mnt/` anything
- Rotate `DB_ENCRYPTION_KEY` without a re-encryption plan
- Rotate `SEARCH_TOKEN_PEPPER` without running the rehash script in the same window
- Deploy a split to production before the local stack is green on it
- ⚠ **Run `make env-local` on staging or production before §5a's two hash checks pass** — a mismatched
  `DB_ENCRYPTION_KEY` is permanent PII loss, and it fails **open and silent**, not loud
- ⚠ **Overwrite a host's `env.local` without backing it up first** — **thirty** variables exist only on staging, four of them credentials, and prod is unmeasured
- ⚠ **Trust a hash comparison that did not use `hash_secret`** — the older one-liner hashes the empty
  string when a variable is absent, so two hosts that both lack it "match" (§5a Hazard 1)
- ⚠ **Introduce `SEARCH_TOKEN_PEPPER` on any host without running the rehash script in the same
  window** — it is unset everywhere today, so *adding* it is the destructive operation, not rotating it
