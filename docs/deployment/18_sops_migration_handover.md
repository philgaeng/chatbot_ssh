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
| 0 · Task zero | Reconciled. [`14_…`](14_key_and_secret_lifecycle.md) §1 is now the **single authority** (15 rows, one per secret, with impact + cadence + procedure + `Last rotated`); [`13_security.md`](13_security.md) §5.3.1 keeps location columns only and points at it |
| 1 · Tooling | `sops` 3.13.3 + `age` 1.1.1 in `~/.local/bin` (no sudo). **Provenance verified** — sops against its published `checksums.txt`, age against the **GPG-signed Ubuntu archive index** |
| 2 · Keypair | `~/.config/sops/age/keys.txt`, mode 0600, dir 0700, on **ext4** (checked `df -T`, and that the path does not resolve under `/mnt`). Public key `age1ke0hk5e…rz95h` |
| 3 · `.gitignore` | Verified, plus `env.local.extra` added (see below) |
| 4 · Split | `.env.shared` (32 vars, committed plaintext) + `secrets.enc.env` (11 vars, SOPS) + `.sops.yaml`; `make env-local` / `make secrets-edit`; generator `scripts/ops/gen_env_local.sh` |
| 5 · Verify | `make wsl-up` green — **14/14 containers healthy**, 0 compose "variable is not set" warnings; regenerated `env.local` has **all 43 names and every value identical** to the pre-migration file; regeneration is idempotent |

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
   authentication principals.
3. **Task zero says five rows are missing from §14. It is six** — `KEYCLOAK_CLIENT_SECRET` was absent
   from both lists' reconciliation notes. This is the defect the section is about, one level down.
4. **The DoD asked for `Last rotated` in §5.3.1 *and* for §5.3.1 to stop owning rotation.** Those
   contradict. `Last rotated` is rotation state, so it went to §14 §1 with the rest.

### ⚠ And one thing that was worse than anything this migration fixed — ✅ now fixed locally

> **Resolved 2026-08-21**, after this section was written and because of it. All 19 compose literals
> (including **Keycloak's `KC_DB_*`**, which the count below misses) now interpolate from `env.local`
> with `${VAR:?}`; the credential is **rotated**; the literal is gone from all six tracked files; and
> `security-preflight.sh` checks what a **container** resolves rather than the inert copy. ⚠ **Staging
> and DOR prod are not done and will fail to start on the next deploy** — see the coordinated runbook in
> [`db-password-hardcoded-in-compose.md`](../sprints/followups/db-password-hardcoded-in-compose.md).
> The description below is kept as the finding, in its original terms.

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
| 4 | Migrate **staging** and **DOR prod**: install sops+age, generate a **per-server keypair**, add it as a recipient (`sops updatekeys`), then `make env-local`. ⚠ Six secrets (§5.3.1 rows 2, 4, 7–10) exist **only** on those hosts and are **not** in `secrets.enc.env` yet | you |
| 5 | ~~The compose-password fix above~~ ✅ **done locally 2026-08-21** — ⚠ but it makes item 4 a **prerequisite for the next deploy**, not a nice-to-have: `${VAR:?}` stops the stack when the value is missing, and neither host can run `make env-local` until its age key is a recipient | deployment |

⚠ **Nothing has been pushed to staging or production.** Local only, on `dpg/sprint2-open-models` — and that is now load-bearing rather than incidental: the compose change in item 5 is **breaking for any host whose database still holds the old credential**, which is both of them.

---

## 0. Read these first, in this order

1. [`13_security.md`](13_security.md) **§5** — the decided approach. **Do not re-litigate it.** SOPS +
   age, no hosted vault, platform-native stores where the platform issues the credential.
2. [`14_key_and_secret_lifecycle.md`](14_key_and_secret_lifecycle.md) — the **operational** doc for
   this project's secrets: impact-if-lost, impact-if-leaked, rotation cadence, backup.
3. [`../../CLAUDE.md`](../../CLAUDE.md) §Docker-only, §Environment variables.

### ⚠ Task zero — there are now TWO inventories, and that is a defect

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

Neither `sops` nor `age` is installed. Verify with `which sops age`.

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
> gitignored on purpose), and the encrypted half holds **11** variables, not 8. The reasoning is in
> *What actually happened* above; the table below is kept as the original intent.

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
   count must be 43. ⚠ Compare **names**, never values, and never print a value.
