# Follow-up — 27 test files have never run in CI

> **Raised:** 2026-08-18, during DPG-02 (deciding where the DPG-01/02 pins should live).
> **Deferred from:** DPG-02 · logged as deviation **D-01** in [`../PROGRESS.md`](../PROGRESS.md).
> **Status:** ⬜ open · **Size:** M (unknown until the suite is actually run once)

---

## What

`.github/workflows/ci.yml`'s pytest step names its test paths **explicitly**:

```
tests/repo tests/ticketing tests/orchestrator tests/actions tests/backend
```

A directory not named there never runs. Two sets of tests fall through that gap:

| Location | Collectible files | Status in CI |
|---|---|---|
| directly in `tests/` | **21** (`test_*.py`; `mocktest_postgres_services.py` is not collectible by pytest's default pattern, and `__init__.py` is not a test) | never run |
| `tests/shared/` | **6** | never run |

**27 files in total.** Among them: `test_complainant_functions.py`, `test_postgres_services.py`,
`test_seah_mappings.py`, `test_seah_outro_logic.py`, `test_seah_service_providers.py`,
`test_sensitive_content_detection.py`, `test_qr_token_integration.py`,
`test_grievance_create_or_update.py`, and 19 more. Several of these cover paths that carry
complainant PII or SEAH routing.

## Why it was not fixed in the licence commit

Two reasons, and the second is the real one:

1. **Nobody knows whether they pass.** They have not run in CI at any point; several predate the
   T3-08 environment fixes and the `public.*` schema changes. Adding the paths to `ci.yml` could
   turn the branch red for reasons that have nothing to do with licensing.
2. **Finding out is its own ticket.** A commit whose subject is "Apache-2.0 licence headers" must
   not also be the commit that discovers 27 files of unknown test debt. Diagnosing and fixing
   whatever they surface is unbounded work; smuggling it into a licence commit would make both
   changes unreviewable.

This is precisely the shape T3-08 dismantled once already — the `-m "not integration"` quarantine —
wearing a different hat. It should not be left standing for long.

## Why it matters beyond hygiene

`tests/repo/` exists **because** of this gap. The SPDX-header walker (T-01) and the licence
classifier pins (T-02) are compliance pins: their entire purpose is to fail when someone adds a file
that breaks a DPG indicator-2 claim. That is why DPG-01 created `tests/repo/` as a **new named
directory** and added it to `ci.yml` explicitly, rather than dropping `test_spdx_headers.py` into
`tests/` where it would have been invisible from birth — a pin CI does not run is decoration.

The same argument applies to the 27: a SEAH-routing test that never runs provides no protection
against a SEAH-routing regression.

## Definition of done

- [ ] Run all 27 files once, in-container, against a migrated + seeded DB — record the raw result
      (passed / failed / errored) in this document before changing anything
- [ ] Triage each failure into: **real bug**, **stale test** (delete, with the reason), or **needs
      fixture work**
- [ ] Fix or delete every one; no `skip`, no `xfail` without a linked issue
- [ ] Add `tests/` and `tests/shared/` to the `ci.yml` pytest paths — or, better, change the step to
      collect `tests/` as a whole so a new directory can never be invisible again
- [ ] Record the before/after test counts in `PROGRESS.md`, as T3-08 did
      (`364 → 897` is the precedent)
- [ ] Delete or rename `tests/mocktest_postgres_services.py` — a file that looks like a test and is
      silently uncollectible is a trap

## Endgame

The `ci.yml` step should name **no** test paths. `pytest` collecting `tests/` wholesale, with
markers doing any excluding, removes the failure mode permanently. Until then, every new test
directory has to be remembered — and this document is evidence that it will not be.

## Related

- [`../PROGRESS.md`](../PROGRESS.md) — deviation **D-01**
- [`../../../engineering/04_testing.md`](../../../engineering/04_testing.md) — what CI runs
- [`../../archive/2026-08_tier3_structural/PROGRESS.md`](../../archive/2026-08_tier3_structural/PROGRESS.md) — T3-08, the same failure mode measured and closed
