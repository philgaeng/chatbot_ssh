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

Grouped by what the answer unblocks. 🔴 = we cannot finish without it. Full text in
[`00_compliance_status.md`](00_compliance_status.md) §5.

### Ownership, licensing and process

- **Q1 🔴 — Does ADB have a standing IP position for software developed under a loan-financed engagement,
  or is it case by case?** Who is the right signatory, and what is a realistic timeline? This blocks the
  copyright holder, the identification of the data controller, and the submission itself. **It is the
  single most valuable thing you can help us with.** ⚠ One process note: the project owner has written to
  *you* about this, which is not the ADB OGC channel an IP determination requires, and we do not know who
  opens that channel.
- **Q2 — Are there precedents?** If ADB has nominated software as a DPG before, can we reuse the shape of
  that ownership determination rather than starting from a blank page?
- **Q3 — Who submits?** Does ADB nominate, or do we self-submit with ADB endorsement? Does DOR need to be
  a party, given that production runs on DOR infrastructure?
- **Q4 — Do you have any objection to Apache-2.0?** The choice was referred to you. We picked it over MIT
  for the express patent grant, which matters when a government adopts the code and other country teams
  fork it, and it is already applied across 593 files. Since indicator 2 fails outright with *no* licence,
  **saying "no objection" is the cheapest unblock on this list.**
- **Q5 — Sequencing.** Can we begin the assessment with the model choice unmade and the CI evidence not
  yet green, or should we complete the engineering first? A rough timeline would help us schedule against
  it.

### Indicator 4 for AI systems — the substance

- **Q6 🔴 — Is our reading correct?** We read the Standard as requiring us to demonstrate that the closed
  component *could* be replaced with minimal configuration change — not that we must run open models in
  production. **We intend to run them anyway** (§5), so we expect to satisfy the stricter reading too. We
  would still like the answer, because it determines how much benchmark evidence the submission needs.
- **Q7 — How does the DPGA treat "open weight" models whose licences are not OSI-approved?** We filter for
  Apache-2.0 or MIT to be safe. That excludes Gemma, Llama and — the one that hurts — `aya-expanse-32b`,
  which is purpose-built for multilingual coverage and exactly the right size, but is CC-BY-NC and
  therefore unusable in a government deployment **however you answer**. The filter **may be costing real
  accuracy on Nepali.** How much does it matter?
- **Q8 — How does the DPGA treat a *partial* open alternative?** Our open configuration runs the text
  paths and **cannot transcribe at all** — the router serves no OpenAI-compatible audio route. Is "open
  for text, absent for speech, documented" acceptable? And separately: if open-weights speech recognition
  works for Nepali at a materially higher error rate, is "functional, with documented degradation"
  acceptable, or does the alternative need parity?
- **Q9 — The "data" limb of the AI questionnaire.** We do no training or fine-tuning; every call is
  zero-shot prompting against a taxonomy we author. We **have** published a 105-item labelled evaluation
  set under CC0-1.0. Is that what the data limb wants, and do you also expect the prompt templates?
- **Q10 — Three dependency-licence readings.** (a) We run Redis as a network service behind a process
  boundary, not as a linked library, and take Redis 8 under **AGPLv3** — the one OSI-approved option of its
  three. **Does AGPLv3 anywhere in the stack cause a problem** for you, for the assessment, or in ADB/DOR
  procurement? If so we will move to Valkey (BSD-3-Clause); we prefer not to pay the switching cost
  speculatively. (b) `psycopg2-binary`'s LGPL-with-linking-exception. (c) Two transitive LGPL libraries,
  both unmodified and dynamically loaded.
- **Q11 — How much benchmark evidence does the submission actually require?** If a smaller published table
  on a synthetic set is sufficient, we would rather scope to that than measure expansively and publish
  late.

### Privacy and safeguarding

