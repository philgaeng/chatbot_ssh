# Handover — rewriting the DPG compliance pack from scratch

**Date:** 2026-08-24
**For:** the agent writing the new `00_compliance_status.md`, `02_questions.md` and
`03_remediation_record.md`, and re-deriving `01_consultant_briefing.md`.
**Read this first.** It exists so you do not re-derive facts that took a week to establish, and do not
repeat the mistakes that made a rewrite necessary.

---

## 0. Why the previous pack was archived

Two root causes, and both produce the same symptom: a document that has to be read with a correction
sheet beside it.

### 0.1 Nobody asked what each document was *for*

The 2026-08-17 originals predate Sprints 1 and 2. A pass on 2026-08-23 "rewrote" them — but kept the
original's shape and voice and replaced only the prose. What followed was five rounds of the owner
saying *"this doesn't belong here"*:

| What the owner had to point out | The underlying error |
|---|---|
| Questions argued their own answers | We were asking the expert to check our homework |
| §5 "Decisions we have already taken" | A changelog inside an assessment |
| §4 narrated the engineering | Reference material inside a pre-read |
| §2 was two-thirds achievements | An assessment listing accomplishments |
| The two documents duplicated each other | No decision about which was the source |

⚠ **So before you write a line, write the contract in the header**: what this document is, as of when,
what it is **not**, and where the other thing lives. If you cannot say what belongs in a section and
what does not, do not write the section.

### 0.2 Claims were written that nobody had executed

Separately and just as damaging: documents asserted things about the system that were plausible,
written by people who understood the design, and false. Six of them were caught this week by running
them — the six host-only secrets, the `SEARCH_TOKEN_PEPPER` hazard, the ops credential, the daily ops
report, the Keycloak event log, "re-run nightly by the ops container".

**The rule that follows, and it is the most important instruction in this document:** prefer
*"verified on DATE by running X"* to *"the system does Y"*. **If you cannot name the command, mark the
claim unverified rather than writing it flat.** That is already the discipline in
`privacy-assessment.md` — which is why that document came through the week intact while the compliance
status did not.

### 0.3 Do not amend; rewrite

If you find yourself appending a correction to a paragraph, or adding a section that supersedes an
earlier one, **stop and rewrite the paragraph.** That practice is what made the archived pack
unreadable, and this document was itself briefly guilty of it.

**The archived files are in [`archive/`](archive/)** — the 2026-08-17 originals and the 2026-08-23
state. Do not edit them; they are the record. `archive/` is excluded from the docs link checker and
the `file.py:line` pin, so they cannot rot or break gates.

---

## 1. The target structure

```
docs/dpg/
  00_compliance_status.md     ← rewrite from scratch, dated today.
                                One paragraph per indicator: what we have / gaps /
                                suggested remedies / questions. CITE the evidence
                                documents, never restate them.
  01_consultant_briefing.md   ← re-derive from the new 00 IN THE SAME PASS.
                                A pre-read. Not a summary of the old 00.
  02_questions.md             ← GENERATED from 00. See §5 — the one mechanical
                                decision that matters.
  03_remediation_record.md    ← what the sprints fixed. Explicitly NOT part of the
                                assessment; sent only in response to one.
                                Derive from docs/sprints/2026-08-llm/PROGRESS.md.
  archive/                    ← the four archived files. Never edited.
  <the five evidence documents, unchanged — see §2>
```

