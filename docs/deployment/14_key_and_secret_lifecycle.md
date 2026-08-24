# Key & Secret Lifecycle

**Status:** Operational policy. Companion to [`13_security.md`](13_security.md) and [`../services/12_security_monitoring_service.md`](../services/12_security_monitoring_service.md) §3 item 10, and the backup procedure in [`../services/11_health_and_monitoring_service.md`](../services/11_health_and_monitoring_service.md) §9.

This is a self-hosted stack — there is no managed secret manager. Secrets are encrypted at rest with
**SOPS + age** in `secrets.enc.env` (committed) and decrypted into `env.local` (gitignored, 0600,
**generated**) by `make env-local`. See [`13_security.md`](13_security.md) §5.2 for the file layout.

> ### ⚠ This section is the single authority for this project's secrets
>
> **Reconciled 2026-08-21.** Until then two inventories existed — this one and
> [`13_security.md`](13_security.md) §5.3.1 — written months apart, disagreeing, and neither
> complete. §5.3.1 now carries **where each secret lives** (authoritative store, other copies,
> consumer) and points here for **everything about rotation and impact**.
>
> **Why one table and not two.** Two rotation procedures for one credential is how a wrong one gets
> followed during an incident — and it had already happened here. Do not solve a future gap by
> re-adding a second table "kept in sync"; that is the failure mode, not the fix. If you add a
> secret, it gets **one row, here**, and a location row in §5.3.1.

---

## 1. Inventory

Impact, cadence and procedure for every secret this project holds. `Last rotated` of
**"unknown — treat as never"** is a valid, honest entry; it is not a placeholder to be tidied away.