- **Q12 — Redaction posture.** We redact **at transmission, not before storage**: the officer handling a
  case needs to see which official was named, and for a GRM, complaints naming officials are a large share
  of the useful ones. **Does the DPGA or ADB safeguards policy take a contrary position?** If PII must not
  be stored in free text at all, that is a much larger change and we want to know now.
- **Q13 — The NER recursion, and a possible contribution.** Person-name detection in Nepali needs an ML
  model, and the most accurate one we can find has **no licence stated** on its model card — shipping it
  would swap one closed dependency for another inside the submission meant to remove one. Our intended
  answer is to fine-tune our own on an openly-licensed corpus, **release it openly**, and run it as a
  standalone anonymiser service reusable by any country programme where in-country self-hosting is
  impossible. **Would the DPGA see that as a positive, and is there ADB appetite to fund it?**
- **Q14 🔴 — The provider's terms, and whether a DPA is required.** The router's no-storage commitment
  covers the **router**, not the partner company that runs the model; the Terms reference no DPA; and the
  default routing policy picks a different third-party processor **per request**. We intend to **pin a
  single named provider** so the processor and its policy are knowable. **Does ADB — or the DPGA — expect a
  signed data-processing agreement** with that provider before complainant narratives are routed through
  it? If the answer is yes and no provider will sign one, that reopens self-hosting — the most expensive
  consequence on this list.
- **Q15 — Who should review the privacy assessment?** It is drafted, thorough on the *system*, and
  explicitly a lay reading of the *law* — every statutory reference is marked unverified and no lawyer has
  read it. **Does the DPGA expect a legally-reviewed assessment, or is a documented, honest engineering
  assessment sufficient?** If the former, who pays for that review, and does ADB have counsel who can do
  it?
- **Q16 — Hosting jurisdiction.** Largely moot for the agency's own infrastructure while self-hosting is
  parked, but the **provider's** jurisdiction is now a permanent question rather than a transitional one,
  and pinning a provider does not make the location of execution knowable. Does the DPGA have a position
  on cross-border processing for a national-government DPG beyond compliance with local law?

### Scope, sustainability and funding

- **Q17 — Which project-hygiene artefacts are actually required** versus merely liked? We have shipped
  `SECURITY`, `CONTRIBUTING`, `CODE_OF_CONDUCT`, issue and PR templates. We have **deliberately not**
  written a governance model or a release/versioning policy, because both describe commitments nobody has
  agreed to on a project whose IP ownership is formally open. Which does the DPGA require?
- **Q18 — Sustainability, and it has already bitten us twice.** Does the assessment look at who funds and
  operates the system after the pilot? We believe it should, and we are living the answer: **we parked
  self-hosted inference precisely because no run-cost owner exists**, and that gate worked. **Inference for
  the benchmark and the demo months is funded** — a few hundred US dollars, paid personally by the project
  owner and to be expensed, covering the pilot's own traffic as well as the model sweep — so the evidence
  is no longer blocked. ⚠ **But that envelope is time-boxed and the CI job is not.** The
  platform-independence job is the only recurring inference cost in the plan and **who pays for it after
  the demo months is unresolved.** We would like to use the DPG process as leverage for a named budget
  line.
- **Q19 — Is there anything in the current Standard revision, or the AI-systems guidance specifically,
  that we have missed** by reading the published Standard and questionnaire?

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

### Three things worth being candid about

**It was a configuration refactor, not a rewrite — and it is done.** The client was constructed with no
base-URL override; the SDK accepts one and the major open-weights serving stacks expose a compatible API.
That is exactly the "minimal configuration changes" the Standard asks about. **The precedent was already
inside our own codebase:** the SMS layer runs two providers behind one interface selected by an
environment variable (AWS SNS internationally, the Government of Nepal gateway for Nepal). Having done it
once was the best evidence it was a refactor; having now done it twice, `diff .env.openai .env.open` is
the evidence.

**The AI paths are fail-soft, which lowers the switching risk.** Intake writes the grievance to PostgreSQL
*before* any model call; classification runs as a retrying background task with explicit failure states;
the chatbot waits on a bounded deadline. **A grievance is never lost because a model was unavailable** —
so a slower model degrades throughput, not intake.

