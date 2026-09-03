# Follow-up / scoping — 95 mutation checks are recorded as prose, so none of them can be re-run

> **Raised:** 2026-08-27, at the end of Sprint 3's DPG-33 step 1.
> **Status:** ⬜ **OPEN — scoped for another agent.** This document is the brief; it is meant to be
> executable from cold without reading the sprint.
> **Size:** M. One data format, one runner script, one seed set. No new dependency.
> **Priority:** 🟠 — nothing is broken today. What is missing is the ability to *know* it is not.

---

## 1. The finding

[`TESTS.md`](../TESTS.md) contains **95 mutation records**. Every one is a sentence like:

> ✅ **Checked** — deadline hard-coded → red · attempt 1 given the background timeout → red

Each was a real manual run: edit a file, run pytest, read the result, restore from a copy in `/tmp`.
**None of them can be re-run**, by anyone, including their author a week later. There is no mutation
tooling in the repository — `grep` for `mutmut` / `cosmic-ray` / `mutpy` returns nothing.

Three consequences, in increasing order of how much they matter:

1. **Nobody can reproduce the check.** The claim and the evidence are the same sentence.
2. **A test that *stops* catching its mutation goes unnoticed.** Someone refactors, an assertion
   quietly becomes decorative, and the ledger still reads `✅ Checked` — now describing something
   that is no longer true.
3. ⭐ **A reviewer cannot verify it.** That matters more here than in a normal codebase, because the
   DPG evidence pack's central claim is *"every assertion is checkable"*. A ledger of 95 unverifiable
   check-marks sits awkwardly beside it.

## 2. Why this is worth building rather than shrugging at

**In one working session (2026-08-27, 16 commits) a mutation caught a decorative test three separate
times.** Not a hypothetical failure mode — the actual, repeated one:

| # | What the test claimed | What the mutation revealed |
|---|---|---|
| 1 | PII is masked at the phone log sites | It tested the **helper**, not the call sites. Reverting the masking at *both* call sites left all ten tests green |
| 2 | The OTP is cleared on successful verification | It scanned **any** dict containing `otp_status`, and the *expired* branch clears the same keys — so deleting the clearing from the *verified* branch passed |
| 3 | The SEAH flag only escalates | It drove `update_grievance_with_tracking` — **the wrong method**. The fix was sitting on a path the defect does not use. The mutation found that; no review would have |

Nothing but a mutation would have caught any of the three. That is the argument for making them
durable, and it is the argument to put in the PR description.

## 3. What to build

### 3.1 The records, as data

One file per test module, beside the tests:

```yaml
# tests/mutations/test_pii_service.yml
- id: T-31-e-global-counter
  target: backend/services/pii_service.py
  find: "    counters: dict[str, int] = {}"
  replace: "    counters = _GLOBAL_COUNTERS"
  tests: tests/backend/test_pii_service.py
  expect: kills                      # the suite MUST go red
  why: >
    Two concurrent grievances must not share <PERSON_1> — a shared counter makes the mapping
    ambiguous and turns placeholders into a cross-document correlation channel.

- id: T-31-a-dual-script-class
  target: backend/services/pii_service.py
  find: '_ANY_DIGIT = rf"[0-9{_D}]"'
  replace: '_ANY_DIGIT = r"[0-9]"'
  tests: tests/backend/test_pii_service.py
  expect: survives                   # ⭐ documented NON-KILL, see §3.3
  why: >
    find_pii normalises once, centrally, so the dual-script class is redundant
    defence-in-depth rather than the working part. Removing the *normalisation* is what kills.
```

### 3.2 The runner

`scripts/ops/run_mutations.py`, roughly:

```
for each record:
    assert `find` occurs EXACTLY ONCE in target      # else the mutation is ambiguous
    apply the replacement
    run `tests`
    restore                                           # see the trap in §4.1
    compare the outcome against `expect`
report: n checked, n as expected, n diverged (and which)
```

Exit non-zero only when an outcome **diverges from `expect`**.

### 3.3 ⭐ `expect: survives` is a first-class outcome, not an exception

This is the design point that makes the tool honest rather than decorative in its own right.

Some mutations *should* survive, and pretending otherwise is how a ledger starts lying. T-31-a is the
worked example: removing the Devanagari half of the digit class changes **no behaviour**, because
matching always happens on the normalised string. A runner that demanded every mutation kill would
force someone to either delete a useful safety net or fake the record.

So the runner asserts **the recorded expectation**, and a `survives` entry must carry a `why` that
explains what *does* kill. A `survives` with no explanation should fail validation.

## 4. Traps — each of these cost real time this sprint

### 4.1 Restore with git, never with a backup copy

Backups in `/tmp` were how this was done by hand, and a runner that dies mid-run would leave the tree
mutated. Use `git stash` / `git checkout --` on the target file, and restore in a `finally`. **Verify
the tree is clean before starting** and refuse to run otherwise, so a mutation is never applied on
top of uncommitted work that the restore would then destroy.

