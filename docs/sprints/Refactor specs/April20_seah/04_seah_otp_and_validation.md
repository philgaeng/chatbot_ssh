# 04 - SEAH OTP and Validation

## Objective

Document how **`form_otp`** behaves for **SEAH intake** (`story_main: seah_intake`) versus other stories, and how **focal-point** staging interacts with phone collection. Align with `01`, `07`, and `backend/actions/forms/form_otp.py`.

This spec is a child of:

- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Related:

- `docs/Refactor specs/April20_seah/01_seah_route_and_slots.md`
- `docs/Refactor specs/April20_seah/07_seah_focal_point_flow.md`

Follow:

- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Source files (implemented)

| Component | Path |
|-----------|------|
| OTP form validation / dynamic slots | `backend/actions/forms/form_otp.py` (`ValidateFormOtp`, `ActionAskOtpConsent`, `ActionAskOtpInput`) |
| Sequencing | `backend/orchestrator/state_machine.py` |
| Phone validation helper | Shared via `BaseFormValidationAction` / `base_validate_phone` (as used in `validate_complainant_phone`) |

---

## Core rule: sensitive `seah_intake` → phone only

In **`ValidateFormOtp.required_slots`**:

When `story_main in ("new_grievance", "grievance_submission", "seah_intake")` **and** `grievance_sensitive_issue is True`:

- Required slots are **`["complainant_phone"]` only**.
- **`otp_consent`**, **`otp_input`**, **`otp_status`** are **not** collected for this branch.

**Consequences:**

1. **Victim identified path** (`01`): after `form_seah_1`, user enters **`form_otp`** once to provide **phone** (or skip). There is **no OTP verification** of phone possession for this sensitive SEAH branch (product rationale captured in `01` devil’s advocate / stakeholder answers).
2. **Focal path** (`07`): every transition into **`form_otp`** while `story_main == seah_intake` and `grievance_sensitive_issue` remains **True** uses the **same** phone-only rule—including **bootstrap reporter** after role `focal_point` and **complainant** capture after `form_seah_focal_point_1` when consent to report is **yes**. There is **no** separate “full OTP” branch in code gated by `seah_focal_stage` today.

If product later requires **SMS OTP verification** for focal reporters or complainants, **`ValidateFormOtp.required_slots`** must branch on e.g. `seah_focal_stage` (and keep `grievance_sensitive_issue` semantics consistent).

---

## Phone skip semantics (all flows using this validator)

`validate_complainant_phone`: when phone is set to skip value, OTP-related slots are set skipped so the form can complete without asking OTP.

---

## Other stories (non–SEAH-sensitive) — reference

- **`new_grievance` / `grievance_submission`** with `grievance_sensitive_issue` true: also **phone-only** (same branch as above)—shared code path with SEAH sensitive.
- **Default grievance OTP path:** phone + `otp_consent` + `otp_input` + `otp_status` when user has not declined OTP.
- **`status_check` retrieve:** mandatory OTP UX via `ActionAskOtpConsent` index selection (`form_otp.py`).

---

## Focal roster lookup / `unverified_focal_point` (policy vs code)

Parent spec **`00`** and stakeholders described:

- Focal roster validation, SMS OTP for focal verification, submission tagging such as **`unverified_focal_point`** on failed OTP.

**Current codebase:**

- Slots such as **`seah_focal_lookup_status`**, **`seah_focal_verification_status`** are passed through **`ActionSubmitSeah`** into `seah_payload` when present on the tracker, but **roster match + OTP-gated focal verification** is **not** fully wired as a distinct sub-flow in `form_otp` / focal forms at the time of this doc refresh.

Track future implementation under this spec id and **`07`**.

---

## Acceptance criteria (current)

1. [x] For **`seah_intake`** with **`grievance_sensitive_issue` true**, `form_otp` completes after **`complainant_phone`** (or skip) without requiring OTP input slots.
2. [x] Victim **identified** path hits `form_otp` before `form_contact` (`state_machine.py`).
3. [x] Focal bootstrap hits `form_otp` immediately after `form_seah_1` when role is focal (`07`).
4. [ ] Focal **roster + OTP verification** + explicit **`unverified_focal_point`** tagging — **pending** if still required by policy (`00` section C).

---

## Test requirements

- Unit: `ValidateFormOtp.required_slots` for combinations of `story_main`, `grievance_sensitive_issue`, `complainant_consent`, `otp_consent`.
- Integration: SEAH identified victim reaches `form_contact` only after `form_otp` completes with phone or skip.
- When focal OTP policy is implemented: success/failure paths and slot tags on submit.

---

## Delivery checklist

- [x] Document sensitive SEAH phone-only behavior in PRs touching `form_otp.py`.
- [ ] If focal OTP is implemented, update `01`/`07`/`02` and add negative/positive SMS tests (with mocks).

---

## Changelog

- **2026-04-21:** Rewrote for implemented `ValidateFormOtp` sensitive branch (phone-only for `seah_intake`); clarified focal stages; separated policy gaps (roster OTP, `unverified_focal_point`) from current code.