**⚠ The CI job has never run in CI.** It is written, it is pinned by a test file of its own, and it
returns 4 passed / 1 xfailed / exit 0 when run by hand against an Apache-2.0 open-weights model. It has
not executed on the runner because the provider account was rate-limited when it was written. **A job
that exists, never runs, and is cited as evidence is not acceptable**, and the workflow header says so in
those words. If the per-commit cadence proves unaffordable the documented fallback is nightly plus release
tags, **declared on the badge** rather than quietly.

Two properties of that job are worth naming, because each is a way it could have become decoration.
Model ids come from repository variables rather than literals, and a test asserts **the endpoint the
tests reached is the one the registry names** — which catches the most embarrassing false green available
here, a job that passes against the commercial provider while reporting that open weights work. And live
tests *skip* on an account-level refusal, because a job that reddens on someone else's billing teaches
everyone to ignore it — ⚠ but a run where everything skipped would exit 0 and show a green tick having
tested nothing, so **the job also fails when nothing passed.** Neither control is safe alone.

### What the measurements found, including two things we were not looking for

The closed baseline — the model production runs today — scores **F1 0.762** on multi-label
classification over 105 authored items, with p99 latency inside the 30-second interactive budget.
⚠ Authored text is cleaner than real complaints, so every figure is an **upper bound** on production
accuracy, not an estimate of it.

⭐ **The classifier was inventing categories on 17% of grievances, and storing them.** Not as noise — as
a coherent fictional `Road Hazard - *` family, stored, **shown to the complainant as the system's
understanding of their own complaint**, and synced to ticketing where it matched no filter and no
priority lookup. Then the open model invented **the same category**: two vendors, two architectures, one
fabricated label. That made it a **taxonomy** finding rather than a model one — the catalogue had no
road-hazard grouping, and independent models kept reaching for the category a road project would expect
to exist. Adding six categories and cutting the prompt took invention from **18 items to 4**, and dropped
p99 latency from 40.6 s to 24.5 s, inside the budget for the first time.

⚠ **The single most important number we do not have is SEAH detection recall, and it decides a model
choice with a safeguarding consequence.** The current model flags **5 of 8** items authored as the hard
case — gendered complaints that are emphatically not harassment: no separate toilet for women workers,
unequal pay for the same work, refused work for being a woman. **The SEAH route is access-isolated**, so
those do not get a wrong label; they **leave the queue of the people who would have fixed them.** The open
candidate flags **nothing at all** — which is either better calibration or a detector that always says no,
and **nothing in the repository can tell those apart**, because the committed benchmark contains no
harassment reports. That is by decision, not omission: three hundred realistic Nepali harassment
complaints sitting in a public repository will be read as leaked case data by somebody, regardless of how
the file is labelled. The positives are held by the project owner and the harness **refuses a dataset path
inside the repository**.

**So neither model may be selected on the evidence that exists**, and the open model's perfect
false-alarm rate must not appear in a submission as an improvement. Detail and the confusion matrix are in
[`model-benchmarks.md`](model-benchmarks.md).

⚠ **And one candidate disqualified itself for a reason that is not about quality.** `Apertus-70B` — the
strongest *DPG story* on our shortlist, fully open weights **and** open training data, built for
low-resource language coverage — replied to the capability probe with *"Your request was blocked"*, in
0.42 seconds. The prompt was our flagship benchmark item: road dust entering a house, children falling
ill. **This system's entire input distribution is human harm**, and dust and sick children is the mildest
end of it. A filter tuned to refuse discussion of harm to children refuses hardest on the reports that
matter most — and because sensitive-content detection fails open by design, a harassment report that
filter blocks would be silently handled as an ordinary complaint.

### Where the residual goes, and under whose terms

