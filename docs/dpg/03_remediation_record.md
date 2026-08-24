# Remediation record — what the DPG sprints changed

> **What this is.** A record of the work done between 2026-08-17 and 2026-08-24 to prepare this
> platform for a DPG assessment, and of what that work found. **As of 2026-08-24.**
>
> ⛔ **This is not part of the assessment, and it should not be read as one.** The assessment is
> [`00_compliance_status.md`](00_compliance_status.md), which states where the platform stands
> **today**; this file states how it got there. A document that lists accomplishments cannot also
> assess gaps — the two were mixed once and the result had to be archived.
>
> **When to send it:** in response to a question about what changed, or about whether the process
> that produced the assessment is one worth trusting. Not otherwise, and never instead of `00`.
>
> **Source:** [`docs/sprints/2026-08-llm/PROGRESS.md`](../sprints/2026-08-llm/PROGRESS.md), which is
> the live tracker and is more detailed than this summary.

---

## 1. The shape of the work

Four sub-sprints, 31 tickets, with a test ledger, a decision register and a deviation log.

| Sprint | Scope | Serves | Status |
|---|---|---|---|
| **0** — licensing & governance | `LICENSE`, `NOTICE`, SPDX headers, a generated dependency scan across four sets with a pin-drift check, project hygiene, the root README, the privacy assessment, the IP determination | Indicators 2, 3, 5, 7, 8 | ✅ Landed, except the IP determination — which is external and cannot be landed here |
| **1** — LLM-agnostic | A characterization-test net **first**; one config file both LLM surfaces read; both surfaces behind configurable clients; schema-constrained output; environment plumbing; a degraded-mode audit | **Indicator 4** | ✅ Landed |
| **2** — open models | A labelled Nepali benchmark set, a provider probe and capability matrix, the closed baseline, a CI platform-independence job, self-hosted deployment documented and costed | **Indicator 4** evidence | 🟡 Landed; the open accuracy column and the ASR evaluation are incomplete |
| **3** — PII redaction | Redaction at the model-call, logging, task-queue and backup boundaries, with measured recall on Nepali | Indicators 7, 9 | ⬜ Not started |

Alongside them, three unplanned repairs in the week of 2026-08-19 to 08-24: the storage-layer privacy
defects, the ops monitor, and the secret inventory.

---

## 2. ⭐ What the work found, which is the part worth reading

**Most closed tickets surfaced something the specification did not know**, and almost all of it was in
code that was already live. This is the argument for the method rather than for the result: a
compliance exercise that finds nothing has usually been conducted by reading.

| What was found | How it presented | Where it came from |
|---|---|---|
| **Voice transcription had never worked at all** | The SDK takes `language`; the code passed `language_code`. Every transcription raised `TypeError` | A ticket to audit degraded modes |
| **A failed classification was stored as if it had succeeded** | Marked `LLM_generated` with no model output behind it | Driving nine call sites against a dead port, rather than reading them |
| **A stored phone number was overwritten with an empty string** | Reproduced — on a path that turned out to have **no production caller**, which also meant an earlier severity claim of ours was too high | The same audit |
| **Two latent `UnboundLocalError`s on the AI paths** | Crash on an error branch nobody had exercised | Writing the characterization net **before** touching anything |
| **Four taxonomy categories had silently lost their high-priority flag** — including the dust category and the SEAH category | A CSV column drift; priority routing quietly stopped applying to them | Building the benchmark set |
| **The classifier invents categories, and the system stores them** | 17% of grievances at the time; an invented category matches no filter and is not found by the priority lookup | The closed baseline run |
| **The SEAH detector flags gendered complaints that are not harassment** | 5 of 8 deliberately-authored confusables, routed into a channel most officers cannot see | The same run |
| **Both an open and a closed model invent the *same* category** | Two vendors, two architectures, one fabricated label — which made it a **taxonomy** finding rather than a model one | Comparing the two columns |
| **A candidate open model refuses a grievance about children falling ill** | *"Your request was blocked"* — a content filter, on the benchmark's flagship item | The capability probe |
| **The classification prompt sent the category catalogue three times** | ~20,700 characters before the complaint; every **English** grievance also carried every Nepali translation, because of an inverted language filter | Investigating a provider rate limit |
| **A floating `redis:7` tag had followed upstream onto a non-OSI licence** | Nobody edited the file; the licence changed underneath it | Auditing container images — a fourth dependency set nobody was scanning |
| **Three storage-layer privacy defects** | Encryption at rest failed **open**; search tokens were unsalted SHA-256 of enumerable phone numbers; backups wrote plaintext narratives and voice recordings | Writing the privacy assessment |
| **Keycloak had recorded no login or admin events at all** | Realm event storage defaults to off. ⚠ The daily ops report queried the empty table and reported `0` rather than "not recorded", which is why it survived every review | Checking a claim in a runbook against the database |
| **The ops monitor had been blind for days while reporting `healthy`** | It authenticated as one role using another's password; a rotation broke it; 253 auth failures; one failed query aborted the whole transaction | Verifying a runbook written the day before |
| **Six secrets existed only on the staging host** | Including a database credential and an SMS gateway token that no inventory tracked | Measuring the host before a secrets migration |

