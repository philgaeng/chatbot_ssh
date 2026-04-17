# 03 - SEAH Submission and Storage

## Objective

Separate SEAH submission from general grievance submission and persist through dedicated SEAH pathway.

This spec is a child of:
- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Follow:
- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

Ticketing-related policy questions live in:
- `docs/Refactor specs/April20_seah/xx-ticketing-sytem-seah.md`

---

## Scope

In scope:
- Create dedicated SEAH submit action/service path (do not reuse generic submit end-to-end behavior).
- Implement/plug dedicated SEAH tables and storage writes.
- Ensure SEAH case reference generation follows decision from `00`.
- Enforce no complainant-facing SMS on SEAH submission path.

Out of scope:
- Full ticketing office workflow and role-policy implementation details (tracked in `xx` file).

---

## Files likely touched

- `backend/actions/action_submit_grievance.py` (guardrail/split points)
- new or updated SEAH submission action module(s)
- DB manager/service files for SEAH writes
- DB schema/migration files (if present in repo layout)

---

## Data and behavior rules

- No SEAH complaint should be committed through general grievance submit path.
- SEAH data storage should follow decisions from `00` (database model and table strategy).
- Keep consistent handling for `skipped` values and encryption/masking policy parity with main flow (as decided).
- Confirmation is on-screen; no complainant SMS recap.

---

## Acceptance criteria

1. SEAH submit path writes to dedicated SEAH storage path.
2. General grievance submission path is not invoked for SEAH route.
3. Complainant SMS recap is disabled for SEAH.
4. User-visible confirmation and case reference behavior matches `00`.

---

## Test requirements

- Unit tests for SEAH submit action and guardrails.
- Integration tests proving no call to general submit for SEAH sessions.
- Tests for case reference generation format.
- Negative test for SMS suppression in SEAH flow.

---

## Delivery checklist

- Document schema/service changes in PR notes.
- Provide migration/backward-compat notes if schema is introduced/changed.
