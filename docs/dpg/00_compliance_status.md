# DPG compliance status — Nepal GRM platform

> **Purpose.** Briefing document for the discussion with ADB's Digital Public Goods consultant.
> It states, indicator by indicator, **where this platform already complies**, **where it does not
> yet**, and **which questions we need the consultant to answer** before we can finish the work or
> submit.
>
> **Audience:** ADB DPG consultant + project team. **Date:** 2026-08-17.
> **Status of this document:** self-assessment against the
> [DPG Standard](https://www.digitalpublicgoods.net/standard) v1.x, written from a direct read of the
> codebase. Rows marked ⚠ are claims we have **not** yet mechanically verified; they are stated as
> expectations, not evidence.
>
> **Companion documents.** The engineering plan that closes the gaps below is already written and
> costed: [`docs/sprints/2026-08-llm/`](../sprints/2026-08-llm/README.md) — 27 tickets across four
> sub-sprints. This document is the *external* view; that folder is the *internal* one.
>
> **Reconciled both ways, 2026-08-17.** This document was written later than the specs and from a fresh
> read of the code, so it found things they missed — **container-image licences** (the fourth dependency set,
> and the one where drift actually happened), **project hygiene**, and the **stale root README**. Those are
> now sprint tickets DPG-02 (extended), **DPG-05** and **DPG-06**. It also asserted four things the specs had
> right, now corrected here: `.env.example` **does** exist (§3.3), there are **nine** model calls not eight
> (§4.1), and the ticket count is 27 not 22. Where a fact is disputed, neither document wins by seniority —
> **both cite the code.**
>
> **Owner decisions taken 2026-08-17** — after this document was drafted, and three of them change what it
> says. **(a) T2 is parked** for want of a funded operator, so §4.5's ladder no longer has a production
> target and the third-party exposure in §4.3 is **permanent, not transitional**. **(b) Production will run
> the open configuration** on cost grounds — *stronger* than indicator 4 requires. **(c) There is no LLM
> budget**, which is why voice transcription is not live and why the benchmark and CI evidence in §4.6 need
> a metered inference line to exist at all. All twenty questions are answered in
> [`QUESTIONS.md`](../sprints/2026-08-llm/QUESTIONS.md), now a decision register.
>
> **⚠ Note on question numbers.** §5's **Q1…Q14** are for the DPG consultant. The sprint folder's
> [`QUESTIONS.md`](../sprints/2026-08-llm/QUESTIONS.md) uses **Q-01…Q-18, hyphenated**, for the project
> owner. The numbers overlap and mean different things; the specs cite these as "consultant-Q*n*".

---

## How to read this

We have deliberately **not** written this as a compliance pitch. Two of the nine indicators have real
gaps, one of them cannot be closed by anyone on the engineering team, and the AI-specific reading of
indicator 4 is the substance of the meeting. The honest version is more useful to us than the
flattering one.

**The short version:**

- **The code and its dependency tree are in good shape.** Everything we build on is open source, and
  the runtime stack has no proprietary components at all — no closed database, no closed identity
  provider, no closed framework, no vendored SDK we could not replace. We can serve indicator 2 with a
  dependency scan and very little argument.
- **The AI layer is our one genuine closed dependency**, and it is the one the DPG Standard scrutinises
  hardest for AI systems. Today all **nine** of our model calls go to OpenAI, with the model names
  hard-coded in Python. That is an indicator-4 problem and, because grievance narratives are the
  payload, an indicator-7 problem as well.
- **Two items need people, not code:** the IP-ownership determination (indicator 3) and the privacy
  assessment against Nepal's Individual Privacy Act 2018 (indicator 7).
- **Two decisions taken 2026-08-17 that change what we are asking you.** **(a) Self-hosted inference (T2)
  is parked** — no owner for the run costs, and we will not start a system nobody funds. A hosted
  open-weights provider is therefore the **steady state**, so grievance text crosses a border
  indefinitely rather than during a transition, and redaction becomes the only control on it.
  **(b) Production will run the open configuration**, on cost grounds. That is *more* than indicator 4
  asks for. **What we now need instead of a GPU budget is a small metered inference budget** — see Q15,
  and it is the only ask on this list that blocks work rather than paperwork.

---

## 1. Scorecard

| # | Indicator | Status | What is missing |
|---|---|---|---|
| 1 | Relevance to SDGs | ✅ **Compliant** | Needs writing up, not building. SDG 16.6 / 16.10, SDG 9.1 |
| 2 | Use of approved open licence | 🟠 **Gap — trivial, now waiting on us both** | The repo is **public with no `LICENSE` file**. Dependency tree is clean; the Redis drift is fixed (§3.1b), `psycopg2-binary` is the only flag. ⚠ **We need two answers before the file can land:** which licence (yours — Apache-2.0 recommended) and which copyright holder (ADB OGC, Q1) |
| 3 | Clear ownership | 🔴 **Blocked — external** | Written IP determination from ADB. **Nobody on the project can resolve this** |
| 4 | Platform independence | 🔴 **Gap — the main work** | Model provider is hard-coded in **9 call sites across 2 subsystems, in 4 files**. §4 is entirely about this |
| 5 | Documentation | ✅ **Compliant, strong** | A ~200-file spec tree, Docker runbook, OpenAPI on both APIs. Deployability warts (§3.3) — the root `README.md` still advertises a Rasa service that does not exist, which works against §2.2. Sprint ticket **DPG-06** |
| 6 | Mechanism for data extraction | ✅ **Compliant** | PostgreSQL, documented schema in 3 migration streams, XLSX + PDF exports, REST APIs |
| 7 | Privacy & applicable laws | 🟠 **Partial** | Encryption and access control are built. **Missing:** legal assessment, data-flow diagram, and free-text PII leaves the country on every model call — ⚠ and with T2 parked that egress is now **permanent, not transitional** (§4.5) |
| 8 | Standards & best practices | ✅ **Compliant** *(2026-08-18)* | OpenAPI, OIDC/Keycloak, Alembic-migrated schema — **and the project hygiene files now exist**: `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `.github/ISSUE_TEMPLATE/` + PR template (DPG-05). Governance model + release/versioning deliberately deferred pending **Q10** ([followup](../sprints/2026-08-llm/followups/governance-and-versioning-policy.md)) |
| 9 | Do no harm by design | 🟢 **Mostly compliant** | RBAC, audit log, SEAH isolation, anonymous intake are built. Retention/breach policy and third-party-PII redaction outstanding |

**Two blockers, one of them ours:** indicator 3 is a signature we have to ask for; indicator 4 is
engineering we have already specced.

---

## 2. Where we already comply

### 2.1 Indicator 1 — Relevance to SDGs ✅

The platform is a Grievance Redress Mechanism for ADB-financed road infrastructure in Nepal
(KL Road / Kakarbhitta–Laukahi, ADB Loan 52097-003). It gives affected people a channel to raise
grievances in Nepali, by chat or voice, and gives implementing agencies a workflow with enforced
service-level deadlines and an escalation ladder up to a Grievance Redress Committee.

- **SDG 16.6** — effective, accountable and transparent institutions
- **SDG 16.10** — public access to information
- **SDG 9.1** — sustainable infrastructure with attention to affected populations

It also implements ADB's own Accountability Mechanism expectations, and a dedicated, access-isolated
SEAH (sexual exploitation, abuse and harassment) intake stream. **This indicator needs a page of
writing, not a change to the product.**

### 2.2 Indicator 2 — Open licensing: the dependency tree ✅ (the licence file itself is §3.1)

This is our strongest card and the reason we think DPG qualification is realistic. **There is no
proprietary component anywhere in the runtime stack.** Every layer is a permissively-licensed open
source project that a third party could self-host without a commercial relationship with anyone.

| Layer | What we use | Licence |
|---|---|---|
| Web frameworks | FastAPI, Uvicorn, Starlette, Pydantic v2 | MIT / BSD-3-Clause |
| Database | **PostgreSQL 15** | PostgreSQL Licence (OSI) |
| ORM & migrations | SQLAlchemy 2, Alembic (3 independent streams) | MIT |
| Task queue | Celery 5.5, Flower | BSD-3-Clause |
| Cache / broker | **Redis 8.10** (pinned minor) | **AGPLv3** at our election — Redis 8 is tri-licensed RSALv2 / SSPLv1 / AGPLv3; only AGPLv3 is OSI-approved. See §3.1(b) |
| Identity | **Keycloak 26** (OIDC + PKCE, self-hosted) | Apache-2.0 |
| Reverse proxy | nginx stable | BSD-2-Clause |
| Officer frontend | Next.js 16, React 19, Tailwind v4, lucide-react | MIT / ISC |
| Reports & documents | openpyxl (XLSX), ReportLab (PDF) | MIT / BSD-3-Clause |
| Images | pyvips / libvips | MIT / LGPL-2.1 (separate process, dynamic link) |
| Chatbot state machine | Hand-rolled; `rasa-sdk` used only for `Tracker`/`CollectingDispatcher` types | Apache-2.0 |
| Container orchestration | Docker Compose | Apache-2.0 |

Points worth making to a reviewer:

- **Identity is self-hosted, not federated to a vendor.** An earlier plan used AWS Cognito; we
  migrated to Keycloak during the build. That decision was made on other grounds but it removes what
  would have been a hard indicator-4 dependency at the authentication layer.
- **There is no Rasa server and no TensorFlow.** The conversational state machine is our own code.
  `rasa-sdk` (Apache-2.0) survives only as a type shim. An earlier assessment flagged Rasa's licence
  as a major risk; it is a non-issue.
- **The only ML dependency in the entire tree is the `openai` SDK** (Apache-2.0 — the *client* is open;
  the *service* it calls is not). See §4.
- **Full inventory in Appendix A.**

⚠ **Not yet mechanically verified.** The licences above are stated from the manifests and our
knowledge of the packages. The deliverable is a generated `pip-licenses` + `license-checker` report
committed as `docs/dpg/dependency-licenses.md`, wired into the existing scheduled `ops/security.py`
scan so it cannot go stale. That is one day of work (sprint ticket DPG-02) and we would rather show
the consultant the machine output than our assertion.

### 2.3 Indicator 5 — Documentation ✅

- `docs/` — a structured spec tree with per-domain indices ([`docs/README.md`](../README.md)):
  deployment runbooks, service contracts, ticketing product specs, chatbot architecture, SEAH privacy
  model, plus an [`engineering/`](../engineering/00_engineering_index.md) set that documents *how* the
  system is built (database rules, service-layer patterns, API conventions, testing pyramid,
  documentation lifecycle).
- **A portable starter kit** ([`docs/_starter_kit/`](../_starter_kit/README.md)) — the engineering
  standards, design system and copy guide stripped of anything project-specific, so another country
  team can reuse the method, not just the code. This is unusually good evidence for indicator 5 and
  we should point at it explicitly.
- `docs/deployment/DOCKER.md` — full build / migrate / seed / debug runbook. The whole stack (11
  services) comes up with Compose.
- **OpenAPI** served by both FastAPI apps (`/docs` on the ticketing API).
- **CI** with four gates: backend tests against real Postgres and Redis with all three migration
  streams applied, UI type-check + lint + unit + build, webchat tests, and a documentation link
  checker.

### 2.4 Indicator 6 — Data extraction ✅

- **All data in PostgreSQL**, no proprietary store. Schema is explicit and version-controlled through
  three separately-owned Alembic streams (`public.*` chatbot, `ticketing.*`, `ops.*`).
- **Non-proprietary exports already built:** quarterly XLSX reports (`ticketing/services/quarterly_report.py`,
  `report_export.py`), complainant case-closure PDFs (`closure_pdf.py`), and REST APIs over the whole
  domain.
- **No lock-in on file storage** — attachments are on the filesystem with a documented archive-tiering
  policy ([`docs/ARCHIVING_AND_RETENTION.md`](../ARCHIVING_AND_RETENTION.md)), not in a vendor bucket
  with a proprietary layout.
- `pg_dump` produces a complete, portable extract. Nothing about the data model requires our code to
  read it.

### 2.5 Indicator 8 — Standards & best practices 🟢

- **OpenAPI** for both HTTP surfaces.
- **OpenID Connect with PKCE** via Keycloak; JWT verification against JWKS.
- **UTC timestamps** with timezone throughout; UUID4 primary keys; Bikram Sambat dates presented in
  the UI where users expect them.
- **Documented architectural invariants pinned by tests** — e.g. the boundary policy that stops
  complainant PII being copied into the ticketing schema is enforced by a test that parses the
  architecture document and fails when code and document disagree
  (`tests/ticketing/test_boundary_policy.py`, `test_pii_boundary.py`). We think this is worth showing;
  it is the sort of thing that makes a "do no harm" claim checkable rather than aspirational.
- Missing: the open-source project hygiene files — see §3.4.

### 2.6 Indicator 9 — Do no harm 🟢

| Requirement | What is built |
|---|---|
| **9a — Data privacy & security** | PII encrypted at rest with pgcrypto, decrypted only server-side at a single boundary; the ticketing subsystem holds **no** encryption key and has no accessor for one (pinned by test); TLS in transit; Keycloak-authenticated officer access with a jurisdiction gate |
| **9b — Inappropriate content** | **Two independent detection paths, not one** — corrected 2026-08-17 after verifying the code. (i) A **deterministic, scored keyword detector** (`backend/shared_functions/keyword_detector.py:257`, scoring at `:342`) runs **synchronously as slot validation inside the conversation**, with no LLM involved; (ii) `detect_sensitive_content_llm` runs asynchronously on Celery as a second pass. So a model outage **degrades the second pass rather than removing detection** — which is also why the LLM leg's fail-open default is acceptable rather than a gap. An earlier draft credited only the LLM path and **understated this control** |
| **9c — Protection from harassment** | Anonymous grievance submission is supported end-to-end; the **SEAH workflow is access-isolated** — configurable by administrators who cannot themselves read the cases; four-tier admin ladder with scoped permissions; full `admin_audit_log` + per-ticket event timeline |

Outstanding for indicator 9: a written **retention and deletion policy** and a **breach procedure**
(both are documentation, gated on the privacy assessment), and **redaction of third-party PII before
model calls** (§4.3).

---

## 3. Gaps we know how to close ourselves

### 3.1 The licence file, and two dependency flags 🟠 (one now closed)

> ⚠ **And we would now like the licence choice itself confirmed by you (2026-08-17).** We had treated
> Apache-2.0 as decided; the project owner has referred the choice to you. So `LICENSE` is currently blocked on
> **two** external answers — which licence text (you) and which copyright holder (ADB OGC, Q1). Given that
> indicator 2 fails outright with **no** licence at all, **if you have no objection to Apache-2.0, saying so
> is the single cheapest unblock available on this list.**

**(a) The repository is public and has no `LICENSE` file.** Under default copyright that means
"all rights reserved" — visible source, no grant of rights. This is the single cheapest and most
urgent fix on the list, and it is arguably worse than a private repo because it invites use it does
not permit. Planned: **Apache-2.0** (chosen over MIT for its express patent grant, which matters when
a government adopts the code and other country teams fork it), plus `NOTICE` and SPDX headers.
**Blocked on indicator 3** — we cannot name a copyright holder until ownership is determined.

**(b) ✅ `redis:7` was a floating tag onto a non-OSI licence. Fixed — now pinned `redis:8.10`.**
Redis 7.2 and earlier are BSD-3-Clause; **Redis 7.4 and later are RSALv2 / SSPLv1, neither of which is
OSI-approved**, and our `docker-compose.yml` pinned only the major, so the tag silently followed
upstream onto that line. Nobody edited the file — the tag moved underneath it. We surfaced this while
writing this document; it was not in our sprint plan.

**Redis 8 is tri-licensed — RSALv2 *or* SSPLv1 *or* AGPLv3 — and the licensee elects.** We elect
**AGPLv3, the one OSI-approved option of the three**, and that is what answers indicator 2. Worth
stating explicitly, because a reviewer who remembers the 2024 relicensing may see "Redis 8" and assume
the source-available terms still apply.

The fix is cheap, and it is worth showing why rather than asserting it. We audited what we actually
ask Redis to do: `PING`, `INFO memory`, `LLEN`, `GET`, `SET … EX`, one redis-py mutex, and pub/sub for
Socket.IO and the Celery broker. **No modules** (JSON, Search, TimeSeries, Bloom), no Streams, no
cluster mode — and **no persistence volume is declared**, so the broker and cache are entirely
ephemeral. Redis is a network service behind a process boundary: we neither link it nor modify it, and
there is no stored dataset to migrate.

⭐ **Done: `redis:8.10` in both `docker-compose.yml` and the CI service definition.** Redis 8 needs no
renaming, no runbook churn and no operational retraining — the binaries are still `redis-server` /
`redis-cli` — and it keeps the Docker Official Image provenance chain, which matters for a deployment
on Government of Nepal infrastructure. AGPLv3 imposes nothing on this repository's own licensing, or on
a downstream fork's: we run an unmodified upstream image as a separate service and convey no Redis
source. The image is ~55 MB compressed, so the bundled Redis 8 data structures cost no meaningful host
capacity.

**We pinned the minor (`8.10`), not `redis:8`,** because the *shape* of this finding was a floating tag,
not Redis specifically: a two-segment pin still receives patches, but a future relicence becomes
something we opt into rather than something that arrives on the next `docker pull`. Redis ships minors
quickly and 8.10 drops to security-only maintenance when the next one lands; if the agency later wants
a longer stable window over current features, **Redis 8.2 carries security support to September 2030**
and is the same licence election. Either is defensible; the floating tag was not.

**If AGPL is flagged, the fallback is Valkey** (BSD-3-Clause, the Linux Foundation fork,
protocol-compatible with the 7.2 line our command set comes from). That cost is small but real: four
call sites hardcode `redis-server` / `redis-cli` (the Compose command and its healthcheck, the CI
service healthcheck, and `scripts/ops/host_watchdog.sh`), roughly ten runbook references would need
updating, and `valkey/valkey` is community-published rather than a Docker Official Image. We would
rather not pay that speculatively. **Ruled out:** pinning `redis:7.2` — BSD-3-Clause, but an
end-of-life line we would have to revisit anyway. See **Q7**.

**(c) `psycopg2-binary` is LGPL-3.0-with-exceptions.** Copyleft, but library-level with a linking
exception and standard practice across the Python ecosystem. We do not expect this to be an issue; we
raise it so the consultant can tell us if the DPGA reads it differently (Q7).

### 3.2 Indicator 3 — Ownership 🔴 **the hard blocker**

Indicator 3 is categorical: a DPG must have clear, documented ownership. Parts of this platform were
developed in the context of an ADB-financed engagement. **If the IP vests in ADB, or is jointly held,
it may not be ours to license.** No amount of engineering resolves this — it needs a written
determination from ADB's Office of the General Counsel, and it has the longest lead time of anything
on this list.

It blocks: the `LICENSE` file's copyright holder, the `NOTICE` file, and the submission itself. It
blocks **no code work**, which is why we are proceeding with the engineering in parallel.

**This is the single most valuable thing the consultant can help us with** — see Q1–Q3.

### 3.3 Indicator 5 — Deployability warts 🟡

Documentation is strong; *reproducibility by a stranger* has rough edges we should fix before a
reviewer clones the repo:

- `backend/services/LLM_services.py:25` calls `load_dotenv('/home/ubuntu/nepal_chatbot/.env')` — a
  hard-coded absolute path from the original AWS host. Harmless in Docker, but it reads as
  machine-specific to anyone evaluating portability.
- **Correction (2026-08-17):** an earlier draft of this section said *"No `.env.example`"*. **It exists**
  — 5,982 bytes, tracked, with `OPENAI_API_KEY=` at `:61`. The real gap is narrower and still worth fixing:
  it documents the **key** and nothing about the endpoint or the model names, so a stranger cannot tell from
  it that the provider is configurable — because today it is not. DPG-16 replaces that single line with the
  full configuration surface.
- The root `README.md` is stale in a way that **works against §2.2 of this document**: it names
  `feature/grm-ticketing` as the active branch, describes intake as "Rasa + FastAPI" (`:6`), and carries a
  **service-table row for "Rasa | Rasa 3 | 5005 | NLU + dialogue"** plus an Action Server on 5055 (`:46-47`),
  with `rasa_chatbot/` in the folder tree (`:76`). We argue below that there is no Rasa server; the repo's
  front page says there is one, with a port number. A reviewer who notices that stops trusting the licence
  section. Now sprint ticket **DPG-06**, and it should land before the consultant meeting.

### 3.4 Indicator 8 — Open-source project hygiene 🟡

Absent — verified at the repo root: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md` (vulnerability
disclosure), `.github/ISSUE_TEMPLATE/`, PR template, public roadmap. All cheap, and now sprint ticket
**DPG-05** (added 2026-08-17 — no ticket covered this before the audit).

**`SECURITY.md` is the one that is not boilerplate here.** This platform holds SEAH disclosures, so a
disclosure route that tells a finder to open a public GitHub issue is the wrong answer: it needs a private
channel, a named recipient, a response window, and an explicit scope boundary (the platform is in scope;
the grievances are not — a researcher must not go fishing in production data). **Q10** asks which of the
rest the DPGA actually requires versus merely likes; we plan to ship the cheap uncontroversial set now and
defer the governance model and a release/versioning policy until you answer, since those carry real process
commitments.

### 3.5 Indicator 7 — Privacy 🟠

> ✅ **UPDATED 2026-08-18 — the assessment and the diagram now exist**:
> [`privacy-assessment.md`](privacy-assessment.md) (DPG-04). Thirteen data-flow legs verified at file
> and line, an Individual Privacy Act 2018 assessment, and a **17-item findings register**.
> ⚠ It carries a mandatory honesty marker — drafted by an AI agent, **no legal review** — and three of
> its findings were **previously unknown**: encryption at rest **fails open** when `DB_ENCRYPTION_KEY`
> is unset or pgcrypto raises; the `*_hash` search tokens are **unsalted SHA-256** of phone/email/name/
> address, so the phone hash is reversible and those columns are personal data rather than pseudonyms;
> and backups are **unencrypted by default**. **This indicator stays 🟠, not 🟢** — the document is
> written, the gaps it names are not closed.

Built: encryption at rest and in transit, single-boundary server-side decryption, an architecturally
enforced PII boundary, scoped officer access, reveal-contact actions written to an audit log.

Still missing after the assessment — and now specific rather than general:

- ~~A formal assessment against Nepal's Individual Privacy Act 2018~~ ✅ **written**; **a legal review
  of it is not**, and the document says so at the top.
- ~~A data-flow diagram~~ ✅ **written**, and DPG-30 will verify it against the code.
- **Retention and deletion policy** — ⚠ sharper than we thought: archiving is implemented and is **not**
  deletion. [`ARCHIVING_AND_RETENTION.md`](../ARCHIVING_AND_RETENTION.md) §5.3/§10 put hard delete out of
  scope for v1, so **no code path deletes personal data anywhere in this platform**. That needs a legal
  position, not a document.
- **A breach procedure** — ⚠ and `SECURITY.md` now promises reporters that one will be followed, so it
  is a promise made against a procedure that does not exist yet.
- **The live gap: grievance narratives leave Nepal on every model call**, unredacted, to a third-party
  provider. See §4.3 — the same finding as indicator 4, seen from the privacy side. ⚠ **And it is now
  permanent rather than transitional:** with self-hosting parked (§4.5), the provider changes and the
  cross-border transfer does not. That raises the bar on the assessment: it has to justify an indefinite
  arrangement, and redaction stops being defence-in-depth and becomes the control.

---

## 4. The LLM question — how we query models today, and what we want to change

This is the substance of the meeting. **For AI systems the DPG Standard's platform-independence
questionnaire asks about the code, the model *and* the data**, and the requirement is specific:

> When the digital public good has mandatory dependencies that create more restrictions than the
> original license, proving independence from the closed component(s) **and/or indicating the existence
> of functional, open alternatives that can be used without significant changes to the core product**
> is required. […] demonstrate that these closed component(s) can be replaced with those open
> alternatives **with minimal configuration changes, without requiring a major overhaul of the entire
> system.**

Our reading — which we still want confirmed (**Q4**) — is that **the Standard does not require us to run
open models in production. It requires us to demonstrate that we could, with a configuration change.**

✅ **Decided 2026-08-17, and it makes the question easier rather than harder: we intend to run the open
configuration in production anyway** — on cost grounds, with the commercial provider retained as a
configurable fallback if government users report quality problems. So whichever way Q4 is answered, we expect
to satisfy the stricter reading. We would still like the answer, because it determines how much benchmark
evidence the submission needs before we can claim it.

### 4.1 Exactly how we query LLMs today

**Nine** call sites, six distinct models, **two independent subsystems**, and **not one of them reads a
configurable endpoint or model name**. Every model string is a Python literal. (An earlier draft said
eight: the table below merges the two ticketing findings/summary calls into row 8. Verified by
`grep -n "\.create(" ` — six in `LLM_services.py`, three in `ticketing/clients/llm_client.py`.)

| # | Subsystem | Function | Model (hard-coded) | What data is sent to the provider |
|---|---|---|---|---|
| 1 | chatbot | `transcribe_audio_file` — `LLM_services.py:45` | `whisper-1` | **Raw complainant voice recording.** ⚠ **This path is not live** — voice transcription is switched off for lack of inference budget, so no audio is currently sent. It also means we have **no baseline** to benchmark open ASR against, and a suspected SDK-argument bug on this path has never been exercised in the field |
| 2 | chatbot | `extract_contact_info` — `:77` | `gpt-3.5-turbo` | **Complainant name and phone number**, free text |
| 3 | chatbot | `extract_all_contact_info` — `:114` | `gpt-3.5-turbo` | As above |
| 4 | chatbot | `classify_and_summarize_grievance` — `:230` | `gpt-5-nano` | **Full grievance narrative** + district + province |
| 5 | chatbot | `translate_grievance_to_english_LLM` — `:322` | `gpt-4` | Full grievance narrative |
| 6 | chatbot | `detect_sensitive_content_llm` — `:383` | `gpt-3.5-turbo` | Grievance text, including potential SEAH disclosures |
| 7 | ticketing | `translate_to_english` — `llm_client.py:88` | `gpt-4` | **Officer case notes**, verbatim |
| 8 | ticketing | `generate_case_findings`, `generate_resolved_case_summary_llm` — `llm_client.py:167, 259` | `gpt-4o-mini` (standard) / `gpt-4o` (SEAH) | **Whole case timeline**, including SEAH cases |

Four things follow from this table that we should be candid about:

1. **There are two LLM surfaces and four files, not one file.** `ticketing/clients/llm_client.py` is a
   second, independent OpenAI client with its own settings object and its own hard-coded models. Any claim
   about platform independence is a claim about the whole product — a reviewer who redirects one and finds
   the other still calling `api.openai.com` has found a false statement in our submission.
   **And two further modules keep their own copies of the model names**, which is worse than untidy:
   `ticketing/services/resolved_summary_builder.py:299` writes a model name into the **stored** resolved-case
   summary as `llm.model`, computed from a duplicated constant in a different module from the one that made
   the call. Change the client and miss that file and every resolved case records a model that never ran it —
   a grievance mechanism publishing false provenance. Our answer is **two client factories but one config
   file** (`backend/config/llm_config.py`, sprint ticket DPG-17): every model name, endpoint and timeout
   declared once, with a test that a single `LLM_BASE_URL` change moves both surfaces. Without that, the
   indicator-4 claim is a promise made in two places that can drift apart silently.
2. **`OpenAI(api_key=…)` is constructed with no `base_url` anywhere.** The OpenAI Python SDK accepts a
   `base_url`, and most open-weights serving stacks (vLLM, Hugging Face Inference Providers, Together,
   Fireworks) expose an OpenAI-compatible API. **The fix is genuinely a configuration refactor, not a
   rewrite** — which is exactly the "minimal configuration changes" the Standard asks about. We are not
   asking for credit for work we have not done, but we are also not facing an architectural overhaul.
3. **Structured output is done two different ways, and one of them is fragile.** Five call sites use
   `response_format={"type": "json_object"}`; the classification call — the primary AI path in the
   product — uses neither, and simply instructs the model to return JSON in the prompt. Prompt-only
   JSON is the least portable choice available: it is precisely what breaks when you change models.
   Moving to schema-constrained decoding with server-side validation is on our list (DPG-13) and it
   *improves* portability rather than trading it away.
4. **The AI paths are already fail-soft, which lowers the risk of switching providers.** Intake writes
   the grievance to Postgres *before* any model call; classification runs as a Celery task with retry
   and explicit `LLM_FAILED` / `LLM_SKIPPED` status codes; the chatbot waits on a bounded 20-second
   deadline rather than indefinitely. A grievance is never lost because a model was unavailable. This
   matters for the open-model conversation: a model that is occasionally slower degrades throughput,
   not intake.

**And the thing we are least comfortable with:** there is **not a single automated test** covering
either LLM surface. Zero. So the first ticket of this work is a characterization-test net, before any
refactor. We mention it because it also means our current claims about model behaviour rest on manual
observation, not on evidence we could hand a reviewer.

### 4.2 The three closed dependencies, named precisely

| Closed component | Where it binds | Open alternative | Confidence |
|---|---|---|---|
| **Inference API** (`api.openai.com`) | 9 call sites, no configurable base URL | Any OpenAI-compatible endpoint — self-hosted vLLM, or a hosted open-weights provider | **High.** Well-trodden; the SDK supports it directly |
| **Model weights** (`gpt-4`, `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo`, `gpt-5-nano`) | Same call sites | Apache-2.0 / MIT open-weights instruction models in the 27–31B class, 4-bit quantised | **Medium.** Portable in principle; **unmeasured on Nepali** — see §4.4 |
| **ASR** (`whisper-1`, hosted) | Voice intake, 1 call site | Whisper large-v3 weights (MIT) self-hosted, or newer open multilingual ASR | **Medium-low.** Weights are open, but **Nepali word-error rates are poor across the board**, including for the hosted model we use today |

There is a fourth dimension the questionnaire raises that we want to discuss (**Q5**): **data**. We do
no training and no fine-tuning — every call is zero-shot prompting with instructions and a category
taxonomy we author. So we have no training-data licence question at all. What we *lack* is an
evaluation set, which is what we would need to substantiate any quality claim about a swap.

### 4.3 The privacy dimension of the same problem

Indicators 4 and 7 meet here. Today, every grievance narrative, every extracted name and phone
number, every officer note and — in the SEAH path — content that is sensitive by definition, is
transmitted to a third-party US provider, unredacted. Additionally, nothing redacts model inputs or
outputs on the logging path, so grievance text can reach application logs and Celery payloads in Redis.

Two clarifications, because the two problems are often conflated:

- **Structured PII at rest is solved.** Name, phone, email and address are encrypted, decrypted at one
  server-side boundary, and architecturally barred from the ticketing schema by tests. That work is done.
- **Free-text egress to third parties is not.** A complainant writes "the site engineer Ram Bahadur
  refused to…" into a narrative field, and that name is in the payload. No amount of column-level
  encryption addresses it.

Our plan is a redaction layer at the model-call boundary — deterministic patterns first (Nepali phone
formats, Devanagari digits, citizenship and vehicle numbers), then NER — with measured recall published
rather than asserted.

**✅ We have decided the design question we had flagged (Q8): redact at transmission, not before storage.**
The officer handling the case still needs to see which official was named — for a GRM, complaints naming
officials are a large share of the useful ones, and redacting before storage would destroy the record's
evidentiary value. The full record stays; a redacted derivative goes to models and logs. **We would still
like to know whether that conflicts with any position you or ADB safeguards hold** — if the agency's legal
view is that PII must not be *stored* in free text at all, that is a much larger change than the sprint.

**⚠ And one gap we are choosing to leave open in the first pass, which we would rather state than have you
find.** Person-name detection needs an ML model; the Nepali NER model with the best published accuracy has
**no licence stated** on its model card, so shipping it would swap one closed dependency for another inside
the very submission meant to remove it (**Q9**). We have therefore split the work:

- **Landing now:** the deterministic layer — Nepali phone formats in **both** digit systems (Devanagari
  digits defeat an ASCII regex, and `९८४१२३४५६७` is a phone number in plain text), citizenship numbers,
  vehicle registrations, emails, and full address spans (settlement qualifiers such as *gaun*, *tole*,
  ward numbers — while leaving the bare district, which the classifier needs). Plus redaction of the
  logging, Celery and backup paths, which is where leaks actually happen.
- **Also landing now — person names, at the rule layer.** An earlier draft of this section said names
  were deferred entirely. That was wrong. Three recognisers ship without any ML dependency:
  **honorific and role-title triggers** (`Er.`, Engineer, overseer, contractor, ward chairperson, `श्री`),
  which catch the *named official* — the sharpest exposure, since that person consented to nothing;
  a **Nepali family-name (thar) gazetteer**, tractable because surnames are a comparatively closed set;
  and **self-identification patterns** (*"my name is …"*, `मेरो नाम … हो`), which catch the opening line the
  voice channel all but guarantees.
- **⚠ What still gets through, stated as a residual rather than rounded away:** a name with no title, no
  recognisable surname and no self-identification frame. *"The man operating the roller"*, named in passing
  three sentences later, is the shape of the miss. Higher recall needs the ML model whose licence is
  unresolved (Q9). **We will publish the measured residual, not a description of it** — and because T2 is
  parked, that residual reaches a third party indefinitely rather than during a transition, which is why
  §4.3a sets out whose terms it lands under.
- **The intended fix, and it may interest ADB beyond this project:** fine-tune a Nepali NER model on an
  openly-licensed corpus, **release it openly**, and run it as a standalone anonymiser service usable by
  any country programme where in-country self-hosting is impossible. Permissively-licensed Nepali NLP
  tooling barely exists, so that would be a genuine DPG *contribution* rather than only a compliance fix.
  **Q9** asks whether you would see it that way and whether there is appetite to fund it.

#### 4.3a Whose terms the residual lands under

**Two framing corrections first, because we had them wrong too.**

**Openness is a licensing property, not a privacy property.** The open-weights migration answers
indicator 4 and does nothing for indicator 7 — an open model served by a third party carries the same
data-flow risk as a commercial one. The two problems share an eventual solution (self-hosting) but T1
solves only the first.

**The legal trigger was never model training.** Under Nepal's Individual Privacy Act 2018 and GDPR-style
regimes, transmitting personal data to a third party **is itself a disclosure and a cross-border
transfer**. Whether the recipient stores it, trains on it or discards it immediately does not change that
a transfer occurred and requires a lawful basis. Non-retention mitigates; it does not answer.

**Hugging Face's actual commitments** — from
[Inference Providers → Security & Compliance](https://huggingface.co/docs/inference-providers/en/security),
and better than an earlier draft of this document assumed (it cited the general privacy policy, which has
no inference-specific clause, and understated them):

> *"Hugging Face does not store any user data for training purposes. We do not store the request body or
> response when routing requests through Hugging Face. Logs are kept for debugging purposes for up to 30
> days, but no user data or tokens are stored."*

Plus TLS/SSL in transit, and the Hub — of which Inference Providers is a feature — is **SOC 2 Type 2
certified**. Genuinely usable in the assessment.

⚠ **Then the sentence that matters, and it is theirs:** *"External providers are responsible for their own
security measures, so please refer to their respective security policies."* **The no-storage commitment
covers the router, not the company that runs the model.** Requests are proxied to third-party partners —
Cerebras, Groq, Together, Fireworks, Novita, DeepInfra, Replicate, Scaleway, OVHcloud — with the default
policy choosing the fastest available *per request*. For a government privacy assessment, **"we cannot name
which company processed this citizen's grievance" is a finding, not a footnote.**

The **Terms of Service** reference no DPA and frame confidentiality around private repositories rather than
inference traffic. For a router architecture a DPA is awkward by construction: one would be needed from
Hugging Face *and* from each downstream provider — which is an underrated practical argument for
self-hosting, where there is one cloud contract and a standard DPA.

**Our fix:** pin one named provider (`model:provider`) in production so DPG-04 can assess that company's
terms and location, while CI keeps automatic routing because it sends only synthetic benchmark data.
**What remains even then** — and belongs in the data-flow diagram: the provider's own retention (commonly
~30 days, some reserving service-improvement use absent an opt-out), the jurisdiction of execution, and
prompt caching. Whether ADB requires a signed DPA on top is **Q16**.

We should also be honest that one of our own documents currently claims summaries are PII-scrubbed
before storage, and nothing scrubs them. It is on our list to fix the document
(`docs/deployment/11_llm_pipeline_policy.md`). We flag it here because we would rather the consultant
hear it from us than find it.

### 4.4 What we do not know, and will not claim

We would rather bring the consultant honest unknowns than optimistic estimates:

- **Nepali quality on open weights is unmeasured — by us and largely by the field.** Nepali is
  low-resource. We have no benchmark set and no numbers, so any statement that an open model is
  "close enough" on grievance classification would be invention. Building the labelled set is the
  long pole of this work and it is data effort, not engineering.
- **Nepali ASR is the weakest link, and it is weak for the closed model too** — and ⚠ **we have to disclose
  that voice transcription is not currently running at all.** It is switched off for lack of inference
  budget, which means **we have no incumbent baseline to compare open ASR against.** If we ship an open
  ASR path, the honest framing is *"we shipped a working voice path where there was none"*, not *"we matched
  the incumbent"*. If open-weights ASR turns out materially worse, the options are (a) accept documented
  degradation on voice while text stays at parity, (b) keep ASR hosted and disclose it as a remaining
  closed dependency, or (c) fund a Nepali fine-tune on the 165 openly-licensed hours of OpenSLR SLR54.
  **Q6** asks how the DPGA treats a *partial* open alternative — one that works but performs worse.
- **Translation may want a specialist model.** A purpose-built seq2seq translation model will likely
  beat a general chat model on Nepali↔English, but it needs its own service rather than a chat
  endpoint. That is a real deployment cost, and the benchmark should decide it, not our prior.
- ~~**Whether production actually switches.**~~ ✅ **Decided 2026-08-17: it does.** Production will run the
  open configuration, on cost grounds, with the commercial provider retained as a configurable fallback if
  government users report quality problems. **What we still do not know is the quality gap** — that is the
  benchmark, and the benchmark needs Q15's inference budget to run.

### 4.5 The deployment ladder — one variable changes

Nepal cannot host GPUs: no machines, no operations staff, and power reliability makes on-premises a
liability. We take that as a fact to design around, not to argue with. The distinction that opens the
path is that **self-hosting the software is not the same as hosting the hardware.**

| Tier | What it is | Who can see grievance text | Role |
|---|---|---|---|
| **T1** ⭐ | Hosted open-weights inference API | The inference provider | Development, CI, **DPG evidence** — **and production**, as of 2026-08-17 |
| **T2** | vLLM on a rented GPU VM under the agency's own contract | Nobody outside the agency's contracted infrastructure | ⏸ **Parked** — documented and costed, not deployed |
| **T3** | On-premises, inside the ministry | Nobody | Not Nepal. Plausible for other country programmes |

**The only thing that differs between the three is the base URL.** That is both the engineering goal
and the indicator-4 answer.

> **⚠ T2 is parked, and we would rather tell you why than present a target we are not funding.** The two
> decisions this needed — jurisdiction and *who pays for the running instance* — are the same decision, and
> the second has no answer today. **A GPU instance with no named budget line is the Babyl failure mode**, so
> we are not starting one. The best case remains ADB financing subcontractor-managed instances leased to
> member countries under a TA with the Ministry of Finance; that is a procurement conversation, and
> `docs/dpg/vllm-deployment.md` will keep the design and the price current so it can be taken as one.
>
> **The consequence we want to be explicit about:** T1 is therefore the **steady state**, not a transition.
> Grievance text will be processed by a third-party provider **indefinitely**. That does not change the
> indicator-4 answer — a hosted open-weights provider is still an open alternative, and we will be running
> it — but it **does** change the privacy analysis in §4.3 from a transitional exposure to a permanent one,
> and it makes the redaction work the only remaining control rather than a defence in depth. We would rather
> you hear that framing from us.

Indicative T2 sizing — one 24 GB GPU instance (AWS `g5`/`g6.xlarge` class) serving one 27–31B model at
4-bit quantisation, co-hosting a Whisper-class ASR model, roughly **$700–900/month** on demand and
materially less with a one-year commitment. ⚠ **Unverified against this deployment's actual volumes.**
Note that a GRM's load is intake-shaped and bursty around road works and public meetings, not
chat-shaped: classification is one request per grievance, not one per conversational turn. We will size
against measured volumes.

The two T2 decisions we had flagged are **answered by parking it** — but both stay live for the day it is
unparked, and one of them has become a different, smaller ask:

- **Jurisdiction (Q11).** Moot while T2 is parked. The analysis stands for later: AWS Mumbai
  (`ap-south-1`) is the obvious latency choice but is still a cross-border transfer from Nepal, and
  Nepal–India data flows carry a political sensitivity Singapore (`ap-southeast-1`) does not.
- **Who operates and who pays (Q12).** No answer today, which **is** the answer: we are not starting an
  instance nobody funds. **The gate condition worked.**
- ⚠ **A smaller ask that has become the live one instead — see Q15 below.** With T2 parked we do not need a
  GPU budget; we need a **metered inference budget** for benchmarking and CI, which is two orders of
  magnitude smaller and is the thing currently blocking our indicator-4 *evidence* rather than our
  indicator-4 *answer*.

### 4.6 What we will be able to show, and when

Sequenced deliberately so that nothing is claimed before it is true:

| Evidence for indicator 4 | Status |
|---|---|
| `LLM_BASE_URL` + `MODEL_*` configuration across **both** LLM surfaces, no code change | Specced, not built |
| An open-weights configuration as the **repository default**, documented | Specced — **deliberately sequenced into Sprint 2, not Sprint 1.** Flipping the base URL to an open router while the model names are still `gpt-3.5-turbo` / `whisper-1` would ship a default configuration that answers **no** request: a reviewer who clones and runs gets a 404, which is weaker evidence than an honest proprietary default. The flip lands as one edit to DPG-17's single config file once the benchmark has named the open models |
| **CI running the full LLM test suite against the open configuration on every commit** | Specced — the strongest single piece of evidence we can offer, because it cannot silently rot. ⚠ **It is also the only *recurring* inference cost in the plan, and we have no inference budget** (see Q15). We will cap it to a small live subset with a hard token cap; if even that is unaffordable we will run it nightly plus on release tags and **say so on the badge** rather than let a job exist that never runs |
| Published benchmark table, open vs closed, on a labelled Nepali set | Specced — needs the benchmark set built first (**synthetic in phase 1**; no labeller budget, so it grows with the live project). ⚠ **Unpriced inference** — see Q15. And **ASR has no baseline column**: voice was never live |
| A documented, **costed** vLLM (T2) deployment | Specced — ⏸ **not deployed, T2 parked.** The end-to-end test against a live endpoint is a logged deferral, not a silent omission |

We will not paste an indicator-4 answer into a submission until the CI job is green. A submission that
overstates deployment is worse than one that understates it.

✅ **And one line of it got stronger, not weaker.** We had planned to argue *demonstrated replaceability*.
Since production will now run the open configuration on cost grounds, we can argue the thing itself — we will
be **running** the open alternative, with the commercial provider retained as a configurable fallback. That is
more than indicator 4 asks for, and it is the sentence we would lead with.

---

## 5. Questions for the consultant

Grouped by what the answer unblocks. 🔴 = we cannot finish the work without it.

### Ownership and process

- **Q1 🔴 — Does ADB have a standing IP position for software developed under a loan-financed
  engagement, or is this determined case by case?** Who is the right signatory, and what is a
  realistic timeline? This blocks our `LICENSE` file and the submission itself.
- **Q2 — Are there precedents?** Has ADB nominated software as a DPG before? What did the ownership
  determination look like, and can we reuse its shape rather than starting from a blank page?
- **Q3 — Who submits?** Does ADB nominate, or do we self-submit with ADB endorsement? Does the
  implementing agency (DOR) need to be a party, given that production will run on DOR infrastructure
  at `grm-chatbot.dor.gov.np`?

### Indicator 4 for AI systems — the substance

- **Q4 🔴 — Is our reading of indicator 4 correct?** Specifically: is a configurable
  OpenAI-compatible endpoint, plus a tested open-weights default, plus CI proving both configurations
  pass the same test suite, sufficient — *even if production continues on a commercial provider*? Or
  does the DPGA expect the deployed system to run open weights?
- **Q5 — How does the DPGA treat "open weight" models whose licences are not OSI-approved?**
  Several strong multilingual models ship under bespoke community licences with use restrictions
  (Llama, Gemma). Do those count as open alternatives for indicator 4, or must the alternative be
  Apache-2.0 / MIT? We are currently filtering for Apache-2.0 or MIT to be safe, which narrows the
  field and may cost us quality on Nepali. **How much does that filter matter?**
- **Q6 — How does the DPGA treat a *partial* open alternative?** If open-weights ASR works for Nepali
  but at a materially higher word-error rate, is "functional, with documented degradation" an
  acceptable answer, or does the alternative need parity? This determines whether we can keep voice
  intake at all in an open configuration.
- **Q7 — Two dependency-licence readings, one of which we have already decided.** (a) Redis 7.4+ is
  RSALv2/SSPLv1, consumed by us as a network service behind a process boundary rather than as a linked
  library. **We have moved to `redis:8.10`, elected under AGPLv3 (OSI-approved)** — see §3.1(b). Our
  question is
  narrow: **does AGPLv3 anywhere in the stack cause a problem** for you, for the DPGA assessment, or
  in ADB / DOR procurement review? If it does, we will switch to Valkey (BSD-3-Clause) instead — we
  simply prefer not to pay the renaming and retraining cost speculatively. (b) Is `psycopg2-binary`'s
  LGPL-with-exceptions an issue for a permissively-licensed DPG?
- **Q5b — The "data" limb of the AI questionnaire.** We do no training or fine-tuning; every call is
  zero-shot prompting. Does that dispose of the data question, or does the DPGA expect us to publish
  an evaluation set and prompt templates as artefacts?

### Privacy

- **Q8 — Redaction posture: we have decided, and we want to know if it conflicts with anything you hold.**
  ✅ **We redact at transmission, not before storage** — the officer needs to see which official was named,
  and redacting before storage destroys the record's evidentiary value. **Does the DPGA or ADB safeguards
  policy take a contrary position?** If the requirement is that PII must not be *stored* in free text at
  all, that is a far larger change than the sprint and we would want to know now rather than later.
- **Q9 — The NER recursion.** The most accurate Nepali NER model we have found has **no licence
  stated** on its model card. Shipping it would swap one closed dependency for another, inside the
  very submission meant to remove it. Our fallback is to fine-tune our own on an openly-licensed
  corpus and **release it openly** — which would itself be a genuine DPG contribution, since
  permissively-licensed Nepali NLP tooling barely exists. **Would the DPGA see that as a positive, and
  is there ADB appetite to fund it?**
- **Q11 — Hosting jurisdiction. ⏸ Moot for now — self-hosting is parked (§4.5)**, so there is no instance
  to place. We keep the question on the list because it returns the day it is unparked, and because the
  *provider's* jurisdiction is now a permanent question rather than a transitional one.
  Does the DPGA have any position on cross-border hosting for a
  national-government DPG, beyond compliance with local law? Practically: does anything in the
  Standard prefer Singapore over Mumbai, or is this purely a Nepal legal question?

### Scope and sequencing

- **Q10 — Which project-hygiene artefacts are actually required** versus merely recommended?
  `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue templates, public roadmap,
  release tags and versioning, governance model. We would rather build the required set once than
  guess and iterate.
- **Q12 — Sustainability, and it has already bitten us.** Does the DPG assessment look at who funds and
  operates the system after the pilot? We believe it should — and we are living the answer: **we parked
  self-hosted inference precisely because no run-cost owner exists** (§4.5). That is the Babyl failure mode
  avoided by not starting, and we would like to use the DPG process as leverage for a named budget line.
  ⚠ **Note the ask has changed shape, not just size:** with T2 parked we no longer need a GPU budget; we need
  a small **metered inference** budget to produce the evidence at all. See **Q15**.
- **Q13 — Sequencing.** Can we begin the assessment process with indicator 4 in progress and the CI
  evidence not yet green, or should we complete the engineering first? A rough timeline for the
  assessment itself would help us schedule the sprints against it.
- **Q14 — Is there anything in the current DPG Standard revision, or in the AI-systems guidance
  specifically, that we have missed by reading the published Standard and questionnaire?**
- **Q15 🔴 — Can ADB fund a small *metered inference* line, and how much evidence does the submission
  actually need?** This is the one ask that currently blocks work rather than paperwork.
  **Today we have no inference budget at all** — enough for a few classification calls a day, which is why
  voice transcription is switched off. Three deliverables in §4.6 are made of inference calls: the ASR
  evaluation, the text benchmark, and the CI job that runs on every commit forever.
  **The amounts are small.** A few hundred short synthetic texts across a handful of candidate models on
  per-token pricing is plausibly tens of dollars, not thousands, and the CI job can be capped. **This is two
  orders of magnitude below the T2 GPU we have just parked**, and unlike that instance it has a defined end
  point for the benchmark and a hard cap for CI. Two questions inside it:
  1. **Is a metered inference line something ADB can fund as part of the DPG work itself?** The evaluation
     exists to substantiate a claim in an ADB-endorsed submission.
  2. **How much benchmark evidence does the submission actually require?** If a smaller published table on a
     synthetic set is sufficient, our cost falls again — and we would rather scope to what is needed than
     measure expansively and publish late.

---

## Appendix A — Full dependency inventory

✅ **Superseded 2026-08-18 — see [`dependency-licenses.md`](dependency-licenses.md)** (DPG-02), the
generated audit over 153 packages in four dependency sets, produced in-container from the resolved
trees. The tables below are the readable summary and are kept for that; where they differ, the
generated report is authoritative. It found two transitive LGPL dependencies this list does not
mention, and a licence contradiction in our own npm manifest.

### Python — chatbot stack (`requirements.txt`)

| Package | Purpose | Licence |
|---|---|---|
| `fastapi` | Orchestrator + backend API | MIT |
| `uvicorn` (<0.50, pinned) | ASGI server | BSD-3-Clause |
| `pydantic` v2 | Validation | MIT |
| `python-multipart` | Uploads | Apache-2.0 |
| `pyyaml` | Config | MIT |
| `email-validator` | Validation | CC0-1.0 |
| `python-socketio` | WebSocket bridge | MIT |
| `rasa-sdk` 3.6.2 | `Tracker` / `CollectingDispatcher` types only | Apache-2.0 |
| `psycopg2-binary` | Postgres driver | ⚠ LGPL-3.0-with-exceptions |
| `SQLAlchemy` 2 / `alembic` | ORM / migrations | MIT |
| `pytz` | Timezones | MIT |
| `redis` (client) | Broker client | MIT |
| `celery` 5.5 / `flower` | Task queue / monitor | BSD-3-Clause |
| `boto3` | AWS SNS SMS + SES | Apache-2.0 |
| **`openai` 1.70.0** | **The one ML dependency — client only** | Apache-2.0 |
| `requests` / `httpx` | HTTP clients | Apache-2.0 / BSD-3-Clause |
| `pyvips` | Image compression (libvips) | MIT |
| `python-dotenv` | Config | BSD-3-Clause |
| `rapidfuzz` | Fuzzy matching | MIT |
| `langdetect` | Language detection | Apache-2.0 |
| `icecream` | Debug | MIT |
| `Flask` / `Werkzeug` / `flask-socketio` | Legacy blueprints; production is FastAPI | BSD-3-Clause / MIT |

### Python — GRM ticketing and ops (`requirements.grm.txt`)

| Package | Purpose | Licence |
|---|---|---|
| `pydantic-settings` | Config | MIT — ⚠ **moves to `requirements.txt`** under DPG-17, since the shared LLM config module is on the chatbot surface too |
| `openpyxl` | Quarterly XLSX reports (deliberately no pandas) | MIT |
| `python-jose[cryptography]` | Keycloak JWT / JWKS verification | MIT |
| `python-keycloak` | Keycloak Admin API | MIT |
| `reportlab` | Case-closure PDFs | BSD-3-Clause (open-source edition) |
| `apscheduler` | Broker-independent ops scheduler | MIT |
| `pip-audit` | Scheduled CVE scan | Apache-2.0 |
| `pytest` | Tests | MIT |

### Frontend (`channels/ticketing-ui/package.json`)

| Package | Licence |
|---|---|
| `next` 16.2.6 | MIT |
| `react` / `react-dom` 19.2.4 | MIT |
| `lucide-react` | ISC |
| `tailwindcss` v4 + `@tailwindcss/postcss` | MIT |
| `typescript` | Apache-2.0 |
| `eslint` / `eslint-config-next` | MIT |
| `vitest` | MIT |

Note: only **four** runtime dependencies. No component library, no state-management library, no
charting library, no analytics SDK.

### Container images

| Image | Licence |
|---|---|
| `postgres:15` | PostgreSQL Licence (OSI) |
| **`redis:8.10`** | **AGPLv3** at our election (Redis 8 is tri-licensed RSALv2 / SSPLv1 / AGPLv3). ✅ Was `redis:7`, a floating tag onto the non-OSI 7.4 line — see §3.1(b) |
| `nginx:stable` | BSD-2-Clause |
| `quay.io/keycloak/keycloak:26.0.7` | Apache-2.0 |

### External services (operational dependencies, not code dependencies)

Worth distinguishing for the consultant: these are services the deployment calls, replaceable by
configuration, and none of them constrains anyone's right to use or fork the code.

| Service | Used for | Replaceability |
|---|---|---|
| **OpenAI API** | All 9 model calls | **The subject of §4** |
| AWS SNS | SMS to complainants (international / development) | Provider-agnostic behind `backend/services/messaging.py`; already **dual-implemented** |
| **DOIT SMS** (`sms.doit.gov.np`) | SMS in Nepal — Government of Nepal gateway | The production path; configured, not compiled in |
| SMTP relay | Email notifications and quarterly reports | Any SMTP server |
| AWS EC2 | Hosting | Any VM |

The SMS layer is a useful counter-example to point at: two providers, one interface, selected by
environment variable. **It is what the LLM layer should look like** — and the fact that we already did
it once, elsewhere in the same codebase, is the best evidence that §4's work is a refactor rather than
an architectural change.

---

## Appendix B — Where the engineering plan lives

Four sub-sprints, 27 tickets, with test ledgers and open questions already written up in
[`docs/sprints/2026-08-llm/`](../sprints/2026-08-llm/README.md):

| Sprint | Scope | Serves |
|---|---|---|
| **0** — [licensing & governance](../sprints/2026-08-llm/01-licensing-and-governance-spec.md) | `LICENSE`, `NOTICE`, SPDX, dependency scan (**four sets, incl. container images + a pin-drift check**), IP determination, privacy assessment, **project hygiene (DPG-05)**, **the stale root README (DPG-06)** | Indicators 2, 3, 5, 7, 8 |
| **1** — [LLM-agnostic](../sprints/2026-08-llm/02-llm-agnostic-spec.md) | Characterization tests first; **one config file both surfaces read (DPG-17)**; then both LLM surfaces behind configurable clients; schema-constrained output; env plumbing | **Indicator 4** |
| **2** — [open models](../sprints/2026-08-llm/03-open-models-spec.md) | Labelled Nepali benchmark set, ASR and text evaluation, CI platform-independence job, T2 vLLM deployment | **Indicator 4** evidence |
| **3** — [PII redaction](../sprints/2026-08-llm/04-pii-redaction-spec.md) | Redaction at the model-call and logging boundaries, measured recall on Nepali | Indicators 7, 9 |

Sprint 0 starts immediately and in parallel, because the IP determination and the privacy assessment
have multi-week external lead times and gate nothing in the code.
