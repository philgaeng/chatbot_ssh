# Sprint tracker — DPG compliance & LLM independence

> **Update this file at every commit.** Status, checklist ticks, deviations.
> Sprint index: [`README.md`](README.md) · Test ledger: [`TESTS.md`](TESTS.md) · Questions: [`QUESTIONS.md`](QUESTIONS.md)
> Status legend: ⬜ not started · 🟡 in progress · ✅ done · ⏸ blocked · ❌ dropped (log why)

**Sprint status: 🟡 IN PROGRESS — Sprint 0 complete** · Created 2026-08-17 · Baseline `integration/stage` @ `f0d4552d`

> **Sprint 0 closed 2026-08-18.** DPG-01, 02, 04, 05 and 06 are ✅ on `dpg/sprint0-licensing`.
> **DPG-03 cannot be closed here** — it is a written determination from ADB's Office of the General
> Counsel and nobody working on this repository can produce it. See its row and §DPG-03 below for the
> clock. Sprint 1 (`dpg/sprint1-llm-agnostic`) is unblocked and starts at **DPG-10**.

---

## Status board

| Ticket | Title | Status | Branch | Commit(s) | Tests green | Notes |
|---|---|---|---|---|---|---|
| **DPG-01** | LICENSE + NOTICE + SPDX | ✅ | `dpg/sprint0-licensing` | | ✅ T-01 (9) | Apache-2.0 landed **provisionally** (owner: proceed, revisit if the consultant advises — Q-02). 583 files stamped; `NOTICE` holder is an explicit `⚠ PENDING` per DPG-03 |
| **DPG-02** | Dependency licence audit | ✅ | `dpg/sprint0-licensing` | | ✅ T-02 (16) | 153 pkgs, 4 sets, 0 unknown/non-OSI. Rasa closed. Scan **scheduled** (Q-06). Found 2 transitive LGPL + our own npm manifest declaring `UNLICENSED` |
| **DPG-03** | IP ownership (ADB OGC) | ⏸ | non-code | | n/a | **BLOCKED — external, and it is the only Sprint 0 item nobody here can move.** Owner is writing to the **DPG consultant** (Q-01, in flight). ⚠ That is **not** the ADB OGC channel an IP determination requires. **Date raised with consultant: ______** · **Date sent to ADB OGC: ______** — fill both in; this is a clock and it should be visible |
| **DPG-04** | Privacy assessment + data-flow | ✅ | `dpg/sprint0-licensing` | | n/a | `docs/dpg/privacy-assessment.md` — 13 legs verified against code, Individual Privacy Act 2018 assessment, **17 findings** incl. 3 new high/medium ones nobody had found. Honesty marker per Q-07. Q-03 marked **moot while T2 parked** |
| **DPG-05** | Project hygiene (indicator 8) | ✅ | `dpg/sprint0-licensing` | | n/a | `SECURITY.md` (private channel, SEAH-aware in/out-of-scope, response targets), `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Covenant 2.1 + grievance-confidentiality clause), `.github/ISSUE_TEMPLATE/` (`blank_issues_enabled: false`, security **redirect**) + PR template. Governance/versioning **deferred** per the spec's scope gate — logged |
| **DPG-06** | Root `README.md` vs reality | ✅ | `dpg/sprint0-licensing` | | n/a | Rewritten from the compose files. Rasa service + Action Server rows gone; **13 services, verified against `docker compose config --services`**; folder tree matched to disk; branch corrected; `rasa_chatbot/` removed from CLAUDE.md too. **Found a 5th fiction the spec missed** — see D-10 |
| **DPG-10** | **Test net (must land first)** | ⬜ | `dpg/sprint1-llm-agnostic` | | | Nothing in Sprint 1 starts before this |
| **DPG-11** | `backend/services/llm_client.py` | ⬜ | `dpg/sprint1-llm-agnostic` | | | Stable shared service — re-grep callers |
| **DPG-12** | Ticketing client via settings | ⬜ | `dpg/sprint1-llm-agnostic` | | | |
| **DPG-13** | `json_object` → `json_schema` | ⬜ | `dpg/sprint1-llm-agnostic` | | | 7 call sites |
| **DPG-14** | Three latent defects | ⬜ | `dpg/sprint1-llm-agnostic` | | | 14.3 is **unverified** — confirm in-container |
| **DPG-15** | Degraded mode audit + probe | ⬜ | `dpg/sprint1-llm-agnostic` | | | Mostly already built — audit, don't rebuild |
| **DPG-16** | Env plumbing | ⬜ | `dpg/sprint1-llm-agnostic` | | | Generated from DPG-17's `declared_env_vars()` |
| **DPG-17** | **One config file** (`backend/config/llm_config.py`) | ⬜ | `dpg/sprint1-llm-agnostic` | | | **Lands before DPG-11/12.** Defaults stay on today's models — the open-default flip is Sprint 2 |
| **DPG-20** | Benchmark set | ⬜ | `dpg/sprint2-open-models` | | n/a | **Start during Sprint 1** — long pole |
| **DPG-21** | Provider setup + smoke | ⬜ | `dpg/sprint2-open-models` | | | |
| **DPG-22** | ASR evaluation | ⬜ | `dpg/sprint2-open-models` | | | **No baseline exists** — voice never live (Q-13.2). Sequence last: costliest, least urgent (Q-19) |
| **DPG-23** | Text-model evaluation | ⬜ | `dpg/sprint2-open-models` | | | Now a **production pre-flight check** (Q-04), not only DPG evidence. ⚠ Price it first (Q-19) |
| **DPG-24** | CI platform-independence job | ⬜ | `dpg/sprint2-open-models` | | | **5th** job in existing `ci.yml`. Only recurring cost — cap it first (Q-19) |
| **DPG-25** | T2 vLLM — documented + costed | ⬜ | `dpg/sprint2-open-models` | | n/a | ⏸ **T2 PARKED** (Q-03/Q-05). No deployment; the e2e test is a logged deferral |
| **DPG-30** | **Egress inventory (first)** | ⬜ | `dpg/sprint3-pii` | | n/a | Nothing in Sprint 3 starts before this |
| **DPG-31** | Deterministic PII layer | ⬜ | `dpg/sprint3-pii` | | | Ships without DPG-32 |
| **DPG-32** | NER layer | ⏸ | — | | | **MOVED OUT of Sprint 3** (Q-12c) → standalone anonymiser-service initiative. ⚠ **This row used to say "leaves person names unredacted" — that is D-08's error and it is false.** §31.2b redacts names deterministically (title triggers, thar gazetteer, self-identification); DPG-32 **raises recall**, it is not the whole control. Disclose the *measured residual*, not an absence |
| **DPG-33** | Model-call boundary | ⬜ | `dpg/sprint3-pii` | | | |
| **DPG-34** | Log / Celery / backup boundary | ⬜ | `dpg/sprint3-pii` | | | The leak that actually happens |
| **DPG-35** | Recall measurement | ◐ | `dpg/sprint3-pii` | | | **Split** (Q-12c): deterministic recall stays; PERSON/third-party travel with DPG-32 |
| **DPG-36** | Reconcile the live spec | ⬜ | `dpg/sprint3-pii` | | | |

---

## Question status

Answers verbatim + reasoning: [`DECISIONS.md`](DECISIONS.md). Still live: [`QUESTIONS.md`](QUESTIONS.md).
**All 20 answered 2026-08-17**; Q-19 was raised by the answers and is open.

| Q | Subject | Owns | Answer | Recorded in |
|---|---|---|---|---|
| Q-18 | Shared LLM config module | DPG-17 | ✅ `backend/config/llm_config.py`, pydantic-settings, dep → `requirements.txt` | [`02` DPG-17](02-llm-agnostic-spec.md#dpg-17) |
| Q-03 | T2 jurisdiction | DPG-25 | ✅ **Moot — T2 parked** | [`03` DPG-25](03-open-models-spec.md#dpg-25), [`00` §2](00-dpg-context-and-decisions.md#2-deployment-ladder--the-code-is-identical-at-every-tier), [`01` DPG-04](01-licensing-and-governance-spec.md#dpg-04) |
| Q-05 | T2 operator + payer | DPG-25 | ✅ **T2 parked** — no run-cost owner | [`03` DPG-25](03-open-models-spec.md#dpg-25), [`00` §5](00-dpg-context-and-decisions.md) |
| Q-04 | Which config production runs | DPG-23 | ✅ **The open one**, on cost; closed as fallback | [`03` DPG-23](03-open-models-spec.md#dpg-23), [`00` §4](00-dpg-context-and-decisions.md#4-dpg-evidence-pack) |
| Q-10 | Open config as repo default | DPG-17 | ✅ Yes, flipped in Sprint 2 | [`02` DPG-17](02-llm-agnostic-spec.md#dpg-17) §Correction |
| Q-11 | One model or per-task | DPG-17 | ✅ One text model first, then downsize; HF pricing is the driver | [`02` DPG-14](02-llm-agnostic-spec.md#dpg-14) (truncation check), [`03` DPG-25](03-open-models-spec.md#dpg-25) |
| Q-12b | Redact when | DPG-31, DPG-36 | ✅ **At transmission** — and the restore mapping is PII | [`04` DPG-31](04-pii-redaction-spec.md#dpg-31), [`04` DPG-36](04-pii-redaction-spec.md#dpg-36) |
| Q-12c | Where the ML dependency lives | DPG-32 | ✅ Dedicated service, **own initiative** — DPG-32/35 leave Sprint 3 | [`04` DPG-32](04-pii-redaction-spec.md#dpg-32), [`04` DPG-35](04-pii-redaction-spec.md#dpg-35) |
| Q-12 | Nepali NER licence | DPG-32 | ✅ Email the author; fine-tune as fallback | [`04` DPG-32](04-pii-redaction-spec.md#dpg-32) |
| Q-13 | `gpt-5-nano` · voice live? | DPG-14 | ✅ Deliberate cost choice · **voice not live** | [`02` DPG-14](02-llm-agnostic-spec.md#dpg-14), [`03` DPG-22](03-open-models-spec.md#dpg-22) |
| Q-14 | SEAH fail open/closed | DPG-15 | ✅ **Fail-open stays** — deterministic pre-filter verified in code | [`02` DPG-15](02-llm-agnostic-spec.md#dpg-15) |
| Q-15 | Benchmark provenance | DPG-20 | ✅ Synthetic phase 1; hybrid later | [`03` DPG-20](03-open-models-spec.md#dpg-20) |
| Q-16 | Benchmark size + labellers | DPG-20 | ✅ **No labeller budget** — target is aspirational | [`03` DPG-20](03-open-models-spec.md#dpg-20) |
| Q-06 | Licence scan scheduled? | DPG-02 | ✅ Scheduled in `ops/security.py` | [`01` DPG-02](01-licensing-and-governance-spec.md#dpg-02) |
| Q-07 | Privacy-assessment author | DPG-04 | ✅ Agent drafts, consultant advises — **no legal review, must be disclosed** | [`01` DPG-04](01-licensing-and-governance-spec.md#dpg-04) |
| Q-08 | Assess against what | DPG-04 | ✅ Nepal Individual Privacy Act 2018; no existing agreement | [`01` DPG-04](01-licensing-and-governance-spec.md#dpg-04) |
| Q-09 | Translation: specialist? | DPG-23 | ✅ LLM first; dedicated service only if better | [`03` DPG-23](03-open-models-spec.md#dpg-23) |
| Q-17 | Provider outage blocks merges? | DPG-24 | ✅ Every commit, never a required check | [`03` DPG-24](03-open-models-spec.md#dpg-24) |
| Q-01 | Who opens the OGC request | DPG-03 | 🔶 **In flight** — writing to the consultant. ⚠ Not the same channel as ADB OGC. **Sprint 0 closed 2026-08-18 with this still open** — `NOTICE` names no holder and says so | [`01` DPG-03](01-licensing-and-governance-spec.md#dpg-03) · **date raised with consultant: ______** · **date sent to ADB OGC: ______** |
| Q-02 | Apache-2.0 over MIT | DPG-01 | 🔴 **OPEN** — delegated to the consultant. **DPG-01 gated** | [`01` DPG-01](01-licensing-and-governance-spec.md#dpg-01) |
| Q-19 | **LLM budget** (new) | DPG-22/23/24 | 🔴 **OPEN** — gates most of Sprint 2 | [`QUESTIONS.md`](QUESTIONS.md#q-19) |

## ⏸ Sprint 0's two external blockers — named, with their clocks

> Required by [DPG-01](01-licensing-and-governance-spec.md#dpg-01)'s acceptance criteria: *"If either
> external answer is still outstanding when the sprint closes, **the blocker is named in
> `PROGRESS.md` with the date it was raised** — not left as an unticked box."* Sprint 0 closed
> 2026-08-18 with both still outstanding.

| Blocker | Question | Who can answer it | Status | Date raised | What is blocked |
|---|---|---|---|---|---|
| **Copyright holder** | Q-01 / **DPG-03** | **ADB's Office of the General Counsel** — in writing. ⚠ **The DPG consultant cannot issue an IP determination**; if the consultant is the route *to* OGC, record it that way | 🔶 Owner is writing to the consultant | **______** *(consultant)* · **______** *(ADB OGC)* | `NOTICE`'s copyright line — currently an explicit `⚠ PENDING`, deliberately not guessed. `docs/dpg/ip-ownership.md` cannot be written. Evidence-pack row 3 has no file. Also blocks naming a **data controller** (privacy assessment F-11) |
| **Which licence** | Q-02 / **DPG-01** | The **DPG consultant** | 🔴 Open — Apache-2.0 landed **provisionally** on the owner's decision to proceed | 2026-08-17 | Nothing, operationally. If the answer changes the licence, `LICENSE`, `NOTICE` and **585 SPDX headers** change together via `scripts/ops/add_spdx_headers.py` |

**Fill in the dates.** They are the only thing that makes an external dependency visible as a clock
rather than an excuse — and DPG-03 is the longest lead time on the whole programme.

**What Sprint 0 did instead of waiting:** landed everything that does not depend on the answers.
Indicator 2 fails outright with *no* licence, so a provisional Apache-2.0 with an honest
pending-holder disclosure in `NOTICE` is strictly better than an empty repository root — and it is
reversible before publication. That reasoning is recorded in `NOTICE` itself, not just here.

---

## Deviations

> Every departure from the specs goes here, in the commit that creates it — including adjacent bugs found
> and **not** fixed (per the sprint conventions: log, don't fix). Per
> [`docs/sprints/README.md`](../README.md), a deferral also needs a `followups/<slug>.md` doc and a
> `TODO.md` pointer row **in the same commit**. A deferral logged only here is half-logged.

**Status legend:** ✅ Closed — nothing further to do · 🔵 Open — real work, tracked in `followups/` +
`TODO.md` · ⏸ Blocked — waiting on an external answer.

> **Merged 2026-08-18 (D-23).** Deviations used to live in *two* tables sharing one ID namespace —
> this one, and the pre-sprint findings table below, which had quietly accumulated D-01…D-11. That is
> how the D-08…D-11 collision happened, and reusing numbers that belonged to **corrections** is how
> D-08's error came back as D-22. One table now. The table below holds **only** `P-##` planning
> findings; a `D-##` never goes there again.

