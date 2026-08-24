# Incident Response — personal-data breach procedure

**Status:** Operational runbook, **drafted 2026-08-24**. Companion to [`13_security.md`](13_security.md)
(controls), [`14_key_and_secret_lifecycle.md`](14_key_and_secret_lifecycle.md) (rotation),
[`15_host_hardening.md`](15_host_hardening.md) (host), and [`../../SECURITY.md`](../../SECURITY.md)
(how a report reaches us). The privacy position it serves is
[`../dpg/privacy-assessment.md`](../dpg/privacy-assessment.md) §5.

> ### ⚠ Three decisions in this document are blank, and they are not engineering's to make
>
> Everything an engineer can decide — what detects an incident, how to contain it, what evidence
> exists and for how long — is written below and was verified against the running stack. **Three
> decisions are held open** (§0). They belong to the **Government of Nepal** — the **Department of
> Roads** as implementing agency, with MoPIT and ADB as escalation parties.
>
> **Philippe Gaeng holds all three on an interim basis**, as the only person who currently *can* act
> on them. That is a stopgap for a pilot on which **no genuine grievance has yet been processed**, not
> an arrangement anyone has agreed to. It must be replaced with named DOR roles before go-live.
> A procedure that names nobody is not followed; a procedure that names the wrong person is followed
> and fails. This one names someone and says so.

---

## 0. The three blanks

| | Decision | Why it is not ours | Interim holder |
|---|---|---|---|
| **B1** | **Who declares that an incident is a personal-data breach, and within what time.** Declaring starts every clock below | It commits the implementing agency to a legal characterisation and to notifying a regulator. Engineering can establish the facts; it cannot make the finding on DOR's behalf | **Philippe Gaeng** — declares, and records the declaration and its time in the incident log |
| **B2** | **Who must be notified, on what clock, and by whom** — DOR, MoPIT, ADB, affected data subjects, and any authority designated under the Individual Privacy Act 2018 | Notification duties and deadlines follow from a legal reading nobody on this project has (Q15, F-16). Guessing a deadline is worse than recording that none is set | **Philippe Gaeng** — notifies the DOR project focal and the ADB project officer through the project channel, immediately and without waiting for a threshold, and records it |
| **B3** | **Whether, how and by whom a survivor is told when a SEAH case is exposed** | A safeguarding decision, not an IT one. Telling a survivor that a report naming them has leaked can itself put them at risk, and the judgement belongs to the safeguarding chain | **Nobody.** ⚠ **Explicitly unheld.** Engineering contains, preserves, and escalates to the SEAH focal person and the GRC chair. It does **not** contact a complainant about a SEAH breach under any circumstance |

**Filling these in is a document edit, not a project.** Replace the interim holder with a named DOR
role, add the clock B2 needs, and record who agreed it and when.

---

## 1. Before anything: is there personal data in this system yet?

⭐ **As of 2026-08-24, no genuine grievance has been processed on this platform.** Every record in
every environment is seed data or a demo dummy
([`../dpg/privacy-assessment.md`](../dpg/privacy-assessment.md) §0.5). An exposure today is a
**security incident with no data subject** — serious as an engineering failure, and **not a personal-data
breach**, because there is no person whose data was breached.

⚠ **One caveat, and do not wave it away** (F-14): the *narratives* are synthetic, but a demo participant
may have typed **their own genuine phone number or email** into a contact field. So "no real data" is true
of the grievances and only *probably* true of the contact columns. If an exposure reaches
`public.complainants`, treat the affected rows as potentially real people and say so in the incident log.

**This is the single largest input to triage, and it expires on the first real grievance.** Check it
first, every time, and do not inherit the answer from the last incident:

```bash
# Are there grievances that are not seeded or demo? Run against the affected environment.
docker exec <db-container> psql -U user -d app_db -tAc \
  "SELECT count(*) FROM public.grievances WHERE created_at > '<go-live-date>';"
```

