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
| 4 | Platform independence | 🟡 **The mechanism is built and running; the model choice is not made** | Every model in the product is a configuration value — nine call sites, two subsystems, one registry, proven by tests and exercised live against an open-weights provider. **But** the repository default is still proprietary, no open model has been selected, and the open configuration **cannot transcribe audio at all**. §4 |
| 5 | Documentation | ✅ **Compliant, strong** | A 365-file spec tree, a Docker runbook for 13 services, OpenAPI on both APIs, and a portable engineering starter kit another country team could reuse |
| 6 | Data extraction | ✅ **Compliant** | PostgreSQL, version-controlled schema in three independent migration streams, XLSX and PDF exports, REST APIs. `pg_dump` gives a complete portable extract |
| 7 | Privacy & applicable laws | 🟠 **Partial — and nothing real has happened yet** | The assessment against the Individual Privacy Act 2018 and a 13-leg data-flow diagram are written, each leg verified against code — which is how the three storage-layer defects in §5 came to light, all three now fixed. ⭐ **No genuine grievance has been processed on this platform**: every record is seed data or a demo dummy, so every exposure is **prospective**, and redaction is a **go-live precondition rather than remediation**. Still missing: that redaction, a deletion capability, a breach procedure, and a lawyer's review (Q15) |
| 8 | Standards & best practices | ✅ **Compliant** | OpenAPI, OIDC/PKCE via self-hosted Keycloak, migrated schema, architectural invariants pinned by tests, and the hygiene set at the repo root. `SECURITY.md` routes disclosure privately rather than to a public issue, because this platform holds SEAH reports. Secrets are SOPS-encrypted in the repository, and a scan of **every blob ever committed** against every live credential confirms none of them is readable in the public history (§5). Governance and release-versioning policy deferred pending Q17 |
| 9 | Do no harm by design | 🟢 **Mostly** | Access control, audit log, SEAH isolation, anonymous intake, and **two independent** content-detection paths. Outstanding: retention and breach policy, third-party PII redaction, and **a measured SEAH detector** — the one with a safeguarding consequence, §4 |

**One blocker that is genuinely ours to close, and one that is not.** Indicator 4 is engineering that is
mostly done and whose last step is a **measurement**, not a refactor. **Indicator 3 is a signature we have
to ask you for** — `LICENSE` and `NOTICE` are in place but cannot name a copyright holder until ADB rules.

**Our strongest card is indicator 2: there is no proprietary component anywhere in the runtime stack.** No
closed database, no closed identity provider, no closed framework, no vendored SDK we could not replace.
The audit is generated inside the running containers against the resolved trees, not read off manifests,
and it returns **zero** unknown and **zero** non-OSI licences across 153 packages. §6.

---

## 2. What has landed, and what is still ahead

Four sub-sprints, 31 tickets, specced in full at
[`../sprints/2026-08-llm/`](../sprints/2026-08-llm/README.md). Sprints 0, 1 and 2 have landed; Sprint 3
has not started.

### ✅ Already in place

**Licensing and hygiene** — *indicators 2, 5, 8*

- `LICENSE` (Apache-2.0), `NOTICE`, and an SPDX header on **593 source files**, applied by a committed
  idempotent script and held in place by a test that imports the script's own scope rather than restating
  it — so coverage cannot decay the first week someone adds a module.
- **A generated dependency-licence audit** over four sets — two Python manifests, npm, container images.
  Machine output, not our assertion. It found two transitive LGPL dependencies **no manifest would have
  shown**, and a licence contradiction in our own npm package. ⚠ A nightly re-run **is scheduled and is
  not yet deployed** — the `ops` container has not shipped to either server, so today it runs only in a
  development stack. The mechanism is committed; the guarantee is not.