### 4.2 A source-level pin can flag its own documentation

Real, and it happened on the first run of `test_log_pii_pruning.py`: the pin banned `slot_value[:` and
then the **comment explaining the repaired call site** contained that exact string. Resolved by
stripping comments before the check — the same resolution T-15b-d already uses.

For this runner the equivalent trap is the `find` string: it may match a comment, a docstring, or the
mutation record's own `why`. Hence the exactly-once assertion in §3.2, and prefer `find` strings that
include indentation and surrounding syntax.

### 4.3 Some tests only run in a container

`backend/services/llm_client.py` and `ticketing/clients/llm_client.py` import the OpenAI SDK at module
level, and **`openai` is not installed on the host**. Those suites are excluded from host runs
(`--ignore=tests/backend/test_llm_services.py` and friends).

For those, the by-hand method that worked was:

```bash
docker cp <mutated file> nepal_chatbot-celery_llm-1:/app/<path>
docker exec nepal_chatbot-celery_llm-1 python -m pytest <tests> -q
docker cp <original file> nepal_chatbot-celery_llm-1:/app/<path>
```

This avoids a full image rebuild per mutation (~90 s each, which makes a 25-mutation run unusable).
A record therefore needs an optional `runner: container` field naming the container.

### 4.4 Do not make it a CI gate — at least not first

It will be slow: every mutation is a full suite run. **A slow gate becomes the gate nobody watches**,
which is D-26's lesson in this repository, learned expensively (CI was red for ten days and
indistinguishable from a build nobody was looking at). Ship it as a script someone runs deliberately —
before a release, or when touching a pinned invariant. Revisit CI only once the runtime is known.

## 5. ⚠ Explicit non-goal: `mutmut`, `cosmic-ray`, generic mutation testing

**Do not reach for an off-the-shelf mutation tester.** They generate thousands of generic mutants —
flip `+` to `-`, `<` to `<=` — and the value in this repository is in the *targeted* ones that encode
a specific, real defect:

> *"the OTP is logged again"* · *"the district is redacted"* · *"expiry is checked after the match"* ·
> *"the payload carries the narrative again"* · *"the flag is written as a plain assignment"*

No generic tool produces those, because they are statements about **this system's failure modes**,
authored by whoever just fixed one. A tool that emits 3,000 mutants would bury the 25 that mean
something, and the runtime would guarantee nobody ran it twice.

The hand-authored mutation is the artefact. This ticket is about making it **repeatable**, not about
generating more.

## 6. The seed set

Do not back-fill all 95. Start with the ~25 from this sprint, which are the freshest and the
best-documented:

- **Where they are:** `git log --since=2026-08-27 --format=%B | grep -i mutation` (12 commits), and
  the `Mutation check` column of [`TESTS.md`](../TESTS.md).
- **Best-documented modules to start with**, because their commit messages name the exact edit:
  `test_pii_service.py` (6), `test_redaction_at_the_model_boundary.py` (4),
  `test_sensitive_flag_only_escalates.py` (3), `test_celery_payload_carries_no_narrative.py` (4),
  `test_log_pii_pruning.py` (4), `test_otp_verification.py` (4).
- ⚠ **Transcribing a record is not mechanical.** The commit message says *what* was changed in prose;
  the `find`/`replace` has to be reconstructed and then **verified to actually reproduce the recorded
  outcome**. A record that does not reproduce is a finding in itself — either the test changed or the
  original claim was wrong, and both are worth knowing.

## 7. Acceptance

- [ ] `tests/mutations/*.yml` for at least the six modules in §6
- [ ] `scripts/ops/run_mutations.py` — applies, runs, restores, compares against `expect`
- [ ] Refuses to run on a dirty tree; restores in a `finally`; verified by killing it mid-run
- [ ] `find` asserted to occur **exactly once**, with a clear error naming the record when it does not
- [ ] `expect: survives` supported as a first-class outcome, and **rejected without a `why`**
- [ ] `runner: container` supported for the OpenAI-importing suites (§4.3)
- [ ] **Every seeded record verified to reproduce its recorded outcome** — and any that does not is
      written up rather than quietly adjusted
- [ ] NOT wired into CI, with the reason in the script header (§4.4)
- [ ] `TESTS.md`'s prose records cross-reference their record `id`, so the ledger and the data agree
- [ ] A short section in [`04_testing.md`](../../../engineering/04_testing.md) — this becomes a house
      practice or it decays back into prose

## 8. Related

- [`../TESTS.md`](../TESTS.md) — the 95 prose records this replaces
- [`../../../engineering/04_testing.md`](../../../engineering/04_testing.md) §5 — pinning tests, where the practice belongs
- [`../PROGRESS.md`](../PROGRESS.md) → **D-42**, the sprint's first decorative test, found the same way
- [`../../../TODO.md`](../../../TODO.md) — the backlog row
