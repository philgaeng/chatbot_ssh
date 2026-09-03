# Follow-up / scoping — 95 mutation checks are recorded as prose, so none of them can be re-run

> **Raised:** 2026-08-27, at the end of Sprint 3's DPG-33 step 1.
> **Status:** ✅ **BUILT 2026-09-03** — `tests/mutations/*.yml` (30 records, 6 modules) +
> [`scripts/ops/run_mutations.py`](../../../../scripts/ops/run_mutations.py). Every record was
> **verified to reproduce its recorded outcome**. House practice:
> [`04_testing.md`](../../../engineering/04_testing.md) §5a. The brief below is kept as written;
> **§9 records what building it actually found**, including the two records that did not reproduce
> first time and where the brief's estimates were wrong.
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

- [x] `tests/mutations/*.yml` for at least the six modules in §6
- [x] `scripts/ops/run_mutations.py` — applies, runs, restores, compares against `expect`
- [x] Refuses to run on a dirty tree; restores in a `finally`; verified by killing it mid-run
- [x] `find` asserted to occur **exactly once**, with a clear error naming the record when it does not
- [x] `expect: survives` supported as a first-class outcome, and **rejected without a `why`**
- [x] `runner: container` supported for the OpenAI-importing suites (§4.3)
- [x] **Every seeded record verified to reproduce its recorded outcome** — and any that does not is
      written up rather than quietly adjusted
- [x] NOT wired into CI, with the reason in the script header (§4.4) — ⚠ and the reason is now
      partly different: see §9.4, the set runs in ~20 s
- [x] `TESTS.md`'s prose records cross-reference their record `id`, so the ledger and the data agree
- [x] A short section in [`04_testing.md`](../../../engineering/04_testing.md) §5a — rules 5.3–5.8,
      plus a definition-of-done row and a command-table entry

## 8. Related

- [`../TESTS.md`](../TESTS.md) — the 95 prose records this replaces
- [`../../../engineering/04_testing.md`](../../../engineering/04_testing.md) §5 — pinning tests, where the practice belongs
- [`../PROGRESS.md`](../PROGRESS.md) → **D-42**, the sprint's first decorative test, found the same way
- [`../../../TODO.md`](../../../TODO.md) — the backlog row

---

## 9. What building it found (2026-09-03)

**Shipped:** 30 records across the six modules in §6, `scripts/ops/run_mutations.py`, and §5a of
[`04_testing.md`](../../../engineering/04_testing.md). Every acceptance box in §7 is ticked. The
count is 30 rather than ~25 because two prose records covered more than one edit: the phone-masking
check reverted **both** call sites (split into one record per site, since the pin now fires per
site), and `test_celery_payload_carries_no_narrative.py` accumulated a second set of four mutations
from the SEAH half in `b348773e` after the ledger row was written.

### 9.1 ⭐ The clean-tree refusal fired on its first real run, and was right

§4.1's rule — restore with git, refuse on a dirty tree — reads like defensive boilerplate. On the
very first invocation it **blocked a `git checkout --` over another session's uncommitted work** on
`backend/services/pii_service.py` (a DPG-32 output-redaction change in flight). Had the runner used
the by-hand `/tmp` method, or skipped the check, that work would have been destroyed silently.

One refinement the brief did not anticipate: `git status --porcelain` counts **untracked** files as
dirty, so the runner refused to start on its own record files before they were committed. Untracked
files cannot be destroyed by `git checkout -- <target>`, so the blanket refusal now counts **tracked
modifications only**, while a target that is dirty *or untracked* still hard-refuses. Without that
split the guard would fire on every run and everyone would learn to pass `--allow-dirty` — D-26's
lesson in miniature.

### 9.2 Two records did not reproduce first time — both authoring faults, both caught by a guard

§6 warned that transcription is not mechanical. It was right, though not in the way expected: the
failures were in the *records*, not in the tests.

| What broke | Which guard caught it |
|---|---|
| The print-ban anchor was `# Get the Celery task ID…` + `task_id = …` — **boilerplate repeated in three tasks**. Mutating two at once would have tested something nobody wrote down | The **exactly-once assertion** (§3.2/§4.2). Re-anchored on the transcribe task's own docstring tail |
| The in-place-redaction `replace` was a **single-quoted YAML scalar**, where `\n` stays two literal characters — so the mutation shipped a `SyntaxError` into the container instead of the edit | pytest exits **2** on a collection error, not 1, so it was reported as `broken` rather than miscounted as a kill. A `ast.parse` guard was then added so this fails at validation with a message naming the cause |

The second one is the more interesting: **without a distinct `broken` outcome, a mutation that does
not compile looks exactly like a mutation the test caught.** That would have manufactured a green
record for an edit that never ran — the precise failure mode this ticket exists to remove,
reintroduced one layer up.

### 9.3 ⚠ A trap the brief did not have: stale bytecode makes the runner report the wrong edit

The nastiest bug found while building this, because it produces a **confident wrong answer** rather
than an error. A record passed in isolation and failed in the full run; the cause was not the record.