When the answer stops being zero, §2 onwards applies in full and B1's clock starts mattering.

---

## 2. Detection — what would tell us

| Source | What it shows | Where |
|---|---|---|
| **Vulnerability report by email** | A reporter's finding, under the terms we published | [`../../SECURITY.md`](../../SECURITY.md) — acknowledge within **3 working days**; that promise is ours and it is already made |
| **Deduped ops alert** | Any `critical` health result, non-retryable task failure | [`../../ops/alerts.py`](../../ops/alerts.py) → `HEALTH_ALERT_EMAIL` |
| **Daily ops report** | Officer logins, **failed logins**, contact-reveal counts, open critical/high dependency findings, backup + preflight status | [`../../ops/reports.py`](../../ops/reports.py) → `DAILY_REPORT_EMAIL` |
| **`ticketing.admin_audit_log`** | Every contact reveal, every officer/settings change — actor, target, payload, timestamp | [`../../ticketing/models/admin_audit_log.py`](../../ticketing/models/admin_audit_log.py) |
| **`keycloak.event_entity`** | Officer logins, login failures, admin actions | Realm `grm` — ⚠ see §4.2, this only works forward from 2026-08-24 |
| **`ops.dependency_findings`** | Nightly CVE and licence scan | [`../services/12_security_monitoring_service.md`](../services/12_security_monitoring_service.md) |

> ### ⚠ Corrected 2026-08-24 — the detection substrate is empty *everywhere*, including here
>
> The `ops` container is **not deployed to either server**, so on staging and production the detection
> column above is empty: an incident there is found by a person noticing, or by a reporter emailing us.
>
> **And in the development stack it was blind from 2026-08-21 to 2026-08-24** — ✅ **now repaired.**
> `ops` had no credential of its own and fell back to `POSTGRES_PASSWORD` while connecting as the
> `ops_app` role; that rotation did not include `ops_app`. 253 auth failures, every report row `n/a`,
> and the container reporting `healthy` throughout. Repairing it uncovered three further defects that
> meant **the activity and security rows had never returned a number on any deployment**: one aborted
> transaction blanked every row after it, four queries named columns that do not exist, and `ops_app`
> lacked SELECT on five of the tables it reads. All fixed, all verified —
> [`../sprints/2026-08-llm/followups/ops-cannot-authenticate-since-rotation.md`](../sprints/2026-08-llm/followups/ops-cannot-authenticate-since-rotation.md).
>
> **So the detection table above is now true of the development stack, and of nothing else.** Deploying
> `ops` to staging and production is the cheapest remaining improvement to this procedure.

---

## 3. Triage — what was exposed, and how bad is it

Ask what the attacker or recipient could read, then read this table. It is a compression of the
verified data-flow legs in [`../dpg/privacy-assessment.md`](../dpg/privacy-assessment.md) §2.2 —
go there for the evidence.

| If they reached… | They get | Protected by |
|---|---|---|
| **`public.complainants` contact columns** | Name, phone, email, address — **ciphertext** | pgcrypto. Useless without `DB_ENCRYPTION_KEY`, which lives only in `backend`'s environment |
| **`DB_ENCRYPTION_KEY` as well** | ⭐ **All stored contact PII, in the clear** | Nothing further. This is the worst single outcome in the system |
| **`public.grievances`** | ⚠ **The grievance narrative, in plaintext** — the field most likely to name a third party | Nothing. It is not encrypted, by design |
| **The uploads volume / its backup tar** | ⚠ **Voice recordings and photographs** — the most directly identifying material here | Nothing at rest. Backups of it are encrypted-or-discarded (§4.1) |
| **`ticketing.*`** | Ticket summaries, categories, locations, officer notes, case timelines — **no complainant contact PII, by invariant** | `tests/ticketing/test_pii_boundary.py`, `test_boundary_policy.py`. ⚠ `grievance_summary` is free text and can carry self-disclosed PII |
| **A sensitive-workflow ticket** | ⭐ A SEAH disclosure — survivor, witness, or accused | Cast-only access, pinned by `tests/ticketing/test_sensitive_workflow_access.py`. **Any exposure here is high severity and goes straight to B3** |
| **Redis** | ⚠ Task payloads carrying `grievance_description` verbatim | No persistence volume — in memory only, but present in any process or host dump |
| **A closure-document or report-share URL** | One case's closure PDF or an XLSX export | ⚠ A UUID4 / `token_urlsafe(24)` in the URL and **nothing else — these links do not expire** (`public_closure.py:38,58`). A leaked link is a live exposure until the code changes |
| **Keycloak** | Officer usernames, emails, names, credential hashes | Self-hosted, same host. No third-party IdP |

