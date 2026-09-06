# OM-04 — Move the sensitive-path question to intake

> **kind:** feature (process) · **profile:** chore+SPEC · **size:** S · **depends on:** OM-01
> Independent of OM-02/03 — can run in parallel.

## Context

`.github/PULL_REQUEST_TEMPLATE.md` already asks the right question: *"If this PR touches a sensitive
path, tick and explain — SEAH visibility · PII boundary · Data egress · Schema."* **At PR time the
answer changes nothing**: the design is written, the model was already chosen, the tests exist or do
not. The same list at intake selects the model, the reviewer, the tests and the gates (07 §4.3).

## Scope

1. An **item template** carrying the six derivation questions (07 §4.1) and producing a profile.
2. The **PR template keeps its checklist as a confirmation**, and points at the item — it stops being
   the first time anyone asks.
3. `AGENTS.md`: the model-selection table gains one line — the profile decides the model, so
   `+SENSITIVE` ⇒ Opus, mechanically rather than by judgment.

## Not in scope

Changing any gate's content. Every check stays exactly as it is; only the moment of decision moves.

## Files

`.github/ISSUE_TEMPLATE/` or `docs/items/TEMPLATE.md` (Q-02 decides which) · `.github/PULL_REQUEST_TEMPLATE.md` · `AGENTS.md` · `docs/engineering/07_work_items.md` §11 row 4

## Acceptance

- [x] An item cannot reach `ready` without a profile — ⭐ **enforced, not just written**: `tests/repo/test_spine.py::test_ready_rows_carry_a_profile` (column-indexed, because `chore`/`bug`/`deviation` are each both a kind and a profile and a substring match would pass a row that has only a kind)
- [x] The PR template no longer asks a question the item has already answered — it confirms it, and names the item id and profile it is confirming
- [x] Ticking `+SENSITIVE` at intake is what selects Opus, with no separate judgment call (`AGENTS.md` § *Model selection*, first paragraph)

## Done 2026-09-06

**Q-02 resolved the home in favour of `docs/items/`, not `.github/ISSUE_TEMPLATE/`** — its answer
sequences the tracker (register in the repo now, GitHub Issues once `D-002`/`D-010` land), and wiring
Issues is OM-07's job, not this one. Putting the intake form in `ISSUE_TEMPLATE/` would have shipped
half of OM-07 under OM-04's name and made the form unusable until the tracker existed.

**What was deliberately not done:** no gate's content changed, per § *Not in scope*. The two existing
issue templates (`bug_report.yml`, `feature_request.yml`) were left alone — they are OM-07's to
reconcile, and they are one of the three vocabularies §11 row 7 is still counting.
