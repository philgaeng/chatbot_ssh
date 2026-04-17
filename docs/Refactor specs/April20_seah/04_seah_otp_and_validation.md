# 04 - SEAH OTP and Validation

## Objective

Implement focal-point validation and OTP behavior for SEAH flow according to decisions captured in `00`.

This spec is a child of:
- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Follow:
- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Scope

In scope:
- Focal-point identity capture and roster lookup flow.
- Immediate verification timing during intake (as decided in `00`).
- OTP channel behavior (as decided in `00`).
- Fallback when focal point not found.
- Failed OTP handling with `unverified_focal_point` tagging.

Out of scope:
- Back-office role administration/policy framework.

---

## Files likely touched

- `backend/actions/forms/form_sensitive_issues.py` (or dedicated SEAH validation form)
- OTP-related actions/forms/services in backend action layer
- state-machine glue where verification events alter flow state

---

## Validation rules

- Do not expose focal-point roster contents to user.
- If focal point not found:
  - allow retry,
  - then fallback contact capture path for offline verification (per `00`).
- Failed OTP must allow submission tagged `unverified_focal_point` (per `00`).

---

## Acceptance criteria

1. Focal-point verification is triggered at correct point in SEAH flow.
2. Retry/fallback behavior matches decisions in `00`.
3. OTP failure does not block final submission; record is tagged correctly.
4. Non-focal complainant flow remains unaffected.

---

## Test requirements

- Unit tests for focal-point lookup and fallback paths.
- Unit tests for OTP success/failure outcomes.
- Integration tests for end-to-end focal-point branch with tagging behavior.

---

## Delivery checklist

- Document any new slots/events used for verification state.
- Confirm slot naming consistency with `01` and test coverage with `05`.