**Severity is decided on what was exposed, not on how clever the bug was.** A SEAH case, or
`DB_ENCRYPTION_KEY`, is high severity on its own. Everything else is judged on whether a real person
is identifiable from what left.

---

## 4. Containment — in this order

> ### ⚠ Read this before you type anything
>
> **`docker compose down` destroys evidence.** Container logs live in the json-file driver and are
> deleted with the container, so `down` erases the log of the incident you are investigating.
> **`restart` and `stop` keep them; `down` and `rm` do not.** Snapshot first (§5), then contain.
>
> **Restarting Redis drops queued tasks.** It has no persistence volume — that is a containment
> lever when the broker is the exposure, and evidence destruction when it is not.

**4.1 — Stop the bleeding.** Pick only what applies:

```bash
# Take the officer UI and API off the network (keeps containers, keeps logs)
docker compose -f docker-compose.yml -f docker-compose.grm.yml stop grm_ui ticketing_api

# Stop all outbound model calls — there is NO feature-flag kill switch; stopping the
# workers is the lever. celery_llm is the chatbot's; grm_celery is ticketing's.
docker compose -f docker-compose.yml -f docker-compose.grm.yml stop celery_llm grm_celery

# Revoke every officer session in the realm
docker exec <keycloak-container> /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master --user "$KEYCLOAK_ADMIN" --password "$KEYCLOAK_ADMIN_PASSWORD"
docker exec <keycloak-container> /opt/keycloak/bin/kcadm.sh create realms/grm/logout-all

# Disable one compromised officer instead of all of them
docker exec <keycloak-container> /opt/keycloak/bin/kcadm.sh update users/<user-id> -r grm -s enabled=false
```

**4.2 — Rotate what leaked.** The inventory, impact and per-secret procedure are
[`14_key_and_secret_lifecycle.md`](14_key_and_secret_lifecycle.md) §1 — **follow it, do not improvise
from memory.** Two entries are traps under time pressure and both fail *silently*:

- **`DB_ENCRYPTION_KEY` is not a rotation, it is a migration** — every pgcrypto value must be decrypted
  with the old key and re-encrypted with the new, and **no script exists**. Under incident conditions
  the honest answer is usually: do not rotate now, record it, plan it as maintenance with a full backup.
- **`SEARCH_TOKEN_PEPPER` requires [`../../scripts/database/rehash_search_tokens.py`](../../scripts/database/rehash_search_tokens.py)
  in the same window.** Skip it and phone/email lookup returns nothing, raising no error — officers
  will report "the complainant isn't in the system" and nobody will connect it to the incident.
- **`POSTGRES_PASSWORD` used to silently kill the ops monitor.** ✅ Fixed 2026-08-24 — `ops_app` has
  its own credential and the healthcheck now probes the database — but the shape is worth remembering,
  because it is the shape these failures take: rotating one role's password broke a *different* role's
  login, nothing raised, and **the thing it broke was the detection you would be relying on during the
  incident**. It ran undetected for three days on a stack somebody looks at daily.