**Two of these deserve to be named together**, because they are the same trap in two unrelated
subsystems in one week: **`X or fallback` on a security-relevant value hides the absence of `X`.** It
is why the search-token pepper silently derives from the encryption key, and why the ops monitor
authenticated with the wrong credential and said nothing.

---

## 3. What was corrected in our own work

Of 21 logged deviations in Sprint 0 alone, **ten of the nineteen closed were corrections of this
process's own errors** — not of the codebase's. Among them:

- An egress inventory that **overstated** the number of model call sites, twice, before reachability
  was established per site rather than counted from the source. Six → four → two.
- A diagnosis of "depleted monthly credits" that was actually a **short-window rate limit** — the
  provider's error message says the first and means the second.
- A claim that four tickets were "green in CI" when CI had not run on the branch at all, because the
  sprint's own branch prefix was missing from the push triggers.
- A specification premise that structured-output support is a property of the **endpoint**. It is a
  property of the **(endpoint, model) pair**, measured one request per cell before any default was
  written.
- A dependency-report prediction that a rebuild would change a licence row. It did not, and the
  correction was recorded rather than quietly applied.

**This is stated plainly rather than buried**, because the rate at which a process catches itself is
the only available evidence that it does. ⚠ It is also the reason the assessment prefers
*"verified on DATE by running X"* to *"the system does Y"*: every one of the findings in §2 was found
by running something, and several of them contradicted a document written by someone who understood
the design.

---

## 4. What was deliberately not done

Recorded so that absence reads as a decision rather than an oversight.

- **A governance model and a release/versioning policy.** Both would state commitments nobody has
  agreed to, on a project whose IP ownership is formally open. Deferred pending Q-08-01.
- **Self-hosted inference.** Designed and costed, then parked: nobody owns the GPU running costs, and
  an excellent system nobody funds to keep running is a worse outcome than not building it.
- **A machine-learning name recogniser.** Moved out of the redaction sprint into a standalone
  initiative; the deterministic layer ships first and its residual gets measured rather than assumed.
- **Positive SEAH scenarios in the committed benchmark.** Three hundred realistic Nepali harassment
  complaints in a public repository would be read as leaked case data whatever the file was called.
  The consequence is accepted: the recall half of the safeguarding measurement is not reproducible
  from this repository.
- **Publishing the repository default as the open configuration.** An open base URL with unvalidated
  model ids is a repository that cannot serve one request on a fresh clone — weaker evidence, not
  stronger.

---

## 5. What remains

These are gaps, so they are assessed properly in
[`00_compliance_status.md`](00_compliance_status.md) rather than listed here. In outline:

- **The IP determination** — external, blocking, and not movable by this team.
- **Sprint 3 (PII redaction)** — not started, and a go-live precondition rather than a remediation
  while no genuine grievance has been processed.
- **The open accuracy column** — unblocked, unmeasured, and waiting on a spending decision.
- **SEAH detection recall** — needs a held-out set that never enters git.
- **Deployment** — `ops` is on neither server, so the licence scan, the CVE scan and the health
  monitor run nowhere but a development stack; and the CI platform-independence job has never
  executed in CI.

---

## 6. Related

- [`00_compliance_status.md`](00_compliance_status.md) — the assessment. Read that first
- [`02_questions.md`](02_questions.md) — what we need from the consultant
- [`../sprints/2026-08-llm/PROGRESS.md`](../sprints/2026-08-llm/PROGRESS.md) — the live tracker, ticket by ticket
- [`../sprints/2026-08-llm/DECISIONS.md`](../sprints/2026-08-llm/DECISIONS.md) — the decision register
- [`../sprints/2026-08-llm/followups/`](../sprints/2026-08-llm/followups/) — every deferral, with a definition of done