Redaction is imperfect by construction, so the honest question is *what happens to the text that gets
through*. With self-hosting parked (§5) that text goes to a third party permanently, so we read the
provider's terms rather than assuming them. **What we found is worth your view (Q14):**

**Two framing points first, because both are easy to get wrong.** Moving to open weights answers
indicator 4 and **does nothing for indicator 7** — openness is a *licensing* property, not a *privacy*
one, and an open model served by a third party carries exactly the same data-flow risk as a commercial one
served by its vendor. **And the legal trigger was never model training:** under Nepal's Individual Privacy
Act 2018 and GDPR-style regimes alike, sending personal data to a third party **is a disclosure and a
cross-border transfer — the event is the transmission itself.** Whether the recipient stores it, learns
from it, or discards it a microsecond later does not change that a transfer occurred and needs a lawful
basis. Non-retention is a mitigation, and a valuable one; it is not an answer.

**Hugging Face's own commitments are substantive, and we cite them**
([Inference Providers → Security & Compliance](https://huggingface.co/docs/inference-providers/en/security)):
no user data stored for training; no request body or response stored when routing; debugging logs for up
to 30 days with no user data or tokens; TLS in transit; and the Hub, of which Inference Providers is a
feature, is **SOC 2 Type 2 certified.**

**⚠ Then the sentence that matters, and it is theirs:** *"External providers are responsible for their own
security measures, so please refer to their respective security policies."* The no-storage commitment
covers the **router**, not the company that actually runs the model.

- **By default the processor is not fixed.** Requests are proxied to third-party partners — Cerebras,
  Groq, Together, Fireworks, Novita, DeepInfra, Replicate, Scaleway, OVHcloud and others — with the
  default policy selecting *the fastest available per request*. **For a government privacy assessment,
  "we cannot name which company processed this citizen's grievance" is a finding, not a footnote.**
- **The Terms of Service reference no DPA**, and frame confidentiality around private repositories rather
  than inference traffic. For a router architecture a DPA is awkward by construction: you would need one
  from Hugging Face *and* from each downstream provider.

**Our engineering response, which we would like sanity-checked:** **pin the provider** in the model path
rather than use automatic routing, turning an unknowable sub-processor chain into one named company whose
policy can be read, cited and made the subject of a DPA request. **Production pins; CI keeps automatic
routing**, because CI sends only synthetic benchmark data.

**What remains even with a provider pinned**, and belongs in the data-flow diagram rather than being
discovered later: the downstream provider's **own retention**; the **jurisdiction of execution**, which
pinning does not fix; and **prompt caching**, which several providers use and which means cached content
sits somewhere briefly. Any submission text naming a single destination country for the model calls would
be a claim we cannot support.

⚠ **One thing we will not overstate.** The router's value for indicator 4 is independence from *any single
vendor*: our chosen model is offered by eight partners and its larger sibling by eleven. **But only one
route has actually been exercised.** The others are OpenAI-compatible and the code needs no change to use
them, but each needs its own account and none has been probed. The fan-out count is not a measurement.

### ⚠ One precision we want right before anyone briefs the ministry

**What redaction produces is pseudonymised text, not anonymised text**, and the difference is not
pedantry. Because we keep the mapping that turns a placeholder back into a name, the text **remains
personal data**. Redaction lowers the risk profile; it does not take the data out of scope.

**We will not let anyone tell the agency the grievances are "anonymised."** That claim would not survive
scrutiny, and an overstatement there would discredit every other claim we make.

**What we can say, accurately and strongly:** *only pseudonymised text crosses the border, and the
re-identification key never leaves Nepal.* Pseudonymisation is an explicitly recognised safeguard, and
that is a genuinely strong position. ⚠ The second clause is a promise about **deployment, not about code**,
and it is quietly easy to void — one careless serialisation putting the mapping into the same task payload
or log line as the text, and the key has travelled with the ciphertext. So in-country residency and
storage separation are **acceptance criteria with a test**, not implementation notes. That mapping is
arguably the most concentrated personal data in the system: identifiers with nothing else attached.

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
