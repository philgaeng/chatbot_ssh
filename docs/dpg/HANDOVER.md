# Handover — rewriting the DPG compliance pack from scratch

**Written:** 2026-08-23, at the end of a session that got this wrong several times.
**For:** the agent writing the new `00_compliance_status.md`, `02_questions.md` and
`03_remediation_record.md`, and re-deriving `01_consultant_briefing.md`.
**Read this first.** It exists so you do not re-derive facts that took a day to establish, and do not
repeat the mistakes that made a rewrite necessary.

---

## 0. Why the previous pack was archived

Not because the facts were wrong. Because the **structure** was.

The 2026-08-17 originals were written before Sprints 1 and 2 landed. On 2026-08-23 they were
"rewritten" — but the rewrite kept the original's shape and voice, and only replaced the prose. What
followed was five rounds of the owner saying *"this doesn't belong here"*:

| What the owner had to point out | The underlying error |
|---|---|
| Questions argued their own answers | We were asking the expert to check our homework |
| §5 "Decisions we have already taken" | A changelog inside an assessment |
| §4 narrated the engineering | Reference material inside a pre-read |
| §2 was two-thirds achievements | An assessment listing accomplishments |
| The two documents duplicated each other | No decision about which was the source |

**The root cause: nobody asked what each document was *for* before writing it.** Every correction
above follows from that one omission.

⚠ **So before you write a line, write the contract in the header**: what this document is, as of when,
what it is **not**, and where the other thing lives. If you cannot state what belongs in a section and
what does not, do not write the section.

**The archived files are in [`archive/`](archive/)** — the 2026-08-17 originals and the 2026-08-23
state. Do not edit them; they are the record. `archive/` is excluded from the docs link checker and
the `file.py:line` pin, so they cannot rot or break gates.

---

## 1. The target structure, as agreed

```
docs/dpg/
  00_compliance_status.md     ← rewrite from scratch, dated today.
                                One paragraph per indicator: what we have / gaps /
                                suggested remedies / questions. CITE the evidence
                                documents, never restate them.
  01_consultant_briefing.md   ← re-derive from the new 00 IN THE SAME PASS.
                                A pre-read. Not a summary of the old 00.
  02_questions.md             ← GENERATED from 00. See §5 — this is the one
                                mechanical decision that matters.
  03_remediation_record.md    ← what the sprints fixed. Explicitly NOT part of the
                                assessment; sent only in response to one.
                                Derive from docs/sprints/2026-08-llm/PROGRESS.md.
  archive/                    ← the four archived files. Never edited.
  <the five evidence documents, unchanged — see §2>
```

**Question numbering: `Q-<indicator>-<n>`.** `Q-03-01` is the first question about indicator 3.
Numbers become *derived from structure*, so inserting a question never renumbers another. Use
**`Q-00-xx` for process questions** that belong to no indicator (submission route, precedents,
assessment timeline, "what are we missing") — otherwise they become a special case that leaks.

---

## 2. The five evidence documents — keep, cite, do not restate

These were deliberately **not** archived. They are measurements and generated inventories, not
positions, and the new `00` is short precisely because it cites them.

| Document | What it is | State |
|---|---|---|
| [`dependency-licenses.md`](dependency-licenses.md) | Generated: `pip-licenses`, `license-checker`, image digests. 153 packages | Good. Has accreted some process narration |
| [`privacy-assessment.md`](privacy-assessment.md) | 13 data-flow legs verified at file+line, 18 findings | **Strongest document in the pack.** ⚠ Being edited by a parallel agent — do not stomp |
| [`model-benchmarks.md`](model-benchmarks.md) | Measured model results | ⚠ **Needs its own from-scratch rewrite — but LATER**, see below |
| [`open-model-configuration.md`](open-model-configuration.md) | How to run on open models + capability matrix | ⚠ One broken bullet, see below |
| [`vllm-deployment.md`](vllm-deployment.md) | Self-hosting design + costing for a parked option | Fine. Small |

⚠ **Do not move them into a subdirectory.** 48 markdown links outside `docs/dpg/` and 10 code
references point at them. Give the new `00` an evidence-index table instead.

