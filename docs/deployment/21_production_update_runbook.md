# Production update runbook — DOR host, from its June checkout to current

**Status:** Operational runbook for a specific, one-off update. Written 2026-09-16 from facts measured on the host that day, not from the specs — several of which were wrong about this box.
**Audience:** internal
**Last updated:** 2026-09-17 — ✅ **the update is COMPLETE and verified end to end** (§11a), and ✅ **the database and Redis credentials are rotated** (§11b); §1a records why this host's ports look internet-exposed and are not. Earlier, 2026-09-16 — §8: ⛔ **the nginx step took the site down** (`GRM-147`) and is rewritten so a failed validation cannot apply; §11 records where production actually stopped. Earlier: §4 question 1 **answered** (`GRM-142`): the vault holds 25 live encrypted payloads, so the public stream stays stuck. §2 gains what production's data actually shows (`GRM-144`, `GRM-145`)

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

## 1a. ⚠ This host's ports look internet-exposed. They are not.

A TCP connect from the open internet **succeeds** on 5432, 5433, 6379, 18080, 3001, 5002 and 8080.
That is the **upstream NAT device** completing the handshake for ports it never forwards — the host
itself is `192.168.20.63`, and the public address is not on it.

⚠ **Measured 2026-09-17, after I called this a critical exposure on the strength of the TCP connect
alone.** The protocol-level check is what settles it: HTTP returns `000` on 3001/5002/18080 and
Postgres sends no packet at all on 5433. Nothing is behind those accepted connections.

**So a port scan of this host is misleading, and anyone who runs one will reach the wrong
conclusion.** Always follow a connect with a protocol probe before acting.

**What remains true at its proper size:** those ports bind `0.0.0.0`, so anything on the DOR internal
network or the VPN reaches Postgres and Redis directly. Binding them to `127.0.0.1` in compose is
the durable fix — an iptables `DOCKER-USER` rule does not survive a reboot, and on this host it
matched zero packets because inbound traffic does not arrive the way the rule assumed.

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

1. ~~Are those 25 vault payloads live SEAH data, superseded data, or test data?~~ ⛔ **ANSWERED
   2026-09-16 — live encrypted content.** The columns are `content_ciphertext`, `content_redacted`,
   `content_hash`, `pii_detection_metadata`, `case_sensitivity`: this is the **sensitive-content
   vault**, 25 rows spanning 2026-04-28 to 2026-06-19. And it is **broader than SEAH** — 25 payloads
   against only 4 `grievances_seah`, keyed by `grievance_id` with its own sensitivity column.
   Running the baseline would destroy 25 encrypted sensitive payloads.
2. If they must be kept — migrated into the canonical model, or exported and retained outside the DB?
3. If they may go — who confirms that, and where is it recorded? CL-01's "0 rows" finding is now
   known to be false for production, so it cannot be the authority a second time.

**Until answered: the public stream stays stuck. That is the correct state, not a problem to clear.**

## 4a. What production's data says about the running system

Measured 2026-09-16 while answering §4. Two findings that change what "update the box" means.

**The SLA watchdog is not running (`GRM-144`).** Tickets: 70 OPEN, 59 ESCALATED, 1 RESOLVED,
created 2026-04-27 → 2026-08-21 — but `sla_breached` is **false on 129 of 130**. The UI computes
overdue live (`queueTiles.ts:28`), so everything correctly *looks* overdue; the flag is the
watchdog's, and `escalation.py:550` selects exactly those unflagged tickets to escalate. If it were
running they would be escalating. It ran once — 58 overdue episodes exist — then stopped. **The last
ticket event of any kind is 2026-08-21.**

**Contact details are present but not displayed.** 70 of 130 tickets join through to a complainant
with both a name and a phone, so the data is reachable. The likely cause is that production
**predates T3-04**: at `00f13230`, `GET /api/grievance/{id}` returned pgcrypto hex and ticketing
decrypted client-side via `pii_vault.py` — the workaround T3-04 deleted when it moved decryption
server-side. ⭐ **If so, this update is the fix.** Confirm from `ticketing_api` logs while opening a
ticket rather than assuming.

**3 phone numbers are stored in plaintext (`GRM-145`)** in a column that is supposed to be
encrypted: of 89 values, 79 are ciphertext, 3 are bare 10-digit numbers, 7 are a 12-character
sentinel containing letters. `_decrypt_field` returns the raw value when decryption fails, which is
why this rendered correctly and stayed invisible.

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

nginx last — ⛔ **and only once `GRM-147`'s `prod.yml` fix is on `main`**, or it crash-loops.

⛔ **These MUST be one `&&`-chained command.** On 2026-09-16 they were given as three separate
lines: the validation failed, the apply ran anyway, and the site went down. A test that cannot
stop what follows it is not a gate.

```bash
$PC run --rm --no-deps -T nginx "sh /etc/nginx/site/bootstrap.sh --test" \
  && $PC up -d --no-deps nginx \
  && sleep 10 && docker ps --format '{{.Names}}\t{{.Status}}' | grep nginx
```

