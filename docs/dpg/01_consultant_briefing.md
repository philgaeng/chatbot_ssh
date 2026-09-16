# Nepal GRM platform — DPG briefing

**Status:** evidence pack — cited by the DPG assessment.
**Last updated:** 2026-09-15 — brought into line with the re-verified assessment: three urgent items surfaced by the monitor's own evidence, documentation moved to *substantially* while no public copy exists, the email search closed, the browser-side map finding added, question counts updated.

> **What this is.** A **pre-read**, for the twenty minutes before a meeting: what the platform is,
> where it stands against the nine indicators, and what we need a decision or an opinion on.
> **As of 2026-09-15.**
>
> **What this is not.** Not the assessment — that is
> [`00_compliance_status.md`](00_compliance_status.md), which states every claim below with its
> evidence and is the document to argue with. Not the evidence itself: six companion documents hold
> the measurements. Not a record of what we built ([`03_remediation_record.md`](03_remediation_record.md)).
>
> **Nothing here is new relative to `00`.** If the two disagree, `00` is right.

---

## The platform, in a paragraph

A Grievance Redress Mechanism for ADB-financed road infrastructure in Nepal (Kakarbhitta–Laukahi
Road, Loan 52097-003). A complainant files in Nepali or English, by text or voice, through a chatbot;
the grievance is classified, a ticket opened, and it escalates through a four-level officer workflow
with enforced deadlines up to a Grievance Redress Committee. Reports of sexual exploitation, abuse and
harassment run in a separate, access-isolated stream that ordinary officers — and administrators —
cannot see into. Open source, Apache-2.0, destined for Nepal Department of Roads infrastructure.

---

## Where we stand

| | |
|---|---|
| ✅ **Compliant** | Relevance to SDGs · Data extraction |
| 🟢 **Substantially** | Open licensing · Documentation — *written, not publicly readable until the first release copy* · Standards & best practices — *with two urgent items below* |
| 🟡 **Partly** | Platform independence — mechanism built and measured, model choice not made |
| 🟠 **Real gaps** | Privacy & applicable laws · Do no harm — *an unfinished half of a deliberate design, not a defect* |
| 🔴 **Blocked, and not by us** | Ownership |

> ## ⛔ Three things we would rather you heard from us first
>
> Found on 2026-09-15 by reading our own monitor's records while preparing this revision — **not by any
> alert**, which is itself the finding:
>
> 1. **The production site's TLS certificate expired on 2026-09-13.** Our staging monitor, which watches
>    the production hostname, reported it critical on ten consecutive nights beforehand. Nobody acted,
>    because nothing carried the finding to a person.
> 2. **The officer portal's web framework now carries two critical advisories**, and one is on an
>    endpoint that is enabled, publicly reachable — and **unused by the portal**, so it can be switched off
>    in one line. It has been our top-ranked vulnerability item since 2026-09-03, and it got worse.
> 3. **Our nightly vulnerability scan has saved nothing on any night**, while reporting a status that
>    looked like a result. Every vulnerability figure in this pack was measured by hand.
>
> **None involves real complainant data** — none has ever been processed — and all three are cheap to
> fix. We raise them because they are the clearest evidence we have that *a control that runs* and *a
> control someone reads* are different things.

**Four sentences that carry most of the meaning:**

1. **There is no proprietary component anywhere in the runtime stack** — no closed database, identity
   provider, framework or SDK. A generated audit over 149 packages in four dependency sets — now scanned
   **inside the images that ship** — returns zero unknown and zero non-OSI licences, and a nightly scan on
   the staging host independently agrees.
2. **The AI layer was our one genuine closed dependency, and the mechanism that removes it is built,
   tested and running** — every model is a configuration value, and one environment change moves both
   LLM subsystems together. **What is not done is the *choice*:** the comparative benchmark is one
   column short, so the repository default is still proprietary.
3. **Grievance text no longer reaches the model provider in clear.** It is pseudonymised at the
   model-call boundary at **87.5% measured recall**, and the log boundary and message broker closed
   with it. ⚠ **Pseudonymised is not anonymised** — we keep the mapping, so it stays personal data —
   and the transfer has been **narrowed, not stopped**. ⚠ **And email was the leak we had not been
   looking at:** three separate paths each mailed the whole grievance record, one of them to an
   office list derived from the grievance's *municipality* rather than the case's cast. All three
   are closed, and a systematic search found **no fourth**. ⚠ **What that search could not see is the
   browser:** pinning a location on the intake map sends the area around the pin — often the
   complainant's home — to a foreign tile service before consent. Open, and ours to fix.
