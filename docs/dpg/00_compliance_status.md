# DPG compliance status — Nepal GRM platform

> **Purpose.** An indicator-by-indicator self-assessment against the
> [DPG Standard](https://www.digitalpublicgoods.net/standard), written for ADB's Digital Public Goods
> consultant. It states where this platform complies, where it does not, and what we need from the
> consultant before we can finish the work or submit.
>
> **Audience:** ADB DPG consultant + project team · **Date:** 2026-08-23 ·
> **State of the code:** branch `dpg/sprint2-open-models`, merged into `integration/stage`.
>
> **Companion documents.** The full evidence pack lives beside this file:
> [`privacy-assessment.md`](privacy-assessment.md) (13 data-flow legs, 17 findings),
> [`dependency-licenses.md`](dependency-licenses.md) (153 packages, generated),
> [`open-model-configuration.md`](open-model-configuration.md) (how to run this system on open
> weights), [`model-benchmarks.md`](model-benchmarks.md) (what the models actually score), and
> [`vllm-deployment.md`](vllm-deployment.md) (self-hosting, designed and costed). The engineering
> plan behind them is [`docs/sprints/2026-08-llm/`](../sprints/2026-08-llm/README.md) — 31 tickets
> across four sub-sprints, of which Sprints 0, 1 and 2 have landed.
>
> **A summary of this document, written to be read before a meeting**, is
> [`01_consultant_briefing.md`](01_consultant_briefing.md).

---

## How to read this

This is not a compliance pitch. Two of the nine indicators have real gaps, one of them cannot be
closed by anyone on the engineering team, and the AI-specific reading of indicator 4 is the substance
of the meeting. The honest version is more useful to us than the flattering one.

**The short version:**

- **The code and its dependency tree are in good shape.** There is no proprietary component anywhere
  in the runtime stack — no closed database, no closed identity provider, no closed framework, no
  vendored SDK we could not replace. A generated audit over 153 packages in four dependency sets
  returns **zero** unknown and **zero** non-OSI licences.
- **The AI layer was our one genuine closed dependency, and the mechanism that removes it is now
  built and running.** Every model this system calls is a configuration value: nine call sites across
  two independent subsystems resolve through one registry, and the product's own code paths have been
  executed live against an open-weights provider. **What is not done is the *choice*** — the
  comparative benchmark that would let us name an open model is unfinished, so the repository default
  is still the proprietary configuration. §4 is entirely about this, clause by clause.
- **Two items need people, not code:** the IP-ownership determination (indicator 3) and a legal review
  of the privacy assessment (indicator 7).
- **Grievance text still leaves Nepal unredacted on every model call**, and because self-hosted
  inference is parked for want of a funded operator, that egress is **permanent rather than
  transitional**. Redaction — Sprint 3, not yet started — is therefore the only remaining control
  rather than a defence in depth.
- **Nothing real has been processed yet.** Every grievance record in every environment is AI-generated
  seed data or a dummy complaint filed during a demo. That makes every exposure below **prospective**,
  and it puts the redaction work in the window where it is a go-live precondition rather than a
  remediation.

---

## 1. Scorecard

| # | Indicator | Status | What is missing |
|---|---|---|---|
| 1 | Relevance to SDGs | ✅ **Compliant** | Needs writing up, not building. SDG 16.6 / 16.10, SDG 9.1 |
| 2 | Use of an approved open licence | 🟢 **Closed, provisionally** | `LICENSE` (Apache-2.0), `NOTICE`, an SPDX header on **593 source files** maintained by a script and pinned by a test, and a **generated** audit over 153 packages. Two things stay provisional: the **licence text** is delegated to the consultant (**Q4**), and the **copyright holder** is blank pending indicator 3 — `NOTICE` says so rather than guessing |
| 3 | Clear ownership | 🔴 **Blocked — external** | A written IP determination from ADB. **Nobody on this project can resolve it.** It is the only thing standing between us and a complete licensing story |
| 4 | Platform independence | 🟡 **Mechanism built and executing; the model choice is not made** | Every model is a configuration value across both LLM surfaces, proven by tests and by a live CI job. **But** the repository default is still proprietary and **no open model has been selected** — the comparative benchmark is unfinished. ⚠ The open provider serves no speech endpoint, which costs nothing today because automatic transcription is switched off on cost grounds and is not expected to be funded. §4 states this clause by clause |
| 5 | Documentation | ✅ **Compliant, strong** | A 365-file spec tree, a Docker runbook covering 13 services, OpenAPI on both APIs, and a portable engineering starter kit another country team could reuse |
| 6 | Mechanism for data extraction | ✅ **Compliant** | PostgreSQL, version-controlled schema in three independent migration streams, XLSX + PDF exports, REST APIs. `pg_dump` gives a complete portable extract |
| 7 | Privacy & applicable laws | 🟠 **Partial** | The assessment and the data-flow diagram exist and three storage-layer defects they found are fixed. **Outstanding:** unredacted egress to a third-party model provider, no deletion capability anywhere, no breach procedure, and no legal review of the assessment (**Q15**) |
| 8 | Standards & best practices | ✅ **Compliant** | OpenAPI, OIDC/PKCE via self-hosted Keycloak, Alembic-migrated schema, architectural invariants pinned by tests, and the project-hygiene set at the repo root. Governance model and a release/versioning policy are deliberately deferred pending **Q17** |
| 9 | Do no harm by design | 🟢 **Mostly compliant** | Access control, audit log, SEAH isolation and anonymous intake are built, and content detection has two independent paths. **Outstanding:** retention/breach policy, third-party-PII redaction, and a measured SEAH detector |

**Two blockers, one of them ours.** Indicator 3 is a signature we have to ask for. Indicator 4 is
engineering that is mostly done and whose last step is a measurement, not a refactor.

---

## 2. Where the platform already complies

### 2.1 Indicator 1 — Relevance to SDGs ✅

The platform is a Grievance Redress Mechanism for ADB-financed road infrastructure in Nepal
(KL Road / Kakarbhitta–Laukahi, ADB Loan 52097-003). It gives affected people a channel to raise
grievances in Nepali, by chat or voice, and gives implementing agencies a workflow with enforced
service-level deadlines and an escalation ladder up to a Grievance Redress Committee.

- **SDG 16.6** — effective, accountable and transparent institutions
- **SDG 16.10** — public access to information
- **SDG 9.1** — sustainable infrastructure with attention to affected populations

It also implements ADB's own Accountability Mechanism expectations, and carries a dedicated,
access-isolated SEAH (sexual exploitation, abuse and harassment) intake stream. **This indicator needs
a page of writing, not a change to the product.**

### 2.2 Indicator 2 — Open licensing 🟢

**(a) The repository's own licence.** `LICENSE` is Apache-2.0, chosen over MIT for its express patent
grant, which matters when a government adopts the code and other country teams fork it. `NOTICE` sits
beside it and **names no copyright holder**, carrying an explicit `⚠ PENDING IP DETERMINATION` marker
instead of a guess — see indicator 3. **593 in-scope source files carry an SPDX header**, applied by a
committed, idempotent script (`scripts/ops/add_spdx_headers.py`) and held in place by a test that
imports the script's own scope definition rather than restating it, so coverage cannot decay the first
week someone adds a module.

Two things about this are provisional and we would rather say so:

- **The licence text is delegated to you (Q4).** We had treated Apache-2.0 as decided; the project
  owner has referred the choice to the consultant. Since indicator 2 fails outright with *no* licence,
  **if you have no objection to Apache-2.0, saying so is the cheapest unblock on this list.**
- **The copyright holder is blocked on indicator 3**, and will stay blank until ADB rules.

**(b) The dependency tree.** This is our strongest card. **There is no proprietary component anywhere
in the runtime stack** — every layer is a permissively-licensed open source project that a third party
could self-host with no commercial relationship with anyone.

| Layer | What it is | Licence |
|---|---|---|
| Web frameworks | FastAPI, Uvicorn, Starlette, Pydantic v2 | MIT / BSD-3-Clause |
| Database | PostgreSQL 15 | PostgreSQL Licence (OSI) |
| ORM & migrations | SQLAlchemy 2, Alembic (three independent streams) | MIT |
| Task queue | Celery 5.5, Flower | BSD-3-Clause |
| Cache / broker | Redis 8.10 (minor pinned) | **AGPLv3 at our election** — Redis 8 is tri-licensed RSALv2 / SSPLv1 / AGPLv3; only AGPLv3 is OSI-approved. See §3.2 |
| Identity | Keycloak 26, self-hosted (OIDC + PKCE) | Apache-2.0 |
| Reverse proxy | nginx stable | BSD-2-Clause |
| Officer frontend | Next.js 16, React 19, Tailwind v4, lucide-react | MIT / ISC |
| Reports & documents | openpyxl (XLSX), ReportLab (PDF) | MIT / BSD-3-Clause |
| Images | pyvips / libvips | MIT / LGPL-2.1 (separate process, dynamic link) |
| Chatbot state machine | This project's own code and its own orchestrator; `rasa-sdk` (Apache-2.0) supplies the action/form base classes it drives — **no Rasa server, no Rasa NLU, no TensorFlow** | Apache-2.0 |
| Container orchestration | Docker Compose | Apache-2.0 |

**The audit is generated, not asserted.** [`dependency-licenses.md`](dependency-licenses.md) was
produced **inside the running containers**, against the resolved trees:

| Set | Packages | Non-OSI | Unknown |
|---|---|---|---|
| Python — declared in the two manifests | 35 | 0 | 0 |
| Python — transitive | 98 | 0 | 0 |
| npm — production tree | 16 | 0 | 0 |
| Container images | 4 | 0 | 0 |
| **Total** | **153** | **0** | **0** |

⚠ **On how fresh that stays, because the honest answer is weaker than "nightly".** A licence scan
*is* scheduled — `ops/security.py` runs it at 01:50 daily beside a `pip-audit` CVE scan, writing to
`ops.dependency_findings`. But **the `ops` container is not deployed to either server yet**, so today
it runs only in a development stack, on a machine that is on when it is on. The mechanism exists and
is committed; the *guarantee* does not, and will not until `ops` ships. We would rather say that than
claim a nightly job a reviewer cannot point at — the same standard §4.5 applies to the CI job.

Reading the manifests instead would have missed 98 of the 133 Python packages, and with them the
three copyleft findings in §3.2 — **none of which is anyone's declared dependency.** A licence
obligation does not care how a package arrived.

Two points a reviewer usually asks about:

- **Identity is self-hosted, not federated to a vendor.** An earlier plan used AWS Cognito; the build
  moved to Keycloak. That decision was made on other grounds, but it removes what would have been a
  hard indicator-4 dependency at the authentication layer
  ([`16_auth_keycloak.md`](../deployment/16_auth_keycloak.md)).
- **There is no Rasa server and no TensorFlow.** The conversational state machine is this project's
  own code, driven by this project's own orchestrator. ⚠ **`rasa-sdk` (Apache-2.0) is more than a type
  shim, and we would rather be precise than tidy:** 49 modules import it, `BaseFormValidationAction`
  **inherits** `FormValidationAction`, and the orchestrator calls `action.run(dispatcher, tracker,
  domain)` — so its form-validation dispatch is executed, not merely annotated against. What is
  genuinely absent is the part that carries the licence weight: **no Rasa server, no Rasa NLU, no
  TensorFlow** — verified against the resolved tree. An earlier assessment flagged Rasa's licence as a
  week-one emergency; `rasa-sdk` is Apache-2.0, so it is a non-issue either way.

### 2.3 Indicator 5 — Documentation ✅

- **`docs/`** — a 365-file structured spec tree with per-domain indices
  ([`docs/README.md`](../README.md)): deployment runbooks, service contracts, ticketing product specs,
  chatbot architecture, the SEAH privacy model, and an
  [`engineering/`](../engineering/00_engineering_index.md) set documenting *how* the system is built
  (database rules, service-layer patterns, API conventions, testing pyramid, documentation lifecycle).
- **A portable starter kit** ([`docs/_starter_kit/`](../_starter_kit/README.md)) — those engineering
  standards, the design system and the copy guide, stripped of anything project-specific, so another
  country team can reuse the method rather than only the code. This is unusually good indicator-5
  evidence and we would point at it explicitly.
- **[`DOCKER.md`](../deployment/DOCKER.md)** — a full build / migrate / seed / debug runbook. The
  whole stack comes up with Compose; the service table is **13 services, verified against
  `docker compose config --services`** rather than remembered.
- **OpenAPI** served by both FastAPI applications.
- **CI with five gates**: backend tests against real Postgres and Redis with all three migration
  streams applied; UI type-check, lint, unit and build; webchat tests; a documentation link checker;
  and the platform-independence job described in §4.5.

### 2.4 Indicator 6 — Data extraction ✅

- **All data in PostgreSQL**, no proprietary store. The schema is explicit and version-controlled
  through three separately-owned Alembic streams (`public.*` chatbot, `ticketing.*`, `ops.*`), which
  never share ownership of a table.
- **Non-proprietary exports already built:** quarterly XLSX reports, complainant case-closure PDFs,
  and REST APIs over the whole domain.
- **No lock-in on file storage** — attachments sit on the filesystem under a documented archive-tiering
  policy ([`ARCHIVING_AND_RETENTION.md`](../ARCHIVING_AND_RETENTION.md)), not in a vendor bucket with a
  proprietary layout.
- `pg_dump` produces a complete, portable extract. Nothing about the data model requires this codebase
  to read it.

### 2.5 Indicator 8 — Standards & best practices ✅

- **OpenAPI** for both HTTP surfaces; **OpenID Connect with PKCE** via Keycloak, with JWT verification
  against JWKS.
- **UTC timestamps** with timezone throughout; UUID4 primary keys; Bikram Sambat dates presented in
  the UI where users expect them.
- **Architectural invariants pinned by tests.** The boundary policy that stops complainant PII being
  copied into the ticketing schema is enforced by a test that *parses the architecture document* and
  fails when code and document disagree (`tests/ticketing/test_boundary_policy.py`,
  `test_pii_boundary.py`). We think this is worth showing: it makes a "do no harm" claim checkable
  rather than aspirational. The same pattern now guards the LLM registry, the SPDX coverage, the CI
  job's own properties, and every `file.py:line` citation in this evidence pack.
- **Project hygiene at the repo root:** `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`,
  `.github/ISSUE_TEMPLATE/` with blank issues disabled and a security redirect, and a PR template.
  **`SECURITY.md` is the one that is not boilerplate here.** This platform holds SEAH disclosures, so a
  disclosure route that tells a finder to open a public GitHub issue is the wrong answer: it names a
  private channel, a recipient, a response window, and an explicit scope boundary — the platform is in
  scope, the grievances are not.
- **Secrets are encrypted at rest in the repository.** SOPS with `age` recipients encrypts
  `secrets.enc.env`; the non-secret half stays plaintext and diffable in `.env.shared`; and `env.local`
  is a generated artefact (`make env-local`) rather than a file each developer maintains by hand.
  **Encryption alone proves nothing about what is already public**, so every live credential was also
  hashed against every blob ever committed — see §3.5 for what that found and what it cleared.
- **Deliberately deferred:** a governance model and a release/versioning policy. Both describe
  commitments nobody has agreed to, on a project whose IP ownership is formally open, so they wait on
  **Q17** ([followup](../sprints/2026-08-llm/followups/governance-and-versioning-policy.md)).

---

## 3. Gaps we know how to close ourselves

### 3.1 Indicator 3 — Ownership 🔴 **the hard blocker**

Indicator 3 is categorical: a DPG must have clear, documented ownership. Parts of this platform were
developed in the context of an ADB-financed engagement. **If the IP vests in ADB, or is jointly held,
it may not be ours to license.** No amount of engineering resolves this — it needs a written
determination from ADB's Office of the General Counsel, and it has the longest lead time of anything
on this list.

It blocks: the copyright holder in `LICENSE` and `NOTICE`, the formal identification of the data
controller in the privacy assessment, and the submission itself. It blocks **no code work**, which is
why the engineering has proceeded in parallel.

⚠ **One process note we would rather flag than have discovered.** The project owner has written to the
DPG consultant about this. **That is not the ADB OGC channel an IP determination requires**, and we do
not know who opens that channel. **This is the single most valuable thing the consultant can help us
with** — Q1 to Q3.

### 3.2 Three dependency-licence readings we would like confirmed 🟡

Ten packages across the four sets carry conditions beyond simple attribution; all ten are dispositioned
in [`dependency-licenses.md`](dependency-licenses.md). Three are worth the consultant's eye (**Q10**):

**(a) Redis 8.10, taken under AGPLv3.** Redis 7.2 and earlier are BSD-3-Clause; **Redis 7.4 and later
are RSALv2 / SSPLv1**, neither OSI-approved. Our compose file pinned `redis:7` — the major only — so
the tag silently followed upstream onto that line. **Nobody edited the file; the licence moved
underneath it.** Redis 8 is tri-licensed RSALv2 *or* SSPLv1 *or* **AGPLv3**, and the licensee elects.
We elect AGPLv3, the one OSI-approved option, and that is what answers indicator 2.

The election is defensible on what we actually ask Redis to do: `PING`, `INFO memory`, `LLEN`, `GET`,
`SET … EX`, one redis-py mutex, and pub/sub for Socket.IO and the Celery broker. **No modules, no
Streams, no cluster mode, and no persistence volume is declared** — the broker and cache are entirely
ephemeral. We run an unmodified upstream image as a separate network service and convey no Redis
source, so AGPLv3 imposes nothing on this repository's licensing or on a downstream fork's.

We pinned the **minor** (`8.10`), not `redis:8`, because the *shape* of the finding was a floating tag
rather than Redis specifically: a two-segment pin still receives patches, but a future relicence
becomes something we opt into rather than something that arrives on the next `docker pull`. **The
dependency audit now carries a pin-drift check** for the same reason.

**If AGPL is flagged, the costed fallback is Valkey** (BSD-3-Clause, the Linux Foundation fork,
protocol-compatible with the 7.2 line our command set comes from). The cost is small but real: four
call sites hardcode `redis-server` / `redis-cli`, roughly ten runbook references would change, and
`valkey/valkey` is community-published rather than a Docker Official Image. We would rather not pay
that speculatively.

**(b) `psycopg2-binary` — LGPL-3.0 with a linking exception.** Copyleft, but library-level with an
exception that exists for exactly this use, and standard across the Python ecosystem. We do not expect
an issue; we raise it in case the DPGA reads it differently.

**(c) Two transitive LGPL dependencies no manifest would have shown.** `jwcrypto` (LGPL-3.0-or-later)
arrives through the Keycloak JWT path, and `@img/sharp-libvips-linux*-x64` (LGPL-3.0-or-later) arrives
through Next.js image optimisation. Both are unmodified, dynamically loaded, and used as the LGPL's own
terms contemplate. **Neither is anyone's declared dependency** — which is the clearest single argument
for the generated audit existing.

### 3.3 Indicator 7 — Privacy 🟠

**The assessment exists.** [`privacy-assessment.md`](privacy-assessment.md) covers **13 data-flow legs
verified against the code**, an assessment against Nepal's Individual Privacy Act 2018, and a
**17-item findings register**.

⚠ **It carries a mandatory honesty marker at the top: it was drafted by an AI agent, no lawyer has read
it, and every statutory section reference is marked unverified** because the numbering was not checked
against the Nepal Law Commission text. It is thorough on the *system* and explicitly a lay reading of
the *law*. **Q15** asks who should review it.

⭐ **The timing matters, and it is the most important fact in the privacy picture: no genuine grievance
has been processed on this platform.** Every record in every environment is AI-generated seed data or a
dummy complaint filed during a demo. So every exposure below is **prospective, not realised** — no real
complainant's words have reached a model provider and no real third party has been named to one. That
makes the redaction work a **go-live precondition rather than remediation**. ⚠ Two caveats: a demo
participant may have entered their **own** genuine contact details, so narratives are synthetic while
some contact fields may be real; and **the statement expires on first production use.**

**What is built:** encryption at rest with pgcrypto and in transit with TLS; server-side decryption at a
single boundary, with the ticketing subsystem holding no encryption key and having no accessor for one
(pinned by test); an architecturally enforced PII boundary; Keycloak-authenticated officer access behind
a jurisdiction gate; reveal-contact actions written to an audit log.

**Three storage-layer defects the assessment found are fixed.** They shared a root cause worth stating:
every privacy document in this repository described the *architecture* — which schema owns what, who may
decrypt, where the boundary sits — and all of it was accurate. **None described what the storage layer
does when a write fails.** That is where all three lived.

| Finding | What it was | Now |
|---|---|---|
| **F-2** — encryption failed open | `_encrypt_field` logged the pgcrypto error and returned the **plaintext**, and the decrypt path mirrored it, so reads came back correct and nothing downstream could tell. A degraded deployment could store complainant PII in the clear and look healthy | ✅ Fails **closed** — a pgcrypto failure with a key configured raises and abandons the write. The keyless developer mode survives deliberately, but now warns once per process instead of never |
| **F-3** — unsalted SHA-256 search tokens | Phone, email, name and address were stored as bare SHA-256 `*_hash` columns. Nepal's mobile number space is a few tens of millions of candidates behind a fixed prefix, so the phone hash was **reversible** and those columns were personal data, not pseudonyms | ✅ **HMAC-SHA256** keyed on a pepper, keeping the equality lookup and removing the reversibility. ⚠ Existing tokens must be re-derived or phone lookup breaks silently; a migration script ships with it |
| **F-4** — backups unencrypted by default | `pg_dump` plus a tar of the uploads volume, encrypted only if an operator happened to set one of two variables. Contact columns stayed ciphertext, but the narrative, every officer note, and **every voice recording and photograph** did not | ✅ The script **discards** an unencryptable dump *and* the uploads archive unless an explicit override says otherwise. The uploads tar is encrypted too, which it never was |

**What is still missing, and it is specific rather than general:**

- **The live gap: grievance narratives leave Nepal on every model call, unredacted**, to a third-party
  provider — along with officer notes and whole case timelines including SEAH cases. This is the same
  finding as indicator 4, seen from the privacy side. ⚠ **It is now permanent rather than
  transitional**: with self-hosting parked (§4.7), the provider changes and the cross-border transfer
  does not. That raises the bar on the assessment — it has to justify an indefinite arrangement — and it
  makes redaction the control rather than a defence in depth.
- **A legal review of the assessment.** Q15.
- **Retention and deletion.** ⚠ Sharper than it sounds: archiving is implemented and is **not**
  deletion. [`ARCHIVING_AND_RETENTION.md`](../ARCHIVING_AND_RETENTION.md) puts hard delete out of scope
  for v1, so **no code path deletes personal data anywhere in this platform**, and no retention period
  has been chosen. That needs a legal position before it needs code.
- **A breach procedure** — and `SECURITY.md` already promises reporters that one will be followed, so it
  is a promise made against a procedure that does not exist.
- **Model inputs and outputs are not redacted on the logging path either**, so grievance text can reach
  application logs and Celery payloads in Redis. In our experience that is the leak that actually
  happens, as opposed to the one everyone designs against.
- **Third parties named in grievances have not consented and cannot exercise any right** over data
  already held. Redaction reduces future exposure; it does not answer this.
- **Intake does not disclose that grievance text is sent to an external AI provider.** Consent is
  genuinely collected, but not for that. Cheap to fix, and it should be.
- **The provider's own data terms are not recorded anywhere**, and **the jurisdiction of execution is
  not knowable** — see §4.6.

### 3.4 Indicator 9 — Do no harm 🟢

| Requirement | What is built |
|---|---|
| **9a — Data privacy & security** | PII encrypted at rest, decrypted only server-side at a single boundary; the ticketing subsystem holds no encryption key and cannot obtain one; TLS in transit; Keycloak-authenticated officer access with a jurisdiction gate; the three storage-layer fixes above |
| **9b — Inappropriate content** | **Two independent detection paths, not one.** A **deterministic, scored keyword detector** runs synchronously as slot validation inside the conversation, with no model involved; `detect_sensitive_content_llm` runs asynchronously on Celery as a second pass. A model outage therefore **degrades the second pass rather than removing detection**, which is also why the LLM leg's fail-open default is acceptable rather than a gap |
| **9c — Protection from harassment** | Anonymous grievance submission end to end; the **SEAH workflow is access-isolated** — configurable by administrators who cannot themselves read the cases; a four-tier admin ladder with scoped permissions; a full `admin_audit_log` plus a per-ticket event timeline |

**Three things outstanding under this indicator, and the second is the one we would want raised in the
meeting rather than buried:**

1. A written **retention and deletion policy** and a **breach procedure** — both documentation, both
   gated on the privacy assessment's legal review.
2. ⚠ **The SEAH detector over-flags, and the SEAH route is access-isolated, so an over-flag is not a
   labelling error — it is a disappearance.** Measured over 105 benchmark items, the detector flagged
   **five of eight items authored specifically as the hard case**: no separate toilet for women workers,
   an unlit route home, unequal pay for the same work, one tap for a whole labour camp, and refused work
   for being a woman. Every one is a women's access or discrimination grievance on an infrastructure
   project — precisely the class a GRM exists to surface — and a flagged grievance moves into a channel
   **most officers cannot see**. ⚠ **And the recall half is unmeasured**, so this cannot be fixed by
   simply loosening the prompt. Full detail and the confusion matrix:
   [`model-benchmarks.md`](model-benchmarks.md) §3.2 and §3.5.
3. **Redaction of third-party PII before model calls** — §4.6.

### 3.5 One deployment-credential defect, found and closed

We include this because the method that found it is the point, and because a reviewer who clones the
repository would have read the defect in seven lines of `docker-compose.yml`.

**What it was.** Every service that talks to Postgres set `POSTGRES_PASSWORD` in its own compose
`environment:` block — 19 sites across the two files once Keycloak's copy is counted — and Compose's
`environment:` **overrides `env_file:`**. So the strong, SOPS-encrypted password in the environment file
was **read by nothing**, and every deployed database ran on a literal committed in the clear.

**Three things each looked like the reassurance, and none was.** The environment file held a strong
password. A promotion gate asserted the password was not the default and **passed — because it read the
inert copy**. And an earlier sprint had found half of this and closed it as a test-fixture problem,
without carrying it across to the question of what the password actually was on a deployed host.

**What was done.** The literals were replaced with `${VAR:?}` interpolation, which fails the stack loudly
rather than falling back to a default; the environment file was set to the identity the deployed volumes
actually hold, having named a role and a database that existed nowhere; the credential was **rotated**;
and the literal was removed from all six tracked files that carried it. The promotion gate now checks
what a **container** resolves rather than what the file says, and both of its new checks were verified by
reintroducing the defect and watching them turn red.

⭐ **The part worth generalising.** Fixing it inverted a test bootstrap that had hardcoded the credential
*deliberately*: while the environment file was dead config, honouring it was the one way host tests could
disagree with the database they talked to. Making the file live turned that safeguard into the bug it was
written to prevent. **A control that encodes a fact about the system has to move when the fact does**, and
nothing but a test will tell you it has stopped being true — which is the same argument this document
makes for pinning architectural claims rather than asserting them (§2.5).

Full finding, remediation and the coordinated runbook for the two hosts that are not yet done:
[`db-password-hardcoded-in-compose.md`](../sprints/followups/db-password-hardcoded-in-compose.md).

**⭐ And a second credential, found by asking the converse question.** The audit above asked *"is this
variable actually read?"*. It cleared the Redis broker password — correctly, on that question. So we
then asked the opposite one — *"is this value already public?"* — by hashing every live credential
against every blob ever committed. The broker password was **live, and sitting in nine now-deleted
files** in a repository that has been public since January 2025. Rotated, and verified four ways: the
new credential authenticates, **the old one is refused**, an unauthenticated connection is refused, and
the workers answer over the rotated broker.

**The pair is the transferable finding.** One was an **inert variable carrying a correct value**; the
other a **live variable carrying an exposed value**. Checking the wiring cannot detect the second;
checking the value cannot detect the first. An audit that does one and reports a clean bill is not
wrong so much as incomplete, and ours was.

⭐ **What the scan cleared matters more than what it caught.** The **database encryption key was never
committed** — the one secret this platform cannot rotate, since no re-encryption path exists and a
leak would be permanent exposure of complainant PII. The mail password, the model-provider keys and
both cloud keys are clean too. ⚠ **A pattern scan would have misled in both directions**, and we would
caution any reviewer against one: ours flagged seventy "secret-shaped" strings, most of them regex
constants, while the genuinely alarming hits — a cloud key, a model-provider key and an *older*
encryption key in a committed example file — were **superseded values that authenticate nothing**.
Only comparison against live values separates those.

⚠ **One exposure cannot be closed, and we would rather state it than have it found.** A maintainer's
email address is in the history because it is the **git author on 865 of the repository's 1,018
commits**. It is the username half of a mail credential whose password is clean. No amount of file
editing removes it, and removing it from history would mean rewriting the author of every commit.

**Our position on purging history: we recommend against it.** With both credentials rotated nothing
left in the history opens a live door, and a rewrite cannot un-publish a repository that has been
public for over a year. **Rotation removes the risk; purging removes only the evidence of it** — which
is why the order matters, and why doing it the other way round buys the appearance of safety while the
credential still works. Method, full table and the reasoning:
[`secrets-in-public-git-history.md`](../sprints/followups/secrets-in-public-git-history.md).

---

## 4. Indicator 4 — the AI layer

This is the substance of the meeting. **For AI systems the DPG Standard's platform-independence
questionnaire asks about the code, the model *and* the data**, and the requirement is specific:

> When the digital public good has mandatory dependencies that create more restrictions than the
> original license, proving independence from the closed component(s) **and/or indicating the existence
> of functional, open alternatives that can be used without significant changes to the core product**
> is required. […] demonstrate that these closed component(s) can be replaced with those open
> alternatives **with minimal configuration changes, without requiring a major overhaul of the entire
> system.**

Our reading — which we still want confirmed (**Q6**) — is that **the Standard does not require us to run
open models in production. It requires us to demonstrate that we could, with a configuration change.**

As it happens, the project has decided to run the open configuration in production anyway, on cost
grounds, with the commercial provider retained as a configurable fallback if government users report
quality problems. So whichever way Q6 is answered we expect to satisfy the stricter reading — **once an
open model has been chosen**, which is the one thing this work has not yet done.

### 4.1 How the system queries models

**Nine call sites, two independent subsystems, and not one of them names a model, a provider or an
endpoint.** All nine resolve through a single registry,
[`backend/config/llm_config.py`](../../backend/config/llm_config.py), which both surfaces import and
neither owns.

| # | Subsystem | Function | Task key | Live? | What is sent to the provider |
|---|---|---|---|---|---|
| 1 | chatbot | `transcribe_audio_file` | `asr` | ⏸ parked | Raw complainant voice recording |
| 2 | chatbot | `extract_contact_info` | `extract` | ⏸ parked | Complainant name and phone number, free text |
| 3 | chatbot | `extract_all_contact_info` | `extract` | ⏸ parked | As above |
| 4 | chatbot | `classify_and_summarize_grievance` | `classify` | ✅ **live** | **Full grievance narrative** + district + province |
| 5 | chatbot | `translate_grievance_to_english_LLM` | `translate` | ⏸ parked | Full grievance narrative |
| 6 | chatbot | `detect_sensitive_content_llm` | `detect` | ✅ **live** | Grievance text, including potential SEAH disclosures |
| 7 | ticketing | `translate_to_english` | `ticket_translate` | ✅ **live** | **Officer case notes**, verbatim |
| 8 | ticketing | `generate_case_findings` | `ticket_findings` | ✅ **live** | **Whole case timeline**, including SEAH cases |
| 9 | ticketing | `generate_resolved_case_summary_llm` | `ticket_findings` / `…_seah` | ✅ **live** | Whole case timeline; the output is shown to the complainant |

**Five call sites are live, not nine**, and the distinction is declared in code rather than in a
document: the four parked paths are the **voice-notes flow**. They are listed in a `PARKED_TASKS`
mapping with a reason each, and a test enforces the only two acceptable states — **enqueued in
production, or declared parked. Nothing else.** They are complete and unrotted, and they resolve models
through the same registry as the live paths, so unparking is a configuration decision rather than a
migration.

⚠ **What is switched off is automatic transcription, not voice intake — the distinction matters and we
had been blurring it.** A complainant can still record a grievance: the audio is captured, stored and
handled by an officer. What does not run is the machine transcription of it. And it is off on **cost
grounds** — this project has no funding for per-minute transcription, and the implementing government
is not expected to allocate any — so this should be read as an **unfunded capability rather than a
pending one**. Anything in this document that says "parked pending a budget" is overstating the odds of
its return.

**Two models, not six.** Every text task resolves to `gpt-5-nano` and transcription to `whisper-1`.
Eight task keys, two values — which is what makes a provider swap a small diff rather than a survey.

### 4.2 What is built — one registry, two factories

The registry declares every endpoint, model, deadline and structured-output capability in the product,
once. Two client factories — one per surface — construct clients from it. **A factory decides how to
construct a client; it never decides what to call.**

That separation is not tidiness. Before it existed, the standard/SEAH model pair was written out in
**four** places, one of them a *persisted provenance field*: a resolved-case summary recorded the model
name from a duplicated constant in a different module from the one that made the call. Change the client
and miss that file, and every resolved case records a model that never ran it — **a grievance mechanism
publishing false provenance.**

| Group | Variables |
|---|---|
| Chat endpoint | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_TIMEOUT`, `LLM_MAX_RETRIES` |
| ASR endpoint | `ASR_BASE_URL`, `ASR_API_KEY`, `ASR_TIMEOUT` — falls back to the chat endpoint field by field |
| Models | `MODEL_CLASSIFY`, `MODEL_EXTRACT`, `MODEL_TRANSLATE`, `MODEL_DETECT`, `MODEL_ASR`, `MODEL_TICKET_TRANSLATE`, `MODEL_TICKET_FINDINGS`, `MODEL_TICKET_FINDINGS_SEAH` |
| Deadlines | `TIMEOUT_CLASSIFY`, `TIMEOUT_TICKET` — per task; 0 means the endpoint's |
| Structured output | `LLM_STRUCTURED_OUTPUT` plus a per-task capability flag |
| Deprecated | `OPENAI_API_KEY`, `OPENAI_CLASSIFICATION_TIMEOUT` — still honoured, with one warning each |

**What backs the claim, in order of how hard it is to argue with:**

| Evidence | Where |
|---|---|
| One environment change moves **both** surfaces — both clients constructed in a single test and asserted onto the same endpoint | `tests/ticketing/test_llm_client.py` |
| No model name exists outside the registry — **AST-parsed**, not grepped, across `backend/` and `ticketing/` | `tests/backend/test_llm_config_pins.py` |
| No client is constructed outside the two factories | same file |
| `.env.example` and the registry agree in **both** directions — undocumented and stale variables each fail the build | same file |
| The two shipped configurations declare the same variables and differ only in values | same file |
| The closed configuration is what a fresh clone gets, so the commercial fallback is one variable away rather than an intention | same file |

**Switching is two committed template files.** Neither contains a secret:

```bash
cp .env.open   env.local.llm   # open weights, via Hugging Face Inference Providers
cp .env.openai env.local.llm   # today's default
```

`diff .env.openai .env.open` is the whole delta. No code, no image rebuild, no migration, no compose
edit.

**Structured output is a per-`(endpoint, model)` property, and that is measured.** `json_schema`
constrains generation to a grammar so a reply is guaranteed parseable. Support is not a property of the
endpoint — which is what our own plan originally assumed. Measured against the live provider, one
request per cell: `gpt-5-nano` and `gpt-4o-mini` accept both modes; `gpt-3.5-turbo` rejects
`json_schema`; `gpt-4` rejects **both**. So each task declares its own capability, the endpoint sets a
ceiling, the effective mode is the weaker of the two, and the ladder degrades `json_schema` →
`json_object` → prompt-only with the rung logged per call. **An endpoint with no JSON mode at all still
works.** This *improves* portability rather than trading it away: prompt-only JSON is the least portable
choice available, and it is what breaks first when you change models.

**The pattern was already proven in this codebase, which is the best evidence it was a refactor rather
than a redesign.** The SMS layer runs two providers behind one interface selected by an environment
variable — AWS SNS internationally, the Government of Nepal gateway (`sms.doit.gov.np`) in Nepal. The
model layer is the same shape, done a second time.

**The AI paths are fail-soft, which lowers the risk of switching providers.** Intake writes the
grievance to PostgreSQL *before* any model call; classification runs as a Celery task with retry and
explicit failure states; the chatbot waits on a bounded deadline rather than indefinitely. **A grievance
is never lost because a model was unavailable**, so a slower model degrades throughput, not intake.

### 4.3 What has been measured — capability

A committed, re-runnable probe (`scripts/ops/llm_smoke.py`) resolves the endpoint from the same
registry the product uses, asks each candidate six questions — one request per cell — verifies the
licence from the model card at probe time, and prints a profile to paste into the registry. A reviewer
can run it themselves; the command is in
[`open-model-configuration.md`](open-model-configuration.md).

| Model | Licence *(verified from the model card)* | chat | `json_object` | `json_schema` | Probe latency |
|---|---|---|---|---|---|
| `openai/gpt-oss-20b` | Apache-2.0 | ✅ | ✅ | ✅ | **0.73 s** |
| `openai/gpt-oss-120b` | Apache-2.0 | ✅ | ✅ | ✅ | **0.68 s** |
| `Qwen/Qwen3.5-27B` | Apache-2.0 | ✅ | ✅ | ✅ | 20.48 s |
| `Qwen/Qwen3.5-35B-A3B` | Apache-2.0 | ✅ | ✅ | ✅ | 9.35 s |
| `Qwen/Qwen3.5-9B` | Apache-2.0 | ✅ | ✅ | ⚠ **accepted, not honoured** | 23.78 s |
| `microsoft/phi-4` | MIT | ✅ | ✅ | ✅ | 1.77 s |
| `swiss-ai/Apertus-70B-Instruct-2509` | Apache-2.0 | ❌ **request blocked** | — | — | 0.42 s |
| *transcription* | — | ❌ **404 — the router serves no `/v1/audio/*` route at all** | | | |

**Four findings from that probe are worth the consultant's time, and two of them bear on
safeguarding rather than on engineering:**

**(a) `Qwen3.5-9B` accepts `json_schema` and silently ignores it.** HTTP 200, well-formed JSON, and
**not one of the fields the schema declares required.** This is invisible to any probe that asks for
*some* JSON and calls a successful parse a pass; the probe's schema requires a field the prompt never
mentions, precisely so "returned JSON" and "was constrained" can be told apart. Had this not been
measured, a fresh clone pointed at that model would have produced malformed output under load and
nothing would have explained why.

**(b) ⚠ `Apertus-70B` refused a grievance about children falling ill.** Its only reply to the
capability probe was *"Your request was blocked"* — in 0.42 s, far too fast to be generation, so a
filter in front of the model rather than the model declining. The prompt was the benchmark's flagship
item: road construction dust entering a house, children becoming ill. **Every other candidate answered
it.** This system's entire input distribution is human harm — dust and sick children is the *mildest*
end; the rest is land seizure, unpaid wages, forced relocation and, on the SEAH path, sexual
harassment. **A filter tuned to refuse discussion of harm to children refuses hardest on the reports
that matter most**, and because the SEAH detection path fails open by design, a harassment report the
filter blocks would be silently handled as an ordinary complaint. That is a safeguarding failure mode,
not a quality one. It is also a genuine loss: Apertus was the strongest *DPG story* in the shortlist —
fully open weights **and** open training data, built for low-resource language coverage.
[Write-up](../sprints/2026-08-llm/followups/apertus-content-filter-blocks-a-grievance.md).

**(c) ⚠ The open configuration cannot transcribe audio at all.** `.env.open` ships an ASR endpoint that
returns **HTTP 404** for every model id tried. Not auth and not billing, and three controls say so:
`GET /v1/models` returns 200, `POST /v1/chat/completions` returns 200, and the audio route returns 401
**without** a token and 404 **with** one — so it exists and authenticates but serves nothing. The
router's own catalogue confirms it: 132 models, **none of them audio**. Hugging Face serves ASR, but not
through the OpenAI-compatible surface this code calls. So *"the open configuration runs the whole
system"* is **false for audio and true for text**.

⭐ **And the consequence runs in our favour, which is why it is worth stating precisely rather than as a
gap.** Automatic transcription is switched off on cost grounds and is not expected to be funded (§4.1),
so **the one path the open provider cannot serve is the one path that does not run.** The open
configuration therefore covers **every model call this system actually makes**. If transcription were
ever funded, it would have to run on the closed provider or on a self-hosted vLLM, which serves
`/v1/audio/transcriptions` — and that is the day this becomes a real indicator-4 gap rather than a
theoretical one.
[Write-up](../sprints/2026-08-llm/followups/the-open-config-has-no-working-asr-endpoint.md).

**(d) Latency spans 30× across the shortlist** — 0.68 s to 23.8 s on a *one-sentence* prompt. Against
a 30-second interactive budget that is pass/fail rather than a table row, and it is a selection input.

**⚠ Capability is not quality.** Everything in this section measures what a model can be *told*. What it
gets *right* is §4.4, and conflating the two is the easiest overstatement available here.

**On the licence filter, and what it costs.** We filter candidates for Apache-2.0 or MIT. The excluded
list is worth naming because on a low-resource language this may be costing real accuracy: Gemma 3/4
and Llama 3.3 ship under bespoke community licences with use restrictions; `Gemma-SEA-LION` inherits
Gemma's terms. **The one that hurts is `aya-expanse-32b` (CC-BY-NC-4.0)** — purpose-built for
multilingual coverage and exactly the right size, but non-commercial is incompatible with a government
production deployment **however Q7 is answered**, so unlike the others that exclusion does not loosen.
The shortlist lives in `scripts/ops/llm_candidates.json` as **data**, deliberately, so a loosened Q7 is
an edit to one file rather than a redesign.

### 4.4 What has been measured — accuracy, latency and cost

A **105-item labelled benchmark set** is committed under CC0-1.0 at
[`tests/data/benchmark/`](../../tests/data/benchmark/README.md), with a provenance README. The harness
(`scripts/ops/llm_benchmark.py`) calls **the product's own functions with the product's prompts,
resolved through the registry the product reads** — nothing is reimplemented — which is what makes it a
pre-flight check on a production change rather than a parallel universe that agrees with production by
luck. It proves the credential before scoring anything, scores classification at set level, scores
detection recall-first with a confusion matrix, and meters real token usage.

⚠ **Every number below comes from synthetic, authored data.** Authored text is cleaner than real
complaints — better punctuated, more complete, less elliptical — so each figure is an **upper bound** on
production accuracy, not an estimate of it.

**The closed baseline is complete.** `gpt-5-nano`, the model production runs today, over all 105 items:

| Metric | Value |
|---|---|
| Classification precision *(set-level)* | 0.773 |
| Classification recall *(set-level)* | 0.752 |
| Category-set **F1** *(multi-label)* | **0.762** |
| Exact-set accuracy *(every gold label, no invented extras)* | 0.686 |
| p95 latency, classification, against a 30 s budget | **20.3 s — passes** |
| p99 latency, classification | **24.5 s — passes** |
| Sensitive-content **false-alarm** rate | 0.067, including **5 of 8** deliberate confusables |
| Sensitive-content **recall** | ⚠ **Not measured — and not measurable from this repository** |

**The open column is one metric in.** `openai/gpt-oss-20b` completed **all 105 detection items** and
**2 of 105 classification items**. ⚠ **The blocker was our prompt, not the model:** the classification
prompt was ~20,700 characters before the grievance was added, and 105 of them in a few minutes exceeded
the provider's short-window token limit. The same run's 105 short detection calls all completed. **That
contrast is the finding**, and it is about us.

⭐ **Two results the benchmark was not looking for, and both changed a decision:**

**(a) The classifier invented categories on 17% of grievances, and they were stored.** Eighteen of 105
items received a category that exists nowhere in the taxonomy — and not as noise, but as a coherent
fictional `Road Hazard - *` family. **21 of the run's 32 false positives were invented categories.** The
storage path logs and never rejects, deliberately, and the stated reason is sound for a *near-miss
name*. `Road Hazard - Dust` is not a near-miss: it was stored, shown to the complainant as the system's
understanding of their own complaint, and synced to ticketing where it matched no filter and no
priority lookup.

⭐ **Then both models invented the *same* category.** `gpt-oss-20b` classified only two items before the
rate limit and returned `Road Hazard - Dust` on both. Two vendors, two architectures, one fabricated
label — which is weak evidence about either model and **strong evidence about the taxonomy**: the
catalogue had no road-hazard grouping, and independent models kept reaching for the category a road
project would expect to exist.

**The fix followed the evidence and was re-measured.** Six `Road Hazard - *` categories were added and
the prompt was reduced. Invention fell from **18/105 to 4/105**, and three of the four residual are real
categories with a formatting failure rather than new concepts. Precision rose, recall fell, F1 moved
−0.009 — flat within the noise floor of a 105-item set — exact-set accuracy rose, and **p99 latency fell
from 40.6 s to 24.5 s, inside the interactive budget for the first time.** ⚠ Three things changed at
once, so this is **not a clean A/B** and the F1 line must not be read as one; the robust findings are
the ones that moved by a lot.

**(b) The prompt was carrying a bug that cost 79% of its size.** The catalogue was sent three times, and
the dictionary was **51,213 characters for an English grievance against 15,121 for a Nepali one**. The
language filter stripped the Nepali keys for a Nepali grievance and stripped **nothing** for an English
one, because no key carried an English marker. **Every English classification therefore carried every
Nepali translation, JSON-escaped at six bytes per character, for a model that never used them.** Net
after the fix: 62,736 → 13,147 characters for English, and ~10,900 → **3,277 prompt tokens per
classification**, while *adding* six categories.

**Cost, measured in tokens rather than dollars**, because tokens do not drift and prices do. Over 212
calls: **11,358 prompt + 3,361 completion tokens per grievance** — both calls, which is what production
makes — of which **93.8% of the completion budget is reasoning tokens**: invisible in the reply, fully
billed. ⚠ Any cost estimate built from output length understates this system by roughly 16×. ⚠ **That
measurement predates the prompt reduction**, which cuts the prompt half by about 70%; the figure needs
re-taking and [`model-benchmarks.md`](model-benchmarks.md) §6 says so.

⚠ **The single most important missing number is SEAH recall, and it decides a model choice.**
`gpt-5-nano` flags 7 of 105 ordinary complaints as sensitive, including 5 of the 8 confusables.
`gpt-oss-20b` flags **0 of 105 — of anything.** Read naively that is a clean win for the open model.
**Do not read it naively:** a detector that flags nothing has a perfect false-alarm rate and catches
nothing. Two hypotheses fit the data equally — the open model is better calibrated, or it says no to
everything and a real harassment report would go unflagged. **Nothing in this repository can tell them
apart**, because the committed set contains no harassment reports at all, by decision: those narratives
are held by the project owner and never enter the repository, since three hundred realistic Nepali
harassment complaints sitting in a public repo will be read as leaked case data by somebody regardless
of how the file is labelled. The harness accepts a set from outside the repository and **refuses a path
inside it**.

**Therefore neither model may be selected on this evidence, and `gpt-oss-20b`'s 0.000 must not appear in
a submission as an improvement.** This is a real weakness in the evidence pack and it is the right
trade; we would rather state it than let a reviewer discover that our headline detection number is not
reproducible from what we published.

### 4.5 The indicator-4 answer, clause by clause

Here is the answer we intend to give, with each clause checked against the code rather than assumed.
**Three of seven do not hold today**, and we would rather show you the audit than the draft.

| Clause | Verdict |
|---|---|
| *"An OpenAI-compatible LLM endpoint, configured entirely through `LLM_BASE_URL` and `MODEL_*` with no code change, across both LLM surfaces"* | ✅ **True.** One registry; both surfaces asserted onto one endpoint by a test; no model name outside the registry, AST-parsed |
| *"Documented in `open-model-configuration.md`"* | ✅ **True**, and it carries the measured capability matrix |
| *"The commercial provider is retained as a configurable fallback"* | ✅ **True**, and pinned — a test asserts the closed configuration is what a fresh clone gets |
| *"A self-hosted vLLM deployment is documented and costed, not deployed"* | ✅ **True**, and the costing sharpened it — see §4.7 |
| *"The repository default is an open-weights configuration"* | ❌ **False, twice.** The defaults are still `gpt-5-nano` / `whisper-1`, because no open model has been **chosen** — the comparative benchmark is unfinished. And the ASR half is false independently: the configured open ASR endpoint **404s** |
| *"The open configuration is what production runs"* | ❌ **False today.** It is decided, and it cannot happen until the clause above is true |
| *"CI runs the **full** LLM test suite against the open configuration on every commit"* | ⚠ **Overstated, and it has never run in CI.** The job runs a deliberately small **live subset** — a cost decision, not an oversight — and calling it "the full suite" would misdescribe it |

**The version that is true today**, which is what we would put in a submission:

> Yes — an OpenAI-compatible LLM endpoint, configured entirely through the `LLM_BASE_URL` and
> `MODEL_*` environment variables with no code change, across **both** of the system's LLM surfaces
> (chatbot intake and ticketing case analysis). All nine model call sites resolve through a single
> registry that neither surface owns, and a test asserts that one environment change moves both. Two
> committed configuration files differ **only in values** — `diff .env.openai .env.open` is the whole
> delta. The open path has been exercised against a hosted open-weights provider: the permissive licence
> was verified from the model card, and `json_schema`-constrained generation was confirmed as *honoured*
> rather than merely accepted. A CI job runs the product's own LLM code paths live against the open
> configuration.
>
> ⚠ The repository default remains the proprietary configuration, deliberately: an open base URL
> combined with proprietary model ids would be a repository that cannot serve a single request on a
> fresh clone, which is weaker evidence than an honest default. The open model has not yet been
> *chosen*, because the comparative benchmark is unfinished — the harness, the labelled dataset and the
> scoring rules are committed and reproducible; the numbers are not yet in.
>
> A self-hosted vLLM deployment is **documented and costed, not deployed**, for want of a funded
> operator.

**About the CI job**, because it is the piece of evidence we care most about and the one most easily
overstated. `dpg-platform-independence` runs the product's own LLM code paths — **both** surfaces —
against a real provider through the open-weights configuration. Run by hand on 2026-08-20 it returned
**4 passed, 1 xfailed, exit 0** against `openai/gpt-oss-20b`. The xfail is the transcription round-trip,
it is strict, and it reddens the day someone fixes the ASR endpoint. **That is indicator 4 executing
rather than asserted**, and a claim a build executes cannot silently rot the way a document can.

Three properties of it are worth stating because each is a way the job could have become decoration:

- Model ids come from **repository variables, not literals**, so swapping a model after the benchmark
  reports is a settings change — and so the workflow never becomes a second place where a model name
  lives. A test asserts the endpoint the tests reached is the one the registry names, which catches the
  most embarrassing false green available here: a job that passes against the commercial provider while
  reporting that open weights work.
- Live tests **skip** on an account-level refusal, because a job that reddens on someone else's billing
  teaches everyone to ignore the job. ⚠ **But a run where everything skipped would exit 0 and show a
  green tick having tested nothing**, so the job also **fails when nothing passed**. Neither control is
  safe alone.
- The suite is deselected in the ordinary test job and selected here, **and a test asserts both**,
  because a quarantined test suite that nobody notices is a failure mode this project has already had
  once.

⚠ **It has never executed in CI**, because the provider account was rate-limited when it was written.
**A job that exists, never runs, and is cited as evidence is not acceptable**, and the workflow header
says so in those terms. If the per-commit cadence proves unaffordable, the documented fallback is
nightly plus release tags, **declared on the badge** rather than quietly.

### 4.6 The privacy dimension of the same problem

Indicators 4 and 7 meet here. Every grievance narrative, every officer note and — in the SEAH path —
content that is sensitive by definition, is transmitted to a third-party provider outside Nepal,
unredacted. Two clarifications, because the two problems are routinely conflated:

- **Structured PII at rest is solved.** Name, phone, email and address are encrypted, decrypted at one
  server-side boundary, and architecturally barred from the ticketing schema by tests.
- **Free-text egress is not.** A complainant writes *"the site engineer Ram Bahadur refused to…"* into a
  narrative field, and that name is in the payload. No amount of column-level encryption addresses it.

**Two framing corrections we would rather make ourselves:**

**Openness is a licensing property, not a privacy property.** Moving to open weights answers indicator 4
and does **nothing** for indicator 7. An open model served by a third party carries exactly the same
data-flow risk as a commercial one served by its vendor. The two problems share an eventual solution —
self-hosting — but the migration solves only the first.

**The legal trigger was never model training.** Under Nepal's Individual Privacy Act 2018 and
GDPR-style regimes alike, transmitting personal data to a third party **is itself a disclosure and a
cross-border transfer; the event is the transmission.** Whether the recipient stores it, learns from it,
or discards it a microsecond later does not change that a transfer occurred and requires a lawful basis.
Non-retention is a mitigation, and a valuable one. It is not an answer.

#### Whose terms the residual lands under

**Hugging Face's own commitments are substantive, and we cite them**
([Inference Providers → Security & Compliance](https://huggingface.co/docs/inference-providers/en/security)):

> *"Hugging Face does not store any user data for training purposes. We do not store the request body or
> response when routing requests through Hugging Face. Logs are kept for debugging purposes for up to 30
> days, but no user data or tokens are stored."*

Plus TLS in transit, and the Hub — of which Inference Providers is a feature — is **SOC 2 Type 2
certified**. Genuinely usable in a transfer assessment.

⚠ **Then the sentence that matters, and it is theirs:** *"External providers are responsible for their
own security measures, so please refer to their respective security policies."* **The no-storage
commitment covers the router, not the company that runs the model.** Requests are proxied to third-party
partners — Cerebras, Groq, Together, Fireworks, Novita, DeepInfra, Replicate, Scaleway, OVHcloud — with
the default policy choosing the fastest available **per request**. For a government privacy assessment,
**"we cannot name which company processed this citizen's grievance" is a finding, not a footnote.**

The **Terms of Service reference no DPA** and frame confidentiality around private repositories rather
than inference traffic. For a router architecture a DPA is awkward by construction: one would be needed
from Hugging Face *and* from each downstream provider — which is an underrated practical argument for
self-hosting, where there is one cloud contract and a standard DPA.

**Our engineering response, which we would like sanity-checked (Q14):** pin one named provider in the
model path (`model:provider`) in production, converting an unknowable sub-processor chain into one
company whose policy can be read, cited and made the subject of a DPA request. **CI keeps automatic
routing**, because it sends only synthetic benchmark data and the multi-provider evidence is worth
having there.

⚠ **What remains even with a provider pinned**, and belongs in the data-flow diagram rather than being
discovered later: the downstream provider's **own retention** (commonly around 30 days, with some
reserving service-improvement use absent an opt-out); the **jurisdiction of execution**, which pinning a
provider does not fix; and **prompt caching**, which several providers use for performance and which
means cached content sits somewhere briefly. Any submission text naming a single destination country
for the model calls would be a claim we cannot support.

**One thing about the router's fan-out that we will not overstate.** The router's value for indicator 4
is independence from *any single vendor*, not just from one: `gpt-oss-20b` is offered by eight partners
and `gpt-oss-120b` by eleven, read from the router's own catalogue. ⚠ **But only one route has actually
been exercised** — the router selected Groq for the successful probes. The alternative base URLs are
OpenAI-compatible and the code needs no change to use them, but none has been probed, because each needs
its own account. **The fan-out count is not a measurement.**

#### The redaction plan, and the residual we will publish rather than describe

Redaction is Sprint 3 and it has **not started**. The design is specced and the decision behind it is
taken: **redact at transmission, not before storage.** The officer handling the case still needs to see
which official was named — for a GRM, complaints naming officials are a large share of the useful ones,
and redacting before storage would destroy the record's evidentiary value. The full record stays; a
redacted derivative goes to models and logs. **Q12** asks whether that conflicts with any position you
or ADB safeguards hold.

What ships in the first pass:

- **The deterministic layer** — Nepali phone formats in **both** digit systems (Devanagari digits defeat
  an ASCII regex, and `९८४१२३४५६७` is a phone number in plain text), citizenship numbers, vehicle
  registrations, emails, and full address spans while leaving the bare district the classifier needs.
- **Person names, at the rule layer, with no ML dependency**: honorific and role-title triggers (`Er.`,
  Engineer, overseer, contractor, ward chairperson, `श्री`), which catch the **named official** — the
  sharpest exposure, since that person consented to nothing; a Nepali family-name (*thar*) gazetteer,
  tractable because surnames are a comparatively closed set; and self-identification patterns
  (*"my name is …"*, `मेरो नाम … हो`), which catch the opening line the voice channel all but guarantees.
- **The logging, task-queue and backup paths**, which is where leaks actually happen.

⚠ **What still gets through, stated as a residual rather than rounded away:** a name with no title, no
recognisable surname and no self-identification frame. *"The man operating the roller"*, named in
passing three sentences later, is the shape of the miss. **We will publish the measured residual, not a
description of it.** Higher recall needs an ML model, and **the most accurate Nepali NER model we can
find has no licence stated on its model card** — shipping it would swap one closed dependency for
another inside the very submission meant to remove one (**Q13**).

⚠ **And one precision we want settled before anyone briefs the ministry: what this produces is
*pseudonymised* text, not *anonymised* text.** Because the mapping that turns a placeholder back into a
name is kept, the text **remains personal data**. Redaction lowers the risk profile; it does not take
the data out of scope. **We will not let anyone tell the agency the grievances are "anonymised"** — that
claim would not survive scrutiny, and an overstatement there would discredit every other claim we make.
What we can say accurately and strongly is: *only pseudonymised text crosses the border, and the
re-identification key never leaves Nepal.* ⚠ The second clause is a promise about deployment, not about
code, and it is quietly easy to void — one careless serialisation putting the mapping into the same task
payload or log line as the text and the key has travelled with the ciphertext. So in-country residency
and storage separation are **acceptance criteria with a test**, not implementation notes. That mapping
is arguably the most concentrated personal data in the system: identifiers with nothing else attached.

**The intended long-term fix, and it may interest ADB beyond this project:** fine-tune a Nepali NER
model on an openly-licensed corpus, **release it openly**, and run it as a standalone anonymiser service
usable by any country programme where in-country self-hosting is impossible. Permissively-licensed
Nepali NLP tooling barely exists, so that would be a genuine DPG **contribution** rather than only a
compliance fix. Q13 asks whether you would see it that way.

### 4.7 The deployment ladder — and why self-hosting is parked

Nepal cannot host GPUs: no machines, no operations staff, and power reliability makes on-premises a
liability. We take that as a fact to design around. The distinction that opens the path is that
**self-hosting the software is not the same as hosting the hardware.**

| Tier | What it is | Who can see grievance text | Status |
|---|---|---|---|
| **T1** ⭐ | Hosted open-weights inference API | The router **and** whichever partner it selects | Supported; the configuration in `.env.open`. **The steady state, and the intended production target** |
| **T2** | vLLM on a rented GPU VM under the agency's own contract | Nobody outside the agency's contracted infrastructure | ⏸ **Parked** — documented and costed, not deployed |
| **T3** | On-premises, inside the ministry | Nobody | Not Nepal. Plausible for other country programmes |

**The only thing that differs between the three is the base URL.** That is both the engineering goal and
the indicator-4 answer, and it is what [`vllm-deployment.md`](vllm-deployment.md) exists to keep true.

**T2 is parked because nobody owns the run costs.** The two decisions it needed — jurisdiction, and *who
pays for the running instance* — are really one decision, and the second has no answer. **A GPU instance
with no named budget line is the failure mode that killed Rwanda's Babyl**, better avoided by not
starting than discovered later. The best case remains ADB financing subcontractor-managed instances
leased to member countries under a TA with the Ministry of Finance; that is a procurement conversation,
and the deployment document exists so that unparking is a procurement decision rather than an
engineering one.

⭐ **And the costing changed the conclusion, which is why we present it rather than a break-even.** The
T1/T2 crossover — the volume at which a dedicated GPU becomes cheaper than hosted inference — sits at
**40,000 to 780,000 grievances per month** across every price assumption we tried. Two pilot districts
handle grievances in the **tens** per month; all 77 districts of Nepal at 100 each would be **7,700**. So
T1 is cheaper at every volume this system will ever see, by three to four orders of magnitude, and
**volume growth does not close the gap** — classification is one request per grievance, not one per
conversational turn, so a dedicated GPU would sit idle almost always, and idle GPU time is the entire
cost.

**That means T2 is not a cost decision at all. It is a data-sovereignty decision with a price
attached**, and presenting it as a break-even would have implied that waiting for volume eventually
justifies it. It does not. ⚠ The token counts behind that arithmetic are measured; the instance prices
are quotes we have not taken, which is why the conclusion is a range rather than a number.

**The consequence we want to be explicit about:** T1 is the steady state, not a transition. Grievance
text will be processed by a third-party provider **indefinitely**. That does not change the indicator-4
answer — a hosted open-weights provider is still an open alternative — but it turns the privacy exposure
in §4.6 from transitional into permanent, and it makes redaction the only remaining control rather than a
defence in depth.

### 4.8 What we do not know, and will not claim

- **Nepali quality on open weights is unmeasured — by us and largely by the field.** Nepali is
  low-resource. The open column of the benchmark has detection only, so any statement that an open model
  is "close enough" on grievance classification would be invention today. ⚠ **And the classification
  blocker was our own prompt**, which has since been cut by 70%; re-running the open column is now the
  next measurement, not a funding question.
- **SEAH recall for both candidates.** §4.4. This is the number that decides a model selection with a
  safeguarding consequence, and no table may rank two candidates that differ by a few points on a
  hand-authored set.
- **Nepali ASR quality, which we may never need to know.** Automatic transcription is switched off on
  cost grounds and is not expected to be funded, so there is no incumbent baseline, no audio in the
  benchmark set, and no reachable open speech endpoint (§4.3(c)) — three absences that all stop
  mattering if the path stays off. We keep it on this list rather than deleting it because the *code*
  is live and correct-by-signature: the day someone funds transcription, all three become real and none
  of them is measured. **Q8** asks whether a capability that never executes is a gap at all.
- **Translation may want a specialist model.** A purpose-built seq2seq model will likely beat a general
  chat model on Nepali↔English, but it needs its own service rather than a chat endpoint. That is a real
  deployment cost, and the benchmark should decide it, not our prior.
- **Whether an open model can hold the interactive latency budget.** The closed baseline now passes p99
  at 24.5 s against a 30 s wait. The shortlist spans 30× on a one-sentence probe. A slower open model
  turns a 2-in-100 tail into a routine event, at which point the wait and the request timeout have to
  move together — which they are pinned to do.

---

## 5. Questions for the consultant

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

## Appendix A — Dependency inventory

**Superseded by the generated report.** [`dependency-licenses.md`](dependency-licenses.md) is the
authoritative inventory: 153 packages across four dependency sets, produced in-container from the
resolved trees, with a written disposition for every entry carrying conditions beyond attribution, and
re-run nightly by the ops container.

We deliberately do **not** keep a hand-maintained mirror of it here. A summary table in a second document
is exactly the drift this evidence pack exists to remove — and the generated report found two transitive
LGPL dependencies and a licence contradiction in our own npm manifest that no hand-written list contained.

The summary counts are in §2.2; the notable dispositions are in §3.2.

## Appendix B — Where the engineering plan lives

Four sub-sprints, 31 tickets, with test ledgers, a decision register and a deviation log at
[`docs/sprints/2026-08-llm/`](../sprints/2026-08-llm/README.md).

| Sprint | Scope | Serves | Status |
|---|---|---|---|
| **0** — [licensing & governance](../sprints/2026-08-llm/01-licensing-and-governance-spec.md) | `LICENSE`, `NOTICE`, SPDX, generated dependency scan across four sets with a pin-drift check, project hygiene, the root README, the privacy assessment, the IP determination | Indicators 2, 3, 5, 7, 8 | ✅ Landed, except the IP determination (external) |
| **1** — [LLM-agnostic](../sprints/2026-08-llm/02-llm-agnostic-spec.md) | A characterization-test net first; one config file both surfaces read; both LLM surfaces behind configurable clients; schema-constrained output; environment plumbing; a degraded-mode audit | **Indicator 4** | ✅ Landed |
| **2** — [open models](../sprints/2026-08-llm/03-open-models-spec.md) | Labelled Nepali benchmark set, provider probe and capability matrix, closed baseline, CI platform-independence job, self-hosted deployment documented and costed | **Indicator 4** evidence | 🟡 Landed; the open column and the ASR evaluation are incomplete |
| **3** — [PII redaction](../sprints/2026-08-llm/04-pii-redaction-spec.md) | Redaction at the model-call, logging, task-queue and backup boundaries, with measured recall on Nepali | Indicators 7, 9 | ⬜ Not started |

**A note on what the sprints found, because it is the argument for the method rather than for the
result.** Of the tickets that closed, most surfaced something the spec did not know: two latent
crash bugs on the AI paths, a transcription call that had **never worked** because it passed the wrong
SDK argument, a failed classification stored as if it had succeeded, a stored phone number overwritten
with an empty string, four taxonomy categories that had silently lost their high-priority flag —
including the dust category and the SEAH category — and the three storage-layer defects in §3.3. **None
of those was found by reading a document.** They were found by running the code against a real database,
a dead port, or a live provider, and then measuring what came back.
