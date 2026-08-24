# Security Features — Platform Overview (June 2026)

**Status:** As-built reference for implemented controls and locked policies.  
**Related:** [09_privacy.md](09_privacy.md), [11_llm_pipeline_policy.md](11_llm_pipeline_policy.md), [../ticketing_system/06_messaging_rules_whatsapp_sms.md](../ticketing_system/06_messaging_rules_whatsapp_sms.md), [../services/05_messaging_service.md](../services/05_messaging_service.md), [../ticketing_system/00_ticketing_decisions.md](../ticketing_system/00_ticketing_decisions.md)

This document is the **single index of security features** across chatbot, backend, and GRM ticketing.

---

## 1. Security architecture (high level)

| Layer | Control |
|---|---|
| **Data separation** | `public.*` (grievance vault) and `ticketing.*` (operational metadata) in one DB, isolated by schema |
| **Integration boundary** | No cross-schema FK; service-to-service via HTTP APIs only |
| **PII boundary** | No complainant PII in `ticketing.*`; brokered reads from grievance API |
| **SEAH boundary** | DB-level `is_seah` filtering + role/workflow scope |
| **Auth boundary** | Keycloak OIDC in production; scoped officer access via `OfficerScope` |

---

## 2. Authentication and session security

| Feature | Where | Notes |
|---|---|---|
| **Keycloak OIDC (production)** | Ticketing UI + API auth stack | Officer login and JWT validation (`KEYCLOAK_ISSUER`) |
| **Officer onboarding lifecycle** | `ticketing.officer_onboarding` | `invited` → `active` via Keycloak webhook |
| **Keycloak webhook auth** | `POST /api/v1/webhooks/keycloak` | Header `X-Keycloak-Webhook-Secret` = `KEYCLOAK_WEBHOOK_SECRET` |
| **Service-to-service API keys** | Messaging, ticketing webhook | `x-api-key` / `X-Ticketing-Secret` |
| **Dev-only bypass mode** | Local UI + API (`:3001`/`:5002`) | `AUTH_MODE=bypass`, honoured **only** when `APP_ENV=dev`; production can never bypass |
| **OTP verification (chatbot intake)** | Complainant flow | Phone verification before grievance submission |

### 2.1 Fail-closed guarantees (HR-01)

Authentication fails **closed**: a missing env var can no longer silently disable auth
(previously an unset `KEYCLOAK_ISSUER` authenticated every request as a demo super_admin,
and an unset `TICKETING_SECRET_KEY` disabled the webhook/API-key check with only a log
warning). After CL-03 two canonical flags gate this, both defaulting to the safe value:
`APP_ENV` ∈ `dev`/`staging`/`production` (default **`production`**) and `AUTH_MODE` ∈
`keycloak`/`bypass` (default **`keycloak`**). The bypass is permitted **only** when
`APP_ENV=dev` **and** `AUTH_MODE=bypass`; production can never bypass. These are set solely
in `env.local` — never in the grm/aws/prod overlays (there is no `docker-compose.override.yml`
any more). `APP_ENV` replaces the old `TICKETING_ENV`/`BACKEND_ENV`/`ENVIRONMENT`.

| Condition | dev bypass (`APP_ENV=dev` **and** `AUTH_MODE=bypass`) | staging / production (default) |
|---|---|---|
| `KEYCLOAK_ISSUER` unset (ticketing) | demo super_admin bypass allowed | **App refuses to start** (`RuntimeError` at boot); per-request `503` as defense in depth |
| `TICKETING_SECRET_KEY` unset (ticketing) | API-key check disabled (warns) | **App refuses to start**; `verify_api_key` returns `503` |
| Backend grievance key list empty (`TICKETING_SECRET_KEY` + `MESSAGING_API_KEY`) | API-key check skipped | **Backend refuses to start**; `_ticketing_auth_check` returns `503` |
| `x-internal-user-id` + valid `x-api-key`, no `x-internal-role` | least-privilege identity (**no roles**) — no default super_admin, any env | same |

Startup guards live in `ticketing/api/main.py` (`_assert_auth_configured`) and
`backend/api/fastapi_app.py` (`_assert_backend_auth_configured`); the per-request
defenses live in `ticketing/api/dependencies.py` (`verify_api_key`,
`_resolve_user_identity`) and `backend/api/routers/grievance.py` (`_ticketing_auth_check`).

---

## 3. Authorization and access control

| Feature | Where | Notes |
|---|---|---|
| **GRM role catalog** | `ticketing.roles` | Role codes with `workflow_scope` (`standard` / `seah` / `both`) |
| **OfficerScope jurisdiction** | `ticketing.officer_scopes` | Org + project + package + location scope for ticket visibility/actions |
| **4-tier ticket participation** | `ticketing.ticket_viewers` | Actor / Supervisor / Informed / Observer |
| **Action-level permissions** | Ticket action API | Step role + assignee/supervisor rules for RESOLVE, ESCALATE, GRC actions |
| **SEAH invisibility** | Ticket list/detail queries | Non-SEAH roles cannot read SEAH tickets (`is_seah=true`) |
| **Workflow scope separation** | Standard vs SEAH workflows | One ticket uses one workflow only |
| **Admin-only settings** | Settings UI/API | Workflows, users, orgs, locations, report limits restricted by role |
| **Report access scope** | Reports API/UI | Same `OfficerScope` model as queue |