| Secret | Used by | Impact if lost | Impact if leaked | Cadence | Rotation procedure | Last rotated |
|---|---|---|---|---|---|---|
| `DB_ENCRYPTION_KEY` | Backend PII vault encryption (`backend` **only**, T3-04) | ⭐ **Permanent PII loss** — encrypted columns unreadable | Decrypt all stored PII | ⚠ Only on compromise | ⚠ **Not a rotation — a migration.** Every pgcrypto value must be decrypted with the old key and re-encrypted with the new. **No script exists.** See §2 | unknown — treat as never |
| `SEARCH_TOKEN_PEPPER` | `base_manager.py` HMAC lookup tokens (phone / email search) | Stored lookup tokens become unmatchable — search returns nothing | Offline brute-force of lookup tokens: confirm whether a given phone/email is in the system | ⚠ Only on compromise | Change value, then **run [`../../scripts/database/rehash_search_tokens.py`](../../scripts/database/rehash_search_tokens.py) on that box in the same window.** ⚠ Skipping it makes lookup return nothing — **silently, raising nothing** | unknown — treat as never |
| `POSTGRES_PASSWORD` | Postgres; all services | DB outage | Full DB access | 12 months / on personnel change | `ALTER ROLE … PASSWORD`, `make secrets-edit`, `make env-local`, restart the stack — **and recreate Keycloak separately**, it is behind the `auth` profile so a plain `up -d` leaves it on the old credential until it next restarts. ⚠ Use an **alphanumeric** value: it is embedded in `DATABASE_URL`, where `@ : / # %` corrupt the connection string | ⚠ **2026-08-21 — LOCAL STACK ONLY.** Staging and DOR prod are **not** rotated and still hold the pre-rotation credential. The old value remains in git history; rotation is what makes those copies worthless. ⭐ This is the first entry in this column that is true rather than aspirational: until 2026-08-21 eleven compose literals overrode `env.local`, so rotating this variable changed nothing and a date here would have been a false record. See [`db-password-hardcoded-in-compose.md`](../sprints/followups/db-password-hardcoded-in-compose.md) |
| `OPS_DB_PASSWORD` | `ops` container (`ops_app` scoped role) | Monitoring can't connect | Read `ops.*` + reporting tables | 12 months / on personnel change | `make secrets-edit` + `make env-local`, then **`ALTER ROLE ops_app PASSWORD` to the same value on every host that runs `ops`**, then recreate the container. ⚠ **It is its own credential — never reuse `POSTGRES_PASSWORD`.** ⚠ **Deploying it to a new host is not just a rotation — see §5.1**, which is what staging and DOR prod will need | **2026-08-24 — LOCAL STACK ONLY.** ⚠ This row previously read *"As `POSTGRES_PASSWORD`, for the scoped role"* and the variable **did not exist anywhere** — not in `.env.shared`, not in `secrets.enc.env`. `ops/config.py` fell back to `POSTGRES_PASSWORD` (`ops_db_password or postgres_password`), so `ops` authenticated as **`ops_app` using the `user` role's credential**. The 2026-08-21 `POSTGRES_PASSWORD` rotation did not touch `ops_app`, and monitoring went blind for three days — 253 auth failures, every report row `n/a`, container still reporting `healthy`. ⭐ **This is the rotation trap this table exists to prevent, and the table itself was carrying it.** Now a distinct 40-char alphanumeric secret. Staging and DOR prod are not rotated and do not run `ops`. See [`ops-cannot-authenticate-since-rotation.md`](../sprints/2026-08-llm/followups/ops-cannot-authenticate-since-rotation.md) |
| `REDIS_PASSWORD` | Celery broker/result + Socket.IO bus | Broker outage | Task injection / inspection | 6–12 months / on suspicion | `make secrets-edit`, `make env-local`, then recreate Redis **and every client** — the compose interpolation carries it into `requirepass` and into all 14 `redis://` URLs, so one `up -d` does both. ⚠ Use an **alphanumeric** value: it is embedded in `redis://:PASSWORD@redis:6379/N`. ⚠ Redis has **no persistence volume**, so a restart drops queued tasks — check `LLEN` on the queues first | ⚠ **2026-08-23 — LOCAL STACK ONLY.** Rotated because a history scan found the previous value in **public git history**, in 9 now-deleted files (`scripts/local/redis.conf`, `scripts/servers/launch_servers.sh` and others). The wiring was always correct — `${REDIS_PASSWORD:-}` interpolation, no compose literal — so unlike `POSTGRES_PASSWORD` this rotation was about an exposed **value**, not an inert variable. Staging and DOR prod still hold the exposed credential. See [`secrets-in-public-git-history.md`](../sprints/followups/secrets-in-public-git-history.md) |
| `TICKETING_SECRET_KEY` | chatbot ↔ ticketing + ticketing → backend webhooks | Integration outage | Forged webhooks / API calls | 6–12 months / on suspicion | `python -c "import secrets; print(secrets.token_urlsafe(32))"`, **update both sides together** | unknown — treat as never |
| `MESSAGING_API_KEY` | Messaging API `x-api-key` — ⚠ **also guards `GET /api/grievance/{id}`, which serves plaintext PII** | Messaging outage | Send messages as the system; **read complainant PII** | 6–12 months / on suspicion | Generate, update caller and callee **atomically** | unknown — treat as never |
| `KEYCLOAK_ADMIN_PASSWORD` | Keycloak realm admin — ⭐ **can mint officer accounts** | KC admin lockout | Full IdP control | On personnel change | Keycloak admin console → user → Credentials → reset | unknown — treat as never |
| `KEYCLOAK_CLIENT_SECRET` | OIDC client | Officer login fails (client auth) | Impersonate the client; mint/exchange tokens | 6–12 months / on suspicion | Keycloak → Clients → Credentials → Regenerate; **update every consumer** | unknown — treat as never |
| `KEYCLOAK_WEBHOOK_SECRET` | Keycloak → ticketing onboarding webhook | Onboarding events stop | Forged Keycloak events | 6–12 months / on suspicion | Generate, update the Keycloak event-listener config **and** the receiver | unknown — treat as never |
| ⭐ `DOIT_SMS_BEARER_TOKEN` | `backend/config/sms_config.py:47` — the **Government of Nepal** SMS gateway (`sms.doit.gov.np`), which is the **production** complainant-notification path (AWS SNS is only the international fallback) | Complainant SMS in Nepal stops — the primary channel for telling a complainant their grievance moved | ⭐ **Send SMS as the project, through a government gateway, to affected people** — a credible impersonation of the official grievance mechanism, aimed at exactly the population it exists to protect | Per DOIT policy / on personnel change | ⚠ **We do not issue this token** — request reissue through DOIT, then `make secrets-edit` + `make env-local` + restart `backend`. No self-service console | ⚠ **unknown — treat as never. Added to this inventory 2026-08-24**, having been tracked by no inventory at all: it is read by the code, documented in four other docs, live in AWS staging's `env.local`, and absent from `.env.shared`, `secrets.enc.env` and `.env.example`. Found by measuring a host rather than reading a list ([`18_… §5a`](18_sops_migration_handover.md) Hazard 2) |
| `SMTP_PASSWORD` (+ `SMTP_USERNAME`) | Officer-invite mail relay | Invite + notification mail stops | Send mail **as the project** — credible phishing of officers | 6–12 months | Mail provider console → rotate app password | unknown — treat as never |
| ~~`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`~~ ✅ **no consumer since 2026-08-24 — revoke, do not rotate** | ~~SNS (complainant SMS), Pinpoint~~ — SNS deleted, Pinpoint never read by any code | Nothing. SMS is DOIT-only and has no fallback | Send SMS as the project + whatever else the IAM policy allows (cost, reputation) | 6–12 months / on personnel change | IAM → Security credentials → create new → update every copy → ⚠ **delete the old key** | unknown — treat as never |
| `OPENAI_API_KEY` | Closed LLM config (the benchmark baseline) | Closed-model path stops | Billed usage on our account | 6–12 months | platform.openai.com → API keys → revoke + create | unknown — treat as never |
| `HG_TOKEN` (+ `HG_USERNAME`) | Open LLM config; `dpg-platform-independence` CI job | Open-model path + that CI job fail | Billed inference; repo access per token scope | 6–12 months | huggingface.co/settings/tokens → revoke + create → ⚠ **also re-paste the GitHub Actions secret `HF_TOKEN`; it is the same credential** | unknown — treat as never |
| `GITHUB_TOKEN` (optional) | Dependabot alerts API | Scan source missing | Repo read per token scope | Per GitHub policy | Reissue, `make secrets-edit`, `make env-local` | unknown — treat as never |

