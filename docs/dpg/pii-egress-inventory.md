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

> ## ✅ Updated 2026-09-03 — what Sprint 3 did to this inventory
>
> **This document was the scope statement; §7 now records the outcome.** Six of the twelve paths
> changed. The short version, and the order matters because it is the order of likelihood, not of
> alarm:
>
> | | Path | Then | Now |
> |---|---|---|---|
> | **E1** | Application logs | 🔴 twelve sites, two of them credentials | ✅ **central filter on `TaskLogger` + 11 call sites pruned + the OTP lines gone** |
> | **E2** | Celery payloads → Redis | 🔴 narrative through the broker, persistence unverified | ✅ **cause removed** — payloads carry `grievance_id`; the task reads Postgres |
> | **E4** | Model provider | 🟠 raw narrative, permanently | 🟢 **pseudonymised at both chokepoints**, 87.5% measured recall — ⚠ *narrower, not closed* |
> | **E5** | Admin recap email | 🟠 the whole grievance dict, every submission | ✅ **built 2026-09-03** — allow-listed, suppressed for sensitive cases, failing closed |
> | **E13** | Status-update email → office list | ⚠ *not in the original twelve* | ✅ **found and closed 2026-09-03** — same shared boundary as E5 |
> | **E6** | XLSX quarterly report | 🟡 `grievance_summary`, may carry names | 🟢 **the stored summary now carries no names** — no report-code change was needed |
> | **E9** | Uploads / audio | 🟡 not redactable | 🟡 unchanged, and **still not redactable** (§5) |
>
> ⭐ **E13 was not in the original twelve, and it is the most useful thing this inventory produced —
> by being missing from it.** Fixing E5 found it: status-update emails carried the full record to an
> office list derived from **municipality**, not from the case's cast, so the recipient set grew with
> deployment. **Three separate email paths each carried the whole grievance record**, each written by
> somebody solving a different problem, none of them wrong-looking at its own call site.
>
> All three are now closed, and behind **one** control rather than three copies of one — the
> allow-list and the sensitivity gate live in `backend/services/admin_notifications.py`, which
> imports neither the chatbot nor the API package. ⚠ **Nobody has grepped for a fourth.** The way to
> do it is to grep the **templates**, not the senders: E5 was a single assignment, and no sender
> looked wrong.
>
> ⭐ **The finding that should outlive the sprint.** Of the defects Sprint 3 found in **live** code —
> the OTP at INFO, the erased SEAH detection, Redis persisting narratives, the classification payload —
> **none was in this inventory.** It was necessary and it was not sufficient: it found the
> *boundaries*, and the leaks were not at the boundaries. They came from driving the code, from the
> owner correcting a wrong model of the intake flow, and from mutations catching decorative tests.

---

## 0. Method, and the one thing that could not be verified

Each path was traced from the code that produces the text to the code that transmits or stores it.
Every citation below was opened and read; none is inherited from another document.

✅ **Verified in-container 2026-08-27.** DPG-30 requires *"Redis persistence configuration and
backup destination **verified in-container**, not assumed"*. This document was first written with
Docker unavailable and said so; Docker came back the same day and **§2 is now measurement, not
inference** — which changed its conclusion in both directions.

⚠ **Read §2 before quoting L3 of the privacy assessment**: the mitigation it carried was false, and
three other documents carried it too.

**What is claimed here and what is not:** every row's *code* facts are verified. Every row's *runtime*
facts — what a container actually does with them — are marked `⚠ unverified` and say so.

---

## 1. The inventory, ranked by likelihood of real exposure

Ranked as DPG-30 requires: **by how likely the text is to end up somewhere nobody intended**, not by
how alarming the destination sounds. The model call is the leak everyone designs against; the logs are
the leak that actually happens.

⚠ **The `What it carries` and `Rank` columns are as of 2026-08-27, when this was a scope statement.**
The `2026-09-03` column is what is true now; where the two disagree, the right-hand column wins.