---

## 4. PII and sensitive data protection

| Feature | Where | Notes |
|---|---|---|
| **No PII in ticketing tables** | `ticketing.*` | Name/phone/email/address never stored in ticketing schema |
| **Non-PII cache only on tickets** | `ticketing.tickets` | Summary, categories, location text cached at creation |
| **Brokered PII fetch** | `GET /api/v1/tickets/{id}/pii` | On-demand read from grievance API; access logged |
| **Reveal session controls** | `POST .../reveal-contact/begin` + `.../close` | Time-bounded reveal with audit trail |
| **Vault domain model** | `public.*` grievance store | Original narrative + identifiers treated as restricted content |
| **Summary-first officer UX** | Ticket detail + LLM summaries | Operational view defaults to redacted/safe content |
| **Resolved summary PII exception** | `ticketing.ticket_resolved_summaries` | Officer-only closure artifact; controlled access roles |
| **Public closure sanitization** | `summary_public_json` | Complainant-facing closure excludes internal notes/officer roster |

Detailed policy: [09_privacy.md](09_privacy.md).

---

## 5. Encryption and secrets

| Feature | Where | Notes |
|---|---|---|
| **Field-level DB encryption** | Backend grievance/complainant data | `DB_ENCRYPTION_KEY` + pgcrypto model. **`backend` is the sole holder** — it decrypts server-side in `get_grievance_by_id`, so `GET /api/grievance/{id}` serves plaintext and ticketing needs no key (T3-04). Ticketing has no accessor for it and must not regain one; pinned by `tests/ticketing/test_pii_boundary.py`. |
| **Envelope/key split by sensitivity** | Vault architecture | Separate handling for standard vs SEAH-sensitive content (policy) |
| **Secrets via environment** | All services | No credentials in repo; `.env` / deployment env vars |
| **Webhook/API shared secrets** | Ticketing + messaging + Keycloak | `TICKETING_SECRET_KEY`, `MESSAGING_API_KEY`, `KEYCLOAK_WEBHOOK_SECRET` |


### 5.1 Principles

> **Scope note.** This policy spans **every repository under `~/projects/`**, not only this one. It
> lives here because this is the project with a security specification; the inventory in §5.3 is
> deliberately wider than the GRM.
>
> **Status: target state, not current state.** As of 2026-08-20 `sops` and `age` are **not
> installed**, no `.sops.yaml` exists in any repository, and no `*.enc.env` exists anywhere. Every
> credential below currently sits in a plaintext, gitignored file. This section describes where
> things are going; §5.7 lists what must happen to get there.

1. **Least scope.** A credential is issued for one consumer in one environment. Same variable name
   across projects (`HF_TOKEN` everywhere) — **the directory is the namespace, not the variable
   name.**
2. **Rotatable without a deploy.** Changing a credential must not require a code change or a release.
   That is why platform-native stores are preferred wherever the platform has one.
3. **One credential per environment per consumer.** Staging must not be able to authenticate as
   production. Per-client credentials are always separate; personal tooling credentials may be shared
   across personal projects.
4. **Every copy known.** A credential whose copies cannot be enumerated cannot be rotated, only
   abandoned. §5.3 is the enumeration, and it is the artefact that makes §5.5 possible.
5. **The vault is for bootstrapping and local development — it is not the runtime source of truth
   for deployed code.** Each secret therefore has **at most two homes**: the platform that consumes
   it, and the encrypted file it is restored from.

#### ⚠ Revocation is not rotation

**No system revokes a secret that has already been read.** Removing an age recipient, deleting an IAM
grant, revoking a share — all of these govern **future** reads only. A credential someone already
holds stays valid until it is **rotated at the provider**.

Access controls and audit logs exist to tell us **what to rotate**, not to undo past access. In
particular, `sops updatekeys` after removing a key stops future decrypts and **does not substitute
for rotating every secret in that file.**

### 5.2 Where secrets live, by category

**Tooling: no hosted secrets manager.** Secrets are encrypted at rest with **SOPS** using **age**
keys. **Proton Pass (free tier)** holds personal passwords and recovery material only — never
application credentials.

| Category | Store | Rationale |
|---|---|---|
| Vercel-deployed config | **Vercel environment variables**, per environment | Rotatable from the dashboard without a deploy; scoped per environment natively |
| Supabase config | **Supabase secrets** | Same — the platform that issues the credential also rotates it |
| Hetzner / self-managed compute | **`secrets.enc.env`**, SOPS-encrypted, committed to the deploy repo | No platform store exists; the repo is already the deploy unit, so the secret travels with what consumes it |
| Client-owned secrets | **SOPS in the client's repo**, with the **client's age public key added as co-recipient from day one** | Day one matters: retrofitting a recipient means re-encrypting, and it means the client could not read their own secrets in the interim |
| Client production credentials where the client runs a cloud KMS | **SOPS with that KMS as recipient** | Gives the client **IAM-level revocation** and a **decrypt audit trail** — neither of which an age recipient list provides |
| Personal passwords, **age private keys**, recovery codes | **Proton Pass** | Human custody, not machine consumption |