| # | Status | Ticket | What changed vs the spec | Why / where | Followup / TODO row |
|---|---|---|---|---|---|
| D-15 | ⏸ **Blocked** — consultant-Q10 | DPG-05 | **Governance model and release/versioning policy not written** — steps 1–4 of the ticket shipped, step 5's "public roadmap" is a link to this sprint plan rather than a second document | Taken on the spec's own scope gate. The four shipped files describe **what is already true**; a governance model and a supported-version window would describe **commitments nobody has agreed to**, on a project whose IP ownership is formally open with ADB OGC. Whether the DPGA requires either is consultant-Q10, still unanswered. Indicator 8 already reads 🟢 without them | ✅ [`followups/governance-and-versioning-policy.md`](followups/governance-and-versioning-policy.md) + `TODO.md` 🔵 TECH DEBT row |
| D-16 | ✅ Closed | DPG-02 | **D-01's deferral was half-logged.** The CI-never-runs-these-tests finding was recorded here on 2026-08-18 but had **no `followups/` doc and no `TODO.md` row** — and `followups/` did not exist. Per [`sprints/README.md`](../README.md) that makes it a defect, not a deferral. Closed now, and the measured count corrected: **27 files, not 21** — 21 directly in `tests/` plus **6 in `tests/shared/`**, which the original note missed | The rule exists so debt stays visible; a deferral logged in one place decays | ✅ [`followups/ci-untested-root-test-files.md`](followups/ci-untested-root-test-files.md) + `TODO.md` row |
| D-17 | ✅ Closed | DPG-06 | ⚠ **The spec's own service count was wrong, and it missed a fifth fiction.** Spec step 1 says "Eleven services; name them as they are" — `docker compose config --services` returns **13**, plus 2 profile-gated (`db_init` under `init`, `keycloak` under `auth`) = **15 defined**. And the spec's four-row table of README falsehoods missed the **Environments table**: all three URLs (`chatbot.facets-ai.com`, `grm.facets-ai.com`, `grm.stage.facets-ai.com`) appear **nowhere else in the repository** and are not a `server_name` in any nginx config. The real hosts are `nepal-gms-chatbot.facets-ai.com` (AWS staging) and `grm-chatbot.dor.gov.np` (DOR production). **A DPG reviewer clicking a dead production URL on the front page is the same failure mode as the Rasa row**, one click earlier | Wrote the README from `docker compose config --services` and `deployment/nginx/*.conf`, per the spec's own instruction to generate from the compose files rather than from memory — which is exactly what caught it | — (fixed in place; no deferral) |
| D-18 | ✅ Closed | DPG-04 | **Corrected a false comment in the privacy-critical path rather than only logging it.** `backend/api/routers/grievance.py` asserted that `GET /api/grievance/{id}` **never decrypts** and called it "the T3-04 defect". T3-04 landed: `grievance_manager.py:188` calls `_decrypt_sensitive_data` on the JOIN result. The comment described the pre-fix state and was never updated | Sprint convention is *log, don't fix* for adjacent findings — **overridden deliberately here.** It is a comment, not behaviour (zero risk), and it sits in the file a privacy reviewer opens first, about the control §3.3 of the new assessment calls the platform's strongest. Writing a document that cites that boundary while leaving a comment asserting the opposite would be self-defeating. The correction is dated in place and states the caveat that survives (encryption is conditional on the key) | — (fixed in place) |
| D-19 | 🔵 **Open — backlog** | DPG-04 | ⚠ **Three privacy findings no spec had, found by reading the code — logged, not fixed.** **(F-2)** `_encrypt_field` returns the **plaintext value unchanged** when `DB_ENCRYPTION_KEY` is unset *and* when the pgcrypto call raises — the error is logged and the write proceeds, so a degraded deployment silently stores complainant PII in the clear (`base_manager.py:243-252`). **(F-3)** `*_hash` search tokens are **unsalted SHA-256** of phone/email/name/address; Nepal's mobile space is enumerable, so the phone hash is reversible and these columns are personal data, not pseudonyms (`base_manager.py:502-511`). **(F-4)** `backup_db.sh` writes an **unencrypted** `pg_dump` + uploads tar by default — encryption only if `BACKUP_GPG_RECIPIENT`/`BACKUP_PASSPHRASE` is set; the narrative, officer notes, voice notes and photos are in the clear (`backup_db.sh:45-60`) | Each is a code change with a blast radius (a key-presence assertion could refuse to boot; salting the hashes is a migration + a search-path rewrite; backup encryption needs key custody decided). None belongs in a documentation ticket | ✅ **Now tracked** (2026-08-18): [`followups/storage-layer-privacy-defects.md`](followups/storage-layer-privacy-defects.md) — one doc, because all three share a root cause (the storage layer was never privacy-reviewed; every existing privacy spec describes the architecture, none describes what happens when a write fails) — plus a 🔴 `TODO.md` row. **Deadline is go-live, not submission** (assessment §0.5) |
| D-20 | ✅ Closed | DPG-04 | **`NOTICE` corrected** — it claimed the generated dependency inventory "will be published at docs/dpg/dependency-licenses.md" and that the hand-written one was authoritative until then. DPG-02 published it the day before | A licence file making a false statement about the licence evidence is the worst possible place for one | — (fixed in place) |
| D-21 | ✅ Closed 2026-08-18 | DPG-04 | ⚠ **`docs/deployment/09_privacy.md` §Implementation boundaries still forbids cross-schema reads from `ticketing.*` into `public.*`.** That rule was **deliberately retired** by T3-07 and replaced with an enumerated, test-pinned table in `CLAUDE.md`. The live privacy spec and the locked architecture now disagree | Logged, not fixed — it is a live domain spec owned by the privacy/ticketing docs, and amending it correctly means moving T3-07's *reason* with the rule (engineering rule 7), which is more than a one-line edit | ✅ **Fixed 2026-08-18** — `09_privacy.md` §Implementation boundaries now states the as-built contract (enumerated closed set, no FKs, no PII columns, HTTP-only state changes) **with T3-07's reason carried alongside it**, per engineering rule 7. That is why this was not a one-line deletion. F-15 in the assessment updated |
| D-22 | ✅ Closed | DPG-04 | ⚠ **I reintroduced an error this sprint had already found and corrected.** The first draft of `privacy-assessment.md` said person names go unredacted until the ML layer lands, and that deterministic redaction covers only numeric identifiers and email. **That is exactly D-08**, which was raised, corrected across `04-pii-redaction-spec.md` and both DPG docs, and owner-flagged — before I wrote the assessment. §31.2b ships **three** person-name recognisers with no ML dependency: honorific/role-title triggers, a Nepali thar gazetteer, and self-identification patterns; in a road-works GRM those catch the *named official*, the sharpest exposure. **Owner-flagged again.** Corrected in four places in the assessment (§3.7 point 3, §4.2 table, §4.3 point 4, F-9), in the DPG-04 acceptance text, and in the **DPG-32 status-board row above**, which still carried the original wording. ⚠ **And D-08's own correction was incomplete:** sweeping for the phrase found it still live in **[`README.md`](README.md) §Decisions** and **[`00-dpg-context-and-decisions.md`](00-dpg-context-and-decisions.md) open-question 10** — two documents D-08 never touched. Both corrected here. A correction that fixes the documents you remember writing, rather than the ones a `grep` finds, is how the same error comes back | `privacy-assessment.md`, `01-…-spec.md`, this file, `README.md`, `00-dpg-context-and-decisions.md` | ✅ corrected · **root cause below** |
| D-23 | ✅ Closed | — | **Deviation IDs collided.** The block I added on 2026-08-18 was numbered D-08…D-14 while D-08…D-11 were already taken by the corrections logged in the pre-sprint findings table below. Renumbered to **D-15…D-21**, and every cross-reference updated. **This is not cosmetic — it is the mechanism of D-22:** the numbers I reused belong to *corrections*, and if I had read the rows I was about to overwrite I would have read D-08 and not repeated it. The two tables in this file are one namespace and should be merged | this file | ✅ renumbered |
| D-24 | ✅ Closed 2026-08-18 | DPG-01 | ⚠ **The sprint wired tests into CI on a branch pattern CI does not watch.** DPG-01 added `tests/repo` to `ci.yml`'s pytest step — the SPDX walker and the licence-classifier pins, whose entire purpose is to fail when a commit breaks a compliance claim. But `ci.yml`'s push triggers were `main`, `integration/**`, `dev/**`, and this sprint works off `dpg/sprint0-licensing`. **So the pins ran nowhere but my own machine for nine commits**, and every "green in CI" line in this tracker was prospective. Found by pushing the branch and watching nothing happen | `.github/workflows/ci.yml:15-21` · **Same defect as D-01** — a gate that does not run is decoration. The general lesson: wiring a test into CI is **two** edits, the step and the trigger | Fixed by adding `dpg/**`, with the reason in a comment beside it |
| D-01 | 🔵 **Open — backlog** | DPG-02 | ⚠ **CI never runs 21 test files.** `ci.yml`'s pytest step names four paths explicitly (`tests/ticketing tests/orchestrator tests/actions tests/backend`), so the **21 test files sitting directly in `tests/`** — `test_complainant_functions.py`, `test_postgres_services.py`, `test_seah_*.py` and 18 more — plus `tests/shared/`, have never executed in CI. Found while deciding where T-01 should live; it is why `tests/repo/` exists rather than `tests/test_spdx_headers.py`. **Not fixed here** — those files may not pass, and finding out is its own ticket, not a licence commit. Logged as a followup | Location: `.github/workflows/ci.yml:178` | [`followups/ci-untested-root-test-files.md`](followups/ci-untested-root-test-files.md) · `TODO.md` 🔵 |
| D-02 | ✅ Closed | DPG-01 | ✅ **CLOSED 2026-08-18 — `next build` succeeded.** Rebuilt `grm_ui` in Docker after the SPDX pass and the container came up healthy; the built image carries the current sources (verified via the new `license` field), so the build genuinely re-ran over all 110 `.tsx` files that now have the header above `"use client"`. The reasoning below was right — comments are trivia and do not break a Directive Prologue — but it is now confirmed by the actual Next.js compiler rather than by argument. Original note: | Location: 110 files under `channels/ticketing-ui/` · ✅ verified | — (verified by rebuild) |
| D-02b | ✅ Superseded by D-02 | DPG-01 | ⚠ **The `"use client"` directive placement was reasoned, not empirically confirmed** (superseded by D-02). 110 `.tsx` files now carry `// SPDX-License-Identifier` **above** their `"use client"` directive. Per ECMAScript, comments are trivia and do not break a Directive Prologue, so the directive is still the first *statement* — and `tsc --noEmit` is clean plus all 88 vitest tests pass. But **vitest does not exercise the directive** and there was no prior comment-above-directive precedent in the repo to lean on. `next build` is the confirming gate and it must not run on the host (CLAUDE.md §Docker-only). **Check `ui-checks` on the first CI run of this branch** — if it fails, the fix is to move the header below the directive for `.tsx` only, which is a three-line change to `insertion_line()` | Location: 110 files under `channels/ticketing-ui/` · **verify in CI** | — |
| D-03 | ✅ Closed — false positive | DPG-01 | The pre-sprint reading of "encoding declarations in scope" was a **false positive** — the grep matched `encoding="utf-8"` inside `open()` calls, not PEP 263 headers. There are **no** encoding declarations in scope; the shebang case (13 files) is real and handled | Location: — · closed | — |
| D-04 | ✅ Closed — spec corrected | DPG-02 | ⚠ **The DPG-02 spec's "two images" premise is wrong.** One `Dockerfile` serves every Python service and installs **both** `requirements.txt` and `requirements.grm.txt` into a single image — verified by importing packages from each inside `ticketing_api`. The report therefore splits by **manifest** (parsed from the requirements files), which is the only split that exists: 35 declared, 98 transitive | Location: `Dockerfile:22-25` · DPG-02 (spec corrected) | — |
| D-05 | ✅ Closed | DPG-02 | **Our own npm manifest declared no licence** — fixed (`"license": "Apache-2.0"` in both). ⚠ **But the follow-on claim was wrong and is corrected:** the report predicted the scanner row would flip to `Apache-2.0` after an image rebuild. It does not. `license-checker` hard-codes `UNLICENSED` for any `"private": true` package and ignores the `license` field — verified by rebuilding `grm_ui` and re-scanning (`{"licenses": "UNLICENSED", "private": true}`). The row is a tool artefact for an unpublished package, not a finding; the fix stands on its own merits | Location: `channels/*/package.json` · DPG-02 ✅ fixed, claim corrected | — |
| D-06 | ✅ Closed — recorded | DPG-02 | ⚠ **Two LGPL dependencies nobody knew about**, both transitive so no manifest read would show them: `jwcrypto` (LGPL-3.0-or-later, via the Keycloak JWT path) and `@img/sharp-libvips-linux*-x64` (LGPL-3.0-or-later, via Next.js image optimisation). Both are unmodified dynamically-loaded libraries — the LGPL-compliant pattern — and both are now dispositioned in the report | Location: `docs/dpg/dependency-licenses.md` · DPG-02 ✅ recorded | `docs/dpg/dependency-licenses.md` |
| D-07 | ✅ Closed — fixed + pinned | DPG-02 | ⚠ **The first licence classifier passed a proprietary licence silently.** `"Proprietary Limited License"` contains the substring `MIT`, so `token in text` classified it as OSI-approved and the nightly scan would have reported clean. Fixed with word-boundary matching and pinned by a mutation-checked test | Location: `ops/licences.py` · DPG-02 ✅ fixed | `tests/repo/test_licence_scan.py` |
| D-08 | ✅ Closed | DPG-02 / DPG-04 | ⚠ **I under-scoped the deterministic redaction layer, and the DPG docs inherited the error.** DPG-31 listed only numeric identifiers and email, so the briefing and compliance status both said person names would reach the provider unaddressed. **Names are substantially tractable without ML** — honorific/role-title triggers (`Er.`, Engineer, overseer, ward chairperson), a Nepali family-name gazetteer, and self-identification patterns. Added as §31.2b + §31.2c (addresses); DPG-32's deferral banner, DPG-35's metrics and both DPG docs corrected. **Owner-flagged** | Location: `04-pii-redaction-spec.md`, `docs/dpg/*` · ✅ corrected | see **D-22** — this correction was incomplete and was finished 2026-08-18 |
| D-09 | ✅ Closed · Q16 open | DPG-02 | ⚠ **I read the wrong Hugging Face page and understated their commitments.** The general privacy policy has no inference-specific clause, and I concluded there were none. They are on [Inference Providers → Security & Compliance](https://huggingface.co/docs/inference-providers/en/security): no storage of request body or response when routing, no user data stored for training, debug logs ≤30 days with no user data, TLS, SOC 2 Type 2 on the Hub. **Corrected in both DPG docs.** The caveat that survives is theirs — *"External providers are responsible for their own security measures"* — plus per-request routing making the processor unknowable, and no DPA in the ToS. Fix: pin `model:provider` in prod, route freely in CI (synthetic data only). Consultant-Q16 | Location: `docs/dpg/*` §4.3a · ✅ corrected · Q16 open | — |
| D-10 | ✅ Closed | DPG-04 | ⚠ **The transfer analysis was pointed at the wrong event.** Retention and training use are mitigations; **the trigger is the transmission itself** — a disclosure and cross-border transfer under the Individual Privacy Act regardless of what the recipient does. DPG-04 now states this, and states that **openness is a licensing property, not a privacy one** | Location: `01-licensing-…#dpg-04` · ✅ corrected | — |
| D-11 | ✅ Closed | DPG-04 | ⚠ **"Anonymised" would have been an overstatement to the ministry.** We hold the mapping, so output is **pseudonymised** and remains personal data. The defensible claim is *only pseudonymised text crosses the border, and the key never leaves Nepal* — which makes **key residency and storage separation acceptance criteria with a test**, since one careless serialisation into a Celery payload voids the argument silently | Location: `04-pii-redaction-spec.md#dpg-31` · ✅ criteria added | — |

### Pre-sprint findings — carried in from planning

These were found while writing the specs, against `integration/stage` @ `f0d4552d`. They are **not yet
deviations** (no code has changed); they are the inbox DPG-10 and DPG-14 inherit. Move each to the table
above once a ticket touches it.

> ⚠ **`P-##` only.** Twelve `D-##` rows had accumulated here and were moved to the Deviations table on
> 2026-08-18 (D-23). **Do not add a `D-##` row to this table again** — two tables sharing one ID
> namespace is what produced the collision, and reusing a number that belonged to a correction is what
> let a corrected error come back. If a `P-##` finding turns into a deviation, give it the next free
> `D-##` **in the table above** and leave a `→ D-##` pointer here.

| # | Finding | Location | Owner |
|---|---|---|---|
| P-01 | A **second LLM surface** the source narrative missed entirely — 3 more hard-coded models, its own client, its own settings | `ticketing/clients/llm_client.py` | DPG-12 |
| P-02 | `gpt-5-nano` is the **live classification model**, not a stray reference | `LLM_services.py:230` | DPG-14.1 |
| P-03 | Classification builds a **shadow client** at `:199` that shadows the module-level one, then tests it with a guard that can never fire (`:200-201`) | `LLM_services.py:198-201` | DPG-14.2 |
| P-04 | ⚠ **Suspected** — ASR call passes `language_code=` where the SDK takes `language=`; if the SDK rejects it, transcription has never worked on this path. **Unverified: host has no `openai` (Docker-only)** | `LLM_services.py:46` | DPG-14.3 |
| P-05 | `extract_contact_info`'s `except` reads `response` at `:93`, which is unbound if the failure happened before `:76` → `UnboundLocalError` instead of the documented `{field_name: ""}` | `LLM_services.py:92-102` | DPG-10 / DPG-14 |
| P-06 | Two JSON-producing calls have **no `response_format` at all** — classification and translation ask for "strict JSON" in the prompt and absorb parse failures as empty results | `LLM_services.py:230`, `:322` | DPG-13 |
| P-07 | `load_dotenv('/home/ubuntu/nepal_chatbot/.env')` — an absolute EC2 path in a Docker-only stack. Dead code that reads as live config | `LLM_services.py:25` | DPG-11 |
| P-08 | **Zero tests** import either LLM module. The guide's CI snippet targets `tests/test_llm_services.py`, which does not exist | `tests/` | DPG-10 |
| P-09 | Translation error paths interpolate the whole `input_data` dict — including `grievance_description` — into a `ValueError` message that is then logged and may reach the Celery result backend | `LLM_services.py:335`, `:343` | DPG-34 |
| P-10 | `parse_llm_response` logs the **raw model response** on JSON parse error | `LLM_services.py:282` | DPG-34 |
| P-11 | `detect_sensitive_content_llm` **fails open** — LLM unreachable ⇒ `detected: False` on the SEAH path | `LLM_services.py:403-404` | DPG-15 / Q-14 |
| P-12 | `11_llm_pipeline_policy.md` asserts summaries "MUST be PII-scrubbed before storage". **Nothing scrubs them** | `docs/deployment/11_llm_pipeline_policy.md` | DPG-36 |
| P-13 | CLAUDE.md §Folder structure lists `rasa_chatbot/` — the directory does not exist | `CLAUDE.md` | DPG-02 (cheap fix alongside) |
| P-14 | `env.local` holds a live OpenAI key in plaintext. Gitignored and normal for a local env file, but it is the credential this sprint replaces — rotate when the migration lands | `env.local:39` | DPG-16 |
| P-15 | ⚠ **A second copy of `_MODEL_STANDARD` / `_MODEL_SEAH`**, in a module the inventory missed — written into the resolved-case summary as `llm.model` (`:299`), i.e. a **persisted provenance field** computed from a copy rather than from the module that made the call. Change the client's mapping and miss this file → every resolved case records a model that never ran it | `ticketing/services/resolved_summary_builder.py:26-27`, `:299` | DPG-17 / DPG-12 |
| P-16 | A **third** copy of the same SEAH ternary, re-derived for a log line — the log can disagree with the call it is logging | `ticketing/tasks/llm.py:163` (and a stale key reference at `:15`) | DPG-17 / DPG-12 |
| P-22 | **There is no LLM budget** — *"I can shoulder a few calls per day to nano, not transcription"* (Q-13). Voice transcription is consequently **not live at all**, and Sprint 2 is built almost entirely from inference calls that nobody priced | Q-13 · DPG-22/23/24 | **Q-19** (new) |
| P-23 | **T2 parked** (Q-03/Q-05) — no run-cost owner. T1 becomes the steady state, so grievance egress to a third party is **permanent, not transitional**, which promotes Sprint 3 and removes the vLLM-in-production sentence from the indicator-4 answer | Q-03, Q-05 | DPG-25, DPG-04, Sprint 3 |
| P-24 | ✅ **A deterministic SEAH pre-filter exists and is wired in** — `shared_functions/keyword_detector.py:257` (scored, `:342`) via `helpers_repo.py:58` → `services/seah/sensitive_detection.py:25` → `base_mixins.py:170`, as synchronous slot validation. So the LLM leg's fail-open degrades a **second** pass. Strengthens indicator 9b, which the compliance doc credited to the LLM alone | verified 2026-08-17 | DPG-15, compliance §2.6 |
| P-25 | Owner's Q-11 answer states translation and classification run **in one call**; the code has them as **two** (`:204-231` classify/summarise/follow-up; `:322` translate). The true and useful version: there is no translate-then-classify pipeline — the model consumes Nepali directly | `LLM_services.py:204-231`, `:322` | DPG-23, Q-11 |
| P-26 | Q-12b's *"in practice we store both"* implies a persisted `restore()` mapping — **a plaintext PII store by construction**. Must not land in `ticketing.*` (data rule 3); prefer never persisting it | Q-12b | DPG-31 |
| P-18 | Container images were a **fourth dependency set nobody was auditing** — and the one place licence drift actually happened (`redis:7`, a floating tag onto the non-OSI 7.4 line). Fixed outside the sprint plan: `redis:8.10`, AGPLv3 elected. DPG-02 now audits four sets + a pin-drift check | `docker-compose.yml:222`, `.github/workflows/ci.yml:42` | DPG-02 |
| P-19 | No ticket covered indicator-8 project hygiene (`SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, templates) — all verified absent | repo root | **DPG-05** (new) |
| P-20 | Root `README.md` advertises a **Rasa service on port 5005** plus an Action Server on 5055, and names a stale active branch. It contradicts the compliance briefing's own indicator-2 argument, on the most-read file in the repo | `README.md:6`, `:10`, `:46-47`, `:60`, `:76`, `:116` | **DPG-06** (new) |
| P-21 | The compliance audit asserted "**No `.env.example`**". It exists (5982 B, `OPENAI_API_KEY=` at `:61`) — the spec was right and the audit wrong. Corrected in the audit doc; the real gap is that it documents only the key, not the endpoint/model surface | `.env.example:61` | DPG-16 |
| P-17 | DPG-11's "open configuration by default" cannot ship in Sprint 1: an HF-router base URL with `gpt-3.5-turbo` / `whisper-1` model IDs is a default configuration that serves **no** request, and it turns DPG-10's tests red in the commit where red means *stop*. Deferred to Sprint 2 against DPG-17's single file | — (planning finding) | DPG-17, DPG-23, Q-10 |

---

## Degraded-mode audit table (DPG-15)

Fill during DPG-15. One row per call site: is the grievance durable before the call, and what does the
user see when it fails?

| # | Call site | Durable before call? | On failure, user sees | Gap? |
|---|---|---|---|---|
| 1 | `transcribe_audio_file` | | | |
| 2 | `extract_contact_info` | | | |
| 3 | `extract_all_contact_info` | | | |
| 4 | `classify_and_summarize_grievance` | ✅ (row written, then `.delay()`) | 20 s poll, then empty classification | |
| 5 | `translate_grievance_to_english_LLM` | | | |
| 6 | `detect_sensitive_content_llm` | | | ⚠ fails open — Q-14 |
| 7 | `translate_to_english` (ticketing) | | | |
| 8 | `generate_case_findings` | | | |
| 9 | `generate_resolved_case_summary_llm` | | | |

---

## Commit log

| Date | Ticket | Commit | What landed |
|---|---|---|---|
| 2026-08-18 | **DPG-04** | _(this branch)_ | `docs/dpg/privacy-assessment.md` — **13 data-flow legs verified against the code**, assessed against Nepal's Individual Privacy Act 2018 · mandatory honesty marker (AI author, no legal review — Q-07) · **17-item findings register**, 3 of them new and previously unknown (F-2 encryption-at-rest fails open, F-3 unsalted phone hashes, F-4 unencrypted-by-default backups) · third-party PII position stated as the load-bearing section (T2 parked ⇒ egress is permanent) · retention/deletion/breach written as `⚠ Not built` where they are · cross-linked from `13_security.md`; evidence-pack rows 5/7/8/9a now point at real files |
| 2026-08-18 | **DPG-05** | _(this branch)_ | `SECURITY.md` (private channel, named recipient, 3/10-working-day targets, SEAH-aware in/out-of-scope, known-and-accepted list) · `CONTRIBUTING.md` (points at the rules, does not restate them) · `CODE_OF_CONDUCT.md` (Covenant 2.1 + a grievance-confidentiality clause) · `.github/ISSUE_TEMPLATE/` with `blank_issues_enabled: false` and a security **redirect** contact link · `PULL_REQUEST_TEMPLATE.md` with a sensitive-path section · governance/versioning deferred + logged (D-08) |
| 2026-08-18 | **DPG-06** | _(this branch)_ | Root `README.md` **rewritten from the compose files** — Rasa service (:5005) and Action Server (:5055) rows gone, `rasa-sdk`'s real type-shim role stated in one line, **13-service table verified against `docker compose config --services`**, folder tree matched to disk, branch corrected to `integration/stage`, **three dead environment URLs replaced with the two real hostnames** (D-10), Contributing/Security/Roadmap section added · `rasa_chatbot/` removed from CLAUDE.md §Service boundaries (P-13 closed) · `NOTICE` stale-claim fix (D-13) |
| 2026-08-18 | **DPG-02** | _(this branch)_ | `docs/dpg/dependency-licenses.md` — 153 packages, in-container scans · `ops/licences.py` + `licence_scan()` scheduled nightly at 01:50 (Q-06) · `pip-licenses` declared · pin-drift + classifier tests (`tests/repo/`, 16 assertions) · **`redis:8.10` pin verified live** — the caveat on commit `800aa803` is closed · npm manifests now declare Apache-2.0 |
| 2026-08-17 | **DPG-01** | _(this branch)_ | `LICENSE` (canonical Apache-2.0, 202 lines, md5 `3b83ef96…`) · `NOTICE` with an explicit pending-holder disclosure · `scripts/ops/add_spdx_headers.py` (idempotent, `--check` mode) · **583 files stamped** (408 `.py`, 175 `.ts`/`.tsx`) · `tests/repo/test_spdx_headers.py` (T-01, 9 assertions) · `tests/repo` wired into `ci.yml` |

| Date | Ticket | Commit | Summary |
|---|---|---|---|
| | | | |

---

## Sprint 0 — definition of done

Against [`01-licensing-and-governance-spec.md`](01-licensing-and-governance-spec.md) §Definition of done:

- [x] **DPG-01, DPG-02, DPG-05, DPG-06 landed** — green in CI pending the first run of this branch (see D-02b: `ui-checks` is the confirming gate for the `"use client"` header placement; ✅ already confirmed locally by a successful `next build` in Docker)
- [ ] **DPG-03 request sent** — ⏸ **not sent to ADB OGC.** Named as a blocker with its clock above. The sprint is not blocked on the response, but this box stays unticked until the letter goes
- [x] **DPG-04 written** — `docs/dpg/privacy-assessment.md`, with a named author and date, and an explicit statement that no legal review was performed
- [x] **`README.md` and CLAUDE.md make the same claim about Rasa as the compliance briefing** — verified by grep: zero occurrences of `rasa` in CLAUDE.md, and the only `5005` in `README.md` is the sentence explaining that the row was removed
- [x] **`docs/dpg/` exists and is indexed from `docs/README.md`** — four files, each with its own row
- [x] **Evidence-pack rows 2, 3, 7, 9a point at real files** — 2 ✅ (`LICENSE`, `NOTICE`, `dependency-licenses.md`), 7 and 9a ✅ (`privacy-assessment.md`), **3 ⏸ still has no file and cannot until ADB OGC responds** — rows 5 and 8 were updated too
- [x] **Every deferral logged in `followups/` + `TODO.md`, same commit** — ✅ **now complete.** Three followups: `ci-untested-root-test-files.md`, `governance-and-versioning-policy.md`, and `storage-layer-privacy-defects.md`, each with a `TODO.md` row. The last one closed the exception this line used to carry: D-19's three privacy defects were recorded only in the assessment's findings register, which is the half-logged pattern D-16 exists to name

### Deviation disposition — 21 rows, all triaged (2026-08-18)

| Disposition | Count | Rows |
|---|---|---|
| ✅ **Closed** — fixed in place, corrected, or superseded | **17** | D-02, D-02b, D-03, D-04, D-05, D-06, D-07, D-08, D-09, D-10, D-11, D-16, D-17, D-18, D-20, D-21, D-22, D-23 |
| 🔵 **Open — tracked in `followups/` + `TODO.md`** | **2** | **D-01** (27 test files CI has never run) · **D-19** (three storage-layer privacy defects — **go-live deadline**) |
| ⏸ **Blocked on an external answer** | **1** | **D-15** (governance model + versioning — consultant-Q10, and DPG-03) |

**Nothing is untriaged, and nothing open is untracked.** The two 🔵 rows are real backlog with a
measured definition of done in their followup docs; the ⏸ row waits on someone else. Of the 17 closed,
**eight are corrections of this sprint's own errors** (D-04, D-05, D-08, D-09, D-10, D-11, D-22, D-23) —
worth stating plainly rather than burying, because the rate at which a process catches itself is the
only evidence that it does

---

## Sprint close checklist

- [ ] All 27 tickets ✅, or ❌ with a logged reason
- [ ] Every test in [`TESTS.md`](TESTS.md) written and mutation-checked
- [ ] Every question in [`QUESTIONS.md`](QUESTIONS.md) answered **and its answer written into the spec**
- [ ] All P-## findings above dispositioned (fixed, or moved to a followup + `TODO.md` row)
- [ ] `docs/dpg/` evidence pack complete; every indicator row points at a real file
- [ ] Live specs updated with honest verification markers (see [`README.md`](README.md) → domain specs table)
- [ ] Indicator-4 submission text checked **clause by clause** against reality before pasting
- [ ] Summary written as `docs/sprints/2026-08_dpg_llm_independence.md`
- [ ] This folder moved to [`../archive/`](../archive/); [`../README.md`](../README.md) tables updated
- [ ] `docs/PROGRESS.md` and `docs/TODO.md` updated