| # | Egress | What it carries | Verified at | Rank | 2026-09-03 |
|---|---|---|---|---|---|
| **E1** | **Application logs** | OTP codes, phone numbers, the full grievance narrative, the whole grievance dict | §3 | 🔴 **1 — happens continuously, today** | ✅ **closed at the boundary** — central filter + 11 sites pruned + OTP lines deleted |
| **E2** | **Celery payloads → Redis** | `grievance_description` verbatim | §2 | 🔴 **2 — every intake; persistence unverified** | ✅ **cause removed** — id-only payloads, both tasks |
| **E3** | **Database backups** | Everything, incl. narratives, notes, voice recordings, photographs | `scripts/ops/backup_db.sh` | 🟠 **3 — off-box destination is operator-set** | 🟠 **unchanged** — encryption fails closed, destination still unnamed (§5.4) |
| **E4** | **Model provider** (crosses the border) | Raw narrative, officer notes, whole case timelines | §5 | 🟠 **4 — deliberate, and the only one already designed for** | 🟢 **pseudonymised, both surfaces** — 87.5% recall, residual named (§5) |
| **E5** | **Admin recap emails → SMTP relay** | The **entire** grievance dict, including narrative and complainant contact | §6 | 🟠 **5 — every submission, to a configured list** | ✅ **closed at the boundary** (§6) |
| **E13** | **Status-update emails → office list** | The **entire** grievance dict | §6 | ⚠ **not in the original twelve — found 2026-09-03** | 🔴 **open** — and its recipient list grows with deployment (§6) |
| **E6** | **XLSX quarterly reports → email** | `grievance_summary`, truncated to 500 chars | `ticketing/services/report_rows.py:459` | 🟡 **6 — quarterly, to named roles** | 🟢 **the summary now carries no names** — upstream, no report change |
| **E7** | **Complainant recap email → SMTP relay** | Their own grievance data | `backend/actions/action_outro.py:153` | 🟡 **7 — consented-ish; see §6** | ⚪ **deliberately unchanged** — their own words back to them |
| **E8** | **Public closure PDF** | Resolution text | `ticketing/api/routers/public_closure.py:38`, `:58` | 🟡 **8 — unauthenticated, non-expiring token** | 🟡 **unchanged** — out of scope, tracked as F-10 |
| **E9** | **Uploads volume** | Voice recordings, photographs | `docker-compose.yml:50`, `:110`, `:147` | 🟡 **9 — not redactable; see §5** | 🟡 **unchanged, and unclosable** — see §5 |
| **E10** | **SMS → DOIT gateway** | Complainant phone + short message body | `backend/api/routers/messaging.py:95` | 🟢 **10 — in-country by design, no fallback** | 🟢 unchanged |
| **E11** | **`POST /message` → orchestrator** | Officer replies | `ticketing/clients/orchestrator.py` | 🟢 **11 — internal** | 🟢 unchanged |
| **E12** | **Observability** | — | — | ⚪ **none installed — verified** | ⚪ still none; **the rule is now written** (`13_security.md` §8.1) |

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

### ✅ MEASURED 2026-08-27 — and it was half right, which is why it had to be run

| Check | Result |
|---|---|
| `docker inspect … .Mounts` | **`[]`** — no volume, not even an anonymous one |
| `docker image inspect redis:8.10 .Config.Volumes` | **`null`** — ⚠ **the image declares no `VOLUME`**, so hypothesis 1 above was **wrong** |
| `CONFIG GET save` | 🔴 **`3600 1 300 100 60 10000`** — the compiled-in defaults. **RDB is ON**, so hypothesis 2 was **right** |
| `CONFIG GET appendonly` | `no` |
| `CONFIG GET dir` · `ls /data` | `/data` · 🔴 **`dump.rdb`, 47,407 bytes** |
| Plant a key → `docker restart` → read it back | 🔴 **It survived.** Redis logged *"DB loaded from disk: keys loaded: 174"* |

**So the mitigation is false, and the mechanism is not the one predicted.** There is no volume; there
is a **`dump.rdb` in the container's writable layer**. Grievance narratives in Celery payloads are
written to disk, unencrypted.

**What that means, precisely — the boundaries matter for the runbook:**

| Action | Does the data survive? |
|---|---|
| `docker restart`, `stop`+`start`, host reboot | 🔴 **Yes** — reloaded from `dump.rdb` |
| `docker compose down`/`up`, `docker rm` | ✅ No — the writable layer goes with the container |
| `docker commit` / `export` / `cp`, host backup of `/var/lib/docker` | 🔴 **Captured** |

