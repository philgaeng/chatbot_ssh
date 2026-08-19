# Follow-up — CI has been red on the mainline for ten days, so it gates nothing

> **Raised:** 2026-08-18, by pushing `dpg/sprint0-licensing` and looking at the result.
> **Deferred from:** DPG-01/DPG-02 verification · logged as deviation **D-26** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** ✅ **CLOSED 2026-08-19** · **Size, in the event:** S for the lint errors — the M for the
> pytest failures was eighteen symptoms of one cause, which is smaller than it looked and worse than it read
> **Why it is not in this sprint:** both failures predate it and neither is a licensing or privacy defect.
> Fixing them is a separate, bounded piece of work that deserves its own commit and its own diagnosis.

---

## The finding

`gh run list` on the default workflow:

| Branch | Runs inspected | Conclusion |
|---|---|---|
| `integration/stage` | **the last 10, 2026-08-08 → 2026-08-17** | **failure, every one** |
| `dpg/sprint0-licensing` | first ever run, 2026-08-18 | failure |

**Both branches fail in exactly the same shape** — verified step by step, not inferred from the
top-level conclusion:

| Job | Step | `integration/stage` | `dpg/sprint0-licensing` |
|---|---|---|---|
| `docs-links` | — | ✅ | ✅ |
| `webchat-checks` | — | ✅ | ✅ |
| `ui-checks` | Type-check | ✅ | ✅ |
| `ui-checks` | **Lint** | ❌ | ❌ |
| `ui-checks` | Unit tests / **Build** | ⏭ skipped | ⏭ skipped |
| `backend-tests` | migrations, gate, seed | ✅ | ✅ |
| `backend-tests` | **pytest** | ❌ | ❌ |

So **this sprint introduced no new failure.** It also means the sprint's own "green in CI" claims were
false when written, which is corrected in the tracker (D-26).

## Why this matters more than either underlying bug

**A permanently red build is indistinguishable from a build nobody is watching.** Ten consecutive
failures over ten days means:

- No one can tell a genuine regression from the standing noise. The next real breakage arrives into a
  build that was already red and changes nothing anybody can see.
- **Every compliance pin this sprint added is affected.** `tests/repo` — the SPDX walker and the
  licence-classifier pins, whose entire purpose is to fail a build when a commit breaks an indicator-2
  claim — now runs, and passes. But "the build fails" no longer carries information, so a future
  failure of *those* pins would look like every other day.