### Three defects to fix before anything is sent

1. **`privacy-assessment.md` §3.7** — the cross-border table still says *"6 chatbot model calls …
   full narrative, complainant name and phone, audio"*. This **contradicts F-1 and leg L4 in the same
   document**, which were corrected to five live sites with contact details not leaving. One-line fix
   in the strongest document in the pack.
2. **`open-model-configuration.md` "What is not yet true"** — the transcription bullet has benchmark
   news appended inside it, so it reads as one incoherent item. Split it.
3. **`model-benchmarks.md`** carries three layers of the same numbers: §2 post-fix, §3.7 before *and*
   after, §4 marked "superseded by §3.7", §6 pre-fix. **Rewrite it from scratch when the open column
   lands**, not now — so it is rewritten once against complete data instead of twice.

⚠ Several `privacy-assessment.md` entries are dated **2026-08-24**, which is in the future. Check
before it goes anywhere external.

---

## 3. Verified facts — do not re-derive these

Every number below was measured this week. Where it was measured *how* matters, that is stated.

### Licensing (indicator 2)
- `LICENSE` Apache-2.0 — **provisional**, the choice was referred to the consultant.
- `NOTICE` names **no copyright holder** — deliberate, blocked on the IP determination.
- **593 source files** carry SPDX headers. Measured with `python3 scripts/ops/add_spdx_headers.py --check`.
- **153 packages** across four sets (35 declared Python / 98 transitive / 16 npm production / 4 images),
  **0 non-OSI, 0 unknown**, 10 dispositions.
- ⚠ The nightly licence scan is **scheduled but not deployed** — `ops` is on neither server, so it runs
  only where a dev stack happens to be up at 01:50. Do not call it a guarantee.

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
  catalogue injected three times), since cut **70%**. Re-running it needs time, not a decision.
- **SEAH recall is unmeasured for both candidates** and cannot be measured from this repository — the
  committed set holds no harassment reports, by decision. **This is the single blocking measurement.**
- T1/T2 crossover **40,000–780,000 grievances/month** vs a national ceiling near **7,700**. So
  self-hosting is a **data-sovereignty decision with a price**, never a cost decision.

### ⚠ Four counter-intuitive corrections — each was wrong in the pack first

1. **Voice intake works; automatic transcription is unfunded.** A complainant records, audio is stored,
   an officer handles it. What does not run is machine transcription — switched off on **cost** grounds,
   and the government is not expected to fund it. Never write "cannot transcribe" unqualified.
2. **The consequence runs in our favour**: the one path the open provider cannot serve is the one path
   that does not run, so **the open configuration covers every model call the system actually makes.**
3. **`rasa-sdk` is NOT a type shim.** 49 modules import it, `BaseFormValidationAction` **inherits**
   `FormValidationAction`, and the orchestrator executes `action.run(...)`. The true and sufficient
   claim is narrower: **no Rasa server, no Rasa NLU, no TensorFlow** — and `rasa-sdk` is Apache-2.0.
4. **GitHub's 34 Dependabot alerts are against `main`, which is 2 months stale** (last touched
   2026-06-25, 333 commits behind, all three manifests differ). Real count on this branch: **6 Python +
   4 npm-high**. Prioritise by **reachability** — `sanic-cors` and `wheel` are unreachable; **`ecdsa`
   (via `python-jose`, the Keycloak JWT path) is reachable and has no published fix.**

### Privacy (indicators 7, 9)
- Assessment + 13-leg data-flow diagram exist, verified at file and line. **No lawyer has read it**;
  every statutory section number is marked unverified.
- ⭐ **No genuine grievance has ever been processed** — every record is seed data or a demo dummy. So
  every exposure is **prospective**, and redaction is a **go-live precondition, not remediation**.
  ⚠ This statement expires at go-live, and a demo participant may have entered their own real contact
  details.
- Three storage defects **fixed** 2026-08-19: encryption fails closed, HMAC search tokens, backups
  discard unencryptable dumps.
- Still open: unredacted egress (Sprint 3, not started), **no deletion capability anywhere**, no
  retention period, breach procedure partially written with three decisions blank, no legal review.
