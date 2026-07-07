# Follow-up — Integration seed↔test reconciliation

> **Status: OPEN** · Model: **Opus** · Created from the CL-01 CI-green work (July 2026).
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
