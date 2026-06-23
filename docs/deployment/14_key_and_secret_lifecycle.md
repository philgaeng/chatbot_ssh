# Key & Secret Lifecycle

**Status:** Operational policy. Companion to [`13_security.md`](13_security.md) and [`../services/12_security_monitoring_service.md`](../services/12_security_monitoring_service.md) §3 item 10, and the backup procedure in [`../services/11_health_and_monitoring_service.md`](../services/11_health_and_monitoring_service.md) §9.

This is a self-hosted stack — there is no managed secret manager. Secrets live in `env.local` (gitignored, confirmed). This doc defines what each secret is, how to rotate it, and how to back it up.

---

## 1. Inventory

| Secret | Used by | Impact if lost | Impact if leaked |
|---|---|---|---|
| `DB_ENCRYPTION_KEY` | Backend PII vault encryption | **Permanent PII loss** — encrypted columns become unreadable | Decrypt all stored PII |
| `POSTGRES_PASSWORD` (+ scoped role pws) | All DB access | DB outage | Full DB access |
| `REDIS_PASSWORD` | Celery broker/result + Socket.IO bus | Broker outage | Task injection / inspection |
| `TICKETING_SECRET_KEY` | chatbot↔ticketing + ticketing→backend webhooks | Integration outage | Forged webhooks / API calls |
| `MESSAGING_API_KEY` | Messaging API (SMS/email) | Messaging outage | Send messages as the system |
| `KEYCLOAK_WEBHOOK_SECRET` | Keycloak → ticketing event webhook | Onboarding events stop | Forged Keycloak events |
| `KEYCLOAK_ADMIN_PASSWORD` | Keycloak admin | KC admin lockout | Full IdP control |
| `OPS_DB_PASSWORD` | `ops_app` monitor role | Monitor can't connect | Read ops + reporting tables |
| `GITHUB_TOKEN` (optional) | Dependabot alerts API | Scan source missing | Repo read per token scope |

---

## 2. `DB_ENCRYPTION_KEY` — the critical one

Losing this key makes every encrypted PII column unrecoverable, so it must be backed up **separately** from the database (a DB backup encrypted *with* a key you also lost is useless).

- **Backup:** store the key in **two** offline locations (e.g. a password manager + an `age`/GPG-encrypted file on separate media). Never in the same bucket as DB dumps.
- **Reference from backups:** `scripts/ops/backup_db.sh` records (but never stores) which key fingerprint a dump expects, so a restore knows which key it needs. Keep the key archive in lockstep with retention.
- **Rotation:** rotating this key requires a **re-encryption migration** (decrypt-with-old → encrypt-with-new) across all PII columns. Treat as a planned maintenance with a full backup first. Do **not** rotate casually.

---

## 3. Rotation cadence (recommended)

| Secret | Cadence | Procedure |
|---|---|---|
| `REDIS_PASSWORD` | 6–12 months / on suspicion | Set new value in `env.local`, `docker compose up -d redis` then dependent services (URLs pick it up via `${REDIS_PASSWORD}`) |
| `TICKETING_SECRET_KEY`, `MESSAGING_API_KEY`, `KEYCLOAK_WEBHOOK_SECRET` | 6–12 months / on suspicion | Rotate value, restart producer + consumer together (shared secret — both sides must update atomically) |
| `POSTGRES_PASSWORD` / scoped role pws | 12 months / on personnel change | `ALTER ROLE ... PASSWORD`, update `env.local`, restart services |
| `KEYCLOAK_ADMIN_PASSWORD` | On personnel change | Rotate in Keycloak + `env.local` |
| `DB_ENCRYPTION_KEY` | Only on compromise | Planned re-encryption migration (see §2) |
| `GITHUB_TOKEN` | Per GitHub policy | Reissue, update `env.local` |

Rotation generation: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

---

## 4. Storage hardening (prod)

- `env.local` permissions: `chmod 600 env.local`, owned by the deploy user only.
- Consider `age`-encrypting `env.local` at rest and decrypting into tmpfs at deploy time, or Docker secrets, over plaintext on disk.
- The preflight gate (`scripts/ops/security-preflight.sh`) asserts each secret above is set and **not** a default/empty value before promotion.

---

## 5. Scoped DB roles

Least-privilege roles reduce blast radius if any one service is compromised. `ops_app` ships least-privilege via the ops Alembic stream; the remaining roles are opt-in via [`../../scripts/ops/create_scoped_roles.sql`](../../scripts/ops/create_scoped_roles.sql) (`chatbot_app` → `public.*`, `ticketing_app` → `ticketing.*` + read `public.grievances`, `keycloak_app` → `keycloak` schema). Apply deliberately and repoint each service's `POSTGRES_USER`/`POSTGRES_PASSWORD` in the same change window.