2. **The encrypted file is actually encrypted.** `grep -c 'ENC\[' secrets.enc.env` must be non-zero,
   and `git show HEAD:secrets.enc.env` must not contain a readable value.

⚠ **Do not push to staging or production until the local stack is green.** Deploys there are
`git pull` + `compose up` on the box, so a broken `env.local` contract breaks the running system.

### ⚠⚠ 5a. Migrating staging and production — the step with no undo

**A single `secrets.enc.env` asserts that every host holds the same value for every secret.** That
is fine, even desirable, for most of them. For two it is **irreversible if the assertion is false**,
and for six more it is destructive in a different way. Neither failure raises an error.

#### Hazard 1 — one file carries one value

`make env-local` on a host **overwrites** that host's `DB_ENCRYPTION_KEY` with the one in
`secrets.enc.env`. If DOR prod's key differs from yours, every encrypted PII column on that box
becomes unreadable **permanently** — pgcrypto does not fail loudly here, and `base_manager.py`
**fails open** when decryption raises (DPG-04 finding). It looks like empty fields, not an outage.

`SEARCH_TOKEN_PEPPER` has the same shape with a quieter failure: phone and email lookup return
nothing, silently, and only `scripts/database/rehash_search_tokens.py` can rebuild the tokens.

⚠ **This is unverified today.** §5.3.1 records *that* copies exist on staging and prod; its own
header says values were never compared, and that check was across **repositories**, not across
these hosts. **Verify by hash on each host before deploying anything** — never by printing, pasting
or eyeballing a value:

```bash
# run ON each host, and locally, then compare the three hashes
grep -oP '^DB_ENCRYPTION_KEY=\K.*'  env.local | tr -d '"' | sha256sum
grep -oP '^SEARCH_TOKEN_PEPPER=\K.*' env.local | tr -d '"' | sha256sum
```

| Result | Action |
|---|---|
| All hashes match | Safe to proceed |
| **Any differ** | ⛔ **Stop.** One shared file cannot hold two values. You need a per-host encrypted file (`secrets.prod.enc.env`, its own recipient, its own `path_regex`) — **or** a planned re-encryption migration. Do **not** "just use the local one" |

#### Hazard 2 — the generator writes `env.local` from scratch

`gen_env_local.sh` builds `env.local` from `.env.shared` + `secrets.enc.env` **only**. Anything
present in a host's current `env.local` and absent from those two halves is **silently dropped**.

⚠ **Six secrets live only on staging and prod and are NOT in `secrets.enc.env`** — §5.3.1 rows 2, 4,
7, 8, 9, 10 (`SEARCH_TOKEN_PEPPER`, `OPS_DB_PASSWORD`, `MESSAGING_API_KEY`,
`KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_CLIENT_SECRET`, `KEYCLOAK_WEBHOOK_SECRET`). Running
`make env-local` on those hosts today would **delete all six**. Officer login and the Messaging API
break; ⚠ `MESSAGING_API_KEY` also guards `GET /api/grievance/{id}`, which serves plaintext PII.

#### The order that is safe

1. **Back up the host's `env.local` first** — `cp env.local env.local.pre-sops && chmod 600 …`, off-box too. It is gitignored, so there is no other copy.
2. Compare the two hashes above. Stop if they differ.
3. Add the six host-only secrets to `secrets.enc.env` (`make secrets-edit`) **before** generating anything.
4. Give the host **its own age keypair** and add it as a recipient — `sops updatekeys secrets.enc.env`. ⚠ Do not copy your personal key onto a server (§5.2).
5. **Dry-run the parity check** — generate to a temp path and diff the variable **names** against the live file. Zero missing names, or stop:
   ```bash
   scripts/ops/gen_env_local.sh /tmp/drill &&      diff <(grep -oE '^[A-Za-z_]+=' env.local | sort) <(grep -oE '^[A-Za-z_]+=' /tmp/drill/env.local | sort)
   ```