⭐ marks the two whose loss or leak is not recoverable by rotation alone.

**Rotation generation:** `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

**Applying any rotation:** `make secrets-edit` (edits `secrets.enc.env` in place via SOPS) then
`make env-local`, then restart whatever consumes it. ⚠ Never hand-edit `env.local` — it is generated,
so the edit is discarded on the next run and never reaches staging or production.

---

## 2. `DB_ENCRYPTION_KEY` — the critical one

Losing this key makes every encrypted PII column unrecoverable, so it must be backed up
**separately** from the database (a DB backup encrypted *with* a key you also lost is useless).

- **Backup:** store the key in **two** offline locations (e.g. a password manager + an `age`/GPG-encrypted file on separate media). Never in the same bucket as DB dumps.
- **Reference from backups:** `scripts/ops/backup_db.sh` records (but never stores) which key fingerprint a dump expects, so a restore knows which key it needs. Keep the key archive in lockstep with retention.
- ⚠ **Deploying it is not neutral.** One `secrets.enc.env` carries one value, so `make env-local` on a
  host **overwrites** that host's key. If the hosts do not already share this value, that is permanent
  PII loss — and `base_manager.py` **fails open**, so it shows up as empty fields, not an error.
  **Compare hashes on every host before the first deploy** — [`18_… §5a`](18_sops_migration_handover.md).
- **Rotation:** requires a **re-encryption migration** (decrypt-with-old → encrypt-with-new) across all PII columns. Treat as planned maintenance with a full backup first. Do **not** rotate casually.

---

## 3. ⚠ The two that are not routine rotations

Both are in §1, both are marked "only on compromise", and both break something **silently** if
rotated carelessly. They are called out again here because a rotation pass that works through §1
top-to-bottom will reach them, and it must stop.

| Secret | Why it is not a rotation | What must happen instead |
|---|---|---|
| `DB_ENCRYPTION_KEY` | No re-encryption script exists. Changing the value orphans every encrypted column | A planned migration with a full backup first — §2 |
| `SEARCH_TOKEN_PEPPER` | Stored HMAC tokens were derived from the old pepper; a new one matches none of them | Rotate **and** run `scripts/database/rehash_search_tokens.py` on that box **in the same maintenance window** |
| `POSTGRES_PASSWORD` → **`ops_app`** | ⚠ **Not the same secret, but rotating the first used to break the second.** `ops` falls back to `POSTGRES_PASSWORD` when `OPS_DB_PASSWORD` is unset, while connecting as a *different* role | Fixed 2026-08-24: `ops_app` has its own password, the fallback now logs an ERROR, and the `ops` healthcheck probes the database so `healthy` cannot mean `blind`. **If you ever unset `OPS_DB_PASSWORD`, the coupling returns** |

⚠ The `SEARCH_TOKEN_PEPPER` failure mode is the dangerous one: phone and email lookup return
**nothing**, raising no error. Nothing alerts. It looks like "no such complainant".

---

## 4. Storage hardening

- **At rest, in the repo:** `secrets.enc.env`, SOPS-encrypted to the age recipients in `.sops.yaml`.
  The plaintext half (`.env.shared`) is committed and carries **no** credential.
- **At rest, on a host:** `env.local` is generated at 0600 by `scripts/ops/gen_env_local.sh`, owned
  by the deploy user only. It is the only plaintext copy, and it is gitignored.
- **The age private key** lives at `~/.config/sops/age/keys.txt` in the **WSL/Linux filesystem**,
  mode 0600. ⚠ **Never under `/mnt/c/`, `/mnt/g/`, or inside `G:\My Drive\`** — Google Drive mirror
  mode would sync it in plaintext to Google, silently, as a backup feature working as designed.
  Backed up as a Proton Pass secure note plus a paper copy. **Losing it makes `secrets.enc.env`
  unreadable.**
- **A separate keypair per server**, rather than copying the personal key onto hosts — a compromised
  host then costs one host, not every secret you can read.
- The preflight gate (`scripts/ops/security-preflight.sh`) asserts each secret above is set and
  **not** a default/empty value before promotion.

---

## 5. Scoped DB roles

Least-privilege roles reduce blast radius if any one service is compromised. `ops_app` ships least-privilege via the ops Alembic stream; the remaining roles are opt-in via [`../../scripts/ops/create_scoped_roles.sql`](../../scripts/ops/create_scoped_roles.sql) (`chatbot_app` → `public.*`, `ticketing_app` → `ticketing.*` + read `public.grievances`, `keycloak_app` → `keycloak` schema). Apply deliberately and repoint each service's `POSTGRES_USER`/`POSTGRES_PASSWORD` in the same change window.

### 5.1 ⚠ Taking `ops` to staging or DOR prod

**Three steps, and two of them are not the secret.**

**`ops` runs on neither server today.** When it does, `make env-local` alone will not make it work,
and its failure mode is the one this project has already paid for: the container reports `healthy`
while writing nothing.

A secret in `secrets.enc.env` carries **one value for every host**, but a **database role's password
lives in the database, per host**. Publishing the secret does not set the role. All three steps, in
this order, on each host:

```bash
# 1. The secret reaches the host (adds OPS_DB_PASSWORD to that host's env.local)
make env-local