4. **Nothing real has been processed yet.** Every grievance record is seed data or a demo dummy —
   which makes every privacy exposure prospective, and puts the remaining work in the window where it
   is a **go-live precondition rather than a remediation**.

⚠ **And two qualifications, which we would rather you heard from us than inferred.**

**First, where the controls run.** Verified inside the running containers on the staging host, and
re-verified on 2026-09-15: **every privacy and security control in this pack is live there** —
redaction, the log filter, the broker fix, the safeguarding correction, the email-boundary controls,
authentication event recording, and since September the edge hardening and single-use officer refresh
tokens. The nightly licence scan has run for eleven nights and agrees with our hand audit. ⛔ **DOR
production runs none of it that we can verify**, and we could not reach it to check.

**Second, where the source is.** Our working repository has been **private since 2026-09-04** — it
carries incident notes and infrastructure detail that do not belong in public. The public repository is
designed as a **release copy** generated at each production release, carrying the source, the
specifications and this pack. **None has been cut yet.** Whether that shape meets the Standard is
Q-02-03.

⭐ **The distinction we would ask you to hold us to runs in a chain: *deployed*, *has run*, *has worked*,
*has been read*.** The three items at the top of this page each failed at a different link. If the
assessment distinguishes a repository from a running system, we would like to know early (Q-00-06).

---

## ⛔ What we need from you

**Five questions block work**, stated in full with their evidence in
[`02_questions.md`](02_questions.md) — generated from the assessment, so it cannot drift out of step
with it. Twenty-one further questions there are useful but not blocking.

| | | Why it blocks |
|---|---|---|
| **Q-03-01** | How is IP ownership determined for software developed under a loan-financed engagement, and who signs it? | Without it `NOTICE` cannot name a copyright holder, and **no submission can be made** |
| **Q-03-02** | What is the correct channel to open that request? | We have written to the consultant, which is not the ADB OGC channel. Nobody here can resolve it |
| **Q-04-01** | How does the DPGA assess platform independence for an **AI system**? | What weight sits on a configurable and tested open alternative, versus on what production actually runs. Our answer today is the first |
| **Q-07-03** | Does ADB or the DPGA expect a signed data-processing agreement with the inference provider? | Unless a provider is pinned, a different third-party processor handles each request, and its terms reference no DPA |
| **Q-07-07** | What does the DPGA accept as evidence of privacy compliance where there is **no operational data protection authority** — and does ADB impose data-protection requirements on an executing agency? | Nepal has the Act but no supervisor. Without an answer we build to our own reading, and **ADB is the nearest candidate standard-setter** |

**Indicator 3 is the one to raise first.** Every other indicator can be worked on. This one cannot be
worked on at all, by anyone here, and it gates the submission rather than merely weakening it.

---

## Five things worth knowing before you read the assessment

**1. We have tried not to overstate, and it cost us some attractive sentences.**

- **We do not use the word "anonymised" about this output, in any sentence.** It is
  **pseudonymised** — we keep the mapping, so it remains personal data. The strongest true claim is *"only pseudonymised text crosses the
  border, and the re-identification key never leaves the process."* Recall is **87.5%**, not 100%, and
  the residual is named rather than rounded away.
- *"The open configuration runs the whole system"* is **false for audio**, true for text — acceptable
  only because the audio path is switched off on cost grounds, so it covers **every model call the
  system actually makes**. ⚠ Audio is also the one thing no redaction layer can touch.
- *"`rasa-sdk` is only a type shim"* is **false** — 49 modules import it and the orchestrator executes
  its form-validation dispatch. The sufficient claim is **no Rasa server, no Rasa NLU, no TensorFlow**;
  `rasa-sdk` is Apache-2.0 anyway.
- **We do not quote a vulnerability count without saying where it was measured.** On 2026-09-15,
  inside the shipped images: **4 Python advisories** (down from 6) and, in the web portal's dependency
  graph, **1 critical, 3 high, 1 moderate** — ranked by **reachability**, not count. Two of the npm
  findings are verified absent from the shipped image; the critical one is not, and its endpoint is live.