6. Only then `make env-local`, then restart the stack.

## 6. The rotation pass

Every credential's "last rotated" date is **unknown**, which means treat as never. Do this **after**
the migration, so each rotation is a single edit to `secrets.enc.env`.

Order by value at risk, and **check `14_key_and_secret_lifecycle.md` §1 for impact-if-lost before
each one**:

1. `AWS_SECRET_ACCESS_KEY` — IAM → create new → update → **delete old**
2. `HG_TOKEN` — ⚠ also re-paste the **GitHub Actions secret `HF_TOKEN`**; it is the same credential
3. `OPENAI_API_KEY`
4. `SMTP_PASSWORD`
5. `POSTGRES_PASSWORD`, `REDIS_PASSWORD` — coordinate with a stack restart

### ⚠ Two that are NOT in the pass

- **`DB_ENCRYPTION_KEY` has no rotation path.** Every pgcrypto value must be decrypted with the old
  key and re-encrypted with the new, and **no script exists**. It is a migration, not a rotation.
  Leave it. Losing it means permanent PII loss (§14 §2).
- **`SEARCH_TOKEN_PEPPER` invalidates every stored lookup token.** If it is rotated,
  `scripts/database/rehash_search_tokens.py` **must** run on that box in the same maintenance
  window. Skipping it makes phone and email lookup return nothing — **silently, raising nothing**.

## 7. ⚠ Things that look like defects and are not — do not "fix" them

| Looks wrong | It is correct |
|---|---|
| `TICKETING_SECRET_KEY` is **empty** in `env.local` | The dev bypass (`APP_ENV=dev` + `AUTH_MODE=bypass`) is active locally. It **fails closed** elsewhere — `backend/api/routers/grievance.py` raises without a key. Checked 2026-08-20 |
| `.env.open` and `.env.openai` are **tracked** | Deliberate (DPG-16). They are secret-free templates and the `diff` between them is the DPG indicator-4 evidence. A test asserts neither carries a key |
| `.env.example` is **tracked** and lists secret names | Names only, generated from `declared_env_vars()` and pinned both ways by a test. ⚠ **If you add a variable, that test fails until `.env.example` is updated** |
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
      comparison, never printed
- [x] `secrets.enc.env` verified encrypted **in the committed object**, not just on disk
- [ ] Rotation pass complete for the five in §6, with dates recorded in `14_…` §1
      — ⚠ **blocked on the compose-password fix for `POSTGRES_PASSWORD`**
- [x] `DB_ENCRYPTION_KEY` and `SEARCH_TOKEN_PEPPER` **deliberately skipped**, and that recorded
      (`14_…` §3)
- [ ] Staging and production migrated only after local is green — **local is green; hosts not started**
- [ ] ⚠ **§5a run on each host before any deploy**: `DB_ENCRYPTION_KEY` + `SEARCH_TOKEN_PEPPER`
      hashes compared, host `env.local` backed up, the six host-only secrets added to
      `secrets.enc.env`, and the name-parity dry run clean
- [x] `Last rotated` recorded as *"unknown — treat as never"* — in **`14_…` §1**, not §5.3.1

## 9. ⚠ Never

- Print, echo, log or commit a secret **value** — including in a commit message or a test fixture
- Put the age private key on `/mnt/` anything
- Rotate `DB_ENCRYPTION_KEY` without a re-encryption plan
- Rotate `SEARCH_TOKEN_PEPPER` without running the rehash script in the same window
- Deploy a split to production before the local stack is green on it
- ⚠ **Run `make env-local` on staging or production before §5a's two hash checks pass** — a mismatched
  `DB_ENCRYPTION_KEY` is permanent PII loss, and it fails **open and silent**, not loud
- ⚠ **Overwrite a host's `env.local` without backing it up first** — six secrets exist only there