#### File layout, per repository

| File | Committed? | Contents |
|---|---|---|
| `.env` | ✅ committed, **plaintext** | **Non-secrets only** — feature flags, log levels, ports, public URLs, `NEXT_PUBLIC_*`, plus all comments and section headers |
| `secrets.enc.env` | ✅ committed, **SOPS-encrypted** | Credentials only |
| `.sops.yaml` | ✅ committed | `path_regex: \.enc\.env$`, **age public keys only** |
| `.gitignore` | ✅ committed | Must cover `.env.local` and `*.decrypted` |

⚠ **Comments and structure live in `.env`, not in the encrypted file.** A SOPS-encrypted file is a
poor place to read documentation, and its diffs are unreadable — so the plaintext half carries the
explanation and the encrypted half carries only values.

#### Secret vs non-secret

**A value is a secret if it would help someone who obtained it.**

| Always secret | Never secret |
|---|---|
| API keys, tokens, passwords | `NEXT_PUBLIC_*` — **these ship to the browser** |
| Database URLs with embedded credentials | Feature flags |
| SMTP credentials | Log levels |
| Webhook signing secrets | Ports, public URLs |
| OAuth client secrets | |
| ⚠ **Usernames and account identifiers *when paired with a credential for the same service*** — e.g. `SMTP_USERNAME` beside `SMTP_PASSWORD` | |

#### Key management

