# Nepal GRM platform — DPG briefing

> **What this is.** A **pre-read**, for the twenty minutes before a meeting: what the platform is,
> where it stands against the nine indicators, and what we need a decision or an opinion on.
> **As of 2026-09-03.**
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
| ✅ **Compliant** | Relevance to SDGs · Documentation · Data extraction |
| 🟢 **Substantially** | Open licensing · Standards & best practices |
| 🟡 **Partly** | Platform independence — mechanism built and measured, model choice not made |
| 🟠 **Real gaps** | Privacy & applicable laws · Do no harm — *an unfinished half of a deliberate design, not a defect* |
| 🔴 **Blocked, and not by us** | Ownership |

**Four sentences that carry most of the meaning:**

1. **There is no proprietary component anywhere in the runtime stack** — no closed database, identity
   provider, framework or SDK. A generated audit over 149 packages in four dependency sets returns
   zero unknown and zero non-OSI licences.
2. **The AI layer was our one genuine closed dependency, and the mechanism that removes it is built,
   tested and running** — every model is a configuration value, and one environment change moves both
   LLM subsystems together. **What is not done is the *choice*:** the comparative benchmark is one
   column short, so the repository default is still proprietary.
3. **Grievance text no longer reaches the model provider in clear.** It is pseudonymised at the
   model-call boundary at **87.5% measured recall**, and the log boundary and message broker closed
   with it. ⚠ **Pseudonymised is not anonymised** — we keep the mapping, so it stays personal data —
   and the transfer has been **narrowed, not stopped**. ⚠ **One egress is untouched and we rank it
   *above* the model call**: an admin recap email still sends the whole grievance record on every
   submission. The replacement was decided a week ago and has not been written.
4. **Nothing real has been processed yet.** Every grievance record is seed data or a demo dummy —
   which makes every privacy exposure prospective, and puts the remaining work in the window where it
   is a **go-live precondition rather than a remediation**.

⛔ **And one qualification that reaches most of the above: the recent work is on a branch, not on a
server.** The redaction layer, the licence and CVE scans, the ops health monitor and authentication
event logging are all built and tested, and **none of them has run anywhere except a development
stack.** There is no continuous deployment on this branch — a server changes only when someone runs a
deploy — and the next staging deploy is currently blocked on an unrelated database credential.
**We would rather you heard that from us than inferred it**, and if the assessment distinguishes a
repository from a running system we would like to know early (Q-00-06).

---

## ⛔ What we need from you

**Five questions block work**, stated in full with their evidence in
[`02_questions.md`](02_questions.md) — generated from the assessment, so it cannot drift out of step
with it. Twenty further questions there are useful but not blocking.

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

- *"Grievance text is anonymised"* is **false** — it is **pseudonymised**, we keep the mapping, and
  the output is still personal data. The strongest true claim is *"only pseudonymised text crosses the
  border, and the re-identification key never leaves the process."* Recall is **87.5%**, not 100%, and
  the residual is named rather than rounded away.
- *"The open configuration runs the whole system"* is **false for audio**, true for text — acceptable
  only because the audio path is switched off on cost grounds, so it covers **every model call the
  system actually makes**. ⚠ Audio is also the one thing no redaction layer can touch.
- *"`rasa-sdk` is only a type shim"* is **false** — 49 modules import it and the orchestrator executes
  its form-validation dispatch. The sufficient claim is **no Rasa server, no Rasa NLU, no TensorFlow**;
  `rasa-sdk` is Apache-2.0 anyway.
- **GitHub's alert count is measured against `main`**, which is months and hundreds of commits stale.
  Measured here on 2026-09-03: **6 Python and 4 npm-high**, ranked by **reachability** rather than
  count. ⚠ **The npm count is unchanged and every finding behind it changed** — `next` now carries nine
  advisories of its own, and that is the one row we would act on rather than explain.

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
a harassment report went to the ordinary queue. **No benchmark could have caught it**: every score we
publish measures the *model*, and all of them were consistent with a pipeline that routed nothing.
**It was found because the project owner corrected a claim we had made.** The same pattern holds for
the other three live defects of the fortnight — a credential in the logs, narratives persisting in
Redis against four documents that said otherwise, a decorative test that a mutation exposed. **None
was in the inventory written to find them.**

⚠ **We are telling you this because it cuts against us as well as for us.** It is the argument for
taking the measured claims here seriously; it is equally the reason to treat any claim in this pack
that is *not* marked as measured as provisional.

---

## Where everything lives

| | |
|---|---|
| [`00_compliance_status.md`](00_compliance_status.md) | **The assessment.** Indicator by indicator: what we have, gaps, remedy, questions |
| [`02_questions.md`](02_questions.md) | The 25 questions, generated from the assessment |
| [`privacy-assessment.md`](privacy-assessment.md) | 13 data-flow legs verified at file and line, 21 findings, assessed against the Individual Privacy Act 2018 |
| [`pii-egress-inventory.md`](pii-egress-inventory.md) | Every path by which grievance text leaves our control — 12, ranked by likelihood, with what closed and what did not |
| [`dependency-licenses.md`](dependency-licenses.md) | Generated: 149 packages, four dependency sets, plus measured CVEs |
| [`open-model-configuration.md`](open-model-configuration.md) | How to run this system on open models, and the measured capability matrix |
| [`model-benchmarks.md`](model-benchmarks.md) | What the models score on a committed 105-item Nepali set |
| [`vllm-deployment.md`](vllm-deployment.md) | Self-hosted inference, designed and costed; why it is parked |
| [`03_remediation_record.md`](03_remediation_record.md) | What the sprints fixed. **Not part of the assessment** — sent only if you ask what changed |