⚠ **Nor did the 2026-08-18 "✅ VERIFIED LIVE" note settle it**, though it reads as though it might:
that check verified the *licence and usage* audit — version, auth, `PING`/`SET`/`GET`/`LLEN`, a
pub/sub round-trip — and its persistence sentence, *"No data to migrate, as predicted — the service
declares no volume"*, **restated the inference rather than testing it.** It was accurate about
everything it checked, which is exactly how an unchecked assumption travels next to checked ones.

**Three consequences. All three documents are corrected; the third is now a decision, not a finding:**

- ✅ **The privacy assessment carried a mitigation that does not exist**, in the leg describing the
  broker that holds unredacted SEAH disclosures. **L3 corrected.**
- ✅ **The incident-response runbook stated a containment property that is false** — *"restarting Redis
  drops queued tasks"* is advice for the worst possible moment, and a restart **reloads** the exposure.
  **Corrected, and the lever replaced**: `compose down`/`rm` discards the writable layer; a restart does
  not. The two actions have different consequences and the runbook no longer treats them as one.
  `14_key_and_secret_lifecycle.md`'s rotation advice inherited the same error and is corrected too.
- ✅ **RESOLVED 2026-08-27 by removing the cause, not by taking the trade.** The question was whether
  to add `--save "" --appendonly no`, accepting task loss on restart to stop persisting PII. **The
  better answer was to stop putting the PII there.** DPG-34 step 3 shipped: the classification payload
  now carries `grievance_id`, and the task reads the narrative from Postgres. Redis no longer holds
  grievance text on this path, so the persistence setting stops mattering for it — **and the
  reliability is kept.**

  ⚠ **The reliability question was real, and checking it is what redirected the fix.** *"Won't Celery
  just retry?"* — **no.** Retry fires when a task **runs and raises**; it re-enqueues a *new* message.
  A message lost from the broker never ran, so there is no retry state, and **nothing sweeps for the
  gap**: the chatbot Celery app has **no beat schedule at all**, and `grievance_sync` (ticketing, every
  2 min) creates tickets and never touches classification. A lost classification would leave the
  grievance at `grievance_classification_status='pending'` **permanently** — a detectable state that
  nothing detects.

  ✅ **The SEAH half shipped too, 2026-08-27, with a different failure mode because the risk differs.**
  Its pre-dispatch write (`persist_grievance_description_for_detection`) is **best-effort** — early
  return without ids, swallowed exception — where classification's is hard, so a missing row is
  **reachable**. The task therefore **retries**, then **fails terminally at ERROR** naming the
  grievance and stating that the deterministic keyword detector still applied. **Silence was the one
  unacceptable outcome**: a SEAH detection that never ran writes no flag and shows no gap anywhere.
  ⭐ Two further leaks went with it — 120 chars of narrative at INFO, and `message_snippet`, **the
  excerpt the model selected because it is the disclosure**, which is now never logged at any length.

  ⏭ And independent of all of it: **no sweeper exists for grievances stuck at `pending`.** That gap
  is real today; it was merely masked by the persistence nobody knew about.

⚠ **Do not "fix" this by adding a named volume.** That makes the exposure durable *and* documented,
which is worse than either alone — a broker holding unredacted SEAH text does not need better
persistence, it needs less.

---

## 3. 🔴 E1 — the log surface is larger than any document says, and two entries are credentials

> ✅ **Closed 2026-09-03.** The table below is the *finding*; the fix is a **central filter on
> `TaskLogger`** plus 11 call sites pruned to the owner's per-field rule — free text → first 8
> characters, phone → last 4, OTP → never logged, whole dict → ids and lengths. Read this section for
> what was there; read §7 item 3 for what was done about it.
>
> ⚠ **A backstop is not a licence.** Call sites are still expected to prune; the filter exists because
> twelve sites were already too many to fix individually and stay fixed. ⚠ **The call-site pin covers
> four files on purpose** — the repo-wide sweep is still owed.
>
> ⭐ **The first test file written for this was decorative, and a mutation proved it.** Reverting the
> masking at both phone call sites left all ten assertions green, because they tested the *helper* and
> not the *call site*. The AST pin added in its place immediately found three more sites the hand
> inventory had missed.

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

- **Live, chatbot:** classification (`LLM_services.py:355`), SEAH detection (`:618`).
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

### ✅ Built 2026-09-03 — and what it does and does not buy

`redact: bool = True`, keyword-only, on **both** `call_llm()` chokepoints — so a call site added
tomorrow is pseudonymised without its author knowing this exists, and switching it off has to be
typed into a diff. Pinned three ways: the default value, the keyword-only kind, and a `git grep` test
that fails if any production site passes `redact=False`. There are none.