⚠ **Standing exposure a responder must know before assessing anything.** Per §1 of the lifecycle doc,
`POSTGRES_PASSWORD` and `REDIS_PASSWORD` were rotated on the **local stack only** (2026-08-21 / 08-23).
**Staging and DOR production still hold the pre-rotation credentials, and the previous values are in
public git history.** Until those two are rotated on both servers, treat any incident touching either
box as one where the database and broker credentials are already known to the internet.

**4.3 — Isolate the blast radius.** Least-privilege database roles exist but are **opt-in**:
[`../../scripts/ops/create_scoped_roles.sql`](../../scripts/ops/create_scoped_roles.sql). If services
are still sharing one superuser role, a compromise of any one of them reaches everything. Applying
those roles is containment work that pays for itself before the next incident, not during this one.

---

## 5. Evidence — what exists, and how long you have

**Snapshot before you contain**, into a directory outside the repo, on an encrypted volume:

```bash
INC=/var/backups/grms/incident-<id>; mkdir -p "$INC"

# Per affected service. `2>&1` matters — docker logs writes the application's stderr to stderr,
# and stack traces are the half you want.
docker logs <container> > "$INC/<container>.log" 2>&1

docker exec <db-container> pg_dump -U user -Fc app_db > "$INC/db.dump"
```

| Evidence | Where | **How long it survives** |
|---|---|---|
| Container logs | json-file driver | **10 MB × 5 per service** — on a busy service that can be hours. **Deleted with the container** |
| Application file logs | `logs/*.log` | **14 days** (`deployment/logrotate/grms.conf`, `rotate 14`) |
| Database backups | `/var/backups/grms` | **14 days** (`RETENTION_DAYS`), then pruned. ✅ Encrypted **or discarded** — an unencrypted dump is only kept if an operator sets `BACKUP_ALLOW_UNENCRYPTED=1` |
| `ticketing.admin_audit_log` | `ticketing` schema | **Indefinitely** — no code path deletes it, and that is the current state of the whole platform (F-7) |
| **Keycloak login + admin events** | `keycloak.event_entity` | **90 days** — ⚠ **and only from 2026-08-24.** See below |
| `ops.system_health_checks` | `ops` schema | **90 days** ([`../../ops/maintenance.py`](../../ops/maintenance.py) `:23`) |
| `ops.dependency_findings` | `ops` schema | Not pruned — nothing deletes it |

> ### ⚠ Keycloak events: fixed 2026-08-24, and forward-only
>
> Keycloak stores **no** login or admin events unless the realm asks for it, and both default to off.
> Nothing in this repository turned them on, so **no login was recorded on any environment before
> 2026-08-24** — and none of it is recoverable. The daily ops report queried `keycloak.event_entity`
> for "Officer logins" and "Failed logins" throughout ([`../../ops/reports.py`](../../ops/reports.py)
> `:45`, `:55`) and reported **0** rather than "not recorded", which is why nobody noticed.
>
> `setup_realm_event_logging` in
> [`../../ticketing/auth/keycloak_setup.py`](../../ticketing/auth/keycloak_setup.py) now enables both
> with a 90-day expiration, applied by `make keycloak-setup`. Verified on the local realm:
> `events_enabled=t`, `admin_events_enabled=t`, `events_expiration=7776000`, and a failed login writes
> a `LOGIN_ERROR` row. ⚠ **Not yet applied to staging or production** — run `make keycloak-setup`
> against each after the next image build.

**The shortest clock is the one that binds.** With backups at 14 days and container logs measured in
megabytes, an incident reported four weeks late may be uninvestigable — which is a fact to record in
the incident log, not a reason to guess.

---

## 6. Notification

**B1 declares. B2 notifies. B3 decides anything involving a survivor.** Until those are filled in by
DOR, the interim holder does the following, and records each step with a timestamp:

1. **Tell DOR and ADB early and without waiting for a threshold.** An implementing agency that learns
   of a breach late has lost the choices it should have had. This costs nothing if the incident turns
   out to be minor.
