# Production update runbook — DOR host, from its June checkout to current

**Status:** Operational runbook for a specific, one-off update. Written 2026-09-16 from facts measured on the host that day, not from the specs — several of which were wrong about this box.
**Audience:** internal
**Last updated:** 2026-09-16 — written; Phase 0 complete, Phase 1 blocked on a decision (§4)

> **Goal beyond this update:** make production and staging differ **only** in the repo root path
> (`/opt/grms` vs `/home/ubuntu/nepal_chatbot`) and in host-specific values, so that every future
> deploy is one command against either. Today they differ in the compose file set, the environment
> variable set, the Compose project name, and whether anything is scheduled at all.

---

## 1. What production actually is, measured 2026-09-16

Do not trust the specs on these — each line below contradicted something written down.

| | Production | Staging |
| --- | --- | --- |
| SSH user | **`administrator`** | `ubuntu` |
| Repo root | **`/opt/grms`** | `/home/ubuntu/nepal_chatbot` |
| Compose project | **`grms`** (containers `grms-db-1`, …) | `nepal_chatbot` |
| Compose files | `docker-compose.yml` + **`aws.yml`** + `grm.yml` + **`prod.yml`** | `yml` + `aws.yml` + `grm.yml` |
| Commit | **`00f13230`** (2026-06-25) | current |
| `env.local` | hand-written, **68 vars**, 11 missing | generated, 54 vars |
| Scheduled tasks | **none at all** | n/a |
| Ops monitor | never ran (`OPS_DB_PASSWORD` absent) | runs |
| Reachable | Sophos VPN + password SSH | Tailscale name only |

⚠ **Production runs *both* the `aws` and `prod` overlays**, with `prod.yml` last so its
`volumes: !override` wins for nginx. This is why `make prod-deploy` is unsafe — see §3.

## 2. Database state

| Stream | Production | Head | Gap |
| --- | --- | --- | --- |
| `ticketing.*` | `g0h2i4j6` | `b3d5f7h9` | **23 behind** |
| `ops.*` | `ops002_depfindings` | `ops003_reportgrants` | 1 behind |
| `public.*` | `pub009_seah_service_providers` | `pub000_public_core_baseline` | ⛔ **unreachable — see §4** |

Row counts that matter (2026-09-16): **130** grievances · **144** complainants · **130** tickets ·
330 ticket_events · 248 admin_audit_log · 19 file_attachments · **25 `grievance_vault_payloads`** ·
**4 `grievances_seah`** · **4 `complainants_seah`**.

⛔ **This rules out drop-and-reinstall.** 130 grievances with a 248-row audit trail is a system in
use, and this codebase has no delete path on purpose: erasure in a government GRM is a suppression
path. Backup, then migrate.

## 3. ⛔ Do not use `make prod-deploy`

