# Nepal GRM platform — DPG qualification briefing

**For:** ADB's Digital Public Goods consultant · **From:** the project team · **Date:** 2026-08-17
**Subject:** self-assessment against the [DPG Standard](https://www.digitalpublicgoods.net/standard), the
engineering that closes the gaps, and fourteen questions for you — **three of which block us** (Q1, Q4, Q15).

> **What this document is.** A summary, written to be read before a meeting. The full
> indicator-by-indicator assessment, with file-and-line evidence for every claim, is
> [`00_compliance_status.md`](00_compliance_status.md) — read that if you want to check our working.
>
> **A note on timing.** §2 lists engineering that is **specced but not yet built**; our meeting falls after
> it lands, so that list is forward-looking. **If any of it slips we will say so in the meeting rather than
> let this page stand.** Nothing in §1 or §5 depends on it.
>
> **We have not written this as a compliance pitch.** Two of the nine indicators have real gaps, one cannot
> be closed by anyone on the engineering team, and the AI-specific reading of indicator 4 is the substance
> of the discussion. The honest version is more useful to us than the flattering one.

---

## The system, in three sentences

A Grievance Redress Mechanism for ADB-financed road infrastructure in Nepal (KL Road /
Kakarbhitta–Laukahi, ADB Loan 52097-003). Affected people raise grievances in Nepali by chat or voice; the
implementing agency works them through a workflow with enforced service-level deadlines and an escalation
ladder up to a Grievance Redress Committee. It includes a dedicated, access-isolated SEAH (sexual
exploitation, abuse and harassment) intake stream, and anonymous submission end to end.

---

## 1. Where we stand

| # | Indicator | Status | The gap, if any |
|---|---|---|---|
| 1 | Relevance to SDGs | ✅ **Compliant** | None. SDG 16.6, 16.10, 9.1. Needs writing up, not building |
| 2 | Approved open licence | 🟠 **Trivial — but waiting on two answers** | The repo is public with **no `LICENSE` file**, which means all rights reserved. We need to know **which licence** (your view — we recommend Apache-2.0) and **who holds copyright** (indicator 3) |
| 3 | Clear ownership | 🔴 **Blocked, external** | A written IP determination from ADB. **Nobody on this project can resolve it** |
| 4 | Platform independence | 🔴 **The main work** | Our AI layer calls one commercial provider, with model names hard-coded in nine places. §4 is entirely about this |
| 5 | Documentation | ✅ **Compliant, strong** | A ~200-file spec tree, a Docker runbook, OpenAPI on both APIs, plus a portable engineering starter kit another country team could reuse |
| 6 | Data extraction | ✅ **Compliant** | PostgreSQL, version-controlled schema, XLSX and PDF exports, REST APIs. `pg_dump` gives a complete portable extract |
| 7 | Privacy & applicable laws | 🟠 **Partial** | Encryption and access control are built. Missing: the legal assessment, a data-flow diagram, and redaction of free text before it leaves the country |
| 8 | Standards & best practices | 🟢 **Mostly** | OpenAPI, OIDC/PKCE, migrated schema. Missing the open-source *project* files — `CONTRIBUTING`, `CODE_OF_CONDUCT`, `SECURITY` |
| 9 | Do no harm by design | 🟢 **Mostly** | Access control, audit log, SEAH isolation, anonymous intake all built. Outstanding: retention/breach policy, and third-party PII redaction |

**Two blockers, one of them ours.** Indicator 3 is a signature we have to ask for. Indicator 4 is
engineering we have specced and are about to build.

**Our strongest card is indicator 2: there is no proprietary component anywhere in the runtime stack.** No
closed database, no closed identity provider, no closed framework, no vendored SDK we could not replace —
every layer is a permissively-licensed open source project a third party could self-host with no commercial
relationship with anyone. Full inventory in §6.

---

## 2. What the engineering sprint closes before we meet

Four sub-sprints, 27 tickets, specced in full at
[`../sprints/2026-08-llm/`](../sprints/2026-08-llm/README.md).

**Licensing and governance** — *indicators 2, 3, 5, 7, 8*
- `LICENSE`, `NOTICE` and SPDX headers, with a re-runnable script and a test so coverage cannot decay —
  *gated on your licence answer and ADB's ownership determination*.
- A **generated** dependency-licence report over four dependency sets (two Python, npm, container images),
  wired into an existing scheduled scan so it cannot go stale. Machine output, not our assertion.
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue templates — the security file written with
  real care rather than templated, since this platform holds SEAH disclosures and "open a public issue" is
  the wrong disclosure route.
- The privacy assessment against Nepal's Individual Privacy Act 2018, with a data-flow diagram naming every
  boundary personal data crosses.

**Platform independence** — *indicator 4, the main work*
- **One configuration file** declaring every model endpoint and model name for the whole product, read by
  both AI subsystems. Switching providers becomes an environment-variable change, **with a test proving a
  single change moves both subsystems.**
- **A characterization test net first** — there is currently not one automated test covering either AI
  surface, so the sprint opens with tests, not refactoring.
- Schema-constrained model output replacing prompt-instructed JSON — which *improves* portability rather
  than trading it away, since prompt-only JSON is the least portable choice available.
- A model-reachability health probe, and a test proving intake still completes with the endpoint dead.

**Open models, and evidence that cannot rot** — *indicator 4 evidence*
- A labelled Nepali benchmark set (synthetic in the first pass) and a published comparison table, every
  number stating its provenance.
- **A CI job running the AI test suite against the open configuration on every commit** — the strongest
  single piece of evidence we can offer, because unlike a document it cannot silently become untrue.
  *Its cost is Q15.*
- A documented and costed self-hosted deployment — **designed, not deployed**; see §5.

**Privacy at the egress boundaries** — *indicators 7, 9*
- Redaction before transmission: Nepali phone formats in **both** digit systems, citizenship numbers,
  vehicle registrations, emails. Devanagari digits are the detail worth naming — `९८४१२३४५६७` is a phone
  number an ASCII pattern misses completely.
- Redaction of the logging, task-queue and backup paths — the model call is the leak everyone designs
  against; logs and queued payloads are the leak that actually happens.
- Measured recall, published, including where it is weak. ⚠ **Person names stay unaddressed in this
  pass** — see Q9.

---

## 3. What we need from you

Grouped by what the answer unblocks. 🔴 = we cannot finish without it.

### Ownership and process

- **Q1 🔴 — Does ADB have a standing IP position for software developed under a loan-financed engagement,
  or is it case by case?** Who is the right signatory, and what is a realistic timeline? This blocks our
  `LICENSE` file and the submission itself. It has the longest lead time on the list and **it is the single
  most valuable thing you can help us with.**
- **Q2 — Are there precedents?** Has ADB nominated software as a DPG before? If so, can we reuse the shape
  of that ownership determination rather than starting from a blank page?
- **Q3 — Who submits?** Does ADB nominate, or do we self-submit with ADB endorsement? Does the implementing
  agency (DOR) need to be a party, given that production runs on DOR infrastructure?
- **Q13 — Sequencing.** Can we begin the assessment with indicator 4 in progress and the CI evidence not
  yet green, or should we complete the engineering first? A rough timeline for the assessment would help us
  schedule against it.

### Indicator 4 for AI systems — the substance

- **Q4 🔴 — Is our reading correct?** We read the Standard as requiring us to demonstrate that the closed
  component *could* be replaced with minimal configuration change — not that we must run open models in
  production. **As it happens we intend to run them anyway** (§5), so we expect to satisfy the stricter
  reading too. We would still like the answer, because it determines how much benchmark evidence the
  submission needs before we can claim it.
- **Q5 — How does the DPGA treat "open weight" models whose licences are not OSI-approved?** Several strong
  multilingual models ship under bespoke community licences with use restrictions. We are filtering for
  Apache-2.0 or MIT to be safe, which narrows the field and **may cost us quality on Nepali specifically.**
  How much does that filter matter?
- **Q6 — How does the DPGA treat a *partial* open alternative?** If open-weights speech recognition works
  for Nepali but at a materially higher error rate, is "functional, with documented degradation" acceptable,
  or does the alternative need parity? This determines whether voice intake can exist in an open
  configuration at all.
- **Q5b — The "data" limb of the AI questionnaire.** We do no training or fine-tuning; every call is
  zero-shot prompting against a taxonomy we author. Does that dispose of the data question, or do you expect
  us to publish an evaluation set and prompt templates as artefacts?
- **Q7 — Two dependency-licence readings.** (a) We run Redis as a network service behind a process
  boundary, not as a linked library, and take Redis 8 under **AGPLv3** — the one OSI-approved option of its
  three. **Does AGPLv3 anywhere in the stack cause a problem** for you, for the assessment, or in ADB/DOR
  procurement? If so we will move to Valkey (BSD-3-Clause); we simply prefer not to pay the switching cost
  speculatively. (b) Is `psycopg2-binary`'s LGPL-with-exceptions an issue for a permissively-licensed DPG?

### Privacy and safeguarding

- **Q8 — Redaction posture.** We have decided to **redact at transmission, not before storage**: the officer
  handling a case needs to see which official was named, and for a GRM complaints naming officials are a
  large share of the useful ones. **Does the DPGA or ADB safeguards policy take a contrary position?** If
  PII must not be stored in free text at all, that is a much larger change and we want to know now.
- **Q9 — The NER recursion, and a possible contribution.** Person-name detection in Nepali needs an ML
  model. The most accurate one we can find has **no licence stated** on its model card — shipping it would
  swap one closed dependency for another inside the submission meant to remove it. Our intended answer is
  to fine-tune our own on an openly-licensed corpus, **release it openly**, and run it as a standalone
  anonymiser service reusable by any country programme where in-country self-hosting is impossible.
  **Would the DPGA see that as a positive, and is there ADB appetite to fund it?**

### The one ask that blocks work rather than paperwork

- **Q15 🔴 — Can ADB fund a small *metered inference* budget?** We have none today — enough for a few
  classification calls a day, which is why voice transcription is switched off. Three deliverables are made
  of inference calls: the speech evaluation, the text benchmark, and the CI job that runs on every commit.
  **The amounts are small** — a few hundred short synthetic texts across a handful of models on per-token
  pricing is plausibly tens of dollars, and the CI job can be capped. **This is two orders of magnitude below
  the GPU instance we just parked**, with a defined end point. Two parts: **can it be funded as part of the
  DPG work itself**, and **how much benchmark evidence does the submission actually require?**
- **Q10 — Which project-hygiene artefacts are actually required** versus merely liked? `CONTRIBUTING`,
  `CODE_OF_CONDUCT`, `SECURITY`, issue templates, public roadmap, release tags, governance model. We would
  rather build the required set once than guess and iterate.
- **Q14 — Is there anything in the current Standard revision, or the AI-systems guidance specifically, that
  we have missed** by reading the published Standard and questionnaire?

> Two questions from the full document are not repeated here. **Q11** (hosting jurisdiction) is moot while
> self-hosting is parked, though the *provider's* jurisdiction is now a permanent question rather than a
> transitional one. **Q12** (sustainability) we have effectively answered ourselves — see §5.

---

## 4. The AI layer, in brief

**How we query models today.** Nine call sites, six distinct models, **two independent subsystems**, and not
one reads a configurable endpoint or model name. Every model string is a Python literal.

| Subsystem | What it does | Data sent to the provider |
|---|---|---|
| Chatbot intake | Voice transcription; contact extraction; grievance classification and summary; Nepali→English translation; sensitive-content detection | Raw complainant voice recordings; names and phone numbers; the full grievance narrative |
| Ticketing | Officer-note translation; case findings; the resolved-case summary shown to the complainant | Officer case notes verbatim; whole case timelines, including SEAH cases |

**Three things worth being candid about.**

**It is a configuration refactor, not a rewrite.** The client is constructed with no base-URL override, but
the SDK accepts one and the major open-weights serving stacks expose a compatible API — exactly the "minimal
configuration changes" the Standard asks about. **The precedent is inside our own codebase:** the SMS layer
already runs two providers behind one interface selected by environment variable (AWS SNS internationally,
the Government of Nepal gateway for Nepal). Having done it once already is the best evidence this is a
refactor rather than a redesign.

**The AI paths are already fail-soft, which lowers the switching risk.** Intake writes the grievance to
PostgreSQL *before* any model call; classification runs as a retrying background task with explicit failure
states; the chatbot waits on a bounded deadline. **A grievance is never lost because a model was
unavailable** — so a slower model degrades throughput, not intake.

**And the thing we are least comfortable with:** there is **not a single automated test** covering either AI
surface, so our statements about model behaviour rest on manual observation rather than evidence we could
hand you. That is why the sprint starts with tests.

---

## 5. Decisions we have already taken

Recorded so they are not re-opened, and because two of them change what we are asking of you.

- **Self-hosted inference is parked.** We had planned to move inference onto a rented GPU instance under the
  agency's own contract, keeping grievance text inside contracted infrastructure. **There is no owner for the
  run costs, so we are not starting it** — the failure mode that killed Rwanda's Babyl, better avoided by not
  starting than discovered later. **The consequence: a hosted third-party provider is the steady state, not a
  transition**, so grievance text crosses a border indefinitely. That does not change the indicator-4 answer —
  a hosted open-weights provider is still an open alternative — but it turns the privacy exposure from
  transitional into permanent, and makes redaction the only remaining control rather than defence in depth.
- **Production will run the open configuration**, on cost grounds, with the commercial provider kept as a
  configurable fallback if users report quality problems. **This is more than indicator 4 requires** and we
  would lead with it: the Standard asks for demonstrated replaceability; we intend to run the replacement.
- **Redaction happens at transmission**, not before storage — see Q8.
- **Person-name redaction is deferred** to the standalone anonymiser service in Q9; the first pass covers
  numeric identifiers and emails. **Third-party names in narrative will still reach the provider** — a
  disclosed residual, not a solved problem.
- **A licence-drift finding we surfaced ourselves and fixed.** Our Redis image tag pinned only the major
  version, so it silently followed upstream onto a non-OSI licence line — nobody edited the file; the licence
  moved underneath it. Now pinned to a minor and taken under AGPLv3. **The class of problem is more
  interesting than the instance:** a floating tag is a licence you did not choose, so our dependency audit
  now includes a pin-drift check.

---

## 6. Dependency inventory

Every library and image in the runtime stack. ⚠ Licences below are stated from the manifests and package
knowledge, **pending the generated report** the sprint produces — we would rather show you machine output
than our assertion, and that is one day of work.

**Two points a reviewer usually asks about.** Identity is **self-hosted** (Keycloak 26, OIDC + PKCE) rather
than federated to a vendor — an earlier plan used AWS Cognito and we migrated away during the build, removing
what would have been a hard indicator-4 dependency at the authentication layer. And the conversational state
machine is our own code, with `rasa-sdk` surviving only as a type shim: **there is no Rasa server and no
TensorFlow anywhere.**

**Python — chatbot stack (`requirements.txt`)**

| Package | Purpose | Licence |
|---|---|---|
| `fastapi` | Orchestrator + backend API | MIT |
| `uvicorn` (<0.50, pinned) | ASGI server | BSD-3-Clause |
| `pydantic` v2 | Validation | MIT |
| `python-multipart` | Uploads | Apache-2.0 |
| `pyyaml` | Config | MIT |
| `email-validator` | Validation | CC0-1.0 |
| `python-socketio` | WebSocket bridge | MIT |
| `rasa-sdk` 3.6.2 | `Tracker` / `CollectingDispatcher` types only — **there is no Rasa server and no TensorFlow** | Apache-2.0 |
| `psycopg2-binary` | PostgreSQL driver | ⚠ LGPL-3.0-with-exceptions — see Q7(b) |
| `SQLAlchemy` 2 / `alembic` | ORM / migrations | MIT |
| `pytz` | Timezones | MIT |
| `redis` (client) | Broker client | MIT |
| `celery` 5.5 / `flower` | Task queue / monitor | BSD-3-Clause |
| `boto3` | AWS SNS (SMS) + SES | Apache-2.0 |
| **`openai` 1.70.0** | **The only ML dependency — client only; the service it calls is the subject of §4** | Apache-2.0 |
| `requests` / `httpx` | HTTP clients | Apache-2.0 / BSD-3-Clause |
| `pyvips` | Image compression | MIT |
| `python-dotenv` | Config | BSD-3-Clause |
| `rapidfuzz` | Fuzzy matching | MIT |
| `langdetect` | Language detection | Apache-2.0 |
| `icecream` | Debug | MIT |
| `Flask` / `Werkzeug` / `flask-socketio` | Legacy blueprints; production is FastAPI | BSD-3-Clause / MIT |

**Python — GRM ticketing and ops (`requirements.grm.txt`)**

| Package | Purpose | Licence |
|---|---|---|
| `pydantic-settings` | Config (moving to the base requirements as shared config lands) | MIT |
| `openpyxl` | Quarterly XLSX reports (deliberately no pandas) | MIT |
| `python-jose[cryptography]` | Keycloak JWT / JWKS verification | MIT |
| `python-keycloak` | Keycloak Admin API | MIT |
| `reportlab` | Case-closure PDFs | BSD-3-Clause (open-source edition) |
| `apscheduler` | Broker-independent ops scheduler | MIT |
| `pip-audit` | Scheduled CVE scan | Apache-2.0 |
| `pytest` | Tests | MIT |

**Frontend (`channels/ticketing-ui/package.json`)** — only four runtime dependencies. No component library,
no state-management library, no charting library, no analytics SDK.

| Package | Licence |
|---|---|
| `next` 16.2.6 | MIT |
| `react` / `react-dom` 19.2.4 | MIT |
| `lucide-react` | ISC |
| `tailwindcss` v4 + `@tailwindcss/postcss` | MIT |
| `typescript` | Apache-2.0 |
| `eslint` / `eslint-config-next` | MIT |
| `vitest` | MIT |

**Container images**

| Image | Licence |
|---|---|
| `postgres:15` | PostgreSQL Licence (OSI) |
| `redis:8.10` | **AGPLv3** at our election — see Q7(a) and §5 |
| `nginx:stable` | BSD-2-Clause |
| `quay.io/keycloak/keycloak:26.0.7` | Apache-2.0 |

**External services** — operational dependencies, not code dependencies. Each is replaceable by
configuration and none constrains anyone's right to use or fork the code.

| Service | Used for | Replaceability |
|---|---|---|
| Commercial LLM API | All nine model calls | **The subject of §4** |
| AWS SNS | SMS to complainants (international / development) | Provider-agnostic behind one interface; already dual-implemented |
| DOIT SMS (`sms.doit.gov.np`) | SMS in Nepal — Government of Nepal gateway | The production path; configured, not compiled in |
| SMTP relay | Email notifications and quarterly reports | Any SMTP server |
| AWS EC2 | Hosting | Any VM |

---

## Where to look next

| | |
|---|---|
| The full assessment, with file-and-line evidence | [`00_compliance_status.md`](00_compliance_status.md) |
| The engineering plan — 27 tickets, four sub-sprints | [`../sprints/2026-08-llm/README.md`](../sprints/2026-08-llm/README.md) |
| Decisions taken, with the reasoning | [`../sprints/2026-08-llm/DECISIONS.md`](../sprints/2026-08-llm/DECISIONS.md) |
| The documentation tree | [`../README.md`](../README.md) |