**Question numbering: `Q-<indicator>-<n>`.** `Q-03-01` is the first question about indicator 3. Numbers
become *derived from structure*, so inserting one never renumbers another. Use **`Q-00-xx` for process
questions** belonging to no indicator (submission route, precedents, assessment timeline, "what are we
missing") — otherwise they become a special case that leaks.

---

## 2. The five evidence documents — keep, cite, do not restate

Deliberately **not** archived. They are measurements and generated inventories, not positions, and the
new `00` is short precisely because it cites them.

| Document | What it is | State |
|---|---|---|
| [`dependency-licenses.md`](dependency-licenses.md) | Generated: `pip-licenses`, `license-checker`, image digests. 153 packages | Good. Has accreted some process narration |
| [`privacy-assessment.md`](privacy-assessment.md) | 13 data-flow legs verified at file+line, 18 findings | **Strongest document in the pack** — and the model for how to write claims |
| [`model-benchmarks.md`](model-benchmarks.md) | Measured model results | Needs its own from-scratch rewrite — but **later**, see below |
| [`open-model-configuration.md`](open-model-configuration.md) | How to run on open models + capability matrix | One broken bullet, see below |
| [`vllm-deployment.md`](vllm-deployment.md) | Self-hosting design + costing for a parked option | Fine. Small |

⚠ **Do not move them into a subdirectory.** 48 markdown links outside `docs/dpg/` and 10 code
references point at them. Give the new `00` an evidence-index table instead.

### Four things to fix or check before anything is sent

1. **`privacy-assessment.md` §3.7** — the cross-border table still says *"6 chatbot model calls … full
   narrative, complainant name and phone, audio"*. This **contradicts F-1 and leg L4 in the same
   document**, which were corrected to five live sites with contact details not leaving. One-line fix.
2. **`open-model-configuration.md` "What is not yet true"** — the transcription bullet has benchmark
   news appended inside it and reads as one incoherent item. Split it.
3. **`model-benchmarks.md`** carries three layers of the same numbers: §2 post-fix, §3.7 before *and*
   after, §4 marked "superseded by §3.7", §6 pre-fix. **Rewrite it from scratch when the open column
   lands** — once, against complete data, rather than twice.
4. **`privacy-assessment.md` leans on the DOIT SMS gateway being in-country** as a jurisdictional
   advantage (leg L9). True — but its credential was tracked by no inventory until 2026-08-24. Do not
   repeat an indicator-9a claim about that path without checking §3's secret inventory.

---

## 3. Verified facts — do not re-derive these

Every number below was measured. Where *how* it was measured matters, that is stated.

### Licensing (indicator 2)
- `LICENSE` Apache-2.0 — **provisional**, the choice was referred to the consultant.
- `NOTICE` names **no copyright holder** — deliberate, blocked on the IP determination.
- **593 source files** carry SPDX headers — `python3 scripts/ops/add_spdx_headers.py --check`.
- **153 packages** across four sets (35 declared Python / 98 transitive / 16 npm production / 4 images),
  **0 non-OSI, 0 unknown**, 10 dispositions.
- ⚠ The nightly licence scan is **scheduled and has never run on a deployed host** — `ops` is on
  neither server. Do not call it a guarantee.

### The AI layer (indicator 4)
- **9 call sites, 2 subsystems, 1 registry** (`backend/config/llm_config.py`). None names a model,
  provider or endpoint.
- **5 are live**; 4 are the parked voice flow, declared in `PARKED_TASKS` with a test enforcing
  "enqueued in production or declared parked, nothing else".
- **2 models, not 6** — every text task resolves to one small model, transcription to one speech model.
  8 task keys, 2 values.
- `diff .env.openai .env.open` is the whole switching delta.
- The CI job `dpg-platform-independence` returns **4 passed / 1 xfailed / exit 0** run by hand against
  an Apache-2.0 open-weights model. ⚠ **It has never executed in CI.**
- Closed baseline: **F1 0.762**, precision 0.773, recall 0.752, exact-set 0.686, **p99 24.5 s** (inside
  the 30 s budget). 105 authored items, synthetic — an **upper bound**, not an estimate.
- Open column: detection only. The classification blocker was **our own prompt** (~20,700 chars,
  catalogue injected three times), since cut **70%**. Re-running needs time, not a decision.
- **SEAH recall is unmeasured for both candidates** and cannot be measured from this repository — the
  committed set holds no harassment reports, by decision. **The single blocking measurement.**
- T1/T2 crossover **40,000–780,000 grievances/month** vs a national ceiling near **7,700**. Self-hosting
  is a **data-sovereignty decision with a price**, never a cost decision.

### ⚠ Four counter-intuitive corrections — each was wrong in the pack first

1. **Voice intake works; automatic transcription is unfunded.** A complainant records, audio is stored,
   an officer handles it. What does not run is machine transcription — off on **cost** grounds, and the
   government is not expected to fund it. Never write "cannot transcribe" unqualified.
2. **The consequence runs in our favour**: the one path the open provider cannot serve is the one path
   that does not run, so **the open configuration covers every model call the system actually makes.**
3. **`rasa-sdk` is NOT a type shim.** 49 modules import it, `BaseFormValidationAction` **inherits**
   `FormValidationAction`, and the orchestrator executes `action.run(...)`. The true and sufficient
   claim is narrower: **no Rasa server, no Rasa NLU, no TensorFlow** — and `rasa-sdk` is Apache-2.0.
4. **GitHub's 34 Dependabot alerts are against `main`, 2 months stale** (2026-06-25, 333 commits behind,
   all three manifests differ). Real count on this branch: **6 Python + 4 npm-high**. Prioritise by
   **reachability** — `sanic-cors` and `wheel` are unreachable; **`ecdsa` (via `python-jose`, the
   Keycloak JWT path) is reachable and has no published fix.**

