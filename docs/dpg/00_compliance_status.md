# DPG compliance status — Nepal GRM platform

> **What this is.** An indicator-by-indicator self-assessment against the
> [DPG Standard](https://www.digitalpublicgoods.net/standard), for ADB's Digital Public Goods
> consultant. Each indicator states **what we have**, **what is missing**, **what we propose**, and
> **what we need from you**. **As of 2026-09-03** · branch `integration/stage`.
>
> **What this is not.** Not a record of what was built — that is
> [`03_remediation_record.md`](03_remediation_record.md), deliberately outside this assessment. Not
> the evidence: the six documents below hold the measurements, and this file **cites them rather
> than restating them**. Not an argument for its own questions — those are in
> [`02_questions.md`](02_questions.md), generated from this file.
>
> **Twenty minutes before a meeting:** [`01_consultant_briefing.md`](01_consultant_briefing.md).

---

## What changed since 2026-08-24

Three sub-sprints closed. **The largest gap in the previous revision is substantially closed, and two
new ones opened in its place** — one of them created by the same work.

| | |
|---|---|
| ✅ **Grievance text no longer reaches the model provider in clear.** Pseudonymised at both model-call chokepoints, **87.5% measured recall**, opt-**out** so a new call site is covered without its author knowing. The stored summary carries no names. The log boundary and the message broker closed with it | Indicator 7 |
| ✅ **All three email legs that carried the whole grievance record are closed** — a submission receipt, a follow-up request, and a status update to an office list derived from **municipality** rather than the case's cast. ⭐ The third was found only by fixing the second, and **none looked wrong at its own call site** | Indicator 7 |
| ✅ **Fixed — a live safeguarding defect in which the final submit erased the model's SEAH detections**, in exactly the case the model exists for. ⚠ It had been live for months, and **how it was found** is the strongest methodological evidence in this pack | Indicator 9 |
| ⛔ **None of it is deployed.** All of it is on `integration/stage`. **Staging has not been deployed since**, and the DOR production host tracks `main`, which is older still. The next staging deploy is blocked on an unrelated database credential | Everything |
| ⚠ **The classification benchmark is now stale for a second reason** — the harness calls the product's own function, and that function now redacts | Indicator 4 |
| ⚠ **The npm vulnerability count held at 4 and every finding behind it changed.** `next` now carries nine advisories of its own, two of them SSRF, in the framework the officer portal ships | Indicator 8 |

---

## How to read this

Two of the nine indicators have real gaps, **one of which nobody on the engineering team can close**,
and the AI-specific reading of indicator 4 is the substance of the meeting.

⛔ **One caveat qualifies every indicator, and it got heavier this fortnight: almost none of this
evidence comes from a deployed host.** The licence scan, the CVE scan, the platform-independence CI
job and the ops monitor all exist and have been run — **on a development stack, by hand.** `ops` is on
neither server. **And now the privacy controls are in the same position**: the redaction layer that
answers the largest indicator-7 finding is on a branch, not on a server. *A control that has not run
where the data is is a control in the same sense that a plan is a building.* This is stated once here
and not repeated under every indicator.

⭐ **One fact reframes the privacy half: no genuine grievance has ever been processed.** Every record
is seed data or a demo dummy, so every exposure is **prospective** and redaction is a **go-live
precondition rather than a remediation**. ⚠ This expires at go-live, and a demo participant may have
entered their own real contact details.

⚠ **And one word this document will not use.** The redaction layer produces **pseudonymised** text,
not anonymised: the mapping exists, so the output is still personal data. Every claim below is written
to that standard, and *"only pseudonymised text crosses the border, and the re-identification key
never leaves the process"* is the strongest form available.

| Evidence | What it holds |
|---|---|
| [`privacy-assessment.md`](privacy-assessment.md) | 13 data-flow legs verified at file and line, **21 findings**, assessed against the Individual Privacy Act 2018 |
| [`pii-egress-inventory.md`](pii-egress-inventory.md) | **Every path by which grievance text leaves the agency's control** — 12, ranked by likelihood rather than by alarm, with what closed and what did not |
| [`dependency-licenses.md`](dependency-licenses.md) | Generated inventory: **149 packages** across four dependency sets, plus measured CVEs — regenerated 2026-09-03 |
| [`open-model-configuration.md`](open-model-configuration.md) | How this system runs on open models; the measured capability matrix |
| [`model-benchmarks.md`](model-benchmarks.md) | What the models score on a committed 105-item Nepali set |
| [`vllm-deployment.md`](vllm-deployment.md) | Self-hosted inference, designed and costed; why it is parked |

---

## Scorecard

| # | Indicator | Status | What is missing |
|---|---|---|---|
| 1 | Relevance to SDGs | ✅ Compliant | Needs writing up, not building |
| 2 | Open licensing | 🟢 Substantially | The licence choice is provisional; the continuous scan has never run on a deployed host |
| 3 | Ownership | 🔴 **Blocked** | No IP determination, so **no copyright holder and no submission**. Not closable by this team |
| 4 | Platform independence | 🟡 Mechanism done, choice not made | The open accuracy column is unmeasured; the repository default is still proprietary. ⚠ The **closed** column is now stale too |
| 5 | Documentation | ✅ Compliant | — |
| 6 | Mechanism for extracting data | ✅ Compliant | — |
| 7 | Privacy & applicable laws | 🟠 Real gaps — **and a different shape from a fortnight ago** | Egress is pseudonymised, not stopped; **nothing is deployed**; no retention schedule; contact details not separable; no systematic search for a fourth email leg — and **no supervisor to validate any of it, while the exposure is criminal** |
| 8 | Standards & best practices | 🟢 Substantially | No governance model or versioning policy, deliberately. ⚠ Nine advisories against the shipped web framework |
| 9 | Do no harm | 🟠 One gap inside a deliberate design | The recall-first classifier has no explicit return path for a cleared case, its recall is unmeasured, and **nothing measures the pipeline end to end** — every figure we have scores the model alone |

---

## 1. Relevance to SDGs

**What we have.** A grievance redress mechanism for ADB-financed road infrastructure, serving
**SDG 16.6** (effective, accountable institutions), **16.10** (public access to information) and
**9.1** (sustainable infrastructure). Multilingual intake by text and voice lowers the barrier for
complainants who cannot file in writing or in English — the access limb of 16.10 rather than a
feature.

**Gap.** None in the platform; the relevance statement has not been written in the form a submission
expects. **Remedy:** write it with the submission package, once indicator 3 unblocks.

---

## 2. Open licensing

**What we have.**

- `LICENSE` — **Apache-2.0**, repository-wide.
- **Every in-scope source file carries an SPDX header** — **601 of 601**, verified 2026-09-03 via
  `scripts/ops/add_spdx_headers.py --check`. The check is wired into `tests/repo`, which is what makes
  *"every"* an **enforced** claim rather than a dated one — the count moves with the codebase and the
  claim does not have to be re-earned.
- **149 packages across four dependency sets** — 34 declared Python, 95 transitive, 16 npm production,
  4 container images — with **zero non-OSI and zero unknown licences**, and a disposition for each of
  the 10 entries carrying conditions beyond attribution
  ([`dependency-licenses.md`](dependency-licenses.md)). ⭐ **Regenerated 2026-09-03**, which replaced
  the previous revision's estimate with a measurement: it predicted the AWS SMS removal would drop the
  count *"by roughly four"*, and it dropped by exactly four.
- ⭐ **26 packages moved version in a fortnight and no licence moved with them.** Stated because the
  one time a licence *did* move under a stable pin is the finding this whole set exists around.
- ⭐ **The container-image set is the one that mattered:** a floating `redis:7` tag followed upstream
  onto the non-OSI RSALv2/SSPLv1 line with nobody editing the file. Pinned, AGPLv3 elected from Redis
  8's tri-licence, and a **pin-drift check** added — because that is the shape the drift took.

**Gaps.**

- ⚠ **The licence choice is provisional.** Apache-2.0 was applied so the repository would not sit
  unlicensed; it was not chosen against ADB's preferences.
- ⚠ **`NOTICE` names no copyright holder** — deliberate, blocked on indicator 3.
- ⚠ **The nightly licence scan has never run on a deployed host.** `ops` is on neither server. **Not
  a continuous guarantee, and must not be described as one.**

**Remedy.** Deploy `ops` to staging, which turns the scan from an artefact into the continuous control
this indicator asks for.

**Questions.**

- **Q-02-01 — Do you have any objection to Apache-2.0?**
  It is applied repository-wide and every file is stamped, so a change is mechanical but not free. We
  would rather change it now than after a submission.
- **Q-02-02 — Do any of these licences cause a problem for the assessment, or in ADB/DOR procurement?**
  AGPLv3 (Redis, elected from its three), LGPL-with-linking-exception (`psycopg2-binary`), and two
  transitive LGPL libraries. All OSI-approved, all weak copyleft, none modified by us.

---

## 3. Ownership

**What we have.** Nothing, and that is the finding.

**Gaps.** 🔴 **There is no IP-ownership determination**, so `NOTICE` cannot name a copyright holder
and **no submission can be made.** ⚠ **Nobody on this project can resolve it**, and the route is
unclear — the approach so far has been to the consultant, which is not the ADB OGC channel.

**Remedy.** The channel identified and the determination initiated. Until then this indicator stays
red and everything else is preparation.

**Questions.**

- **Q-03-01 🔴 — How is IP ownership determined for software developed under a loan-financed
  engagement, and who signs that determination?**
  We cannot name a copyright holder or submit without it.
- **Q-03-02 🔴 — What is the correct channel to open that request?**
  We do not know whether the consultant is the right door.

---

## 4. Platform independence

The indicator the AI layer sits under, and the substance of the meeting. **The mechanism is built and
measured; the model choice is not made.** Those are different claims, and the difference is the whole
of what follows.

**What we have — the mechanism.**

- **Nine model call sites across two independent subsystems, resolving through one registry**
  ([`backend/config/llm_config.py`](../../backend/config/llm_config.py)). **None names a model, a
  provider or an endpoint** — pinned by an AST-parsing test, not a grep.
- **Five are live; four are the parked voice flow**, declared in `PARKED_TASKS` with a test enforcing
  *"enqueued in production, or declared parked, nothing else"* — so the count cannot quietly drift.
- **Two models, not six.** Eight task keys resolve to two values.
- **`diff .env.openai .env.open` is the entire switching delta** — no code, no image rebuild, no
  migration ([`open-model-configuration.md`](open-model-configuration.md)).
- A CI job, **`dpg-platform-independence`**, runs the live LLM paths against the **open**
  configuration: **4 passed, 1 xfailed, exit 0** against an Apache-2.0 open-weights model.

⭐ **The open configuration covers every model call this system actually makes.** Voice intake works —
a complainant records, an officer handles it — but **automatic transcription is switched off on cost
grounds** and is not expected to be funded, so the one path the open provider cannot serve is the one
path that does not run.

⭐ **The consolidation paid a second time, for a different indicator.** Those two `call_llm()`
functions were built so the model would be a configuration value. When the privacy work needed *a
single place where all outbound text passes*, that place already existed — so pseudonymisation
shipped as **two hooks rather than nine call sites**, with an opt-**out** default that covers a call
site added tomorrow by an author who has never heard of it. ⚠ **The dependency runs one way:**
consolidation made the privacy control cheap; it did not make it correct. Its recall was measured
separately, and it is 87.5%, not 100%.

⚠ **One claim we narrowed, because the loose version is false.** `rasa-sdk` is **not** a type shim —
49 modules import it and the orchestrator executes its form-validation dispatch. The true and
sufficient claim is **no Rasa server, no Rasa NLU, no TensorFlow**, and `rasa-sdk` is Apache-2.0
anyway.

**Gaps.**

- ⚠ **The comparative accuracy evidence is one column short.** The closed baseline is measured in
  full; the open column has **detection only**. Open classification stopped at 2 of 105 items on a
  provider rate limit caused by **our own prompt**, since cut 70%. The blocker is gone and the run has
  not been made — it needs owner-funded inference spend, deferred 2026-08-24
  ([`model-benchmarks.md`](model-benchmarks.md) §4).
- ⚠ **And as of 2026-09-03 the *closed* column is stale as well**, for a reason worth stating because
  it is a consequence of doing the privacy work properly. The benchmark harness calls **the product's
  own functions** rather than a reimplementation — deliberately, and it is the right design — so when
  redaction became the default at the chokepoint, the harness inherited it. **Every classification
  figure now describes an input the system no longer sends.** Detection figures are unaffected.
  ⭐ **This is the cheapest measurement in the pack and the only one blocked on neither money nor
  absent data.** It needs one command, and nobody has run it.
- ⛔ **SEAH detection recall is unmeasured for both candidates and cannot be measured from this
  repository** — the committed set holds no harassment reports, by decision. **The one gap money
  cannot close** ([`model-benchmarks.md`](model-benchmarks.md) §5).
- ⚠ **The repository default is therefore still proprietary**, deliberately: an open base URL with
  unvalidated model ids is a repository that cannot serve one request on a fresh clone — weaker
  evidence, not stronger.
- ⚠ **The CI job has never executed in CI.** It passes by hand. **A gate that has not run is not yet a
  gate.**
- **Self-hosting is designed, costed and parked** for want of an operator, not a budget line. ⭐ A
  **data-sovereignty decision with a price, never a cost decision**
  ([`vllm-deployment.md`](vllm-deployment.md) §3).

**Remedy.** Run the open column and re-meter cost in the same run; measure SEAH recall against the
owner's held-out set; then flip the default and let CI run the job on every commit. The first is a
spending decision, the second a data-availability constraint, the third follows from both.

**Questions.**

- **Q-04-01 🔴 — How does the DPGA assess platform independence for an AI system?**
  Specifically, what weight sits on a configurable and tested open alternative versus on what
  production actually runs. Our answer today is the first of those.
- **Q-04-02 — How does the DPGA treat open-weight models whose licences are not OSI-approved?**
  We filter for Apache-2.0 and MIT, which excludes several of the strongest multilingual models for
  Nepali — including one purpose-built for low-resource languages.
- **Q-04-03 — How does the DPGA treat a partial open alternative?**
  Ours serves every model call the system makes; the one path it cannot serve is switched off on cost
  grounds and is not expected to be funded.
- **Q-04-04 — What does the *data* limb of the AI questionnaire expect from a system that does no
  training and no fine-tuning?**
  Every call is zero-shot prompting, so there is no training-data licence question. We have published a
  105-item labelled evaluation set under CC0-1.0; we do not know whether the prompt templates are also
  expected.
- **Q-04-05 — How much benchmark evidence does a submission need to substantiate an open-alternative
  claim?**
  Each measurement costs owner-funded inference, so we would rather know the bar than guess at it.

---

## 5. Documentation

**What we have.** A full specification tree under [`docs/`](../README.md): service contracts,
ticketing and chatbot specs, deployment runbooks, an engineering craft-rules index binding on every
change, and a per-sprint decision register. APIs are OpenAPI-described, and every architectural
invariant that matters is **pinned by a test**, so documentation and code cannot drift silently apart.

**Gap.** None blocking. It is written for a maintainer rather than an external adopter; no
deployment-from-scratch guide for a third party exists. **Remedy:** write the adopter quickstart if
the DPGA expects one (Q-08-01).

---

## 6. Mechanism for extracting data

**What we have.** Case data exports as XLSX, individual cases as a closure PDF, every API surface is
OpenAPI-described, and storage is PostgreSQL with no proprietary layer — so bulk extraction needs no
cooperation from us and nothing is locked in a vendor format.

**Gap.** None here. ⚠ One related defect is assessed under indicator 7, where it belongs: the public
closure endpoint is unauthenticated and its token does not expire.

---

## 7. Privacy & applicable laws

⭐ **Read this indicator against one structural fact: Nepal has no *operational* data protection
authority, and enforcement is criminal.** There is no supervisor to register with or be audited by and
little jurisprudence to read, so *"this platform complies"* is a claim **no supervisory body can
confirm** — and counsel would be interpreting an untested statute, which **limits legal advice as much
as compliance**. Enforcement is nonetheless real: through the **District Courts**, brought by an
individual or the State, and violation is a **criminal offence** — so no warning, no corrective order,
no chance to remediate first. The authority legislated by the **Data Act 2079** is not yet
operational, so the target is scheduled to move. Sources:
[`privacy-assessment.md`](privacy-assessment.md) §0.6.

**Absent a supervisor we self-bind:** name a controller, adopt a named external standard, publish the
assessment, obtain an independent review, and build an internal route for a data complaint. ⚠ **None
of that equals a regulator**, and **ADB is the nearest candidate standard-setter** (Q-07-07).

**What we have.**

- A written privacy assessment against Nepal's **Individual Privacy Act, 2075 (2018)**, with a
  **13-leg data-flow inventory verified at file and line** and **21 findings** — plus a second
  document, [`pii-egress-inventory.md`](pii-egress-inventory.md), that traces **every** path by which
  grievance text leaves the agency's control and **ranks them by likelihood of real exposure rather
  than by how alarming the destination sounds.**
- ⭐ **Grievance text is pseudonymised before it leaves the process.** Applied at both `call_llm()`
  chokepoints, **opt-out** rather than opt-in, pinned three ways including a `git grep` test that no
  production site opts out. **Measured recall 87.5% (14/16)** — person names 7/7, phones 3/3,
  addresses 4/6 — with the residual **named**: bare settlement names carrying no qualifier. A second
  pass runs on what the model **returns**, so the summary that gets *stored* carries no names either.
  ⚠ Read the two paragraphs after this list before quoting any of it.
- **Staff notifications carry no complainant PII, and nothing at all for a sensitive case.** An
  allow-list projected before formatting, a sensitivity gate that **fails closed on an unknown flag**,
  a template naming a non-safe field **refusing to send** rather than retrying with everything, and
  every call site reading the flag from the stored row rather than a tracker slot that can hold a
  stale answer. ⭐ **One control, not three copies:** it lives in a module that imports neither the
  chatbot nor the API package, because the same defect existed on three paths across both and a
  security control with two implementations has one that is out of date.
- **The logging boundary and the message broker closed with it.** A central filter on the logger
  (not a handler — `_setup_logger` adds two, and a handler filter is missed by any added later)
  redacting the **formatted** message, so `%s` arguments are covered; plus eleven call sites pruned
  to a per-field rule. Celery payloads now carry a `grievance_id` and the task reads the narrative
  from Postgres, so **the broker no longer holds grievance text at all** — the cause removed rather
  than the store obscured.
- An **architecturally enforced PII boundary**: the ticketing subsystem cannot decrypt complainant PII
  and has no accessor for a key — pinned by a test. One audited server-side decryption point.
- Granular consent, recorded and refusable; **anonymous submission end-to-end**; self-hosted identity;
  an in-country SMS gateway with no cross-border fallback; a full audit trail; archiving implemented.
- **Three storage-layer defects fixed 2026-08-19**: encryption at rest now **fails closed**; search
  tokens are HMAC rather than unsalted SHA-256 of enumerable phone numbers; backups **discard** an
  unencryptable dump rather than writing it in the clear. **A fourth, 2026-08-27:** the OTP had no
  expiry of any kind and was not cleared on use; it now has a ten-minute window that **fails closed**
  and is erased on success.

⛔ **Three qualifications, and none of them is optional.**

**1. Pseudonymised is not anonymised, and the difference is legal, not linguistic.** The mapping
exists, so the output remains personal data. The claim that holds is *"only pseudonymised text
crosses the border, and the re-identification key never leaves the process"* — the mapping is never
persisted, never serialised and never returned to a caller, pinned by a test that fails the day some
caller needs it to be.

**2. The border is narrower, not closed.** Every classification still crosses it, permanently,
because self-hosting is parked. **The transmission is the event that needs a lawful basis** — not the
provider's retention, not whether it trains on the data, and **not what the text was scrubbed of
first**. Redaction reduced the payload; it did not change the legal question.

**3. None of it is running anywhere.** All of the above is on `integration/stage`. **Both servers run
the unredacted behaviour**, and the next staging deploy is blocked on an unrelated database
credential. *This is the single most important sentence in the indicator.*

**Gaps.**

- ⚠ **Nobody has grepped for a fourth email leg.** Three carried the whole grievance record — a
  submission receipt, a follow-up request, and a status update to an office list derived from the
  grievance's **municipality** rather than from the case's assigned cast. All three are fixed, but
  the third was found only by fixing the second, so **the search was never systematic.**

  ⭐ **The pattern is worth more than the legs, and it is the reason this stays in the gap list.**
  **None of the three looked wrong at its own call site** — each was written by somebody solving a
  different problem. The first had no admin template at all: `GRIEVANCE_RECAP_ADMIN_BODY` was
  *assigned* from `GRIEVANCE_RECAP_COMPLAINANT_BODY` in one line, so the admin list received the
  complainant's own receipt. Nobody decided that. **Grep the templates, not the senders.**
- ⚠ **Grievance text still leaves Nepal on every model call, permanently** — self-hosted inference is
  parked, so there is no future state in which the transfer stops.
- ⛔ **Audio cannot be redacted at all.** A voice note carries the speaker's name in the speaker's own
  voice and there is no step between the microphone and the model where a redactor could run. **Only
  moving the inference endpoint solves it.** No waveform is sent today solely because transcription
  is switched off on cost grounds — **a funding decision standing in for a privacy control**, and
  unparking voice re-opens an egress no layer built so far can close.
- ⭐ **Erasure of a grievance record is deliberately not offered, and we would defend that rather than
  fix it.** This is a government accountability mechanism: the realistic threat is **an officer or
  contractor making an inconvenient complaint disappear**, not a complainant seeking privacy, so a
  delete path would be a suppression path and its absence protects the complainant. Complaint
  **withdrawal** is built and officer-decided, with an audit trail (Q-07-04, Q-07-06).
- ⚠ **No retention *schedule* has been written** — a separate, real gap. Permanent retention is a
  legitimate answer for an accountability record; *"nobody decided"* is not that answer.
- ⚠ **Contact details are not separable from the record.** The audit function needs the grievance, its
  handling and its outcome — not a phone number a decade later. **Minimising contact after closure
  would cut exposure without touching the record**, and it is the one piece here that is genuine
  engineering work.
- ⚠ **No lawyer has read the assessment**, and per the note above a review is not a determination.
- ⚠ **A complainant has no *internal* route to raise a data complaint.** The District Court is the
  Act's route, but an adversarial process is not a substitute for telling us first — **the internal
  route is ours to build.**
- ⚠ **Three further items need people rather than code:** the breach runbook has **three decisions
  blank**; the **data controller is not formally identified** (overlapping indicator 3); and the
  **provider's own data terms are recorded nowhere** — retention window, service-improvement use,
  prompt caching. Citing an unverified mitigation is worse than citing none.
- ⚠ **Intake does not disclose that grievance text is sent to an external AI provider.** Consent is
  genuinely collected, but not for that. ⚠ The disclosure must say **pseudonymised**, never
  *anonymised*, and must not imply the transfer stopped.
- ⚠ **Nothing re-drives a classification that never ran.** Celery retry covers a task that ran and
  raised, not a message lost from the broker, and there is no periodic sweep. Recorded here rather
  than only as reliability because an uncategorised grievance is also one the keyword safeguarding
  route never scored.

**Remedy.** **Deploy.** That is now the whole of the difference between a documented control and an
operating one — every privacy control above is written, tested and running nowhere. Then: write the retention schedule and
build contact minimisation at closure; purge the demo rows carrying real contact details; obtain and
file the provider terms; and get a legal review — the last of which we cannot resource ourselves.

⚠ **One instruction we would pass to whoever reviews this next, because it is the most transferable
thing the last fortnight produced.** The defects that mattered — a credential in the logs, a
safeguarding flag being silently erased, Redis persisting narratives against four documents that said
it did not — **were not in the data-flow inventory, and no re-reading of it would have found them.**
They came from running the commands, from driving the code against a live database, and from the
owner correcting a wrong model of the intake flow. **An inventory finds the boundaries. It does not
tell you the leaks are somewhere else.**

**Questions.**

- **Q-07-01 — What posture do the DPGA or ADB safeguards policy expect on personal data held in free
  text?**
  We redact at transmission rather than before storage, a deliberate choice with consequences either
  way.
- **Q-07-02 — Would an openly-released Nepali anonymiser model count as a DPG contribution, and is
  there ADB appetite to fund one?**
  The most accurate existing Nepali NER model states no licence at all, so the gap is real and the
  contribution would be reusable well beyond this project.
- **Q-07-03 🔴 — Does ADB or the DPGA expect a signed data-processing agreement with the inference
  provider?**
  Unless a provider is pinned, the router selects a different third-party processor per request, and
  its terms reference no DPA.
- **Q-07-04 — Does the DPGA expect a legally-reviewed privacy assessment, or is a documented
  engineering one sufficient?**
  Ours is written and thorough; no lawyer has read it, and we would need to resource that.
- **Q-07-05 — Does the DPGA have a position on cross-border processing for a national-government DPG?**
  There is no authority in Nepal to seek an adequacy finding from.
- **Q-07-06 — Does the DPGA expect a data subject to be able to erase their record, in a system whose
  integrity depends on them not being able to?**
  We would rather have your view than discover at assessment that a delete button was expected.
- **Q-07-07 🔴 — What does the DPGA accept as evidence of privacy compliance where there is no
  operational data protection authority, and does ADB impose data-protection requirements on an
  executing agency?**
  Without an answer we build to our own reading of an untested statute.
- **Q-07-08 — Does pseudonymisation at the border change the assessment of a cross-border transfer,
  given that we keep the mapping?**
  We can state a measured recall figure and we are careful not to call the result anonymised. What we
  do not know is whether that moves the analysis at all, or whether the transfer is assessed the same
  way regardless of what the text was scrubbed of first.

---

## 8. Standards & best practices

**What we have.** OpenAPI-described APIs; OIDC via self-hosted Keycloak; architectural invariants
pinned by tests that fail the build; `SECURITY.md` with a private reporting channel and a SEAH-aware
scope, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and issue/PR templates — all describing what is already
true rather than aspirations.

**Gaps.**

- ⚠ **No governance model and no release/versioning policy**, deliberately deferred: both would state
  commitments nobody has agreed to, on a project whose IP ownership is formally open (Q-08-01).
- ⚠ **Keycloak recorded no login, login-failure or admin events at all until 2026-08-24** — realm event
  storage defaults to off and nothing enabled it, so the platform's primary authentication evidence did
  not exist. Now enabled, but **forward-only** and **not yet applied to staging or production.**
- ⚠ **Nine advisories now stand against the shipped web framework.** Re-measured 2026-09-03: the npm
  count held at *"4 high"* and **every finding behind it changed.** `next@16.2.6` carries nine of its
  own — including a middleware/proxy bypass in App Router and two server-side request forgeries — and
  it is what the officer portal ships. Two of the other three rows (`postcss`, `nanoid`) are in the
  lockfile graph but **verified absent from the shipped image**, which is the distinction we would
  rather make than inflate a count. **Python is unchanged at 6, and 2 of those 6 are unreachable.**
  ⭐ *A count that holds still is not a tree that holds still* — which is the argument for the
  scheduled scan below, and for deploying the thing that runs it.

**Remedy.** Bump `next` past the advisory range — it is one move and it takes three of the four npm
rows with it. Apply event logging to both deployed environments; deploy `ops` so the scans run
somewhere other than a laptop; write the governance and versioning documents once Q-08-01 and
indicator 3 answer.

**Questions.**

- **Q-08-01 — Which project-hygiene artefacts does the DPGA require?**
  We have `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and issue/PR templates. We have no
  governance model and no versioning policy, and would rather write what is required than guess.

---

## 9. Do no harm

**What we have.** SEAH cases run in an access-isolated stream administrators cannot circumvent; two
independent detection paths; a full audit trail; anonymous submission; and an escalation ladder with
enforced deadlines, so a complaint cannot silently stall.

⭐ **The safeguarding classifier is deliberately tuned recall-first — a design decision, not an
accuracy result.** A **miss** leaves a harassment report in the ordinary queue where nobody knows to
look for it: unrecoverable, and the reason the SEAH route exists. A **false alarm** costs a SEAH
officer a review, and **a SEAH officer reading an ordinary complaint discloses nothing to anyone.** So
the system prefers the cheap, recoverable error. On the benchmark that shows up as **5 of 8** flags on
the hardest class of gendered non-harassment items — **the trade being paid, not a defect**
([`model-benchmarks.md`](model-benchmarks.md) §3.2).

**The return path is what makes the trade sound, and it exists.** Verified in code 2026-08-24:
correcting a ticket's classification (`api/routers/tickets/crud.py:523`) re-resolves the workflow
(`services/ticket_workflow_reroute.py:28`) from the corrected categories with `legacy_is_seah=False`
— **so the detector's flag is not sticky** — clears `is_seah`, and restarts the case at L1 of the
standard workflow. ⚠ **One behaviour there is deliberate and must not be "fixed":** a grievance the
*complainant* routed to SEAH stays there regardless of categories. Only a machine flag is reversible.

> ### ✅ Fixed 2026-08-27 — until then, one of the two detection paths was silently erasing the other
>
> **This is closed, and it belongs at the top of the indicator rather than in the gap list, because it
> is the strongest evidence in this pack about how the rest of it was found.**
>
> The asynchronous model check writes its result to the grievance record seconds after dispatch —
> during the contact and OTP steps. The **final submit** then collected a tracker slot still holding
> the **keyword** detector's earlier answer and wrote `False` over the model's `True`. The ticket's
> SEAH flag is read from that column, so **a harassment report was silently routed to the ordinary
> queue.**
>
> ⭐ **It failed in precisely the case the second detector exists for** — the one where keywords miss
> and the model catches. Two paths described as independent were not: one was overwriting the other,
> and always in the direction of *less* protection.
>
> **Fixed:** the flag only ever escalates, expressed **in SQL rather than read-modify-write**, because
> reading then OR-ing leaves a window and the consequence of losing that race is a missed harassment
> report. Driven end to end against the live database.
>
> ⚠ **Fixed in code, and — like everything else this fortnight — not yet on a server.** The deployed
> hosts still carry the defect. No genuine grievance has been processed anywhere, so nothing has been
> misrouted; but **this is the one item on the undeployed list where the cost of waiting is a missed
> harassment report**, and it should be the reason the next deploy happens rather than a line in it.
>
> ⚠ **Two things follow that are worth more than the fix.** First, **no benchmark would have caught
> it**: every detection figure we publish scores the *model*, and all of them were consistent with a
> pipeline that routed nothing. **Detector accuracy is necessary and it is not sufficient.** Second,
> it was found because **the owner corrected a claim we had made** — that the model-based leg barely
> mattered. It was the most consequential find of the programme and it came from being wrong out loud.

**Gaps.**

- ⚠ **There is no explicit "not SEAH — return to the standard queue" action.** The capability exists
  only as a side effect of editing categories, and the audit trail records a classification edit rather
  than a de-flag with a reason. **For a design that deliberately generates false positives the return
  path is load-bearing and should be first-class.**
- ⚠ **No test pins it.** Nothing asserts that a re-resolution clears `is_seah`, so the single property
  the trade depends on is unprotected against regression — and invisible when it breaks.
- ⚠ **The round-trip is unmeasured.** A recall-first design is only as good as the latency of its
  return.
- ⛔ **Detection recall is unmeasured** — the metric the design exists to optimise is the one we cannot
  measure here.
- ⚠ **There is no end-to-end measurement at all** — grievance in, correctly-routed ticket out. Every
  number we have scores a function. The defect above lived in the gap between the two.
- ⚠ **The detector's own graded confidence is computed on every call and discarded three times.** It
  is never persisted, never reaches the ticket, and one code path reads it and always receives its
  default — so **a queue that by design holds deliberate false positives is presented with no ordering
  signal.** Plumbing, not a prompt change, and queued.

**Remedy.** Add the explicit return action with its own audit event and a test pinning the
flag-clearing; instrument the round-trip; persist the confidence and order the queue by it; build an
end-to-end routing test; and measure recall **before** touching the detection prompt — the benchmark
as it stands would reward the wrong change.

**Questions.**

- **Q-09-01 — Is a recall-first safeguarding classifier with human review the posture the DPGA or ADB
  safeguards policy expects, and what evidence does it expect for it?**
  We can measure and publish the false-alarm rate and the return latency; we do not know whether a
  threshold is expected on either, or whether the expectation runs the other way.

---

## 10. Process questions

- **Q-00-01 — Has ADB nominated software as a DPG before, and what should we take from how it was
  handled?**
- **Q-00-02 — What is the submission route?**
  Whether ADB nominates or we self-submit with endorsement, and whether the implementing agency needs
  to be a party.
- **Q-00-03 — When in the engineering should the assessment start, and how long does it usually take?**
  We started it late enough that some of it became remediation.
- **Q-00-04 — Does the assessment consider who funds and operates the system after the pilot?**
  Our inference budget is time-boxed and personally funded, and the CI job producing the indicator-4
  evidence has no owner beyond that.
- **Q-00-05 — What are we missing?**
  Anything in the current Standard revision, or the AI-systems guidance, that we would not find by
  reading the published documents.
- **Q-00-06 — Does the assessment look at the repository or at a running deployment?**
  Several of our controls — the redaction layer, the licence and CVE scans, authentication event
  logging — are built and tested but run nowhere except a development stack. We would rather know
  whether that distinction is material to an assessor than discover it matters after a submission.