**2. ⭐ Nepal has no operational data protection authority**, and that frames the privacy half. The
Individual Privacy Act 2018 establishes none and the authority legislated by the Data Act 2079 is not
operational — so there is nobody to register with or be audited by, little jurisprudence to read, and
*"we comply"* is a claim **no supervisory body can confirm**. That limits legal advice as much as
compliance.

⚠ **It makes the exposure sharper, not softer.** Enforcement runs through the **District Courts**, a
case may be brought by an individual or the State, and violation is a **criminal offence** carrying up
to three years' imprisonment — **with no supervisory step in between**: no warning, no corrective
order, no chance to remediate first.

**3. One measurement is blocked in a way money cannot fix.** SEAH detection recall — whether the
classifier *catches* harassment reports — cannot be measured here, because the committed benchmark
contains no harassment narratives by deliberate decision. It needs a held-out set the owner keeps
outside git.

**4. ⭐ One number will look like a defect unless read correctly.** The safeguarding classifier flags
5 of 8 deliberately-authored gendered complaints that are *not* harassment. **That is the design:** a
missed report is unrecoverable, while a false alarm costs a SEAH officer a review and **carries no risk
to the complainant**, so the system prefers the cheap, recoverable error. **The indicator-9 gap is not
the over-flagging — it is that returning a cleared case is not yet an explicit, audited action.**

**5. ⛔ The finding we would most want you to take from this fortnight is a method one.** We found that
one of the two safeguarding detection paths had been **silently erasing the other** — the model wrote
`True`, a later step wrote `False` over it, and it failed in exactly the case the model exists for, so
a harassment report went to the ordinary queue. ✅ **Fixed 2026-08-27**, verified end to end against a
live database; the flag now only ever escalates. **The method is the point, not the bug.** **No
benchmark could have caught it**: every score we publish measures the *model*, and all of them were
consistent with a pipeline that routed nothing. **It was found because the project owner corrected a
claim we had made.** The same pattern holds for
the other three live defects of the fortnight — a credential in the logs, narratives persisting in
Redis against four documents that said otherwise, a decorative test that a mutation exposed. **None
was in the inventory written to find them.**

**The same pattern repeated the following week, which is why we mention it twice.** Asked to close the
admin-email finding, we checked it before building — and found it was two templates rather than one,
that neither was gated for sensitive cases, and that a third path nobody had inventoried was doing the
same thing. **None of the three looked wrong at its own call site.** The first was a single
assignment: an admin body defined as the complainant's own receipt. ⚠ **And our own inventory had
missed the third** — it was found by fixing the second, not by the document written to find exactly
this.

**And it repeated a third time in the week this revision was written.** Our monitor had been
producing correct findings for twelve days — including production's certificate approaching expiry —
and **the finding that production's certificate had expired was made by a person reading the monitor's
tables for a different purpose**, not by the monitor reaching anyone.

⚠ **We are telling you this because it cuts against us as well as for us.** It is the argument for
taking the measured claims here seriously; it is equally the reason to treat any claim in this pack
that is *not* marked as measured as provisional.

---

## Where everything lives

| | |
|---|---|
| [`00_compliance_status.md`](00_compliance_status.md) | **The assessment.** Indicator by indicator: what we have, gaps, remedy, questions |
| [`02_questions.md`](02_questions.md) | The 26 questions, generated from the assessment |
| [`privacy-assessment.md`](privacy-assessment.md) | 13 data-flow legs verified at file and line, 27 findings, assessed against the Individual Privacy Act 2018 |
| [`pii-egress-inventory.md`](pii-egress-inventory.md) | Every path by which personal data leaves our control — 16, ranked by likelihood, three of them from the browser, with what closed and what did not |
| [`dependency-licenses.md`](dependency-licenses.md) | Generated from the images that ship: 149 packages, four dependency sets, plus measured CVEs |
| [`open-model-configuration.md`](open-model-configuration.md) | How to run this system on open models, and the measured capability matrix |
| [`model-benchmarks.md`](model-benchmarks.md) | What the models score on a committed 105-item Nepali set |
| [`vllm-deployment.md`](vllm-deployment.md) | Self-hosted inference, designed and costed; why it is parked |
| [`03_remediation_record.md`](03_remediation_record.md) | What the sprints fixed. **Not part of the assessment** — sent only if you ask what changed |
