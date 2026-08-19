# Follow-up — CI has been red on the mainline for ten days, so it gates nothing

> **Raised:** 2026-08-18, by pushing `dpg/sprint0-licensing` and looking at the result.
> **Deferred from:** DPG-01/DPG-02 verification · logged as deviation **D-26** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** 🔵 open · **Size:** S for the lint errors, M for the pytest failures
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
