# Handover — migrate this project's secrets to SOPS + age, and rotate

> **For:** an agent or engineer picking this up cold.
> **Scope:** **`nepal_chatbot` only.** The policy in
> [`13_security.md`](13_security.md) §5 covers every repository under `~/projects/`; this document is
> the slice for this one, so the issue can be closed here without waiting on the others.
> **Written:** 2026-08-20. **Status:** ⬜ not started.
> **Prerequisite that is not yours:** the owner answers the `TBC` cells in `13_security.md` §5.3.1.
> You can do steps 1–4 without them; step 6 needs them.

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

- [ ] The two inventories reconciled — one authority, the other points at it (Task zero)
- [ ] `sops` + `age` installed; keypair in the **WSL** filesystem; backed up to Proton Pass + paper
- [ ] `.gitignore` covers `*.decrypted`
- [ ] `.env` (plaintext, committed) + `secrets.enc.env` (encrypted, committed) + `.sops.yaml`
- [ ] `make env-local` regenerates a working `env.local`; `make wsl-up` green on it
- [ ] All 43 variable names present after the split — verified by name, never by value
- [ ] `secrets.enc.env` verified encrypted **in the committed object**, not just on disk
- [ ] Rotation pass complete for the five in §6, with dates recorded in `14_…` §1
- [ ] `DB_ENCRYPTION_KEY` and `SEARCH_TOKEN_PEPPER` **deliberately skipped**, and that recorded
- [ ] Staging and production migrated only after local is green
- [ ] `13_security.md` §5.3.1 `Last rotated` cells filled — *"unknown, treat as never"* is a valid
      entry for anything not rotated

## 9. ⚠ Never

- Print, echo, log or commit a secret **value** — including in a commit message or a test fixture
- Put the age private key on `/mnt/` anything
- Rotate `DB_ENCRYPTION_KEY` without a re-encryption plan
- Rotate `SEARCH_TOKEN_PEPPER` without running the rehash script in the same window
- Deploy a split to production before the local stack is green on it
