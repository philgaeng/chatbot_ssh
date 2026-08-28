# PII egress inventory — every path by which grievance text leaves the agency's control

> **Ticket:** [DPG-30](../sprints/2026-08-llm/04-pii-redaction-spec.md#dpg-30) · **Written:** 2026-08-27
> · **Branch:** `dpg/sprint3-pii`
>
> **What this is.** The scope statement for [DPG-33](../sprints/2026-08-llm/04-pii-redaction-spec.md#dpg-33)
> and [DPG-34](../sprints/2026-08-llm/04-pii-redaction-spec.md#dpg-34), and an indicator-7 artefact in
> its own right. Every row was found **by reading the code**, not by reading the data-flow diagram —
> and §4 lists what the diagram got wrong, which is the point of doing it this way round.
>
> ⚠ **Authored by an AI agent. No legal review.** Same honesty marker as
> [`privacy-assessment.md`](privacy-assessment.md), and for the same reason (Q-07).

---

## 0. Method, and the one thing that could not be verified

Each path was traced from the code that produces the text to the code that transmits or stores it.
Every citation below was opened and read; none is inherited from another document.

🔴 **One acceptance item could not be met, and it is not a formality.** DPG-30 requires *"Redis
persistence configuration and backup destination **verified in-container**, not assumed"*. **Docker is
unavailable in this WSL distro** (`docker: command not found` — Docker Desktop's WSL integration is
off), so nothing here was checked at runtime.

That matters more than usual, because **§2's headline finding is precisely a claim that was inferred
rather than checked**, and this document cannot close it either — it can only show that it is open.
Logged: [`followups/redis-persistence-is-inferred-not-verified.md`](../sprints/2026-08-llm/followups/redis-persistence-is-inferred-not-verified.md).

**What is claimed here and what is not:** every row's *code* facts are verified. Every row's *runtime*
facts — what a container actually does with them — are marked `⚠ unverified` and say so.

---

## 1. The inventory, ranked by likelihood of real exposure

Ranked as DPG-30 requires: **by how likely the text is to end up somewhere nobody intended**, not by
how alarming the destination sounds. The model call is the leak everyone designs against; the logs are
the leak that actually happens.

| # | Egress | What it carries | Verified at | Rank |
|---|---|---|---|---|
| **E1** | **Application logs** | OTP codes, phone numbers, the full grievance narrative, the whole grievance dict | §3 | 🔴 **1 — happens continuously, today** |
| **E2** | **Celery payloads → Redis** | `grievance_description` verbatim | §2 | 🔴 **2 — every intake; persistence unverified** |
| **E3** | **Database backups** | Everything, incl. narratives, notes, voice recordings, photographs | `scripts/ops/backup_db.sh` | 🟠 **3 — off-box destination is operator-set** |
| **E4** | **Model provider** (crosses the border) | Raw narrative, officer notes, whole case timelines | §5 | 🟠 **4 — deliberate, and the only one already designed for** |
| **E5** | **Admin recap emails → SMTP relay** | The **entire** grievance dict, including narrative and complainant contact | §6 | 🟠 **5 — every submission, to a configured list** |
| **E6** | **XLSX quarterly reports → email** | `grievance_summary`, truncated to 500 chars | `ticketing/services/report_rows.py:459` | 🟡 **6 — quarterly, to named roles** |
| **E7** | **Complainant recap email → SMTP relay** | Their own grievance data | `backend/actions/action_outro.py:153` | 🟡 **7 — consented-ish; see §6** |
| **E8** | **Public closure PDF** | Resolution text | `ticketing/api/routers/public_closure.py:38`, `:58` | 🟡 **8 — unauthenticated, non-expiring token** |
| **E9** | **Uploads volume** | Voice recordings, photographs | `docker-compose.yml:50`, `:110`, `:147` | 🟡 **9 — not redactable; see §5** |
| **E10** | **SMS → DOIT gateway** | Complainant phone + short message body | `backend/api/routers/messaging.py:95` | 🟢 **10 — in-country by design, no fallback** |
| **E11** | **`POST /message` → orchestrator** | Officer replies | `ticketing/clients/orchestrator.py` | 🟢 **11 — internal** |
| **E12** | **Observability** | — | — | ⚪ **none installed — verified** |

**E12, verified rather than assumed:** `grep` over `requirements*.txt` and the UI `package.json` files
finds **no** Langfuse, OpenTelemetry, Sentry, Datadog or New Relic. The source narrative's §3.4 assumes
Langfuse and it does not exist here. **The rule still needs writing for whatever is added later** — an
LLM-tracing tool is the single fastest way to undo this entire sprint, because tracing tools capture
prompts by default and prompts are where the narrative is.

---

## 2. 🔴 E2 — "Redis has no persistence volume" is an inference, and four documents state it as fact

**What is verified, from source:**

- `docker-compose.yml:214-234` defines `redis` **once**. It declares **no `volumes:` key**.
- Its command is `redis-server` with, at most, `--requirepass` — **no `--save`, no `--appendonly`, no
  config file.** No `redis.conf` is mounted anywhere in the repository.
- `redis` is **not overridden** in `docker-compose.grm.yml`, `.prod.yml` or `.aws.yml` — the service is
  absent from all three, so the base definition is what runs everywhere.

**What is inferred, and repeated as fact in four documents (five statements):**

> *"the `redis` service declares **no persistence volume**, so payloads are not written to durable
> storage — but they are in memory and in any process dump"* — [`privacy-assessment.md`](privacy-assessment.md) §2.2 leg **L3**

The same inference appears in [`14_key_and_secret_lifecycle.md`](../deployment/14_key_and_secret_lifecycle.md)
(*"a restart drops queued tasks"*), [`19_incident_response.md`](../deployment/19_incident_response.md)
twice (*"in memory only"*, and *"restarting Redis drops queued tasks — that is a containment"*), and
[`TODO.md`](../TODO.md) (*"no persistence volume, so no dataset to migrate"*).

⚠ **"Compose declares no volume" does not establish "nothing is written to disk."** Two mechanisms sit
between them, and neither is visible in the compose file:

1. **The official `redis` image declares its own `VOLUME /data`.** A service that declares no volume
   still gets an **anonymous** one, created by Docker, living on the host.
2. **`redis-server` with no config file uses Redis's compiled-in defaults**, and the default `save`
   points enable RDB snapshotting. Redis would write `dump.rdb` into that directory on its own
   schedule.

**If both hold, the mitigation is backwards**: grievance narratives are being snapshotted to a host
volume that no backup covers, no retention policy names, and no document knows exists.

🔴 **This document cannot settle it** — that needs `docker compose exec redis redis-cli CONFIG GET save`,
`CONFIG GET appendonly` and `docker inspect` on the container's mounts, and Docker is unavailable here
(§0). **Nor did the 2026-08-18 "✅ VERIFIED LIVE" note settle it**, though it reads as though it might:
that check verified the *licence and usage* audit — version, auth, `PING`/`SET`/`GET`/`LLEN`, a pub/sub
round-trip — and its persistence sentence, *"No data to migrate, as predicted — the service declares no
volume"*, **restates the inference rather than testing it.**

**Three consequences, and the third is the one to act on first:**

- **The privacy assessment carries a mitigation that may not exist**, in the leg describing the broker
  that holds unredacted SEAH disclosures.
- **The incident-response runbook states a containment property that may be false.** *"Restarting Redis
  drops queued tasks"* is advice someone will follow **during an incident**, when being wrong is
  expensive — if an RDB file exists, a restart reloads it and the containment does not happen.
- ⚠ **Do not "fix" the documents by adding a volume, and do not fix them by deleting the sentence.**
  Run the three commands. If persistence is on, the fix is `--save ""` plus `--appendonly no` on the
  command line, which makes the claim *true* rather than merely written down — and that belongs in
  DPG-34, not here.

---

## 3. 🔴 E1 — the log surface is larger than any document says, and two entries are credentials

[`privacy-assessment.md`](privacy-assessment.md) finding **F-6** names the log sink and, as corrected on
2026-08-27, points at one site: the complainant's phone in `phone.py:27`/`:38`. **Reading the code finds
more, and two of them are worse than a phone number.**

| Site | What it logs | Level | Note |
|---|---|---|---|
| `backend/actions/forms/form_otp.py:312` | 🔴 **The OTP the complainant just typed** — `f"{self.name()} - Received value: {slot_value}"` in `validate_otp_input` | **INFO** | **An authentication credential in application logs** |
| `backend/actions/forms/form_otp.py:343` | 🔴 The OTP again, on the invalid-format path | **INFO** | |
| `backend/actions/forms/form_otp.py:169` | The complainant's phone | DEBUG | |
| `backend/actions/forms/form_status_check.py:76` | 🔴 The complainant's phone — **behind a truncation that does nothing** | **INFO** | See below |
| `backend/actions/action_outro.py:145` | 🔴 **The entire `grievance_data` dict** — narrative, summary, categories, contact fields | DEBUG | One line, whole record |
| `backend/actions/services/contact/phone.py:27`, `:38` | The complainant's phone, on **every** validation | **INFO** | The site F-6 already names |
| `backend/actions/forms/form_grievance.py:133` | The grievance detail as typed | DEBUG | |
| `backend/actions/forms/form_grievance_complainant_review.py:93`, `:243`, `:349`, `:496`, `:627` | `grievance_summary` and its edits | DEBUG / INFO | Five sites in one file |
| `backend/services/database_services/postgres_services.py:185` | The whole `data` dict, on a save error | ERROR | Fires exactly when something is already wrong |

⭐ **`form_status_check.py:76` is worth reading closely, because it looks mitigated and is not:**

```python
_sv = slot_value if not isinstance(slot_value, str) else (slot_value[:20] + "..." if len(slot_value) > 20 else slot_value)
self.logger.info("validate_complainant_phone: entry | slot_value=%s", _sv)
```

A Nepali mobile number is **10 digits**. The truncation triggers at 21 characters, so it never fires and
**the full number is logged**. A reviewer skimming for `[:20]` sees a redaction; there isn't one. This is
the shape DPG-34 should hunt for specifically — a bound that is real code and always false.

### ⚠ Corrected 2026-08-27, before anyone acted on it — the OTP finding was overstated

**This section first claimed the logged OTP completes a status-check impersonation. It does not, and
the claim was made without tracing whether the value is usable.** The correction, and what survives:

**Why it is not directly replayable.** Verification is
`otp_matches(slot_value, tracker.get_slot("otp_number"))` (`form_otp.py:349-352`) — the expected value
lives in **that conversation's own slot**. An attacker running their own session holds their own
`otp_number`, so knowing a victim's OTP string authenticates nothing. Using it would require session
replay or hijack as well, which is a different finding nobody has established. **Severity 🔴 → 🟡.**

**What survives, and is still worth the two-line fix:** a credential is written to the application log
at INFO. That is a finding on its own terms — logs are copied, tailed and pasted far more casually than
databases are, and `len(slot_value)` gives every diagnostic the line currently provides. It is cheap;
it is just not urgent.

⭐ **And checking it turned up two things that were not in the original finding and are more
interesting than it:**

1. **There is no expiry on the OTP at all.** `backend/actions/services/otp/verification.py` is three
   functions — generate six digits, check it is six digits, `input == expected`. **No timestamp, no
   TTL, no expiry check anywhere in the path.** The bound is the lifetime of the conversation slot, not
   a clock. Anyone reasoning about this control as time-limited — which is the natural assumption — is
   reasoning about a window that does not exist.
2. **`otp_number` is not cleared on successful verification.** The success branch
   (`form_otp.py:352-364`) sets `otp_input`, `otp_status`, `otp_verified` and `otp_resend_count`, and
   never `otp_number: None`. The accepted secret stays in session state after it has been used.

⚠ **Open question, flagged rather than claimed because it has not been traced:** when SMS delivery
fails, `form_otp.py:121` does `dispatcher.utter_message(text=message_sms)` — **the OTP is printed into
the chat window** as the designed fallback. On the intake path that may be acceptable. On the
**status-check** path, where the OTP's job is to prove the person controls the phone tied to the
grievance, printing it to whoever typed the number would defeat the control — and with the DOIT gateway
having no fallback transport (the SNS path was deleted 2026-08-24), "SMS is down" is a single condition
that reaches it. **Someone should trace whether the status-check flow hits that branch.** Not asserted
here; the last claim made in this section without tracing it was wrong.

---

## 4. Reconciliation against DPG-04's data-flow diagram

[`privacy-assessment.md`](privacy-assessment.md) §2.2 draws 13 legs (L1–L13). Reconciled against the
code, **the diagram is structurally sound and wrong in four specifics.** Each is now recorded in both
documents, per DPG-30's acceptance.

| # | The diagram says | The code says | Where it lands |
|---|---|---|---|
| **R1** | **L3**: Redis is a mitigated leg — *"payloads are not written to durable storage"* | The mitigation is an **inference that has never been tested**, and two mechanisms make it doubtful | §2. **Blocks nothing in Sprint 3; changes L3's assessment if confirmed** |
| **R2** | **F-6**: one log site (the phone) | **At least twelve**, including **two OTP sites** and one line carrying the whole grievance dict | §3 |
| **R3** | **L9** frames messaging as *"complainant phone number and message body"* | The **admin recap email carries the entire grievance dict** to `ADMIN_EMAILS` over the SMTP relay, on every submission. That is a different leg with a different recipient | §6 |
| **R4** | **L10** covers reports and closure documents generically | The XLSX carries `grievance_summary` (`report_rows.py:459`), which by CLAUDE.md rule 4's own caveat **can contain self-disclosed and third-party PII** — so the quarterly report is a PII egress to external roles, not a metadata export | §6 |

**Nothing in the diagram is invented, and no leg is missing outright.** The pattern in all four is the
same: **the diagram is right about topology and optimistic about content.** A leg that exists is
assessed as carrying less than it carries.

---

## 5. E4 — the model-provider boundary, and the part of it that cannot be redacted

**Nine call sites, two chokepoints, five live.** `call_llm()` in `backend/services/llm_client.py:80`
and `ticketing/clients/llm_client.py:69` (DPG-18) are the only places a request is built, which is what
makes DPG-33 two hooks rather than nine.

- **Live, chatbot:** classification (`LLM_services.py:312`), SEAH detection (`:618`).
- **Live, ticketing:** note translation (`:152`), case findings (`:230`), resolved summary (`:309`).
- **Parked** (`PARKED_TASKS`, `registered_tasks.py:96`): ASR, contact extraction ×2, translation. They
  carry **no production egress** until transcription is funded — inventory them, do not spend
  redaction effort on them, and do not delete them.

⚠ **Audio is not redactable and this is the strongest argument in the document for T2.**
`transcribe_audio_file` sends the raw waveform; a voice note carries the speaker's name in the
speaker's own voice, and there is no step between the microphone and the model where a redactor could
run. **Only moving the inference endpoint solves it.** Redaction applies to the transcript, immediately
after — never before. This is stated here so DPG-33 does not spend time looking for a hook that cannot
exist.

---

## 6. E5/E6/E7 — the email legs, and a correction to Sprint 3's own decision table

`backend/actions/action_outro.py` sends **two** recap emails, and they are not the same leg:

| Leg | Call | Recipient | Carries |
|---|---|---|---|
| **E5 — admin recap** | `:148` (submission), `:243` (status-check follow-up) | `ADMIN_EMAILS` (`backend/config/constants.py:141`, env-configured) | The whole `grievance_data` / `email_data` dict — narrative at `:225`, summary at `:220`, categories, timeline |
| **E7 — complainant recap** | `:153`, gated on a valid `complainant_email` | The complainant | Their own grievance data |

⚠ **This corrects the three-consumer table in
[`04-pii-redaction-spec.md`](../sprints/2026-08-llm/04-pii-redaction-spec.md#dpg-33) (added 2026-08-27),
and the correction changes the reasoning rather than a citation.** That table cites
`action_outro.py:220` as **complainant-facing**, with the rationale *"they wrote the name;
`<PERSON_1>` back at them is absurd."* **`:220` is in the block that feeds
`send_recap_email_to_admin` at `:243`** — it is the *admin* leg. The complainant-facing send is `:153`.

The distinction is load-bearing for the decision the sprint owes: *"they wrote it, showing it back is
absurd"* is a good argument about a complainant reading their own words, and **not an argument at all**
about a recap mailed to a configured admin list. **E5 is an egress that should be assessed on its
merits, not inherited into the complainant's exemption.**

---

## 7. Scope statement for DPG-33 / DPG-34

**DPG-33 (model boundary):** E4's two chokepoints. Audio is out of scope by physics (§5).

**DPG-34 (logs, Celery, backups):** E1, E2, E3 — and in this order:

1. 🔴 **Delete the two OTP log lines** (`form_otp.py:312`, `:343`). Not a redaction-filter task; a
   credential does not belong in a log at any level, and this is a two-line change.
2. 🔴 **Settle Redis persistence** with the three runtime commands (§2), then make the documents match
   the answer — or make the answer match the documents with `--save "" --appendonly no`.
3. 🔴 **The logging filter** at `backend/logger/logger.py` (`TaskLogger`), covering §3's table. Wire it
   once, centrally: twelve call sites is already too many to fix individually and stay fixed.
4. 🟠 **Celery payloads** — pass a `grievance_id` and let the task read from Postgres, rather than
   serialising the narrative into the broker. Cleaner than redacting the payload, and it removes the
   store instead of obscuring it. ⚠ Touches `backend/task_queue/`, a stable shared service.
5. 🟠 **Backups** — `backup_db.sh` already supports GPG encryption and an off-box `BACKUP_REMOTE`; both
   are **operator-set and optional**. Name the destination and its jurisdiction, per DPG-04 F-11.

**Out of scope for both, logged rather than fixed:**

- **E8** — the public closure endpoint is unauthenticated behind a non-expiring UUID4 token. Already
  tracked in the privacy assessment (L10); this inventory adds nothing to it.
- **E12** — the observability rule. Nothing to redact today; the rule needs writing before a tracing
  tool arrives, not after.

---

## 8. Related

- [DPG-30](../sprints/2026-08-llm/04-pii-redaction-spec.md#dpg-30) — the ticket
- [`privacy-assessment.md`](privacy-assessment.md) §2.2 — the diagram this reconciles against; §4's four discrepancies are recorded there too
- [`19_incident_response.md`](../deployment/19_incident_response.md) — carries the Redis containment claim §2 questions
- [`followups/redis-persistence-is-inferred-not-verified.md`](../sprints/2026-08-llm/followups/redis-persistence-is-inferred-not-verified.md)
- [`followups/otp-and-phone-logged-at-info.md`](../sprints/2026-08-llm/followups/otp-and-phone-logged-at-info.md)