A **second pass runs on what comes back** (§31.4), on both producers of a stored summary — including
the translation call that reads as a translation step and in fact *generates* one. A firing logs at
**WARNING**, because it means the input pass missed a name that has already reached a third party.

| What can be said | What must not be said |
|---|---|
| *"Only pseudonymised text crosses the border"* | ⛔ **The word "anonymised", in any sentence about this output.** The mapping exists, so it remains personal data |
| *"The re-identification key never leaves the process"* — the mapping is never persisted, never serialised, never returned to a caller; pinned by a test that fails the day a caller needs it | ~~*"Names cannot reach the provider"*~~ — measured recall is **87.5%**, not 100% |
| *"The residual is named, not rounded away"* — bare settlement names with no qualifier (`Duhabi`, `Itahari`) | ~~*"The transfer has stopped"*~~ — it has **narrowed**. Every classification still crosses the border |
| *"A bare district survives on purpose"* (`Jhapa`) — the classifier derives district from the narrative, and a district identifies nobody | ~~*"Audio is covered"*~~ — it is not, and no layer in this sprint can cover it |

⚠ **Unparking voice re-opens an egress this sprint cannot close.** No waveform is sent today only
because transcription is switched off on cost grounds. That is a funding decision standing in for a
privacy control, and it should be recorded as one.

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

### ✅ E5 — closed 2026-09-03, and closing it found E13

> **Built at the boundary, not per template.** `send_recap_email_to_admin` is the one function
> every admin send passes through, so the control sits there — the same choice DPG-33 and DPG-34
> made, for the same reason: *a per-template fix is correct until someone adds a template.*
>
> **Four controls, because each has a failure mode the others cover.** An **allow-list**
> (`ADMIN_SAFE_FIELDS`) projected *before* formatting, so no other key can reach the body; a
> **sensitivity gate that fails closed** on an unknown flag and suppresses entirely rather than
> trimming, because categories and a summary would themselves disclose that a SEAH case exists; a
> **refusal to send** when a template names a non-safe field, rather than a retry with the full
> dict; and both call sites reading the flag from the **stored row**, since the tracker slot can
> hold the stale keyword answer (D-64).
>
> ⚠ **Residual, stated rather than designed away:** the detector can raise the flag *after* the
> send. The window is small — it writes during the contact/OTP steps and this runs after them —
> and the allow-list is what bounds the damage when it happens. That is why both controls exist.
>
> 🔴 **And there is a third leg, which this does not cover.** See E13 below.

### What was actually wrong — kept, because the shape of it is the lesson

The owner's decision: **send the pseudonymised summary and a link into the platform, never the
record.** The recipient then reads the case behind Keycloak, with an audit trail, instead of holding a
copy in a mailbox with neither.

**It has not been implemented.** Verified end to end on 2026-09-03, template and recipient included:

| Step | Where | State |
|---|---|---|
| The send fires on every submission | `action_outro.py:151` → `send_recap_email_to_admin(grievance_data, …)` | ✅ unchanged |
| The payload is the whole dict | `recap_email.py:52-57` — `grievance_description`, `complainant_full_name`, `complainant_phone`, `complainant_address`, `complainant_email` | ✅ unchanged |
| The body renders all of them | `constants.py:172-199` — *Grievance Details*, *Address*, *Phone*, *Email* are literal fields in the template | ✅ unchanged |
| A recipient is configured | `ADMIN_EMAILS` is empty, so it falls back to `ADMIN_EMAIL` — **one address, in committed config** | ✅ it sends |

⭐ **There is no admin template, and that is the whole explanation.** `constants.py:330`:

```python
EMAIL_TEMPLATES['GRIEVANCE_RECAP_ADMIN_BODY'] = EMAIL_TEMPLATES['GRIEVANCE_RECAP_COMPLAINANT_BODY']
```

**The admin is sent the complainant's own receipt.** Nobody chose to mail the full record to an
administrator; a template written for the one reader who already knows the whole story was reused,
and the audience changed without the content changing. ⚠ **This is the reasoning error described in
prose above, present in the code as an assignment** — *"they wrote it, showing it back is absurd"*
justifies the complainant's copy and justifies nothing about a mailing list, and one line of aliasing
carried the exemption across.