- `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue and PR templates.
- A root `README` rewritten from the compose files. It had advertised a Rasa NLU service on port 5005
  that has never existed in this codebase — directly contradicting our own indicator-2 argument, on the
  most-read page in the repository.
- Secrets encrypted at rest in the repository with SOPS and `age`; `env.local` became a generated
  artefact rather than a file each developer maintains by hand. **And then we checked whether that was
  worth anything**, by hashing every live credential against every blob ever committed — which is how
  the two findings in §5 surfaced. ⭐ **The credential that matters most came back clean:** the database
  encryption key has never been committed, and it is the one secret this platform *cannot* rotate,
  because no re-encryption path exists and a leak would be permanent.

**Privacy** — *indicator 7*

- The **privacy assessment and a 13-leg data-flow diagram**, each leg verified against code. ⚠ It carries
  an unsoftened honesty marker — drafted by an AI agent, reviewed by no lawyer, statutory section numbers
  marked unverified — and it is the reason we can show you §5's three defects rather than still not
  knowing about them.
- **All three of those defects are fixed**, which is the change since the assessment was written.

**Platform independence** — *indicator 4, the main work*

- **One configuration file** declaring every model endpoint, model name and deadline in the product, read
  by **both** AI subsystems. Switching providers is an environment-variable change, **with a test proving a
  single change moves both subsystems** and an AST-parsed test proving no model name exists anywhere else.
- **A characterization test net landed first.** There had been **not one** automated test covering either
  AI surface, so the sprint opened with tests rather than refactoring — and that net found two latent
  crash bugs before anything was moved.
- **Two committed configuration templates** that differ only in values. `diff .env.openai .env.open` is
  the whole delta, and it is the answer to indicator 4.
- Schema-constrained model output replacing prompt-instructed JSON, with a degradation ladder, because
  prompt-only JSON is the least portable choice available and is exactly what breaks when you change
  models.
- **A CI job running the product's own AI code paths live against the open configuration.** Run by hand it
  returns **4 passed, 1 xfailed, exit 0** against an Apache-2.0 open-weights model. ⚠ **It has never
  executed in CI** — see §4.

**Evidence** — *indicator 4*

- A **105-item labelled Nepali benchmark set** published under CC0-1.0, with its provenance and its limits
  written down, and a harness that calls the product's own functions rather than a reimplementation.
- **The closed baseline measured in full**, and a capability matrix over seven open candidates with every
  licence verified from the model card at probe time.
- **A costed self-hosted deployment** — designed, not deployed; see §5.

### Still ahead

- **Choose an open model.** The open column of the benchmark has detection only. ⚠ The blocker was **our
  own prompt** — 20,700 characters, because the category catalogue was injected three times — which has
  since been cut by 70%, so re-running the open column is now the next measurement rather than a
  procurement problem.
- **Measure SEAH recall for both candidates.** This is the number that decides the model choice, it has a
  safeguarding consequence, and it cannot be measured from anything in the repository. §4.
- **Redaction at the egress boundaries** — *indicators 7, 9*. Nepali phone formats in **both** digit
  systems (`९८४१२३४५६७` is a phone number an ASCII pattern misses completely), citizenship numbers,
  vehicle registrations, emails, address spans; **person names at the rule layer** with no ML dependency —
  honorific and role-title triggers, a Nepali family-name gazetteer, and self-identification patterns; and
  the logging, task-queue and backup paths, which is where leaks actually happen rather than where
  everyone designs against them. ⚠ **Some names will still get through** — see §4.
- **A retention period, a deletion capability, and a breach procedure.** Archiving is implemented and is
  not deletion: **no code path deletes personal data anywhere in this platform**, and `SECURITY.md`
  already promises reporters a breach procedure that does not yet exist.

---

## 3. What we need from you

Grouped by what the answer unblocks. 🔴 = we cannot finish the work without it.

**These are deliberately short and open.** The evidence behind each sits in the sections above. The
judgement is yours — a question that arrived pre-argued would be asking you to check our reasoning
rather than to give us yours.

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
- **Q8 — How does the DPGA treat a partial open alternative?** Our open configuration serves the text
  paths; it has no OpenAI-compatible speech endpoint, so voice has no open path today.
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

## 4. The AI layer, in brief

**How we query models.** Nine call sites, two independent subsystems, and **not one of them names a
model, a provider or an endpoint.** All nine resolve through a single registry that both surfaces import
and neither owns.

| Subsystem | What it does | Data sent to the provider |
|---|---|---|
| Chatbot intake | Grievance classification and summary; sensitive-content detection. *(Voice transcription, contact extraction and grievance translation are complete but **switched off**.)* | The full grievance narrative; district and province |
| Ticketing | Officer-note translation; case findings; the resolved-case summary shown to the complainant | Officer case notes verbatim; whole case timelines, including SEAH cases |

**Five call sites are live, not nine.** The other four are the voice-notes flow, switched off in the
prototype for want of a transcription budget. They are declared in code as parked, each with a reason,
and a test enforces the only two acceptable states — **enqueued in production, or declared parked,
nothing else.** They resolve models through the same registry as the live paths, so unparking is a budget
decision, not a migration.

**And it is now two models, not six.** Every text task resolves to one small model; transcription to one
speech model. Eight task keys, two values.

### What is done, and what is not

**It is a configuration refactor, and it is finished.** `diff .env.openai .env.open` is the whole delta —
no code, no rebuild, no migration.

**What is not finished, and you should hear it from us rather than find it:**

- **No open model has been chosen.** The comparative benchmark is unfinished, so the repository default
  is still the proprietary configuration — deliberately, because an open endpoint pointed at proprietary
  model ids is a repository that cannot serve one request on a fresh clone.
- **The open configuration cannot transcribe.** The provider serves no OpenAI-compatible speech endpoint,
  so the claim is true for text and false for voice.
- **⚠ The CI job that demonstrates all of this has never run in CI.** It passes when run by hand; the
  provider account was rate-limited when it was written. **A job that exists, never runs, and is cited as
  evidence is not acceptable** — the workflow header says so in those words.
- **⚠ One measurement is missing and it carries a safeguarding consequence.** Sensitive-content *recall*
  decides the model choice, and it cannot be measured from anything in this repository: the committed
  benchmark holds no harassment reports, by decision rather than omission.

The benchmark figures, the two live defects the measurements exposed, and the candidate that refused a
grievance about children falling ill are in
[`00_compliance_status.md`](00_compliance_status.md) §4.3–§4.4 and
[`model-benchmarks.md`](model-benchmarks.md).

### Where the residual goes, and under whose terms — the substance of Q14

Redaction is imperfect by construction, so the honest question is what happens to the text that gets
through. With self-hosting parked, that text reaches a third party permanently, so we read the
provider's terms rather than assuming them.

Hugging Face's own commitments are substantive and we cite them: no user data stored for training, no
request body or response stored when routing, debugging logs for 30 days, SOC 2 Type 2 on the Hub.
⚠ **Then the sentence that decides it, and it is theirs:** *"External providers are responsible for
their own security measures."* **The no-storage commitment covers the router, not the company that runs
the model** — and by default the router picks a different third-party processor *per request*. For a
government privacy assessment, "we cannot name which company processed this citizen's grievance" is a
finding, not a footnote. The Terms reference no DPA.

We intend to pin one named provider so the processor is knowable. **What that still does not fix** —
the downstream provider's own retention, the jurisdiction of execution, and prompt caching — is why
Q14 asks whether a signed agreement is expected.

⚠ **And one precision we want settled before anyone briefs the ministry.** What redaction produces is
**pseudonymised** text, not **anonymised** text: we keep the mapping, so the text remains personal data.
**We will not let anyone tell the agency the grievances are "anonymised"** — the claim would not survive
scrutiny and would discredit everything else we say. What we can say is accurate and strong: only
pseudonymised text crosses the border, and the re-identification key never leaves Nepal.

Full analysis, including what we will not overstate about the router's multi-vendor fan-out:
[`00_compliance_status.md`](00_compliance_status.md) §4.6.

---

## 5. Decisions we have already taken

Recorded so they are not re-opened, and because two of them change what we are asking of you.

- **Self-hosted inference is parked.** We had planned to move inference onto a rented GPU instance under
  the agency's own contract, keeping grievance text inside contracted infrastructure. **There is no owner
  for the run costs, so we are not starting it** — the failure mode that killed Rwanda's Babyl, better
  avoided by not starting than discovered later. **The consequence: a hosted third-party provider is the
  steady state, not a transition**, so grievance text crosses a border indefinitely. That does not change
  the indicator-4 answer — a hosted open-weights provider is still an open alternative — but it turns the
  privacy exposure from transitional into permanent, and makes redaction the only remaining control rather
  than defence in depth.
- ⭐ **And when we costed it, the conclusion changed.** The crossover volume at which a dedicated GPU
  becomes cheaper than hosted inference is **40,000 to 780,000 grievances per month** across every price
  assumption we tried. Two pilot districts handle grievances in the **tens** per month; all 77 districts of
  Nepal at 100 each would be **7,700**. Hosted inference is cheaper at every volume this system will ever
  see, by three to four orders of magnitude, and **volume growth does not close the gap** — classification
  is one request per grievance, not one per conversational turn, so a dedicated GPU would sit idle almost
  always, and idle GPU time is the entire cost. **So self-hosting is not a cost decision at all. It is a
  data-sovereignty decision with a price attached**, and presenting it as a break-even would have implied
  that waiting for volume eventually justifies it. It does not.
- **Production will run the open configuration**, on cost grounds, with the commercial provider kept as a
  configurable fallback if users report quality problems. **This is more than indicator 4 requires**, and
  we would lead with it: the Standard asks for demonstrated replaceability; we intend to run the
  replacement. ⚠ It **cannot happen until an open model is chosen**, which is the measurement in §2.
- **The repository default stays proprietary until then, deliberately.** An open base URL combined with
  proprietary model ids is a repository that cannot serve a single request on a fresh clone — weaker
  evidence than an honest default, not stronger.
- **Redaction happens at transmission**, not before storage — see Q12.
- **Person names are redacted, imperfectly, and we would rather quantify that than round it either way.**
  What ships: honorific and role-title triggers (`Er.`, Engineer, overseer, contractor, ward chairperson,
  `श्री`) which catch the *named official* — the sharpest exposure, because that person never consented to
  anything; a Nepali family-name (*thar*) gazetteer, tractable because surnames are a comparatively closed
  set; and self-identification patterns (*"my name is …"*, `मेरो नाम … हो`), which catch the opening line
  the voice channel all but guarantees. **What still gets through:** a name with no title, no recognisable
  surname and no self-identification frame — *"the man operating the roller"*, named in passing three
  sentences later. **We will publish the measured residual rather than describe it.** Higher recall needs
  the model in Q13; the rule layer is not a placeholder for it, it is the part that works without an
  unlicensed dependency.
- **⚠ Three storage-layer defects the privacy assessment found — now fixed, and we are telling you about
  them rather than quietly leaving them out.** Writing the data-flow diagram against the **code**, instead
  of against our own existing privacy specs, surfaced all three; none appeared in any spec. They shared a
  root cause worth stating: every privacy document described the *architecture* — which schema owns what,
  who may decrypt, where the boundary sits — and all of that was accurate. **None described what the
  storage layer does when a write fails.**
  **(a) Encryption at rest failed open** — when the key was absent, or the encryption call raised, the
  error was logged and the write proceeded in plaintext, so a degraded deployment silently stored
  complainant PII in the clear and nothing downstream could tell. ✅ It now **fails closed**: the write is
  abandoned, and the deliberate keyless developer mode warns once per process instead of never.
  **(b) The search-token hashes were unsalted SHA-256** of phone, email, name and address — Nepal's mobile
  number space is enumerable in seconds, so the phone hash was reversible and those columns were personal
  data, not pseudonyms. ✅ Now HMAC-keyed, which keeps the lookup and removes the reversibility; existing
  tokens must be re-derived and a migration script ships with it.
  **(c) Backups were unencrypted by default** — contact columns stayed ciphertext inside the dump, but the
  narrative, every officer note and every voice recording did not. ✅ The script now discards an
  unencryptable dump *and* the uploads archive unless an explicit override says otherwise.
  **We would rather you saw the method that finds this class of thing than a document that never had any.**
- **⭐ A deployment-credential defect found and closed, and the way it broke is the interesting part.**
  Every service that talks to the database set `POSTGRES_PASSWORD` in its own compose `environment:` block —
  19 sites once Keycloak's own copy is counted — and Compose's `environment:` **overrides `env_file:`**. So the
  strong, encrypted password was **read by nothing**, and every deployed database ran on a literal committed in
  the clear. Three things each looked like the reassurance and none was: the environment file held a strong
  password; a promotion gate asserted the password was not the default and **passed, because it read the inert
  copy**; and an earlier sprint found half of it and closed it as a test-fixture problem. The literals are gone,
  the credential is **rotated**, it is removed from all six tracked files that carried it, and the gate now checks
  what a **container** resolves — verified by reintroducing the defect and watching it go red.
  ⭐ **The part worth generalising:** fixing it *inverted* a test bootstrap that had hardcoded the credential
  deliberately — while the environment file was dead config, honouring it was the one way host tests could
  disagree with the database. Making the file live turned that safeguard into the bug it was written to prevent.
  **A control that encodes a fact about the system has to move when the fact does**, and only a test will tell
  you it has stopped being true.
- **⭐ And a second credential, found by asking a different question of the same repository.** Having
  fixed the one above, we scanned for the converse: not *"is the variable read?"* but *"is the value
  already public?"* — hashing every live credential against every blob ever committed. It found the
  **Redis broker password**, live, sitting in nine now-deleted files in a repository that has been
  public since January 2025. Rotated.
  ⭐ **The pair is the lesson, and we would offer it as one:** the database password was an **inert
  variable carrying a correct value**; the broker password was a **live variable carrying an exposed
  value**. Each audit is blind to the other's failure, and our first audit had explicitly cleared Redis
  — correctly, on the only question it asked.
  **What the scan cleared matters more than what it caught.** The database encryption key, the mail
  password, and every model-provider and cloud key were never committed. ⚠ One exposure cannot be
  closed and we would rather state it than let you find it: a maintainer's email address is in the
  history because it is the **git author on 865 of the repository's 1,018 commits**. It is the username
  half of a mail credential whose password is clean, and no amount of file editing removes it.
  **Our position on purging history: we recommend against it, and the reasoning is the point.** With
  both credentials rotated, nothing left in the history opens a live door — and a rewrite could not
  un-publish a repository that has been public for over a year. **Rotation is what removes risk;
  purging is what removes evidence of it.** Doing them in the wrong order buys the appearance of
  safety while the credential still works.
- **A licence-drift finding we surfaced ourselves and fixed.** Our Redis image tag pinned only the major
  version, so it silently followed upstream onto a non-OSI licence line — nobody edited the file; the
  licence moved underneath it. Now pinned to a minor and taken under AGPLv3. **The class of problem is more
  interesting than the instance:** a floating tag is a licence you did not choose, so our dependency audit
  now includes a pin-drift check.

---

## 6. Dependency inventory

**There is no proprietary component anywhere in the runtime stack**, and no dependency in any tree carries
an unknown, unparseable or non-OSI licence. The figures below come from a scan run **inside the running
containers** against the resolved trees — not from reading manifests. The full per-package listing, with a
written disposition for every entry carrying conditions beyond attribution, is
[`dependency-licenses.md`](dependency-licenses.md). ⚠ The scheduled re-run that keeps it fresh is
**built but not yet deployed** (§2).

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
| **Model client** | **`openai` — the only ML dependency, and the *client* is open; the service it calls is the subject of §4** | Apache-2.0 |

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
| Commercial LLM API | The five live model calls | **The subject of §4** — one environment variable |
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
