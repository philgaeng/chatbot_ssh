# 05 - SEAH Tests and Regression

## Objective

Define and implement test coverage that proves SEAH behavior changes while protecting existing flows.

This spec is a child of:
- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Follow:
- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Scope

In scope:
- Unit, integration, and regression tests for specs `01` to `04`.
- Negative tests for prohibited behavior (notably complainant SMS in SEAH flow).
- Mapping tests for utterance/button keys.

Out of scope:
- Ticketing-system internal workflow tests not present in chatbot backend.

---

## Required suites

1. **Flow tests**
   - main menu -> SEAH route
   - ordered slot progression
   - focal-point branch rendering
2. **Branch tests**
   - `Not an ADB project` behavior
   - non-focal vs focal-point paths
3. **Submission tests**
   - SEAH submit path selected
   - general grievance submit not invoked
4. **Notification tests**
   - no complainant-facing SMS recap for SEAH
5. **Content mapping tests**
   - required keys in `utterance_mapping_rasa.py`
   - required groups in `mapping_buttons.py`
6. **Regression tests**
   - legacy non-SEAH grievance path unchanged

---

## Acceptance criteria

1. New tests pass locally and in CI.
2. Existing relevant suites remain green.
3. Failures are actionable and mapped to spec sections (`01`-`04`).

---

## Suggested commands

- `pytest backend -k "seah or sensitive or grievance"`
- `pytest backend/orchestrator/scripts`
- project-standard Docker validation path

---

## Delivery checklist

- Add test matrix in PR description (`scenario`, `expected`, `result`).
- Call out any intentionally deferred tests with rationale.
