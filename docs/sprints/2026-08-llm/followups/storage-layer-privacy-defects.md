# Follow-up — three privacy defects in the storage layer

> **Raised:** 2026-08-18, while writing [`docs/dpg/privacy-assessment.md`](../../../dpg/privacy-assessment.md) (DPG-04).
> **Deferred from:** DPG-04 · logged as deviation **D-19** in [`../PROGRESS.md`](../PROGRESS.md) ·
> registered as **F-2, F-3, F-4** in the assessment's §6.
> **Status:** 🔵 open · **Size:** M each, S to schedule together
> **Deadline that matters:** ⭐ **before go-live**, not before submission — see §Why the clock matters.

---

## Why these are one document and not three

They were found in a single pass and they have a single root cause: **`backend/services/database_services/`
was never privacy-reviewed.** Every existing privacy document in this repository —
[`09_privacy.md`](../../../deployment/09_privacy.md), [`13_security.md`](../../../deployment/13_security.md),
the SEAH vault specs — describes the *architecture*: which schema owns what, who may decrypt, where the
boundary sits. All of that is accurate, and the architecture is genuinely good.

**None of them describes what the storage layer does when something goes wrong.** That is where all three
of these live, and it is why no spec had any of them. They surfaced only because DPG-04's data-flow
diagram was built by reading the code rather than by reading the specs — which is the transferable lesson
and is stated as such in the assessment.

Fix them together, in one pass, by someone holding the whole file. Fixing one at a time means three
passes over `base_manager.py` and three chances to reintroduce the next.

---

## F-2 — Encryption at rest fails open

**`backend/services/database_services/base_manager.py:243-252`**

```python
def _encrypt_field(self, value: str) -> Optional[str]:
    if not value or not self.encryption_key:
        return value                 # ← plaintext, silently
    try:
        ...
    except Exception as e:
        self.logger.error(f"Error encrypting field: {str(e)}")
        return value                 # ← plaintext, silently
```

Two paths return the **plaintext value unchanged**: no key configured, and any exception from the
pgcrypto call. The error path logs and then lets the write proceed.

**Why it matters.** `DB_ENCRYPTION_KEY` unset is not a hypothetical — the constructor only
`logger.warning`s about it (`:60-64`), so a deployment missing the key boots, works, and stores
complainant names, phones, emails and addresses in the clear. **Nothing downstream can tell the
difference:** `_decrypt_field` mirrors the behaviour, returning its input unchanged when there is no
key, so reads look correct. The column contains plaintext, the application is happy, and the only
evidence is a warning in a log nobody reads.

Worse in the exception case: a transient pgcrypto failure writes one plaintext row into an otherwise
encrypted column. There is no way to find those rows afterwards except by inspecting every value.

**Blast radius of the fix.** A key-presence assertion at construction makes the service **refuse to
boot** without a key. That is the correct behaviour and it is a fail-closed change to a stable shared
service — it must not surprise anyone mid-deploy. `HR-01` already established the fail-closed pattern
for auth; this is the same argument applied to encryption, and it should reuse that mechanism
(`APP_ENV`, refuse outside `dev`).

**Definition of done**

- [ ] `DB_ENCRYPTION_KEY` absent → the service refuses to start outside `APP_ENV=dev`, with a message
      naming the variable
- [ ] An encryption failure **raises** rather than returning plaintext — a failed write is recoverable,
      a silent plaintext write is not
- [ ] A test that pins both: no key ⇒ boot fails; pgcrypto raises ⇒ the write raises, not succeeds
- [ ] Decide and document what happens in `dev` — plaintext is acceptable there, but say so in the code
      rather than leaving it as a fallthrough
- [ ] **Check for existing plaintext rows** before assuming the fix is forward-only. Cheap while the
      data is synthetic (§0.5); not cheap later

---

## F-3 — Search tokens are unsalted SHA-256 of PII

**`base_manager.py:502-511`**, consumed at `complainant_manager.py:121` and `grievance_manager.py:537`

```python
def _hash_value(self, value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()
```

Applied to `HASHED_FIELDS` = phone, email, full name, address, stored as `complainant_*_hash` and used
for lookup (`WHERE complainant_phone_hash = %s`).

**Why it matters.** A Nepali mobile number is `+977` plus a 10-digit number with a small set of valid
prefixes. That search space is exhaustible in seconds on a laptop. **An unsalted hash of a phone number
is not a pseudonym; it is a reversible encoding of the phone number.** The same argument applies with
less force to names and addresses, and with more force to email if the domain is guessable.

So `public.complainants` has a column that reads as protected, is treated as protected, and is
recoverable to plaintext by anyone who obtains a database dump — including anyone who obtains the
**unencrypted backup** in F-4. The two findings compound.

The assessment states this as: *these columns are personal data, not pseudonyms.* Any future claim that
the platform pseudonymises contact details must exclude them.

