# Follow-up — Integration seed↔test reconciliation

> # ✅ CLOSED 2026-07-15 by T3-08 — integration is running in CI
>
> **The reconciliation was already done; nobody re-enabled the gate.** Most of the work below
> landed in `4f0140dd` ("test/seed reconciliation: full ticketing suite green, 360 passed from
> 34 failed"), which is why the acceptance list checks out almost entirely as *already fixed*
> rather than *fixed by T3-08*. The quarantine outlived its reason by ~6 weeks.
>
> **Measured on a clean migrate+seed matching CI's steps exactly, stable across three runs:**
>
> | | before | after |
> |---|---|---|
> | `backend-tests` | 364 passed / 3 skipped / **390 deselected** — 3m16s | **897 passed** / 7 skipped / 0 deselected — 3m32s |
> | `tests/ticketing` alone (incl. `@integration`) | — | **563 passed / 5 skipped / 0 failed** |
>
> ⇒ **+533 tests gated for +16 seconds.**
>
> ## Acceptance — outcome
>
> | Item | Outcome |
> |---|---|
> | Product decision on `l1-officer-2@Jhapa` recorded and applied | ✅ **Already decided: YES, it is intended demo data**, and the 7 tests were updated — via the opt-in `without_seeded_jhapa_l1` fixture (`tests/ticketing/conftest.py:148-152`), which removes only that scope for tests that need Jhapa unstaffed. Decision recorded here retroactively; it was applied in code without ever being written down. |
> | `seah_workflow_id` seed-ordering bug fixed | ✅ **Already fixed** — `test_seah_grievance_uses_seah_workflow` passes on a fresh `--reset`. |
> | P2 L2 + package coverage added to the seed | ✅ **Already fixed** — the P2-supervisor and package tests pass on a pristine seed. |
> | Test-isolation teardown so the suite is stable when re-run without reseeding | ✅ **Holds** — 3 consecutive runs against one DB with no reseed: 563/5/0 every time, officer load unchanged. The suite cleans up after itself. |
> | `tests/ticketing` (incl. `@integration`) 0 failures, stable across two runs | ✅ **Verified** (three runs). |
> | Remove `-m "not integration"` from `ci.yml`; CI green with full coverage | ✅ **Done** (T3-08 commit 3), plus `tests/backend` added (D-37) — it was never gated at all. |
>
> **One genuine bug survived and was fixed by T3-08:** three assertions in
> `test_officer_assignment.py` named a hardcoded 2-officer pair as the acceptable province-fallback
> result. The seed staffs **four** L1s in province 1, and assignment ranks by active ticket load, so
> the pair held on a pristine DB only by luck of the `user_id` tie-break and failed on any developer
> DB with accumulated tickets (D-44). They now assert the province **pool**, sourced from
> `ticketing.constants.demo_officers`. This is the row below that reads *"tests assume Jhapa has no
> local L1"* — the residue of the same 2→4 roster growth (`b8cab274`).
>
> **The lesson worth keeping:** this quarantine is *why* that bug lived. CI seeded the DB
> specifically for these tests and then deselected them — paying the cost, gating nothing. See
> `pytest.ini`: the `integration` marker is a **dependency, not a quarantine**.
>
> ---
>
> **Original, retained below.**

> **Status:** ~~OPEN~~ **CLOSED — see above** · Model: **Opus** · Created from the CL-01 CI-green work (July 2026).
> **Why this exists:** CI's `backend-tests` gates on `-m "not integration"` (`.github/workflows/ci.yml`) — the `@integration` ticketing tests are quarantined because they fail on a pristine DB for reasons **unrelated to the schema**. This ticket fixes them and **re-enables integration in CI**.

## Context

CL-01 made the public schema canonical, so the ticketing suite runs to completion on a clean migrate+seed for the first time (before, CI died at `grievance_classification_taxonomy.category_key`). The non-integration suite is **green (195 passed / 0 failed)**. But ~12 `@integration` tests (mostly `test_officer_assignment.py`) fail on a **pre-existing seed↔test mismatch** — the tests encode assumptions that drifted from `mock_tickets`/`kl_road_standard`. Deterministic assignment (`user_id` tie-break), the 403 authz fix, and the FK test fix are already committed (`3cd31a61`); the remainder is genuine seed/test reconciliation.

## The failures & root causes (from the CL-01 verification)

| Failing | Root cause | Fix direction |
|---|---|---|
| 7× `test_officer_assignment` (Jhapa-related: `test_district_officer_covers_municipality_via_includes_children`, `test_local_district_excludes_cross_district_province_fallback`, `test_least_loaded_among_two_officers_same_district`, `test_tie_break_is_stable_when_load_equal`, `test_country_fallback_not_used_when_local_district_exists`, `test_full_intake_with_local_jhapa_officer`, `test_province_fallback_when_no_local_l1`) | Tests assume Jhapa has no local L1, but `mock_tickets.py:265-266` seeds `l1-officer-2@grm.local` at `P1_JHA` (load 0, added commit `b8cab274`, 2026-05-19). The engine correctly includes it and it wins the tie. | **PRODUCT DECISION** (below) |
| `test_seah_grievance_uses_seah_workflow` | **Real seed bug:** `projects.seah_workflow_id` is NULL on a fresh `--reset` — `seed_all` runs `seed_standard`→`seed_project` (which only sets `seah_workflow_id` if the SEAH workflow already exists) **before** `seed_seah` creates it. Effect: SEAH tickets fall back to the standard workflow. | Fix seed ordering: create the SEAH workflow before `seed_project`, or re-run `seed_project`'s `seah_workflow_id` backfill after `seed_seah`. |
| `test_simulated_create_falls_back_to_supervisor_when_no_l1` | L2 (`pd_piu_safeguards_focal`) seeded only under Province 1 (`mock_tickets.py:276-284`); a Province 2 ticket finds no L2. | Add P2 L2 coverage to the seed, or adjust the test. |
| Package tests (`test_location_linked_package_officer_without_ticket_package_id`, + 2 full-suite-only regressions) | Package `01` doesn't cover `P1_JHA` in `package_locations`; plus **test-isolation pollution** — non-isolated API tests leave assigned tickets that shift officer loads for later tests. | Fix package coverage in seed; add teardown to the non-isolated API tests. |

## Product decision needed (blocks the 7 Jhapa tests)

**Is `l1-officer-2@grm.local` seeded at Jhapa intended demo data?**
- **If yes** → update the 7 tests (they must stop assuming Jhapa is unstaffed).
- **If no** → remove/relocate the load-0 L1 from the seed so the tests' "sole candidate" assumption holds.

## Acceptance

- [ ] Product decision on `l1-officer-2@Jhapa` recorded and applied (tests or seed).
- [ ] `seah_workflow_id` seed-ordering bug fixed (SEAH tickets route to the SEAH workflow on a fresh seed).
- [ ] P2 L2 coverage + package coverage added to the seed as needed.
- [ ] Test-isolation teardown added so the suite is stable when re-run without reseeding.
- [ ] `tests/ticketing` (incl. `@integration`) **0 failures, stable across two runs** on a clean migrate+seed.
- [ ] Remove `-m "not integration"` from `.github/workflows/ci.yml`; CI green with full coverage.

## Also worth doing (adjacent, found during this work)

- Rebuild the running `ticketing_api` container — it's unhealthy with stale pre-`h2j4l6n8` code and can't run the current suite (DOCKER/ops hygiene, not a code bug).
