# DPG compliance status — Nepal GRM platform

> **What this is.** An indicator-by-indicator self-assessment against the
> [DPG Standard](https://www.digitalpublicgoods.net/standard), for ADB's Digital Public Goods
> consultant. Each indicator states **what we have**, **what is missing**, **what we propose**, and
> **what we need from you**. **As of 2026-08-24** · branch `dpg/sprint2-open-models`.
>
> **What this is not.** Not a record of what was built — that is
> [`03_remediation_record.md`](03_remediation_record.md), deliberately outside this assessment. Not
> the evidence: the five documents below hold the measurements, and this file **cites them rather
> than restating them**. Not an argument for its own questions — those are in
> [`02_questions.md`](02_questions.md), generated from this file.
>
> **Twenty minutes before a meeting:** [`01_consultant_briefing.md`](01_consultant_briefing.md).

---

## How to read this

Two of the nine indicators have real gaps, **one of which nobody on the engineering team can close**,
and the AI-specific reading of indicator 4 is the substance of the meeting.

⚠ **One caveat qualifies four indicators at once: almost none of this evidence comes from a deployed
host.** The licence scan, the CVE scan, the platform-independence CI job and the ops monitor all exist
and have been run — **on a development stack, by hand.** `ops` is on neither server.

⭐ **One fact reframes the privacy half: no genuine grievance has ever been processed.** Every record
is seed data or a demo dummy, so every exposure is **prospective** and redaction is a **go-live
precondition rather than a remediation**. ⚠ This expires at go-live, and a demo participant may have
entered their own real contact details.

| Evidence | What it holds |
|---|---|
| [`privacy-assessment.md`](privacy-assessment.md) | 13 data-flow legs verified at file and line, 18 findings, assessed against the Individual Privacy Act 2018 |
| [`dependency-licenses.md`](dependency-licenses.md) | Generated inventory: 153 packages across four dependency sets, plus measured CVEs |
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
| 4 | Platform independence | 🟡 Mechanism done, choice not made | The open accuracy column is unmeasured; the repository default is still proprietary |
| 5 | Documentation | ✅ Compliant | — |
| 6 | Mechanism for extracting data | ✅ Compliant | — |
| 7 | Privacy & applicable laws | 🟠 Real gaps | Unredacted egress, no retention schedule, contact details not separable — and **no supervisor to validate any of it, while the exposure is criminal** |
| 8 | Standards & best practices | 🟢 Substantially | No governance model or versioning policy, deliberately |
| 9 | Do no harm | 🟠 One gap inside a deliberate design | The recall-first classifier has no explicit return path for a cleared case, and its recall is unmeasured |

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
- **Every in-scope source file carries an SPDX header** — 595 of 595, verified 2026-08-24 via
  `scripts/ops/add_spdx_headers.py --check`. The check is wired into `tests/repo`, which is what makes
  *"every"* an **enforced** claim rather than a dated one.
- **153 packages across four dependency sets** — 35 declared Python, 98 transitive, 16 npm production,
  4 container images — with **zero non-OSI and zero unknown licences**, and a disposition for each of
  the 10 entries carrying conditions beyond attribution
  ([`dependency-licenses.md`](dependency-licenses.md)). ⚠ **Counted 2026-08-18**; removing the AWS SMS
  path dropped `boto3` and its transitives, so the figure is ~4 lower and the scan needs re-running.
  **The compliance claim is unaffected** — every departing package was Apache-2.0 or MIT.
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
  **13-leg data-flow inventory verified at file and line** and **18 findings**.
- An **architecturally enforced PII boundary**: the ticketing subsystem cannot decrypt complainant PII
  and has no accessor for a key — pinned by a test. One audited server-side decryption point.
- Granular consent, recorded and refusable; **anonymous submission end-to-end**; self-hosted identity;
  an in-country SMS gateway with no cross-border fallback; a full audit trail; archiving implemented.
- **Three storage-layer defects fixed 2026-08-19**: encryption at rest now **fails closed**; search
  tokens are HMAC rather than unsalted SHA-256 of enumerable phone numbers; backups **discard** an
  unencryptable dump rather than writing it in the clear.

**Gaps.**

- ⚠ **Grievance text leaves Nepal unredacted on every model call, permanently** — self-hosted
  inference is parked, so there is no future state in which the transfer stops. Redaction is **not
  started**.
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
  genuinely collected, but not for that.

**Remedy.** Ship redaction before go-live; write the retention schedule and build contact minimisation
at closure; purge the demo rows carrying real contact details; obtain and file the provider terms; and
get a legal review — the last of which we cannot resource ourselves.

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

**Remedy.** Apply event logging to both deployed environments; write the governance and versioning
documents once Q-08-01 and indicator 3 answer.

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

**Remedy.** Add the explicit return action with its own audit event and a test pinning the
flag-clearing; instrument the round-trip; measure recall **before** touching the detection prompt.

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