⚠ **The redaction work reached one field of this email and not the other.** `grievance_summary`
arrives from the model path and is now pseudonymised; `grievance_description` is the raw slot. The
email therefore renders **`<PERSON_1>` under *Grievance Summary* and the person's actual name two
lines below under *Grievance Details*.** Neither half is individually wrong, which is exactly why a
boundary control belongs at the boundary and not at the producer.

⚠ **This is the state a reader is most likely to get wrong, so it is stated twice.** Sprint 3 closed
the model boundary, the log boundary and the broker. It did **not** close the leg this document ranks
*above* the model call. A decision recorded in `TODO.md` and a control in the code are different
things, and only one of them stops an email.

⚠ **The link, as built.** `dispatch_grievance_from_tracker` returns `None` — the `ticket_id` is
logged and never plumbed back — and the portal has no deep link keyed on a grievance id. So the mail
carries the **grievance id** and a link to the queue, from `GRM_PORTAL_BASE_URL`. **Empty by
default**, and when empty the mail names the id and says to open the portal. ⭐ **It never falls back
to including the narrative because the link is missing**, which is the failure mode worth naming: a
notification that degrades into a record is how this whole finding started.

---

## 6b. ✅ E13 — a third leg, found while fixing E5, closed with it

Not in the original twelve. `backend/api/routers/grievance.py:323` mails
`GRIEVANCE_STATUS_UPDATE_BODY` on every status change, carrying **the full narrative, complainant
name, phone, municipality, village and address**.

⛔ **The recipient list is the part that makes this worse than E5.**
`get_office_emails_for_grievance` (`grievance_manager.py:1015`) resolves it from the grievance's
**municipality** — the PD office plus whichever office covers that location — **not from the case's
assigned cast.** So a status update on a SEAH case mails a survivor's record to a location-derived
office list, and unlike E5's single configured address **that list grows with deployment.**

⭐ **The pattern is worth more than the leg.** Three separate email paths each carried the whole
grievance record, and each was written by somebody solving a different problem — a receipt, a
follow-up, a status notification. None of them looked wrong at its own call site. **Grep for the
templates, not for the senders**, and assume a fourth until someone has looked.

✅ **Fixed 2026-09-03, in its own commit.** ⭐ **The fix was not a third copy of E5's logic — it was
making E5's logic shared.** The allow-list and the sensitivity gate moved to
`backend/services/admin_notifications.py`, which imports neither `backend/actions/` nor
`backend/api/`, and all three legs delegate to it. A security control with two implementations has
one that is out of date the first time either changes.

⭐ **And a test found a real bug while it was being written.** The shared builder resolves a subject
as `f"{body_name}_SUBJECT"`; this template's subject had been authored as
`GRIEVANCE_STATUS_UPDATE_SUBJECT`, without the `_BODY`, because the old call site formatted both by
hand. The builder returned `None` and the email would have silently stopped sending. **A
per-template test would have passed** — it was the parametrised one, added to cover the third leg,
that caught it.

---

## 7. Scope statement for DPG-33 / DPG-34 — and what was built against it

**Written 2026-08-27 as a scope statement; closed out 2026-09-03.** Each item keeps its original
wording so the plan and the outcome can be read against each other.

**DPG-33 (model boundary):** E4's two chokepoints. Audio is out of scope by physics (§5).
✅ **Built** — both `call_llm()` hooks, opt-out, plus §31.4's output pass. Audio remains out of scope
and the reason is still physics, not effort.

**DPG-34 (logs, Celery, backups):** E1, E2, E3 — and in this order:

1. 🔴 **Delete the two OTP log lines** (`form_otp.py:312`, `:343`). Not a redaction-filter task; a
   credential does not belong in a log at any level, and this is a two-line change.
   ✅ **Done** — and the follow-up found more than the two lines: the OTP had **no expiry at all** and
   was **not cleared on success**. Both fixed (a 10-minute window that fails closed, checked *before*
   the match; the code erased once the number is verified). ⚠ **The original finding was also wrong
   and was retracted the same day** — it claimed the logged OTP completed a status-check
   impersonation. It does not: verification is against that conversation's own slot, so a leaked code
   authenticates nothing. *A credential in a log is a finding on its own terms; the attack around it
   was written from the shape of the finding rather than from the check.*
2. 🔴 **Settle Redis persistence** with the three runtime commands (§2), then make the documents match
   the answer — or make the answer match the documents with `--save "" --appendonly no`.
   ✅ **Measured, and then resolved by removing the cause rather than taking either trade** — see §2.