**Blast radius of the fix.** This is the largest of the three. A per-value salt breaks the equality
lookup the columns exist for. The realistic options, in rough order of preference:

1. **Keyed hash (HMAC-SHA256 with a server-side pepper).** Preserves the equality lookup exactly —
   `WHERE hash = HMAC(key, value)` still works — and makes brute force require the key. Migration
   rewrites every hash column once. **This is almost certainly the right answer**; the key can be the
   existing secret-management path (`14_key_and_secret_lifecycle.md`).
2. Encrypted-index / deterministic-encryption approaches — more machinery, no real gain over (1) here.
3. Drop the hash columns and search on decrypted values — simplest, but moves decryption into the
   search path, which the T3-04 boundary work deliberately narrowed. **Do not do this without re-reading
   that decision.**

**Definition of done**

- [ ] A keyed construction (or an argued alternative) replacing bare SHA-256, with the key in the
      documented secret path — and a note on what rotating it costs
- [ ] Migration rewriting existing `*_hash` values, in the `migrations/public/` stream
- [ ] Every lookup site updated together — `complainant_manager.py:92,121`, `grievance_manager.py:495,537`
- [ ] A test pinning that a known phone number does **not** hash to its bare SHA-256
- [ ] `docs/deployment/09_privacy.md` updated: these columns' status changes, and the reason moves with it
- [ ] The privacy assessment's F-3 and §1.2 row updated to match

---

## F-4 — Backups are unencrypted by default

**`scripts/ops/backup_db.sh:45-60`**

`pg_dump -Fc app_db` plus a tar of the uploads volume, written to `/var/backups/grms`, retained 14
days. GPG (asymmetric) or passphrase (symmetric) encryption runs **only if `BACKUP_GPG_RECIPIENT` or
`BACKUP_PASSPHRASE` is set**; neither has a default. The off-box copy (`BACKUP_REMOTE`) is likewise
optional, and **its destination is not recorded anywhere in this repository** — which is why the
assessment marks the backup jurisdiction `⚠ Not verified`.

**Why it matters.** The four contact columns stay ciphertext inside the dump, because pgcrypto encrypts
at the column level — that part is fine, and worth saying. **Everything else does not:**
`grievance_description` in full, every officer note, every case timeline, every resolution, and — via
the uploads tar — **every voice recording and photograph**. For a SEAH case that is the disclosure
itself, in the clear, on the host filesystem.

F-3 compounds it: the same dump carries reversible phone hashes.

**Blast radius of the fix.** Small technically, real operationally: encryption without key custody is
theatre, and a backup you cannot decrypt during an incident is worse than one you can. The decision
that must be made first is **who holds the restore key and where**, which is
[`14_key_and_secret_lifecycle.md`](../../../deployment/14_key_and_secret_lifecycle.md)'s territory.

**Definition of done**

- [ ] Encryption **on by default**; the script refuses to write an unencrypted dump outside an explicit
      opt-out flag, rather than silently degrading
- [ ] Key custody decided and written down — who can restore, from where, and how that is tested
- [ ] A **restore rehearsal**, because an untested backup is a belief
- [ ] The off-box destination and its **jurisdiction** named in
      [`12_environment_urls.md`](../../../deployment/12_environment_urls.md) or the ops spec — the
      assessment cannot close L11 without it
- [ ] `ops/checks.py::backup_status_check` surfaces "last backup was unencrypted" as a finding, so a
      regression is visible rather than silent

---

## Why the clock matters

⭐ **No genuine grievance has been processed on this platform yet** — every record is AI-generated seed
data or a demo dummy (assessment §0.5, owner-confirmed 2026-08-18). So none of these three has caused
harm, and all three are currently **ordinary engineering tasks**.

That stops being true on first production use. After go-live:

- F-2 means an unknown number of plaintext PII rows you cannot identify without scanning every value.
- F-3 means every historical hash is a recoverable phone number, and re-keying is a migration over live data.
- F-4 means real SEAH disclosures sit in 14 days of rolling unencrypted backups, and the remediation is
  a breach assessment rather than a patch.

**Schedule these before go-live, not before submission.** The DPG submission can honestly disclose them
as known and scheduled — the assessment already does. What it cannot do is disclose them as known,
scheduled, and then have them still be open when real complainants arrive.

## Related

- [`docs/dpg/privacy-assessment.md`](../../../dpg/privacy-assessment.md) §6 — F-2, F-3, F-4; §0.5 — the clock
- [`../PROGRESS.md`](../PROGRESS.md) — deviation **D-19**
- [`docs/deployment/14_key_and_secret_lifecycle.md`](../../../deployment/14_key_and_secret_lifecycle.md) — key custody for F-2 and F-4
- [`docs/deployment/09_privacy.md`](../../../deployment/09_privacy.md) — must be updated by F-3