- **One age keypair per person**, at **`~/.config/sops/age/keys.txt`** in the **WSL filesystem**.
- ⚠ **Never under `/mnt/c/`, `/mnt/g/`, or inside `G:\My Drive\`.** Google Drive mirror mode would
  sync the private key **in plaintext** to Google. This is the single most damaging misplacement
  available, because it is silent and it is a backup feature working as designed.
- **A separate keypair per server**, rather than copying the personal key onto hosts. A compromised
  host then costs one host, not every secret you can read.
- Private key backed up as a **Proton Pass secure note**, with a **paper copy for the personal key
  only**.

#### Proton account hardening

- 2FA enabled via an **external authenticator app** — ⚠ **not Proton Pass's own TOTP feature.**
  Storing the Proton account's second factor inside Proton Pass is circular: losing access to Proton
  loses the means of regaining access to Proton.
- **Recovery codes stored outside Proton.**

### 5.3 Inventory

Discovered 2026-08-20 by scanning every git repository under `~/projects/`. **Values were never
read or compared directly** — cross-repo sameness was established by hashing, so this table records
*that* two things match, never *what* they are.

⚠ **`Authoritative store` is the TARGET store** per §5.2. Today every row lives in a plaintext
gitignored file; the migration is §5.7.

#### 5.3.1 Nepal GRM — `nepal_chatbot` (ADB Loan 52097-003)

**Migrated to SOPS + age on 2026-08-21** — see [`18_sops_migration_handover.md`](18_sops_migration_handover.md).
`env.local` is now a **generated artefact** (`make env-local`), not a source; the committed halves are
`.env.shared` (plaintext, no credentials) and `secrets.enc.env` (SOPS-encrypted).

> ⚠ **This table records WHERE each secret lives. It does not record how to rotate it.**
> Rotation procedure, cadence, impact-if-lost, impact-if-leaked and `Last rotated` live in
> **[`14_key_and_secret_lifecycle.md`](14_key_and_secret_lifecycle.md) §1**, which is the single
> authority. Until 2026-08-21 both documents carried rotation columns, they disagreed, and neither
> was complete — two procedures for one credential is how the wrong one gets followed during an
> incident. **Do not re-add a rotation column here.**

| # | Secret | Owner | Authoritative store | Other copies | Consumed by |
|---|---|---|---|---|---|
| 1 | `DB_ENCRYPTION_KEY` | TBC | `secrets.enc.env` (SOPS) | `env.local` (generated) · AWS staging · DOR prod | `backend` **only** (T3-04) |
| 2 | `SEARCH_TOKEN_PEPPER` | TBC | `secrets.enc.env` (SOPS) | staging · prod · **not in local** | `base_manager.py` HMAC lookup tokens |
| 3 | `POSTGRES_PASSWORD` | TBC | `secrets.enc.env` (SOPS) | `env.local` (generated) · staging · prod | Postgres, all services |
| 4 | `OPS_DB_PASSWORD` | TBC | `secrets.enc.env` (SOPS) | `env.local` (generated) — ⚠ **new 2026-08-24**; staging · prod run no `ops` container, so any copy there is inert and its presence is **unverified from here** | `ops` container (`ops_app` role) |
| 5 | `REDIS_PASSWORD` | TBC | `secrets.enc.env` (SOPS) | `env.local` (generated) · staging · prod | Broker + result backend |
| 6 | `TICKETING_SECRET_KEY` | TBC | `secrets.enc.env` (SOPS) | ✅ **Empty locally by design** — the dev bypass (`APP_ENV=dev` + `AUTH_MODE=bypass`) is active; **checked, it fails closed** elsewhere (`grievance.py:251-263` raises without a key) · staging · prod | Ticketing ↔ chatbot webhook |
| 7 | `MESSAGING_API_KEY` | TBC | `secrets.enc.env` (SOPS) | staging · prod · **not in local** | Messaging API `x-api-key` — ⚠ **also guards `GET /api/grievance/{id}`, which serves plaintext PII** |
| 8 | `KEYCLOAK_ADMIN_PASSWORD` | TBC | `secrets.enc.env` (SOPS) | staging · prod · **not in local** | ⭐ Realm admin — **can mint officer accounts** |
| 9 | `KEYCLOAK_CLIENT_SECRET` | TBC | `secrets.enc.env` (SOPS) | staging · prod · **not in local** | OIDC client |
| 10 | `KEYCLOAK_WEBHOOK_SECRET` | TBC | `secrets.enc.env` (SOPS) | staging · prod · **not in local** | Onboarding webhook |
| 11 | `SMTP_PASSWORD` (+ `SMTP_USERNAME`) | TBC | `secrets.enc.env` (SOPS) | `env.local` (generated) · staging · prod | Officer-invite mail relay |
| 12 | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | TBC | `secrets.enc.env` (SOPS) | `env.local` (generated) · staging · prod | SNS (complainant SMS), Pinpoint |
| 13 | `OPENAI_API_KEY` | me | `secrets.enc.env` (SOPS) | `env.local` (generated) | Closed LLM config (the benchmark baseline) |
| 14 | `HG_TOKEN` (+ `HG_USERNAME`) | me | `secrets.enc.env` (SOPS) | `env.local` (generated) · **GitHub Actions secret `HF_TOKEN`** | Open LLM config; `dpg-platform-independence` CI job |
| 15 | `GITHUB_TOKEN` (optional) | me | `secrets.enc.env` (SOPS) | **GitHub PAT** — reissued, not copied | Dependabot alerts API (security monitoring) |

⚠ Rows 2, 4, 7, 8, 9, 10 are **not present in local `env.local`** — the local stack runs the dev
bypass. They exist only on staging and production, so a local `secrets.enc.env` round-trip does not
prove those hosts are covered. Migrate each host explicitly.

#### 5.3.2 `frank` — **mine** · Vercel + Supabase (Hetzner on the M2 roadmap, not yet live)

| # | Secret | Owner | Authoritative store | Other copies | Consumed by | Rotation procedure | Last rotated |
|---|---|---|---|---|---|---|---|
| 16 | `SUPABASE_SERVICE_ROLE_KEY` | me | **Supabase secrets** | `.env` local · Vercel env | Server-side Supabase — ⭐ **bypasses RLS entirely** | Supabase dashboard → Project Settings → API → rotate, **then update Vercel env** | TBC |
| 17 | `SUPABASE_ACCESS_TOKEN` | me | **Proton Pass** (personal account token) | `.env` local | Supabase **management API** — ⭐ can create/delete projects | supabase.com → Account → Access Tokens → revoke + generate | TBC |
| 18 | `DATABASE_URL` | me | **Supabase secrets** | `.env` local · Vercel env | Direct Postgres — ⚠ **embeds credentials** | Rotate the DB password in Supabase, then re-derive the URL everywhere | TBC |
| 19 | `ANTHROPIC_API_KEY` | me | **Vercel env** | `.env` local | Claude calls | console.anthropic.com → API keys → revoke + create | TBC |
| 20 | `DEEPSEEK_API_KEY` | me | **Vercel env** | `.env` local | Fallback model | DeepSeek console → API keys → revoke + create | TBC |
| 21 | `FRANK_SERVICE_KEY` | me | **Vercel env** | `.env` local | Internal service-to-service auth | Self-issued: generate, update both sides | TBC |
| 22 | `SUPABASE_ANON_KEY` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` | TBC | **Supabase secrets** | `.env` local · Vercel env · **the browser, by design** | Client-side Supabase | ✅ **Public by contract** — RLS is the control, not secrecy. Rotate only if RLS was found misconfigured | n/a |

#### 5.3.3 `agents/plant_care_v1` — personal, no deploy target detected