3. 🔴 **The logging filter** at `backend/logger/logger.py` (`TaskLogger`), covering §3's table. Wire it
   once, centrally: twelve call sites is already too many to fix individually and stay fixed.
   ✅ **Done** — on the **logger**, not a handler (`_setup_logger` adds two, and a handler-level filter
   is missed by any added later), and it redacts the **formatted** message so `%s` arguments are
   covered. That last detail is the whole point: a filter rewriting only `record.msg` passes the
   obvious test and leaks on the common case. Failure path decided deliberately — **never raise**
   (a raising filter drops the line someone is reading during an incident) and **never emit
   unredacted** (a record whose redaction failed has unknown contents).
4. 🟠 **Celery payloads** — pass a `grievance_id` and let the task read from Postgres, rather than
   serialising the narrative into the broker. Cleaner than redacting the payload, and it removes the
   store instead of obscuring it. ⚠ Touches `backend/task_queue/`, a stable shared service.
   ✅ **Done, both tasks** — and handled *differently* for each, because the risk differs.
   Classification's pre-dispatch write is hard; SEAH detection's is best-effort, so a missing row is
   reachable and that task **retries, then fails terminally at ERROR** naming the grievance. Silence
   was the one outcome not acceptable on a safeguarding path.
5. 🟠 **Backups** — `backup_db.sh` already supports GPG encryption and an off-box `BACKUP_REMOTE`; both
   are **operator-set and optional**. Name the destination and its jurisdiction, per DPG-04 F-11.
   🟠 **Not done, and not doable here** — it is a deployment decision with a named owner, addressed to
   DOR in `privacy-assessment.md` §5.4.

**Out of scope for both, logged rather than fixed:**

- **E8** — the public closure endpoint is unauthenticated behind a non-expiring UUID4 token. Already
  tracked in the privacy assessment (L10); this inventory adds nothing to it. **Still open.**
- **E12** — the observability rule. Nothing to redact today; the rule needs writing before a tracing
  tool arrives, not after. ✅ **Written** — `13_security.md` §8.1, before any such tool exists, which
  is the only time writing it is cheap.

### ⏭ What this inventory now owes

| | Item | Who |
|---|---|---|
| 🟠 | **Grep the templates for a fourth email leg.** Three carried the whole record and one was found only by fixing another; no systematic search has been done | engineering |
| ⚪ | ~~E5 — build the decided admin-email change~~ ✅ **done 2026-09-03** | — |
| ⚪ | ~~E13 — the status-update email to the office list~~ ✅ **done 2026-09-03**, behind the same shared boundary | — |
| 🟠 | **Name the backup destination and its jurisdiction**, and assign key custody | DOR |
| 🟠 | **Nothing re-drives a classification that never ran.** Independent of the Redis fix — that removed one way to lose the message, not the absence of recovery | engineering |
| 🟡 | **The log-pruning call-site pin is scoped to four files on purpose.** The repo-wide sweep is not done | engineering |
| ⚪ | **Re-run this inventory when voice is unparked.** Every audio row here is true only while transcription is switched off | whoever unparks it |

---

## 8. Related

- [DPG-30](../sprints/2026-08-llm/04-pii-redaction-spec.md#dpg-30) — the ticket
- [`privacy-assessment.md`](privacy-assessment.md) §2.2 — the diagram this reconciles against; §4's four discrepancies are recorded there too
- [`19_incident_response.md`](../deployment/19_incident_response.md) — carries the Redis containment claim §2 questions
- [`followups/redis-persistence-is-inferred-not-verified.md`](../sprints/2026-08-llm/followups/redis-persistence-is-inferred-not-verified.md)
- [`followups/otp-and-phone-logged-at-info.md`](../sprints/2026-08-llm/followups/otp-and-phone-logged-at-info.md)
- [`04-pii-redaction-spec.md`](../sprints/2026-08-llm/04-pii-redaction-spec.md) — DPG-31/33/34, the work this inventory scoped
- [`PROGRESS.md`](../sprints/2026-08-llm/PROGRESS.md) — deviations **D-62** (the OTP correction), **D-63** (Redis), **D-64** (the erased SEAH detection)
- [`13_security.md`](../deployment/13_security.md) §8.1 — the observability rule, written before a tracing tool exists