Every deploy action in the prod targets goes through `REMOTE_COMPOSE`, which hardcodes
`docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml` — it **omits
`docker-compose.prod.yml`**, which production actually runs. `aws.yml` sets
`NGINX_SITE_CONF: webchat_rest_compose_aws.conf` (staging's server_name); `prod.yml` mounts
`webchat_rest_compose_prod.tls.conf` for `grm-chatbot.dor.gov.np` plus the certbot certificates,
via `volumes: !override`.

So that target would point production's nginx at staging's hostname and drop the TLS certificate
mount, then reload. Separately, its `PROD_SERVER_USER` / `PROD_REMOTE_DIR` defaults are wrong for
this host (`GRM-136`). **Until `GRM-141` is fixed, deploy by hand with all four `-f` flags.**

Define this once per session on the host:

```bash
cd /opt/grms
PC="docker compose --env-file env.local -f docker-compose.yml -f docker-compose.aws.yml -f docker-compose.grm.yml -f docker-compose.prod.yml --profile auth"
```

## 4. ⛔ THE BLOCKER — decide this before Phase 1

Production's `alembic_version_public` is **`pub009_seah_service_providers`**, a revision that no
longer exists: CL-01 squashed `pub000..pub009` into `pub000_public_core_baseline` on 2026-07-06.
`alembic upgrade head` on the public stream fails with *"can't locate revision"* rather than doing
anything — **the stream is stuck, and being stuck is what is protecting the data.**

That baseline's own docstring says it DROPS, as *"product-owner-confirmed dead, 0 rows"*:
`grievance_history`, `users`, `contact_info`, `resource_persons`, `grievance_reveal_sessions`,
`grievance_sensitive_access_audit`, **`grievance_vault_payloads`**.

**Production holds 25 rows in `grievance_vault_payloads`**, plus 4 and 4 in `grievances_seah` and
`complainants_seah`. **The audit that authorised the drop was not run against production.** No
application code reads any of the three — they are dead to the code — but the rows are SEAH PII
vault content, the most sensitive category this system handles.

⚠ **The obvious fix is the dangerous one.** `alembic stamp pub000_public_core_baseline` clears the
stuck revision in one command and is what anybody would reach for. It would leave 33 rows of SEAH
data sitting outside the schema's declared source of truth, invisible to the baseline check, with
no record of the decision.

**Answer these before touching the public stream:**

1. Are those 25 vault payloads live SEAH data, superseded data, or test data? (`grievance_parties`
   + PII vault is the canonical model; these may predate it.)
2. If they must be kept — migrated into the canonical model, or exported and retained outside the DB?
3. If they may go — who confirms that, and where is it recorded? CL-01's "0 rows" finding is now
   known to be false for production, so it cannot be the authority a second time.

**Until answered: the public stream stays stuck. That is the correct state, not a problem to clear.**

## 5. Phase 0 — safety ✅ DONE 2026-09-16

- ✅ `chmod 600 /opt/grms/env.local` (`GRM-135`) — was `0644`, world-readable, holding
  `DB_ENCRYPTION_KEY` beside `POSTGRES_PASSWORD`.
- ✅ First backup this system has ever taken: `app_db_20260916T081356Z.dump` (600 KB) +
  `uploads_…tar.gz` (1.2 MB). Invoke through `bash` until `GRM-139`'s mode fix reaches the host:
  `sudo BACKUP_DIR=/var/backups/grms bash /opt/grms/scripts/ops/backup_db.sh /opt/grms`
- ✅ `/var/backups/grms` set to `700`, files `600`.
- ⏳ **Nothing has ever been restored from a backup of this system.** Verify the archive before
  relying on it: `sudo docker exec grms-db-1 pg_restore --list /tmp/b.dump | head`
- ⏳ Backups are `enc=false, offbox=false` — unencrypted and on the machine they protect
  (`GRM-140`).

## 6. Phase 1 — environment parity (do before any deploy)

Eleven variables the code expects are absent from production's `env.local`. Two block the deploy
itself:

| Missing | Consequence |
| --- | --- |
| **`GHCR_READ_TOKEN`** | image pulls fall back to unauthenticated — a private registry answers *denied* |
| **`OPS_DB_PASSWORD`** | the ops monitor cannot connect — **this is why production has never had monitoring**, despite its ops migrations having run |
| `AUTH_MODE`, `APP_ENV` | runtime mode selection |
| `ADMIN_EMAILS`, `SES_VERIFIED_EMAIL` | recap mail recipients (`ADMIN_EMAIL` still works as fallback) |
| `UPLOAD_DIR`, `UPLOAD_PROTOCOL`, `VENV_DIR` | path/protocol defaults |
| `HG_TOKEN`, `HG_USERNAME` | optional — open-model route only |

Also present and stale: **`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`** — the credentials
`GRM-095` removed *and revoked* — plus `PINPOINT_APPLICATION_ID` from the SNS path deleted
2026-08-24, and the unused `TEMP_SMTP_*` fallback set.

⛔ **Do not run `make env-local` on this host.** It regenerates from `.env.shared` +
`secrets.enc.env` and would overwrite ~10 host-specific values this box needs — `KC_HOSTNAME_URL`,
`KEYCLOAK_ISSUER`, `KEYCLOAK_ADMIN_URL`, `KEYCLOAK_JWKS_URL`, `KEYCLOAK_INVITE_REDIRECT_URI`,
`KC_HTTP_RELATIVE_PATH`, `NEXT_PUBLIC_OIDC_ISSUER`, `NEXT_PUBLIC_BYPASS_AUTH`, `SMS_ENABLED`,
`CHATBOT_WEBCHAT_URL` — and `sops` is not installed here anyway. Add the missing keys **by hand**,
one at a time, keeping a backup of the file.

## 7. Phase 2 — code

`main` is the production branch and sits at `00f13230`. Merge `integration/stage` into it; that
also brings the **`uvicorn>=0.22.0,<0.50`** pin, absent from `main`, without which a fresh build
crash-loops.

Merging does not deploy. Nothing changes on the host until §8.

## 8. Phase 3 — deploy, by hand

With `$PC` from §3, and `IMAGE_TAG` set to the **first 7 characters** of the merge commit:

```bash
git -C /opt/grms fetch origin && git -C /opt/grms status --short   # expect a clean tree first
git -C /opt/grms pull --ff-only origin main
IMAGE_TAG=<7-char-sha> $PC pull ticketing_api backend celery_default grm_celery grm_celery_beat ops grm_ui
IMAGE_TAG=<7-char-sha> $PC up -d ticketing_api backend celery_default grm_celery grm_celery_beat ops grm_ui
```

Then migrations — **ticketing and ops only**, never public until §4 is answered:

```bash
IMAGE_TAG=<7-char-sha> $PC run --rm --no-deps backend python -m alembic -c ticketing/migrations/alembic.ini upgrade head
IMAGE_TAG=<7-char-sha> $PC run --rm --no-deps backend python -m alembic -c ops/migrations/alembic.ini upgrade head
```

nginx last, validated before applied:

```bash
$PC run --rm --no-deps -T nginx "sh /etc/nginx/site/bootstrap.sh --test"
$PC up -d --no-deps nginx
$PC exec -T nginx nginx -s reload
```

## 9. Phase 4 — what production has never had

Neither of these is optional if production is meant to be operable rather than merely running.

- **Scheduled tasks.** The host has **no crontab at all** — no backup, no restore drill, no
  watchdog, and no certbot renewal, which is why the TLS certificate expired on 2026-09-13
  (`GRM-112`, cause found 2026-09-16). Install per [`15_host_hardening.md`](15_host_hardening.md) §6.
- **The ops monitor**, once `OPS_DB_PASSWORD` exists. Until then nothing on that box reports
  anything to anyone — which is how a certificate expiry, a missing backup and a three-month-old
  checkout all went unnoticed simultaneously.

## 10. Convergence — the actual goal

After the update, close the remaining differences so future deploys are one command:

1. **`GRM-141`** — give the prod targets their own `PROD_COMPOSE` including `prod.yml`.
2. **`GRM-136`** — correct `PROD_SERVER_USER` to `administrator` and `PROD_REMOTE_DIR` to `/opt/grms`.
3. **`GRM-143`** — bring production's `env.local` to the same 54-variable shape, with host-specific
   values in an `env.local.extra` as [`18_sops_migration_handover.md`](18_sops_migration_handover.md) §5a describes, so it can eventually be generated rather than hand-kept.
4. Decide whether the Compose **project name** should match (`grms` vs `nepal_chatbot`). Container
   names follow it, so every runbook command that names a container is environment-specific until
   it does. ⚠ Renaming a Compose project **orphans its volumes** — this is not a cosmetic change and
   needs its own plan.