- Secrets: `POSTGRES_PASSWORD` and `REDIS_PASSWORD` both rotated this week. **`DB_ENCRYPTION_KEY` was
  never committed** — the one secret that cannot be rotated. `SMTP_USERNAME` is in history and
  **unremovable** (git author on 865 of 1,018 commits). **Recommendation on record: do not purge
  history.**

### Blocked externally
- **No IP determination** → no copyright holder, no submission. Nobody on the project can resolve it,
  and the owner has written to the *consultant*, which is not the ADB OGC channel.

---

## 4. Open work that is not documentation

Carry these into the new `00` as gaps; do not treat them as done.

- **Deploy to AWS staging and DOR prod — six interlocking steps, none started.** ⚠⚠ Compare
  `DB_ENCRYPTION_KEY` and `SEARCH_TOKEN_PEPPER` hashes per host **first** — mismatched values make a
  shared `secrets.enc.env` push **irreversible**. Then SOPS per host, Postgres credential + `ALTER
  ROLE`, Redis credential, `TICKETING_SECRET_KEY` (empty — the ticketing API refuses to boot), and the
  taxonomy re-seed. Runbook: [`../sprints/followups/db-password-hardcoded-in-compose.md`](../sprints/followups/db-password-hardcoded-in-compose.md).
- **SEAH recall measurement** — blocks model selection.
- **The open benchmark column** — unblocked by the prompt cut.
- **Sprint 3 (PII redaction)** — not started.
- **`ops` container not deployed** — so no nightly CVE or licence scan runs on either server.

---

## 5. ⭐ Generate `02_questions.md`; do not hand-maintain it

The single most valuable mechanical decision available. Two hand-maintained copies of the same
questions cost two reconciliation passes this week.

**This repository already has the pattern**: `.env.example` is generated from
`declared_env_vars()` and `tests/backend/test_llm_config_pins.py` fails if either side drifts. Do the
same — questions live under each indicator in `00`, a script extracts them into `02`, and a test fails
if regenerating produces a diff. ~30 lines, and drift becomes **impossible** rather than discouraged.

---

## 6. Traps that cost real time this session

Every one of these produced a wrong result that looked right.

| Trap | What happens |
|---|---|
| **Markdown bold breaks greps** | `grep "fails closed"` misses `fails **closed**`. Verification reports a false negative and you "fix" something already correct |
| **`\|` is not alternation under `grep -E`** | It matches a literal pipe. A multi-probe check silently reports everything missing |
| **`§(\d+)(?!\.)`** | Excludes any section reference ending a sentence. A dangling-reference check reported clean while `§6` dangled |
| **Anchor-based edit scripts** | Validate-then-write-at-the-end means **a failed anchor applies nothing** while earlier `print` output claims success. Always re-read the file after |
| **Guessing line wraps in anchors** | Three attempts failed on this in one pass. Match with regex and flexible whitespace instead |
| **`tests/repo` in a container** | 6 tests fail because `git` exits 255 there. They pass on the host and in CI. Not defects |
| **Containers run baked images** | `backend` has no bind mount, so a code change appears not to work — or worse, appears to work when it did not. Bind-mount with `-v "$PWD:/app"` or the result is meaningless |
| **A "success" line printed by an earlier statement** | I reported "6 cross-references remapped" when zero had been applied. Verify by re-reading, never by the script's own output |

**Docker-only.** Per `CLAUDE.md`, anything that builds, serves, or mutates the database goes through
Compose. Host CLIs are for reading.

---

## 7. Suggested order

1. Fix the three evidence-document defects in §2 — small, and they are wrong *now*.
2. Write the new `00` indicator by indicator. Header contract first. Cite, never restate.
3. Generate `02_questions.md` from it; add the pin test.
4. Re-derive `01` from the new `00` **in the same pass**.
5. Write `03_remediation_record.md` from `PROGRESS.md`, headed "not part of the assessment".
6. Verify: relative links across `docs/` resolve (~1,620), `tests/repo` passes **on the host**, no live
   secret appears in any tracked file.

**The discipline that matters most:** if you find yourself appending a correction to a paragraph,
stop. That is how the archived pack got the way it did. Rewrite the paragraph.