CPython validates a cached `.pyc` against the source's `(mtime, size)`, and **the mtime in the pyc
header has one-second granularity**. Two mutations of the same file that change its length by the
same number of bytes — utterly ordinary; both of the `T-31-d` pair append `, "Jhapa",` to different
lists, i.e. **exactly 9 characters each** — produce an identical `(mtime, size)` pair when they run
inside the same second, which they do at ~0.2 s per record. The second mutation then executed **the
first mutation's bytecode**, and the runner faithfully reported the result of an edit it had not made.

For a tool whose entire job is to say *"this edit produces this outcome"*, that is the worst
available failure. Fixed by running every mutated suite with `PYTHONDONTWRITEBYTECODE=1` (host and
container), plus purging any existing `__pycache__` entry for the target first. Two consecutive full
runs are now identical at 31/31.

⭐ **Note how it was caught:** by the outcomes disagreeing between a `--module` run and a full run,
which only happens because the expectations are *recorded* and *compared*. Run by hand, this would
have looked like one flaky record and been shrugged at.

### 9.4 Where the brief's estimates were wrong

* **Runtime: ~20 s for all 30**, not the "slow, every mutation is a full suite run" §4.4 assumed.
  These suites are small and fast (0.1–0.9 s each). §4.4's conclusion still stands, but **for a
  different reason**: 10 of the 30 need a live Compose stack, which CI does not have. If the
  container records were ever split out, the host set (~13 s) would be a defensible gate.
* **`docker cp` is genuinely required.** Confirmed rather than assumed: `docker inspect` shows the
  container has **no bind mounts**, so the code is baked into the image and a host edit is invisible
  to it. The runner snapshots the container's *own* bytes before mutating rather than assuming they
  equal the host's — so a stale image surfaces as a `find` that does not match, which is a finding
  ("rebuild first"), not something to loosen an anchor for.
* **`git worktree` is the way to run this while other work is in flight.** With `pii_service.py`
  dirty from another session, the records were verified in a detached worktree at `HEAD` — which is
  also the *right* baseline, since the records describe committed code.

### 9.5 ⭐ It caught a live regression within an hour of existing — in a commit made while it was being built

The strongest argument for the tool is not the seeding; it is what happened next. Commit
`7dddf5e8` (DPG-33 output redaction) landed **during** this work and tightened the roman address
pattern in `_find_addresses`. Re-running the 30 records against the new `HEAD` turned
`T-31-d-district-added-to-qualifiers` from **kills** to **survives**.

**What the ledger claimed:** *"✅ Checked — `Jhapa` added to the qualifier list → red"*, guarding
§31.3's rule that a bare district must NOT be redacted, because the classifier derives district
from the narrative and a district alone identifies nobody.

**What changed.** The old pattern allowed **zero** trailing digits, so a bare qualifier matched and
adding `Jhapa` redacted the district. `7dddf5e8` replaced it with two alternatives — a capitalised
word *before* the qualifier, or **at least one digit after it** — which correctly stopped the bare
word *"ward"* being redacted as an address (a real false positive, found by a test asserting a
clean summary stayed clean). The side effect: the test's own sentence, *"…in **Jhapa** district…"*,
has a lowercase `in` before and no digits after, so it matches neither alternative. **The mutation
became inert and the test went quiet about it.**

**This is the exact failure mode §1.2 predicted** — *"someone refactors, an assertion quietly
becomes decorative, and the ledger still reads ✅ Checked"* — reproduced end to end, by accident,
within an hour. Under the old regime nothing would have said so: the test still passes, the commit
is a genuine improvement, and the ledger row would have gone on claiming a check that no longer
happens.

**What is actually lost**, stated precisely rather than dramatised: the district test no longer
notices a district being added to the qualifier list, *even though* `"Birtamod Jhapa"` would still
be redacted through alternative 1. So the risk is narrowed, not eliminated, and the guard against
it is gone.

**Handled without quietly adjusting anything** (§7's rule), as two records:

* `T-31-d-district-in-the-surname-gazetteer` — **kills**. Adds `Jhapa` to `THAR_SURNAMES_ROMAN`
  instead. This is arguably the better mutation for the property anyway: the surname gazetteer is
  the recogniser most likely to over-fire on a place name (many Nepali *thar* are also toponyms)
  and it matches a bare surname with no trigger word.
* `T-31-d-district-added-to-qualifiers` — **survives**, carrying the whole history in its `why` and
  flagged as a **documented regression rather than a designed non-kill**. Keeping it executable is
  the point: deleting it would turn the finding back into prose, which is what this ticket exists
  to stop.

⏭ **Owner decision needed, deliberately not taken here:** whether `test_a_bare_district_survives…`
should gain a case the tightened pattern still reaches — e.g. `"Birtamod Jhapa"` — restoring the
qualifier-list mutation as a kill. That is a change to another session's in-flight test file and
belongs with whoever owns DPG-32/33.

### 9.6 Still open

* **~65 ledger entries remain prose.** Deliberately not back-filled: §6 says start with the freshest
  and best-documented, and the older ones need their `find`/`replace` reconstructed from commit
  messages that are thinner. Back-fill a module's records when next touching that module.
* **No pin ties a `tests/mutations/` record to the test module it names.** A module could be deleted
  or renamed and its records would rot silently — the same class of decay this ticket was raised
  about. Small, and worth doing next.