### Privacy (indicators 7, 9)
- Assessment + 13-leg data-flow diagram exist, verified at file and line. **No lawyer has read it**;
  every statutory section number is marked unverified.
- ⭐ **No genuine grievance has ever been processed** — every record is seed data or a demo dummy. Every
  exposure is **prospective**, and redaction is a **go-live precondition, not remediation**. ⚠ This
  expires at go-live, and a demo participant may have entered their own real contact details.
- Three storage defects **fixed** 2026-08-19: encryption fails closed, HMAC search tokens, backups
  discard unencryptable dumps.
- Still open: unredacted egress (Sprint 3, not started), **no deletion capability anywhere**, no
  retention period, a breach runbook with three decisions blank, no legal review.

### Secrets, as of 2026-08-24
- `secrets.enc.env` holds **17 keys** — including `OPS_DB_PASSWORD`, `DOIT_SMS_BEARER_TOKEN`,
  `KEYCLOAK_ADMIN_PASSWORD`, `KEYCLOAK_CLIENT_SECRET` and `KEYCLOAK_WEBHOOK_SECRET`, all folded in on
  2026-08-24 after they were found living only on the staging host.
- `POSTGRES_PASSWORD` and `REDIS_PASSWORD` rotated. **`DB_ENCRYPTION_KEY` has never been committed** —
  the one secret that cannot be rotated, since no re-encryption path exists.
- ⭐ **No live secret is in public git history.** `SMTP_USERNAME` was the exception and was unremovable,
  being the git author on 865 commits — staging's mail config replaced it, so the live value is a
  different address (verified: 0 of 1,037 commits). **Recommendation on record: do not purge history.**
- ⚠ **`TICKETING_SECRET_KEY` is empty** (0 chars). The ticketing API refuses to boot without it outside
  the dev bypass, so this blocks any deployment.
- ⚠ **`SEARCH_TOKEN_PEPPER` is unset everywhere**, and `base_manager.py:557` reads
  `os.getenv("SEARCH_TOKEN_PEPPER") or self.encryption_key`. Every stored search token therefore derives
  from `DB_ENCRYPTION_KEY`. See §4 — this makes *defining* it the destructive act.

### Ops monitoring
- **Repaired 2026-08-24, and it has never run on a deployed host.** Four independent defects: `ops`
  authenticated as `ops_app` using the `user` role's password (which the `POSTGRES_PASSWORD` rotation
  then broke — 253 auth failures, last successful write 2026-08-18, container reporting `healthy`
  throughout); one failed query aborted the whole Postgres transaction with no rollback, making per-row
  degradation per-report; four queries named columns that do not exist; and `ops_app` lacked `SELECT` on
  five tables it reads.
- Keycloak recorded **no login or admin events at all** until 2026-08-24 — realm event storage defaults
  to off. Forward-only; nothing before that date is recoverable, and it is not yet applied to staging or
  prod.

### Blocked externally
- **No IP determination** → no copyright holder, no submission. Nobody on the project can resolve it,
  and the owner has written to the *consultant*, which is not the ADB OGC channel.

---

## 4. Open work that is not documentation

Carry these into the new `00` as gaps.

### Deploying to AWS staging and DOR prod — nothing started

The authoritative runbook is
[`../deployment/18_sops_migration_handover.md`](../deployment/18_sops_migration_handover.md) §5a. Its
hazards, as they now stand:

- ✅ **`DB_ENCRYPTION_KEY` — the step with no undo — is cleared for staging.** Digests match locally
  and on the host. ⚠ **DOR prod is still unchecked** (no access from the dev box), so this hazard is
  open **for prod only**.
- ⚠ **`SEARCH_TOKEN_PEPPER`: the destructive act is *introducing* it, not rotating it.** It is unset
  everywhere and falls back to the encryption key, so every stored token already derives from that. The
  first host to define the variable orphans every search token — silently, presenting as *"no such
  complainant"*.
