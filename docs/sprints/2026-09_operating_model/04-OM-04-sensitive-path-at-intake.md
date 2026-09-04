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

- [ ] An item cannot reach `ready` without a profile
- [ ] The PR template no longer asks a question the item has already answered — it confirms it
- [ ] Ticking `+SENSITIVE` at intake is what selects Opus, with no separate judgment call