Expect `Up … (healthy)`, **never** `Restarting`. Then confirm from **outside the box** — the host
cannot reach its own public hostname (hairpin NAT), so an empty `curl` run on the box proves nothing.

**Rollback** routes traffic back to the June `_auth` containers, which must still be running:

```bash
git checkout 00f13230 -- docker-compose.yml docker-compose.aws.yml docker-compose.grm.yml docker-compose.prod.yml deployment/nginx \
  && $PC up -d --no-deps --force-recreate nginx \
  && git checkout HEAD -- docker-compose.yml docker-compose.aws.yml docker-compose.grm.yml docker-compose.prod.yml deployment/nginx
```

⚠ **Do not remove the orphan `_auth` containers until the new site is verified.** The June nginx
routes to `grm_ui_auth:3001` and `ticketing_api_auth:5003`; they are the rollback path.

## 11. Where production actually stopped, 2026-09-16

| Step | State |
| --- | --- |
| Backup | ✅ first ever — `app_db_20260916T081356Z.dump`, dir `700`, files `600` |
| `env.local` | ✅ `0600`; ✅ `GHCR_READ_TOKEN` added; ⏳ `OPS_DB_PASSWORD` not yet set |
| Code | ✅ `main` at `b3e890d2`, pulled on the host |
| Images | ✅ `app:b3e890d`, `ui:b3e890d` pulled (registry is private — the token was required) |
| Ticketing migrations | ✅ **all 23 applied**, head `b3d5f7h9`; `HR-03` dedup was a no-op |
| Ops migration | ⏳ not run |
| Public stream | ⛔ deliberately not run (§4) |
| New containers | ✅ `ticketing_api`, `grm_ui`, `backend`, `celery_default`, `grm_celery`, `ops` up at `b3e890d` |
| `grm_celery_beat` | ⏳ **held back on purpose** — the old one still runs from June; see §12 |
| nginx | ⛔ **rolled back to June** after crash-looping (`GRM-147`); site served, `302` from outside |
| Serving users | the June `grm_ui_auth` + `ticketing_api_auth`, against the **migrated** schema |

⚠ **June's code is serving against the new schema.** The migrations are additive, and the site
answered `302` afterwards — but the cutover should not wait long.

## 11a. ✅ Verified end to end, 2026-09-17

The owner **read a SEAH grievance's phone number through the new UI**. That single act closes the
chain this whole update existed for:

- **Contact details display again.** The §4a hypothesis was right: production predated T3-04 and was
  still attempting the deleted client-side decryption path. The update was the fix.
- **PII decryption works server-side** on the deployed code.
- **SEAH access works, and works the way it is designed to** — via cast membership on a
  `KL_ROAD_SEAH` step, not via `org_admin`, which grants configure rights and no case access.
- **The officer UI is live on the new code**, serving from the migrated database through the new
  nginx routing.

Also settled the same day: the queue was pruned to **54 live tickets** (76 pre-16-June trials
soft-deleted, reversible), and the two live SEAH tickets surface under **High Priority** — the
Actor and Supervisor tabs are correctly empty, since neither is assigned to the reader and they sit
at a Level 1 step.

## 11b. ✅ Credentials rotated and the stack fully restarted, 2026-09-17

`POSTGRES_PASSWORD` and `REDIS_PASSWORD` rotated in one pass: `sed` on `env.local` (backed up to the
operator's home directory, **outside the repo**), `ALTER ROLE` for the Postgres role, then
`up -d --force-recreate --remove-orphans` across the whole stack.

- **Verified by consequence, not assumption.** Every container holds the new value from `env.local`;
  had the `ALTER ROLE` not run, all of them would be failing authentication. The site returns `200`
  and the queue renders, which only works if file and role agree.
- **Redis came up on `8.10.1`** — the `redis:8.10` pin is a **licence** decision (Redis 8 is
  tri-licensed and AGPLv3 is elected; `redis:7` had floated onto the non-OSI line), and the minor pin
  is doing its job: patches arrive, a relicence does not.
- **The June `_auth` containers were removed**, ending the nginx rollback path — acceptable only
  because the cutover had been verified down to reading a grievance's phone number (§11a).
- ⚠ **The passwords now differ from AWS staging**, which is un-rotated. A single `secrets.enc.env`
  asserts one value per secret across hosts; production's is hand-written, so that assertion does not
  bind here — but it will the moment anyone migrates this host to SOPS. See
  [`18_sops_migration_handover.md`](18_sops_migration_handover.md) §5a Hazard 1.

## 12. ⚠ The SLA watchdog is already running

`docker ps` after Step 5 showed **`grms-grm_celery_beat-1` — `Up 2 months (healthy)`**, the June
container, still running. "Holding back `grm_celery_beat`" only kept the *new* image from starting;
the old scheduler was never stopped. So whatever it does, it has been doing throughout — yet
`GRM-144` found 129 tickets unflagged, which means that beat is running and **not escalating**.
Find out why before replacing it: the new watchdog may behave very differently from the old one.

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