# 2. Set the ROLE to match. Reads the value back out of env.local — never retype or paste it.
awk -F= '/^OPS_DB_PASSWORD=/{print substr($0, index($0,"=")+1)}' env.local | tr -d '\n' | { read -r P
  printf "ALTER ROLE ops_app PASSWORD '%s';" "$P" | docker exec -i <db-container> psql -U <admin> -d app_db -q; }

# 3. Grants. ops001 grants ticketing.tickets behind `IF to_regclass(...) IS NOT NULL`, which SKIPS
#    SILENTLY when ops migrates before ticketing — which is how the local box ended up without it.
docker exec <ops-container> sh -c 'cd /app && alembic -c ops/migrations/alembic.ini upgrade head'

# 4. Verify — do not assume. This exits 1 and names the role if the credential is wrong.
docker exec <ops-container> python -m ops.selfcheck && echo OK
```

⚠ **Step 4 is the point.** Before 2026-08-24 the healthcheck only proved the scheduler was ticking,
so a wrong credential looked identical to a working one for three days. It now probes the database.
**A green `selfcheck` is the only evidence that steps 2 and 3 actually landed.**

⚠ **Unlike `DB_ENCRYPTION_KEY` (§2), getting this wrong is recoverable** — re-run step 2. Nothing is
lost, only unmonitored. Do not let it inherit §2's gravity; do not skip it either.
