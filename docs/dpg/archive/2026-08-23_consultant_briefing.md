# Nepal GRM platform — DPG qualification briefing

**For:** ADB's Digital Public Goods consultant · **From:** the project team · **Date:** 2026-08-23
**Subject:** a self-assessment against the [DPG Standard](https://www.digitalpublicgoods.net/standard),
the engineering that closes the gaps, and **nineteen questions for you — three of which block us**
(Q1, Q6, Q14). A fourth, **Q4**, blocks nothing but is the cheapest answer on the list: a licence we
have already applied, waiting only for you to say you have no objection.

> **What this document is.** A summary, written to be read before a meeting. The full
> indicator-by-indicator assessment, with the evidence behind every claim, is
> [`00_compliance_status.md`](00_compliance_status.md) — read that if you want to check our working.
>
> **We have not written this as a compliance pitch.** Two of the nine indicators have real gaps, one
> cannot be closed by anyone on the engineering team, and the AI-specific reading of indicator 4 is the
> substance of the discussion. The honest version is more useful to us than the flattering one.

---

## The system, in three sentences

A Grievance Redress Mechanism for ADB-financed road infrastructure in Nepal (KL Road /
Kakarbhitta–Laukahi, ADB Loan 52097-003). Affected people raise grievances in Nepali by chat or voice;
the implementing agency works them through a workflow with enforced service-level deadlines and an
escalation ladder up to a Grievance Redress Committee. It includes a dedicated, access-isolated SEAH
(sexual exploitation, abuse and harassment) intake stream, and anonymous submission end to end.

---

## 1. Where we stand

| # | Indicator | Status | The gap, if any |
|---|---|---|---|
| 1 | Relevance to SDGs | ✅ **Compliant** | None. SDG 16.6, 16.10, 9.1. Needs writing up, not building |
| 2 | Approved open licence | 🟢 **Closed, provisionally** | `LICENSE` (Apache-2.0), `NOTICE`, an SPDX header on **593 source files** maintained by a script and held by a test so coverage cannot decay, and a **generated** licence audit over 153 packages in four dependency sets. Two things stay provisional: the **licence text** is yours to confirm (Q4), and the **copyright holder** is blank pending indicator 3 — `NOTICE` says so rather than guessing |
| 3 | Clear ownership | 🔴 **Blocked, external** | A written IP determination from ADB. **Nobody on this project can resolve it**, and it is now the only thing standing between us and a complete licensing story |
| 4 | Platform independence | 🟡 **The mechanism is built and running; the model choice is not made** | Every model in the product is a configuration value — nine call sites, two subsystems, one registry, proven by tests and exercised live against an open-weights provider. **But** the repository default is still proprietary and **no open model has been selected** — the comparative benchmark is unfinished. ⚠ The open provider serves no speech endpoint; that costs nothing today, because automatic transcription is switched off on cost grounds and is not expected to be funded. §3 |
| 5 | Documentation | ✅ **Compliant, strong** | A 365-file spec tree, a Docker runbook for 13 services, OpenAPI on both APIs, and a portable engineering starter kit another country team could reuse |
| 6 | Data extraction | ✅ **Compliant** | PostgreSQL, version-controlled schema in three independent migration streams, XLSX and PDF exports, REST APIs. `pg_dump` gives a complete portable extract |
| 7 | Privacy & applicable laws | 🟠 **Partial — and nothing real has happened yet** | The assessment against the Individual Privacy Act 2018 and a 13-leg data-flow diagram are written, each leg verified against code rather than against our own
specs, which is how three storage-layer defects surfaced
([`00_compliance_status.md`](00_compliance_status.md) §3.3). ⭐ **No genuine grievance has been processed on this platform**: every record is seed data or a demo dummy, so every exposure is **prospective**, and redaction is a **go-live precondition rather than remediation**. Still missing: that redaction, a deletion capability, and a lawyer's review (Q15) — now the only thing gating the notification clock in the breach procedure written on 2026-08-24 |
| 8 | Standards & best practices | ✅ **Compliant** | OpenAPI, OIDC/PKCE via self-hosted Keycloak, migrated schema, architectural invariants pinned by tests, and the hygiene set at the repo root. `SECURITY.md` routes disclosure privately rather than to a public issue, because this platform holds SEAH reports. Secrets are SOPS-encrypted in the repository, and a scan of **every blob ever committed** against every live credential confirms none of them is readable in the public history
([`00_compliance_status.md`](00_compliance_status.md) §3.5). Governance and release-versioning policy deferred pending Q17 |
| 9 | Do no harm by design | 🟢 **Mostly** | Access control, audit log, SEAH isolation, anonymous intake, and **two independent** content-detection paths. Outstanding: a retention policy, third-party PII redaction, and **a measured SEAH detector** — the one with a safeguarding consequence. The breach procedure is written; three decisions in it are DOR's |

**One blocker that is genuinely ours to close, and one that is not.** Indicator 4 is engineering that is
mostly done and whose last step is a **measurement**, not a refactor. **Indicator 3 is a signature we have
to ask you for** — `LICENSE` and `NOTICE` are in place but cannot name a copyright holder until ADB rules.

**Our strongest card is indicator 2: there is no proprietary component anywhere in the runtime stack.** No
closed database, no closed identity provider, no closed framework, no vendored SDK we could not replace.
The audit is generated inside the running containers against the resolved trees, not read off manifests,
and it returns **zero** unknown and **zero** non-OSI licences across 153 packages. §5.

---

## 2. What is not done

The work is specced in full at [`../sprints/2026-08-llm/`](../sprints/2026-08-llm/README.md) — 31 tickets
across four sub-sprints, of which Sprints 0, 1 and 2 have landed. What is *in place* is the evidence
column of §1; what remains is here, because that is the part worth your time.

**Indicator 4 — one measurement, not a refactor**

- **No open model has been chosen.** The comparative benchmark has the closed baseline complete and the
  open column one metric in.
- **⚠ Sensitive-content recall is unmeasured for both candidates**, and it decides the choice. It cannot
  be measured from anything in this repository: the committed benchmark holds no harassment reports, by
  decision rather than omission.
- **⚠ The CI job that demonstrates platform independence has never executed in CI.** It passes when run
  by hand ([`00_compliance_status.md`](00_compliance_status.md) §4.5).

**Indicators 7 and 9 — the egress boundary, not yet built**

- **Grievance text still leaves the country unredacted** on every model call, along with officer notes and
  whole case timelines. Sprint 3 builds the redaction; it has not started.
- **No code path deletes personal data anywhere in this platform.** Archiving is implemented and is not
  deletion, and no retention period has been chosen — that needs a legal position before it needs code.
- **The breach procedure is written** ([`../deployment/19_incident_response.md`](../deployment/19_incident_response.md)),
  and `SECURITY.md` now points at it rather than at a promise with nothing behind it. **Three decisions in
  it are blank, and they are for the Department of Roads rather than for us:** who declares a breach, who
  is notified on what clock, and how a survivor is told when a SEAH case is exposed. The maintainer holds
  all three on an interim basis and the document says so. ⭐ **Writing it caught a live defect** — Keycloak
  was recording **no login events at all**, and the daily ops report was printing `0` logins rather than
  "not recorded". Fixed the same day, and forward-only: nothing before it is recoverable.
- **The privacy assessment has had no legal review** (Q15).

**Indicator 3 — not ours to close**

- **No written IP determination**, so `LICENSE` and `NOTICE` name no copyright holder and the submission
  cannot proceed (Q1).

---

## 3. The AI layer — what is built

Every model this system calls is a configuration value. Nine call sites across two subsystems resolve
through one registry that both import and neither owns; **none names a model, a provider or an endpoint.**

| Built | Evidence |
|---|---|
| One config file — every endpoint, model, deadline and output mode, declared once | `backend/config/llm_config.py` |
| Two configurations that differ only in values | `diff .env.openai .env.open` is the whole delta |
| One environment change moves **both** subsystems, and no model name survives anywhere outside the registry | two tests, the second AST-parsed |
| Schema-constrained model output, per-model capability measured against the live provider | 7 call sites, with a degradation ladder |
| The product's own code paths, run live against an Apache-2.0 open-weights model | `dpg-platform-independence` CI job |
| A 105-item labelled Nepali benchmark set, published CC0-1.0 | scored by the product's own functions |

**Switching providers is an environment-variable change** — no code, no rebuild, no migration. What is
*not* built is in §1 and §2; the open questions it raises are §4.

---

## 4. What we need from you

Grouped by what the answer unblocks. 🔴 = we cannot finish the work without it.


### Ownership, licensing and process

- **Q1 🔴 — How is IP ownership determined for software developed under a loan-financed engagement, and
  who signs that determination?** We cannot name a copyright holder or submit without it, and we do not
  know the right channel to open.
- **Q2 — Has ADB nominated software as a DPG before, and what should we take from how it was handled?**
- **Q3 — What is the submission route?** Whether ADB nominates or we self-submit with endorsement, and
  whether the implementing agency needs to be a party.
- **Q4 — Do you have any objection to Apache-2.0?**
- **Q5 — When in the engineering should the assessment start, and how long does it usually take?**

### Indicator 4 for AI systems

- **Q6 🔴 — How does the DPGA assess platform independence for an AI system?** In particular, what weight
  sits on a configurable and tested open alternative, versus on what production actually runs.
- **Q7 — How does the DPGA treat open-weight models whose licences are not OSI-approved?** We filter for
  Apache-2.0 and MIT, which excludes several of the strongest multilingual models for Nepali.
- **Q8 — How does the DPGA treat a partial open alternative?** Our open configuration serves **every
  model call the system actually makes**. The one path it could not serve — speech — is switched off
  on cost grounds and is not expected to be funded.
- **Q9 — What does the *data* limb of the AI questionnaire expect from a system that does no training or
  fine-tuning?** We have published a 105-item labelled evaluation set under CC0-1.0.
- **Q10 — Do any of these licences cause a problem for the assessment, or in ADB/DOR procurement?**
  AGPLv3 (Redis, elected from its three), LGPL-with-linking-exception (`psycopg2-binary`), and two
  transitive LGPL libraries.
- **Q11 — How much benchmark evidence does a submission need to substantiate an open-alternative claim?**

### Privacy and safeguarding

- **Q12 — What posture do the DPGA or ADB safeguards policy expect on personal data held in free text?**
  We redact at transmission rather than before storage.
- **Q13 — Would an openly-released Nepali anonymiser model count as a DPG contribution, and is there ADB
  appetite to fund one?** The most accurate existing Nepali NER model states no licence.
- **Q14 🔴 — Does ADB or the DPGA expect a signed data-processing agreement with the inference provider?**
  Unless pinned, the router selects a different third-party processor per request, and its terms
  reference no DPA.
- **Q15 — Does the DPGA expect a legally-reviewed privacy assessment, or is a documented engineering one
  sufficient?** Ours is written; no lawyer has read it.
- **Q16 — Does the DPGA have a position on cross-border processing for a national-government DPG?**

### Scope, sustainability and funding

- **Q17 — Which project-hygiene artefacts does the DPGA require?** We have `SECURITY`, `CONTRIBUTING`,
  `CODE_OF_CONDUCT` and issue/PR templates; no governance model and no versioning policy.
- **Q18 — Does the assessment consider who funds and operates the system after the pilot?** Our inference
  budget is time-boxed and personally funded, and the CI job that produces the indicator-4 evidence has
  no owner beyond it.
- **Q19 — What are we missing?** Anything in the current Standard revision, or the AI-systems guidance,
  that we would not find by reading the published documents.

---

## 5. Dependency inventory

**There is no proprietary component anywhere in the runtime stack**, and no dependency in any tree carries
an unknown, unparseable or non-OSI licence. The figures below come from a scan run **inside the running
containers** against the resolved trees — not from reading manifests. The full per-package listing, with a
written disposition for every entry carrying conditions beyond attribution, is
[`dependency-licenses.md`](dependency-licenses.md). ⚠ The scheduled re-run that keeps it fresh is
**built but not yet deployed** — the `ops` container has not shipped to
either server, so today the scan runs only in a development stack.

| Set | Packages | Unknown or non-OSI |
|---|---|---|
| Python — declared in the two manifests | 35 | 0 |
| Python — transitive | 98 | 0 |
| npm — production tree | 16 | 0 |
| Container images | 4 | 0 |
| **Total** | **153** | **0** |

| Layer | What it is | Licence |
|---|---|---|
| Web frameworks | FastAPI, Uvicorn, Starlette, Pydantic v2 | MIT / BSD-3-Clause |
| Database | PostgreSQL 15 | PostgreSQL Licence (OSI) |
| ORM & migrations | SQLAlchemy 2, Alembic (three streams) | MIT |
| Task queue | Celery 5.5, Flower | BSD-3-Clause |
| Cache / broker | Redis 8.10 | **AGPLv3 at our election** — Q10(a) |
| Identity | Keycloak 26, self-hosted (OIDC + PKCE) | Apache-2.0 |
| Reverse proxy | nginx stable | BSD-2-Clause |
| Officer frontend | Next.js 16, React 19, Tailwind v4, lucide-react | MIT / ISC |
| Reports & documents | openpyxl, ReportLab | MIT / BSD-3-Clause |
| Images | pyvips / libvips | MIT / LGPL-2.1 |
| Conversational state machine | This project's own code and orchestrator; `rasa-sdk` supplies the action/form base classes — **no Rasa server, no NLU, no TensorFlow** | Apache-2.0 |
| **Model client** | **`openai` — the only ML dependency, and the *client* is open; the service it calls is the subject of §3** | Apache-2.0 |

**Reading manifests would have missed 98 of the 133 Python packages**, and with them the three copyleft
findings worth your eye (Q10): `psycopg2-binary` (LGPL with a linking exception), and two **transitive**
LGPL libraries — `jwcrypto`, arriving through the Keycloak JWT path, and the prebuilt libvips binaries,
arriving through Next.js image optimisation. **None of the three is anyone's declared dependency.** A
licence obligation does not care how a package got there.

**Two points a reviewer usually asks about.** Identity is **self-hosted** (Keycloak 26) rather than
federated to a vendor — an earlier plan used AWS Cognito and we moved during the build, removing what
would have been a hard indicator-4 dependency at the authentication layer. And the conversational state
machine and its orchestrator are our own code. ⚠ **`rasa-sdk` is more than a type shim** — 49 modules
import it and our form base class inherits its `FormValidationAction`, whose dispatch our orchestrator
executes. The claim that carries the licensing weight is narrower and it holds: **there is no Rasa
server, no Rasa NLU and no TensorFlow anywhere**, and `rasa-sdk` itself is Apache-2.0.

### External services

Operational dependencies, not code dependencies. Each is replaceable by configuration, and none constrains
anyone's right to use or fork the code.

| Service | Used for | Replaceability |
|---|---|---|
| Commercial LLM API | The five live model calls | **The subject of §3** — one environment variable |
| AWS SNS | SMS to complainants (international / development) | Provider-agnostic behind one interface; already dual-implemented |
| DOIT SMS (`sms.doit.gov.np`) | SMS in Nepal — Government of Nepal gateway | The production path; configured, not compiled in |
| SMTP relay | Email notifications and quarterly reports | Any SMTP server |
| AWS EC2 | Hosting | Any VM |

---

## Where to look next

| | |
|---|---|
| The full assessment, indicator by indicator | [`00_compliance_status.md`](00_compliance_status.md) |
| The privacy assessment + 13-leg data-flow diagram | [`privacy-assessment.md`](privacy-assessment.md) |
| The generated dependency-licence audit | [`dependency-licenses.md`](dependency-licenses.md) |
| How to run this system on open models | [`open-model-configuration.md`](open-model-configuration.md) |
| What the models actually score | [`model-benchmarks.md`](model-benchmarks.md) |
| Self-hosted inference — designed, costed, not deployed | [`vllm-deployment.md`](vllm-deployment.md) |
| The engineering plan — 31 tickets, four sub-sprints | [`../sprints/2026-08-llm/README.md`](../sprints/2026-08-llm/README.md) |
| Decisions taken, with the reasoning | [`../sprints/2026-08-llm/DECISIONS.md`](../sprints/2026-08-llm/DECISIONS.md) |
| The documentation tree | [`../README.md`](../README.md) |