2. **Do not notify data subjects unilaterally.** Whether, when and how a complainant is told is B2's
   decision, and for a SEAH case it is B3's — which nobody currently holds.
3. **A SEAH exposure escalates to the SEAH focal person and the GRC chair, and stops there** pending a
   safeguarding decision. Engineering does not contact the complainant.
4. **Tell the reporter, if one reported it.** [`../../SECURITY.md`](../../SECURITY.md) promises them we
   will say when a report turns out to have exposed real complainant data. That promise is now written
   against this document.

**What we cannot yet say** — and should say we cannot: whether a statutory deadline applies under the
Individual Privacy Act 2018, and to which authority. That is Q15's dependency, tracked as **F-8** in
[`../dpg/privacy-assessment.md`](../dpg/privacy-assessment.md) §6.

---

## 7. Recovery and post-incident review

- Restore from `/var/backups/grms` only after the entry vector is closed — the backup may predate the
  intrusion, or contain it.
- Re-run `scripts/ops/security-preflight.sh` before putting the service back on the network.
- **Write the review within a week, while it is still uncomfortable.** What was exposed, what the
  detection latency was, which control should have caught it, and — the question this project keeps
  finding value in — **what did we believe was true that was not?** The Keycloak gap in §5 was found
  exactly that way: a claim in a privacy document, checked against the database.
- Every fix that comes out of a review gets a ticket and a follow-up file, per
  [`../sprints/README.md`](../sprints/README.md). A lesson with no ticket is a lesson lost.

---

## 8. Known gaps in this procedure

Stated so the omissions are deliberate and findable, per engineering rule 9.

| Gap | Consequence | Owner |
|---|---|---|
| **B1, B2, B3 unfilled** (§0) | No declaration authority, no notification clock, no survivor-notification decision | **DOR** |
| **`ops` not deployed to staging or production** | The detection column of §2 is empty on both servers | Engineering — deploy |
| ~~**`ops` cannot authenticate to the database**~~ ✅ **fixed 2026-08-24** | Was: every report row `n/a` while the container reported `healthy`. Now: `ops_app` has its own credential, the healthcheck probes the database, and every report row returns a number | — |
| **Keycloak events not yet enabled on staging/production** | No login evidence there until `make keycloak-setup` is re-run | Engineering — next deploy |
| **`POSTGRES_PASSWORD` / `REDIS_PASSWORD` not rotated on either server** | Both are in public git history and still live there | Engineering — [`14_key_and_secret_lifecycle.md`](14_key_and_secret_lifecycle.md) §1 |
| **No `DB_ENCRYPTION_KEY` re-encryption script** | The one rotation that matters most cannot be executed under incident conditions | Engineering |
| **Public closure and report-share links never expire** | A leaked URL stays live indefinitely | Engineering |
| **No deletion capability anywhere** (F-7) | "Delete the exposed record" is not an available remediation | Needs a legal position first |
| **No off-box backup destination in the repo** | Whether an off-site copy exists is a deployment fact this document cannot verify | Engineering — record it |

---

## Related

| | |
|---|---|
| How a vulnerability reaches us, and what we promised the reporter | [`../../SECURITY.md`](../../SECURITY.md) |
| Privacy position, data-flow legs, findings register | [`../dpg/privacy-assessment.md`](../dpg/privacy-assessment.md) |
| Secret inventory and rotation procedures | [`14_key_and_secret_lifecycle.md`](14_key_and_secret_lifecycle.md) |
| Security controls index | [`13_security.md`](13_security.md) |
| Host-OS hardening | [`15_host_hardening.md`](15_host_hardening.md) |
| Keycloak realm, clients, invites | [`16_auth_keycloak.md`](16_auth_keycloak.md) |
| Archiving policy (which is not deletion) | [`../ARCHIVING_AND_RETENTION.md`](../ARCHIVING_AND_RETENTION.md) |
