# Follow-up — the seeds still author named role keys

> # ✅ CLOSED 2026-08-09 — done in the same change
>
> The seeds, `DEMO_OFFICER_SPECS` and the demo `officer_scopes` all write per-slot keys now, and
> a fresh `migrate + seed` reports **zero** collisions across all three workflows. The test pass
> came to 6 files, not the 31 feared: most of those reference operational roles for permissions
> and tracks, which are unchanged. Suite 739 passed, 5 skipped — back to the 10 pre-existing
> failures in `test_grievance_sync` / `test_ticket_uniqueness`.
>
> The one design point settled while doing it: an officer who is level N's supervisor **and**
> level N+1's actor now has **two scope rows**, one per slot. That is the honest expression of
> "one person, two jobs" — the single shared row was what made the two indistinguishable.


**Logged:** 2026-08-09, alongside migration `x0z2b4d6` (synthetic per-slot keys).
**Owner:** ticketing · **Size:** medium — the seed is mechanical, the test fallout is not.

## The gap

`x0z2b4d6` converts **existing** databases so every (step, tier) slot has its own key. The
**seeds still write named operational keys**:

- `ticketing/seed/kl_road_standard.py` — `assigned_role_key="site_safeguards_focal_person"`,
  `supervisor_role="pd_piu_safeguards_focal"`, … across four steps
- `ticketing/seed/kl_road_seah.py` — the same shape across two
- `ticketing/seed/mock_tickets.py` — the demo `officer_scopes` rows use the same named keys

So a **fresh** deployment reintroduces the collision the migration just removed: migrations run
against an empty schema, then the seed inserts colliding steps. The publish guard does not catch
it, because seeded workflows are inserted with `status='published'` rather than published through
the endpoint.

Existing environments (staging, prod) are fixed by the migration and stay fixed.

## Why it was not done in the same change

The seeded `officer_scopes` use the same named keys as the steps, so converting the steps alone
would unstaff the demo data. Converting both is mechanical — but **31 test files** reference
`site_safeguards_focal_person` / `pd_piu_safeguards_focal` / `adb_hq_safeguards` / `grc_chair` /
`seah_national_officer` directly, and several assert on staffing that would move. That is a
deliberate pass with its own verification, not a tail-end addition to a migration.

## What to do

1. Seed steps with `wf:{workflow_key}:{step_key}:{tier}`, minting the backing `roles` rows
   (`ensure_tier_role` already does this — the seed can call it).
2. Convert `mock_tickets.py` scopes to the matching synthetic keys.
3. Work through the 31 test files: those asserting *operational* roles (permissions, tracks,
   visibility) keep named keys; those asserting *staffing* move to synthetic.
4. Consider having the seed call the same normalisation the migration performs, so the two
   cannot drift.

## Acceptance

- [ ] A fresh `migrate + seed` produces zero output from `duplicate_slot_keys` on every workflow
- [ ] `tests/ticketing` green, including `@integration`
- [ ] Staffing an officer at L3 shows them at L3 on a freshly seeded database