- ⚠ **Staging's `env.local` holds 30 variables that existed in neither committed half**, measured on
  the host. They are now folded: 5 secrets and 8 non-secrets shared, 2 overwritten, and **10 host-specific
  ones that must stay in `env.local.extra`** because they encode a hostname or an auth mode.
  **`SMS_ENABLED=true` is one of them** — shared, every developer's stack would send real SMS to Nepali
  phone numbers.
- ⚠ **Publishing a database credential does not set it.** `make env-local` puts `OPS_DB_PASSWORD` on a
  host; until someone runs `ALTER ROLE ops_app PASSWORD` on that box, `ops` cannot authenticate and will
  report `healthy` while writing nothing. Recoverable, but nothing tells you.
- Then: the Postgres credential + `ALTER ROLE`, the Redis credential, `TICKETING_SECRET_KEY` (empty),
  and the taxonomy re-seed. Database credentials:
  [`../sprints/followups/db-password-hardcoded-in-compose.md`](../sprints/followups/db-password-hardcoded-in-compose.md).

### The rest

- **SEAH recall measurement** — blocks model selection.
- **The open benchmark column** — unblocked by the prompt cut; needs time.
- **Sprint 3 (PII redaction)** — not started.
- **`ops` not deployed** to either server, so no CVE or licence scan runs anywhere but a dev stack.

---

## 5. ⭐ Generate `02_questions.md`; do not hand-maintain it

The single most valuable mechanical decision available. Two hand-maintained copies of the same
questions cost two reconciliation passes this week.

**This repository already has the pattern**: `.env.example` is generated from `declared_env_vars()` and
`tests/backend/test_llm_config_pins.py` fails if either side drifts. Do the same — questions live under
each indicator in `00`, a script extracts them into `02`, and a test fails if regenerating produces a
diff. ~30 lines, and drift becomes **impossible** rather than discouraged.

---

## 6. Traps

Every one of these produced a wrong result that looked right.

### The one that is not mechanical

⭐ **`X or fallback` on a security-relevant value hides the absence of `X`.** It hid
`SEARCH_TOKEN_PEPPER` (§3) and it blinded the ops monitor (§3) — in the same week, in two unrelated
subsystems. When you meet the pattern, ask what happens when the left side is empty, and whether
anything would tell you.

### The mechanical ones

| Trap | What happens |
|---|---|
| **Markdown bold breaks greps** | `grep "fails closed"` misses `fails **closed**`. A verification pass reports a false negative and you "fix" something already correct |
| **`\|` is not alternation under `grep -E`** | It matches a literal pipe. A multi-probe check silently reports everything missing |
| **`§(\d+)(?!\.)`** | Excludes any section reference ending a sentence. A dangling-reference check reported clean while `§6` dangled |
| **Hashing a missing variable** | `grep -oP '^VAR=\K.*' \| sha256sum` on an absent variable hashes the empty string and returns the same digest on every host that also lacks it — reading as "match, safe to proceed" |
| **Anchor-based edit scripts** | Validate-then-write-at-the-end means **a failed anchor applies nothing** while earlier `print` output claims success. Re-read the file, never trust the script's own summary |
| **Guessing line wraps in anchors** | Three attempts failed on this in one pass. Match with regex and flexible whitespace |
| **`tests/repo` in a container** | 6 tests fail because `git` exits 255 there. They pass on the host and in CI. Not defects |
| **Containers run baked images** | `backend` has no bind mount, so a code change appears not to work — or appears to work when it did not. Bind-mount with `-v "$PWD:/app"` or the result is meaningless |

**Docker-only.** Per `CLAUDE.md`, anything that builds, serves, or mutates the database goes through
Compose. Host CLIs are for reading.

---

## 7. Suggested order

1. Fix the evidence-document defects in §2 — small, and they are wrong *now*.
2. Write the new `00` indicator by indicator. Header contract first. Cite, never restate.
3. Generate `02_questions.md` from it; add the pin test.
4. Re-derive `01` from the new `00` **in the same pass**.
5. Write `03_remediation_record.md` from `PROGRESS.md`, headed "not part of the assessment".
6. Verify: relative links across `docs/` resolve, `tests/repo` passes **on the host**, no live secret
   appears in any tracked file.