| # | Secret | Owner | Authoritative store | Other copies | Consumed by | Rotation procedure | Last rotated |
|---|---|---|---|---|---|---|---|
| 23 | `OPENAI_API_KEY` | me | `secrets.enc.env` (SOPS) | `.env` local | LLM calls | platform.openai.com → API keys. ⚠ **Distinct from #13** — verified different | TBC |
| 24 | `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | me | `secrets.enc.env` (SOPS) | `.env` local | S3, SES, Pinpoint | IAM → create new → update → delete old. ⚠ **Distinct from #12** — verified different | TBC |
| 25 | `HUGGINGFACE_API_KEY` | me | `secrets.enc.env` (SOPS) | `.env` local | HF inference | huggingface.co/settings/tokens. ⚠ **Distinct from #14** — verified different | TBC |
| 26 | `GOOGLE_API_KEY` | me | `secrets.enc.env` (SOPS) | `.env` local | Calendar / Sheets | Google Cloud Console → APIs & Services → Credentials | TBC |
| 27 | `GOOGLE_CLIENT_SECRET` (+ `GOOGLE_CLIENT_ID`) | me | `secrets.enc.env` (SOPS) | `.env` local | OAuth client | Google Cloud Console → Credentials → OAuth client → reset secret | TBC |
| 28 | `GSHEET_BEARER_TOKEN` | me | `secrets.enc.env` (SOPS) | `.env` local | Sheets access | TBC — depends how it was issued | TBC |
| 29 | `TELEGRAM_BOT_TOKEN` | me | `secrets.enc.env` (SOPS) | `.env` local | Telegram bot | BotFather → `/revoke` → new token | TBC |
| 30 | `DISCORD_WEBHOOK_URL` | me | `secrets.enc.env` (SOPS) | `.env` local | Notifications — ⚠ **the URL *is* the credential** | Discord → Channel → Integrations → Webhooks → delete + recreate | TBC |
| 31 | `OPENWEATHER_API_KEY` | me | `secrets.enc.env` (SOPS) | `.env` local | Weather API | openweathermap.org → API keys | TBC |
| 32 | `SMTP_PASSWORD` (+ `SMTP_USERNAME`) | me | `secrets.enc.env` (SOPS) | `.env` local | Mail | Provider console. ⚠ Username **matches** #11; **password does not** — see finding F2 | TBC |
| 33 | `DATABASE_URL` / `TEST_DATABASE_URL` | me | `secrets.enc.env` (SOPS) | `.env` local | Local DB | ⚠ Short values — likely a SQLite path, not a credential. **Verify** and reclassify to `.env` if so | n/a |

#### 5.3.4 `stratcon` — **mine today, migrating to a client soon** · Vercel (website) + Hetzner (API, `make hetzner-deploy`)

> ⭐ **Act on this before the migration, not after.** §5.2 requires the client's age public key added
> as a **co-recipient from day one**. For this repository "day one" is a date in the near future and
> it is knowable now — so add the recipient as part of the handover, not once they are already
> waiting to read something they cannot.
>
> ⚠ And rows 33/35 change owner at that moment. **Rotate at handover** regardless of whether anything
> is suspected: every credential I hold today is one the client did not choose to share with me
> (§5.1 — revocation is not rotation).

| # | Secret | Owner | Authoritative store | Other copies | Consumed by | Rotation procedure | Last rotated |
|---|---|---|---|---|---|---|---|
| 34 | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | me → **client at handover** | **Supabase secrets** | `website/.env.local` · Vercel env · **the browser, by design** | Client-side Supabase | ✅ Public by contract; RLS is the control. ⚠ **Different value and format from #21** — a separate Supabase project | n/a |
| 35 | `VERCEL_OIDC_TOKEN` | n/a — machine-issued | **not managed** | `website/.env.local` | `vercel dev` local auth | ⚠ **Do not manage.** Auto-issued by the Vercel CLI and short-lived; it regenerates on `vercel link`/`vercel dev` | n/a |
| 36 | Hetzner API/deploy credentials | me → **client at handover** | TBC | TBC | `make hetzner-deploy`, Celery workers | TBC | TBC |

#### 5.3.5 SSH keys — `~/.ssh/`

Contents never read. ⚠ **`~/.ssh/config` is empty**, so the host↔key mapping below is inferred from
file names and public-key comments and **must be confirmed**.

| # | Key | Owner | Authoritative store | Corresponds to | Rotation procedure | Last rotated |
|---|---|---|---|---|---|---|
| 37 | `nepal_gms_prod` (comment `philg@ZEPHYRUS-PG`) | TBC | Proton Pass (backup) | DOR production, inferred | `ssh-keygen` new pair → append pub to `authorized_keys` → verify login → **remove old pub** | TBC |
| 38 | `hetzner-stratcon` (comment `stratcon-hetzner`) | TBC — **client?** | Proton Pass (backup) | Stratcon Hetzner box | As #36 | TBC |
| 39 | `aws-key.pem` | TBC | Proton Pass (backup) | AWS staging, inferred | EC2 key pairs cannot be rotated in place — add a new pub to `authorized_keys`, then retire | TBC |
| 40 | `pg_rasa_train.pem` | TBC | Proton Pass (backup) | TBC — a training box? ⚠ **May be obsolete** | As #38, or **delete if the host is gone** | TBC |

### 5.4 Engagement offboarding

| Engagement | Client-owned credentials | My access to remove | Client-allocated email? | Status |
|---|---|---|---|---|
| Nepal GRM (ADB / DOR) | rows 1–12 | `nepal_gms_prod` SSH key · DOR VPN · Keycloak admin | TBC | active |
| Stratcon | rows 33, 35 | `hetzner-stratcon` SSH key · Vercel project · Supabase project | TBC | ⭐ **migration to client PENDING** — add their age key as co-recipient now, rotate at handover |
| `frank` | none — **mine** | n/a | n/a | ✅ not an engagement; §5.4 does not apply |
| `visionlife-bm` | TBC — no credentials found | TBC | TBC | TBC |

#### Execution checklist

Run **in this order**. The ordering is not cosmetic — step 6 is the one that strands you if it is
done late.

1. **Rotate client-owned credentials.** ⭐ **The client does it where possible** — that way the new
   value never passes through my hands, and the rotation is provably complete from their side.
2. **Remove my age key from `.sops.yaml`** and run `sops updatekeys` on every encrypted file in
   that repository.
   > ⚠ **This is not a rotation.** It stops *future* decrypts. Every secret I could previously read
   > remains valid until step 1 rotates it. If step 1 was skipped, this step accomplishes nothing
   > of substance — see §5.1.
3. **Remove IAM / KMS grants** — including any KMS recipient used for SOPS.
4. **Remove my SSH public keys** from `authorized_keys` on every host in the engagement.
5. **Delete local clones and any decrypted files** (`*.decrypted`, generated `.env.local`).
6. ⚠ **BEFORE any client-allocated email is deactivated**, confirm nothing depends on it for
   recovery — password resets, 2FA recovery, platform account ownership, domain registrar contact.
   **An account whose recovery address no longer exists cannot be recovered by anyone**, including
   the client.
7. **Mark inventory rows retired with a date** in §5.3 — ⚠ **do not delete them.** A deleted row
   destroys the record of what was once exposed, which is exactly what a later incident review needs.

### 5.5 Incident response

**Rotate first, investigate second.** Investigation is unbounded; exposure is not.

1. **Rotate the credential immediately**, before establishing scope or cause.
2. **Enumerate every copy using §5.3** — the `Other copies` column exists for this moment. Update
   each one. A rotation that misses a copy is an outage *and* an unrotated credential.
3. ⚠ **Check for anything still valid that was issued *using* the credential.** Rotating a parent
   does not invalidate its children: sessions, downstream tokens, signed URLs, cached OAuth grants,
   and anything minted by `KEYCLOAK_ADMIN_PASSWORD` or `SUPABASE_ACCESS_TOKEN` survive their
   parent's rotation.
4. **Notify the owner** — the client for client-owned credentials, promptly and before they discover it.
5. **Record the cause** in the deviation log, and add whatever control would have caught it.

⚠ **Assume the credential was used.** Absence of evidence in a log is not evidence of absence — most
of these providers do not log reads at all, which is precisely why §5.2 prefers a KMS recipient for
client production: it is the only option here that produces a decrypt audit trail.

### 5.6 Review triggers

**Last reviewed: 2026-08-20.**

Revisit the no-hosted-vault decision when **either** becomes true:

| Trigger | Why it changes the answer |
|---|---|
| **(a)** A credential must be issued **short-lived and per-session** (dynamic secrets) | SOPS encrypts a value at rest; it cannot mint one. Dynamic secrets need an issuer, which is a different class of tool |
| **(b)** Enough people are involved that **"who read what" cannot be reconstructed from memory** | An age recipient list records *who can*, never *who did*. Past that scale, an audit trail stops being optional |

⚠ **Explicitly NOT triggers**, because both are already solved:

- **Sharing with one person** — add their age public key as a co-recipient.
- **Cutting off their future access** — remove the key and run `sops updatekeys`, **then rotate**
  (§5.1). SOPS with multiple recipients and a KMS backend handles both cases without a vault.

### 5.7 ⚠ Getting from here to there

Nothing in §5.2 is in place yet. In dependency order:

1. **Install `sops` and `age`.** Neither is present.
2. **Generate the personal age keypair** at `~/.config/sops/age/keys.txt` — ⚠ **in the WSL
   filesystem**, never under `/mnt/c/`, `/mnt/g/`, or `G:\My Drive\` (§5.2). Back it up to Proton
   Pass and on paper.
3. **Fix the `.gitignore` gaps first** (findings F4/F5) — before any file is created, so the window
   where a plaintext file is committable never opens.
4. **Split each `.env`** into non-secret `.env` (committed) + `secrets.enc.env` (SOPS) per §5.2.
5. **Fill in the `TBC` cells** in §5.3, particularly `Owner`, which decides what §5.4 applies to.
6. **Record a `Last rotated` date for every row** — even if the honest entry is *"unknown, treat as
   never"*, which is itself the argument for a first pass of rotations.


---

## 6. Messaging security

| Feature | Where | Notes |
|---|---|---|
| **Central Messaging API** | `POST /api/messaging/send-sms`, `send-email` | Single delivery layer with auth + logging |
| **API key enforcement** | Messaging router | `x-api-key` required when key configured |
| **No PII in staff SMS/WhatsApp alerts** | Policy + caller responsibility | Link + reference only |
| **Context metadata for audit** | Messaging request `context` | `source_system`, `purpose`, `grievance_id`, `ticket_id`, etc. |
| **Delivery failure envelope** | Messaging API responses | Structured `FAILED` + `error_code` |

Policy: [../ticketing_system/06_messaging_rules_whatsapp_sms.md](../ticketing_system/06_messaging_rules_whatsapp_sms.md)  
Contract: [../services/05_messaging_service.md](../services/05_messaging_service.md)

---

## 7. Audit logging and traceability

| Feature | Where | Notes |
|---|---|---|
| **Ticket event audit trail** | `ticketing.ticket_events` | Append-only lifecycle and communication events |
| **Admin audit log** | `ticketing.admin_audit_log` | Settings/user/role/org changes |
| **Contact reveal logging** | Reveal endpoints + ticket events | Who accessed PII, when |
| **Messaging send logs** | Messaging service | Destination + truncated content + context + result |
| **SLA/overdue accountability** | `ticketing.ticket_overdue_episodes` | Officer/step context at breach time |
| **Correlation keys** | Cross-service audits | `grievance_id`, `ticket_id`, `request_id`, reveal session id |

---

## 8. LLM and AI safety controls

| Feature | Where | Notes |
|---|---|---|
| **PII-clean context for findings** | `ticketing.ticket_context_cache` | Findings generated from policy-safe context |
| **Role-gated AI outputs** | `ai_summary_en`, findings endpoints | Hidden from L1/L2 where configured |
| **SEAH model tiering** | LLM tasks | Stronger model path for SEAH-sensitive processing |
| **Structured JSON outputs** | LLM client contracts | Validated response format + retry/failure states |
| **No PII in staff notification content** | Notification builders | Chatbot/SMS templates use references/links |

Policy detail: [11_llm_pipeline_policy.md](11_llm_pipeline_policy.md).

### 8.1 ⚠ Self-hosted inference (T2) — the intended posture, **not deployed**

Added by [DPG-25](../sprints/2026-08-llm/03-open-models-spec.md#dpg-25), 2026-08-20. **None of this
is built.** T2 is parked because nobody owns the GPU running costs (Q-05), and this section exists so
that unparking starts from a decided network posture instead of an improvised one. Full document:
[`../dpg/vllm-deployment.md`](../dpg/vllm-deployment.md).

| Control | Requirement | Status |
|---|---|---|
| **Network placement** | Private subnet; reachable **only** from the application security group. Never internet-facing | ⚠ not deployed |
| **Transport** | TLS terminated at a reverse proxy in front of vLLM | ⚠ not deployed |
| **Authentication** | `--api-key` set **even on a private network** — defence in depth | ⚠ not deployed |
| **Recovery** | Instance snapshotted once configured, so a rebuild is minutes | ⚠ not deployed |
| **Ownership** | A named owner for monitoring and restart | ⏸ **the parked item** — Q-05. Not the hardware: the *person* |

⚠ **The API-key row is not boilerplate.** §13 of this document already carries a row about a service
bound to `0.0.0.0` *"because the firewall holds"*. **Do not add a second one.** A private network is
a blast-radius control, not an authentication story, and an inference endpoint holds grievance text
in memory.

⚠ **And note what T1 means for this section while T2 stays parked.** T1 is the **steady state, not a
transition**: grievance text — including SEAH narratives — leaves the country indefinitely, reaches a
provider that is selected per request unless the model id pins one, and is unredacted until
[Sprint 3](../sprints/2026-08-llm/04-pii-redaction-spec.md) lands. That is the trade this parking
decision makes, and it is the reason redaction moved from prudent to necessary
([privacy assessment](../dpg/privacy-assessment.md) F-17).

---

## 9. Public and token-based access controls

| Feature | Where | Notes |
|---|---|---|
| **QR token intake** | `ticketing.qr_tokens`, `GET /api/v1/scan/{token}` | Opaque token, revocable, optional expiry |
| **Public closure token** | `closure_public_token` on resolved summary | Unguessable token URL for complainant closure page |
| **Token rate limiting (planned/enforced at edge)** | Nginx/middleware | Protect public endpoints from abuse |
| **No ticket_id in public URLs** | Public closure routes | Token-only public access surface |

---

## 10. Application and API hardening

| Feature | Where | Notes |
|---|---|---|
| **Schema-scoped migrations** | Alembic (`ticketing` + `public` streams) | Prevents accidental cross-domain DDL |
| **Deny-by-default sensitive reads** | Grievance broker APIs | Explicit reveal flow required for vault content |
| **Webhook-only ticket creation from chatbot** | `POST /api/v1/tickets` | `X-Ticketing-Secret` required |
| **Export rate limits** | `report_limits` settings | Caps synchronous export volume |
| **Quarterly assignment caps** | Reports plan settings | Max reports per role per quarter |
| **Internal-only service endpoints** | Messaging and admin APIs | Not exposed as public internet features |

---

## 11. Infrastructure and deployment security

| Feature | Where | Notes |
|---|---|---|
| **TLS termination** | Nginx / production domains | HTTPS for chatbot + GRM endpoints |
| **Keycloak enforced in production** | `docker-compose.grm.yml` (`--profile auth`) | Single `grm_ui` + `ticketing_api` run with `AUTH_MODE=keycloak` |
| **Environment separation** | staging vs production URLs | Independent deployment targets |
| **Backup encryption (ops requirement)** | Operations runbook | Required in production checklist |
| **Least-privilege DB roles (ops target)** | Deployment/operations | App roles scoped to required schemas |

References: [10_production_server_spec.md](10_production_server_spec.md), [03_operations.md](03_operations.md).

---

## 12. Security feature matrix by component

| Component | Key controls |
|---|---|
| **Chatbot / orchestrator** | OTP intake, session-bound replies, no direct ticketing DB access |
| **Backend grievance API** | Encryption, brokered PII, reveal sessions, status APIs |
| **Messaging service** | API key auth, audit context, delivery policy |
| **Ticketing API** | Role/scope checks, SEAH filter, action authorization, webhooks |
| **Ticketing UI** | OIDC auth, bypass disabled in prod, role-gated screens/actions |
| **Reports** | OfficerScope filtering, export limits, role-gated quarterly admin |

---

## 13. Planned / partial controls (tracked)

| Item | Status | Tracking doc |
|---|---|---|
| Executive Summary report tab hardening | Planned | `../ticketing_system/09_reports_and_report_builder.md` §12 |
| Automated PII pattern blocking in Messaging API | Optional enhancement | `../services/05_messaging_service.md` |
| Public closure OTP (ref + phone last-4) | Post-v1 option | `../ticketing_system/08_ticket_resolution_and_case_summary.md` §3.9 |
| SSE/real-time officer notifications | Post-proto | `../ticketing_system/05_ticketing_impl_plan.md` |
| Health/monitoring (healthchecks, watchdog, daily ops report, self-hosted backups) | Proposed | `../services/11_health_and_monitoring_service.md` |
| Security monitoring + hardening backlog (Redis auth, CORS, dep/CVE scan, rate limiting, log rotation) | Proposed | `../services/12_security_monitoring_service.md` |

---

## 14. Security verification checklist (ops)

Use before staging/production promotion:

- [ ] `APP_ENV=production` (or `staging`) and `AUTH_MODE=keycloak` — never `bypass` in deployed UI/API builds
- [ ] `KEYCLOAK_ISSUER` set and Keycloak brought up with `--profile auth`
- [ ] `TICKETING_SECRET_KEY`, `MESSAGING_API_KEY`, `KEYCLOAK_WEBHOOK_SECRET` set and rotated
- [ ] `DB_ENCRYPTION_KEY` set and backed up securely
- [ ] TLS certificates valid on public domains
- [ ] SEAH role visibility tested (standard roles cannot access SEAH tickets)
- [ ] Reveal-contact audit events verified in logs/DB
- [ ] Messaging test confirms no PII in staff notification payloads

---

## 15. Related specifications

> **Privacy assessment (2026-08-18).** This document inventories the *controls*.
> [`../dpg/privacy-assessment.md`](../dpg/privacy-assessment.md) inventories the **data flows** —
> every leg where personal data crosses a boundary, verified against the code — and assesses them
> against Nepal's Individual Privacy Act 2018. It also carries a findings register (§6) with items
> this document does **not** cover: encryption at rest failing open when the key is unset,
> unsalted search hashes, unencrypted-by-default backups, and the permanent unredacted egress of
> grievance text to a model provider outside Nepal. ⚠ It was drafted by an AI agent and **has had no
> legal review** — read its §0.1 before citing it.

| Topic | Document |
|---|---|
| **Privacy assessment + data-flow inventory (indicators 7, 9, 9a)** | [`../dpg/privacy-assessment.md`](../dpg/privacy-assessment.md) |
| Privacy architecture and reveal policy | [09_privacy.md](09_privacy.md) |
| LLM safety and processing policy | [11_llm_pipeline_policy.md](11_llm_pipeline_policy.md) |
| Ticketing security decisions | [../ticketing_system/00_ticketing_decisions.md](../ticketing_system/00_ticketing_decisions.md) |
| Ticketing API auth/integration | [../ticketing_system/03_ticketing_api_integration.md](../ticketing_system/03_ticketing_api_integration.md) |
| Staff messaging policy | [../ticketing_system/06_messaging_rules_whatsapp_sms.md](../ticketing_system/06_messaging_rules_whatsapp_sms.md) |
| Messaging service contract | [../services/05_messaging_service.md](../services/05_messaging_service.md) |
| Health, monitoring & self-hosted backups | [../services/11_health_and_monitoring_service.md](../services/11_health_and_monitoring_service.md) |
| Security monitoring & hardening backlog | [../services/12_security_monitoring_service.md](../services/12_security_monitoring_service.md) |
