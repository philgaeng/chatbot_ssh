# OM-03 — The enforcement point

> **kind:** feature · **profile:** chore+TEST · **size:** S · **depends on:** OM-02, Q-05…Q-07
> ⭐ **Not optional.** Without it, every rule in `07_work_items.md` is a preference.

## Context

This repository has measured what an unenforced rule is worth: rule 6.1 (a dated header on every doc)
existed from 2026-08-03 and was honoured **7 of 7** inside the folder where it was written and **40 of
80** everywhere else. `scripts/ops/doc_headers.py` is what made it true.

## Scope

`tests/repo/test_spine.py`, parsing `docs/SPINE.md`:

1. IDs unique and well-formed (`GRM-###`).
2. **Exactly one `current` per lane** (07 §7.3) — not per project; parallel streams are legal.
3. Every row has `kind`, `profile`, `state`, `verification`, `size`, `lane`.
4. `state: done` ⇒ verification level meets the profile's requirement (07 §7.2).
5. `state: blocked` ⇒ a blocker **and** an unblock condition are named.
6. `state: dropped` ⇒ a reason is named.
7. Every `kind: debt` row links a `followups/` document that exists.
8. Every sprint folder under `docs/sprints/` with an open tracker has at least one register row.

## Not in scope

Estimating, scheduling, or checking that the plan is *good*. This checks that it is *well-formed and
internally consistent* — the same floor `test_doc_code_refs.py` sets for citations.

## Files

`tests/repo/test_spine.py` (new) · `.github/workflows/ci.yml` if `tests/repo` is not already collected
in the `backend-tests` job — **verify, do not assume**: this repo has twice shipped a gate that ran on
nobody's machine (nine `dpg/**` commits, and 27 uncollected test files).

## Acceptance

- [ ] All eight checks implemented, each with a test that proves it **fails** on a bad register
- [ ] Runs in CI on push to `dev/**` and on every PR — verified by watching an actual run, not by reading YAML
- [ ] Deliberately breaking the register turns CI red
- [ ] The failure message names the row and the rule, not just an assertion