- It is the same disease as [`ci-untested-root-test-files.md`](ci-untested-root-test-files.md) (27 test
  files CI never collects) and **D-24** (the sprint's own branch prefix missing from the push triggers),
  seen from a third angle. Three findings, one root: *nobody has been able to rely on this signal, so
  nobody has been maintaining it.*

## The two underlying failures

### 1. `ui-checks` → Lint — **2 errors**, and it skips the Build step

`✖ 166 problems (2 errors, 164 warnings)` on this branch. `npx eslint . --max-warnings=-1` allows
unlimited warnings, so **the 2 errors are what fails it.** Both are
`react-hooks/set-state-in-effect` — calling `setState` synchronously inside a `useEffect` body — in
`channels/ticketing-ui/lib/useTicketThread.ts` and the PII card effect.

⚠ **Two things follow that are worth stating separately from the fix:**

- **`docs/TODO.md` records the portal at "143 warnings, 0 errors."** It is now 164 warnings and 2
  errors. That row is stale, and the drift is the thing the row exists to prevent.
- **The Build step is skipped whenever Lint fails**, and Build is the `next build` gate. That is the
  gate **D-02b** named as the confirming check for the SPDX header sitting above `"use client"` in 110
  `.tsx` files. **It has therefore never run in CI and cannot until these 2 errors are fixed.**
  The claim is not unevidenced — the same Next.js compiler ran the build successfully inside Docker on
  2026-08-18 (D-02) — but the CI gate specifically named in the deviation is unavailable, and the
  tracker now says so instead of implying otherwise.

## ✅ CLOSED 2026-08-19 — both jobs green

**Eighteen failures, one root cause, said four different ways.** Every one of them came from the
same mistake:

> **Something reads data that the seeder writes afterwards.**

CI's order is fixed: migrations, then `mock_tickets.py`. A back-fill migration that derives its
rows from data the seed creates therefore finds nothing — **on a fresh database, and only on a
fresh database.** On the deployment where a human looks, the data is already there and the
back-fill works perfectly. Nothing raises. A table is simply empty, and the symptom surfaces much
later wearing an unrelated face.

| # | What was skipped | Reads | Written by | Failures |
|---|---|---|---|---|
| 1 | `b3c5d7e9` — project workflow slots | `projects.standard_workflow_id` | `seed_standard()` | (feeds #2) |
| 2 | `n0p2r4t6` — project types | `project_workflows` | #1 | 8 |
| 3 | `p2r4t6v8` — per-package staffing | seed staffs project-wide, level says lot by lot | — | 10 |
| 4 | `apply_donor_informed_defaults` — a **service-layer side effect**, not a migration | the API calls it when a donor is added; the seed writes `project_donors` directly | — | 1 (see below) |

**The fix is in the seeder, not the migrations.** A migration must not invent data that did not
exist — `n0p2r4t6` documents that choice deliberately, and it is right. The seeder is the thing
that runs on a fresh database, so the seeder is where these facts have to be asserted. All four
additions **derive** their values from the project's own rows rather than hard-coding them, so
they cannot drift from `seed_standard()` the first time a workflow changes.

⚠ **#4 deserves its own note, because it presented as flaky rather than broken.**
`test_kl_road_has_donor_and_is_informed` failed on a fresh database and passed on a used one — the
test that exercises `apply_donor_informed_defaults` **commits**, so a single full-suite run
repaired the database permanently. Anyone who re-ran to check would have watched it go green.

**What now pins it:** [`tests/ticketing/test_seed_completeness.py`](../../../../tests/ticketing/test_seed_completeness.py)
— eight tests asserting the *outcome* rather than any one mechanism, because the mechanism will
change and the outcome must not: **a freshly built database must produce a project that can accept
a grievance.** Five mutations verified red, each reproducing its original failure exactly.

**Three tests were asserting the absence of seed data** and went red when the gap was filled —
"a per-lot level is not satisfied by a project-wide officer" arranged that state by staffing
nobody, and read as if it were arranging nothing. They now take a `without_seeded_package_l1s`
fixture that says the precondition out loud.

**`ui-checks`:** 2 errors, both `react-hooks/refs` in `CastStaffing.tsx` — a `roleStaffedRef`
assigned during render to let `byRoleFor` call a `roleStaffed` defined below it. There was no cycle
to break; reordering the two removes the ref, the errors, and a stale-closure risk. 164 warnings
remain and are not gating (`--max-warnings=-1`). Type-check, 88 unit tests and the build all pass.

**Result — verified by rebuilding the database exactly as CI does, not inferred:**

| Job | Before | After |
|---|---|---|
| `backend-tests` | 18 failed, 1166 passed | **0 failed, 1388 passed** |
| `ui-checks` | 2 errors | **0 errors** |
| `docs-links` | ✅ | ✅ |
| `webchat-checks` | ✅ | ✅ |

---

### 2. `backend-tests` → pytest — **18 failed, 1166 passed, 8 skipped**

> **Re-checked 2026-08-19** on `dpg/sprint1-llm-agnostic` (run 32229396825, commit `1e540b9e`, the end
> of Sprint 1): **18 failed, 1365 passed** — the *same eighteen*, file for file and message for
> message, with 199 more passing tests beside them. That is the useful thing this row now does: it is
> a fixed number to compare against, so "did I break CI" is answerable without reading the log. The
> failures are all one shape — the seed leaves no active project type and no Level 1 officer staffing,
> so intake refuses and every downstream ticket assertion falls over. `ui-checks` is still the same
> lint failure. `docs-links` and `webchat-checks` are green.

The failures cluster in four files, and they are about project types, the back-fill migration and the
grievance-sync watermark — nothing to do with this sprint:

| File | Shape of failure |
|---|---|
| `tests/ticketing/test_donor_guardrail.py` | `assert 'ADB' == 'DOR'`; `KL Road must have a type — the back-fill gave every project one`; `'NoneType' object has no attribute 'actor_roles'` |
| `tests/ticketing/test_grievance_sync.py` | `backfill should create a ticket`; `full sweep must process rows below the watermark` |
| `tests/ticketing/test_project_type_authoring.py` | `'NoneType' object has no attribute 'actor_roles'` |
| `tests/ticketing/test_roles_crud.py` | `no active project type — the back-fill migration should have made one` |

`docs/TODO.md` already documents part of this — *"10 ticket tests fail whenever an admin closes KL
Road's intake"* and *"the 10 pre-existing `test_grievance_sync` / `test_ticket_uniqueness` failures are
unrelated and fail on a clean tree too"*. **There are 18, not 10.** Whether the extra 8 are the same
root cause or a second one is exactly the diagnosis this followup exists to fund.

✅ **`tests/repo` passes** — the DPG pins are among the 1166. They were added to the pytest step by
DPG-01 (the step name changed from `(ticketing, orchestrator, actions, backend)` to
`(repo, ticketing, …)`, visible in the run diff) and they are green.

## Definition of done

- [ ] Fix the 2 lint errors, or make a deliberate decision to downgrade that rule with the reason
      recorded — **not** a blanket suppression; `react-hooks/set-state-in-effect` is flagging real
      cascading-render risk
- [ ] Confirm **Build** then runs, and that `next build` is green in CI — **this closes D-02b properly**
- [ ] Diagnose the 18 pytest failures: are they one root cause (project-type back-fill + a shared
      fixture) or several? Record the answer before fixing
- [ ] Fix or quarantine each **with a linked issue** — no bare `skip`
- [ ] Update `docs/TODO.md`'s portal-lint row with the measured numbers, and the "10 ticket tests" row
      with the real count
- [ ] **Get to a green build once**, then treat any red as actionable. That is the whole point — the
      value is not in the 20 fixes, it is in restoring a signal that means something
- [ ] Consider a branch-protection or required-check rule **only after** green; requiring a check that
      cannot pass is worse than requiring none

## Related

- [`ci-untested-root-test-files.md`](ci-untested-root-test-files.md) — 27 files CI never collects (D-01)
- [`../PROGRESS.md`](../PROGRESS.md) — **D-24** (sprint branch missing from push triggers), **D-26** (this)
- [`../../../TODO.md`](../../../TODO.md) 🔵 TECH DEBT — the stale portal-lint and ticket-test rows
