# 07 - SEAH Focal Point Flow

## Objective

Align the SEAH focal-point pathway with a multi-form architecture (instead of one large focal-point form), while keeping behavior consistent with decisions already captured in `00`.

This spec is a child of:
- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Follow:
- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Why this spec exists

The current focal-point form implementation includes fields that are not present in the updated PDF flow and misses several fields that are now required for the focal-point reporting path. This spec narrows the implementation target for the focal-point branch only.

---

## Source of truth for this spec

- **`backend/orchestrator/state_machine.py`** — focal sequencing and `seah_focal_stage` transitions (authoritative with `01`).
- **`backend/actions/forms/form_seah_focal_point.py`** — validators, `required_slots`, `action_prepare_seah_focal_complainant_capture`.
- `docs/Refactor specs/April20_seah/01_seah_route_and_slots.md` (victim vs focal entry from `form_seah_1`).
- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md` (policy).
- `docs/Refactor specs/April20_seah/NEP-chatbot-v2.pdf` (product wording intent).

When these conflict, prioritize:

1. **Implemented orchestration** (`state_machine.py`) for what actually runs.
2. **Validators** in `form_seah_focal_point.py` for conditional slots.
3. PDF / `00` for copy and policy gaps to close later.

---

## Target focal-point flow (from updated PDF)

This applies only when user selects:
- `No, I am the SEAH Focal Point`

### Required sequence
1. 'when did you learn about this incident?' 
[Date]
2. `did the complainant consent to you reporting this here?` (Yes/No)
   - If `No`, jump directly to step 14 (`did you refer the complainant (if victim-survivor) to proper support?`) and then step 15 acknowledgment.
3. `did the complainant agree to be identified or be anonymous?`
   - Complainant name [free text]
   - Anonymous
4. `Contact Number of Complainant`
   - free text (numbers only)
   - none/did not want to provide
5. `Email Address of Complainant`
   - free text
   - none/did not want to provide
6. `Name of ADB Project`
   - free text
   - not sure
   - not an ADB project
7. `Summary of SEAH incident` (free text)
8. 'additional risks to the health, safety, or wellbeing of the alleged survivor/s'
- Retaliation, intimidation, or threat to job security
- Personal safety 
- Trauma
- None
- [Free text]
9. in what way have you mitigated these risks?
- Referral to support services 
- Provided information on police and/or legal services
- [Free text]
- None
10. 'aside from the survivor, who else is at risk?'
- Witnesses 
- Other family members 
- Other project workers 
- Other members of the community
- [Free text]
- None
11. 'is there a risk to the ADB project?'
- Project delay
- [Free text]
- None
12. is there reputational risk for ADB?
- Yes
- None
13. `does the complainant consent to being contacted for further information?`
   - yes via contact number only
   - yes via email address only
   - yes via contact number and email address
   - no
14. 'did you refer the complainant (if victim-survivor) to proper support?'
15. acknowledgement text

### Required policy constraints (from PDF and `00`)

- All fields are mandatory to ask, with non-disclosure answers where applicable.
- SEAH complaints stay in confidential route only.
- SEAH complaints do not enter general grievance tracker.
- SEAH flow must not trigger standard chatbot status notifications.

---

## Implemented focal flow (orchestrator + forms)

Focal is selected in **`form_seah_1`** (`seah_victim_survivor_role: focal_point`). **`seah_focal_stage`** tracks sub-stages across reused forms.

### High-level sequence

| Order | Active loop / step | What happens |
|------|---------------------|--------------|
| 1 | `form_seah_1` | Same as victim path until role = `focal_point`. |
| 2 | `form_otp` | `seah_focal_stage = bootstrap_reporter_otp`. For `seah_intake` + sensitive, **`complainant_phone` only** (see `04`). |
| 3 | `form_contact` | `seah_focal_stage = bootstrap_reporter_contact`. `ValidateFormContact.required_slots` returns **location + `complainant_consent` + `complainant_full_name` only** (no email in this stage). |
| 4 | `action_prepare_seah_focal_complainant_capture` | Copies reporter data into **`seah_focal_phone`**, **`seah_focal_full_name`**, **`seah_focal_city`** (`complainant_municipality`), **`seah_focal_village`**; clears shared complainant slots for complainant capture. |
| 5 | `form_seah_focal_point_1` | `seah_focal_stage = focal_point_1`. Slots: `seah_focal_learned_when`, `seah_focal_reporter_consent_to_report`, `sensitive_issues_follow_up` (complainant identity mode). |
| 6a | If consent **no** | Jump to **`form_seah_focal_point_2`** immediately with defaults (skipped complainant contact, `seah_contact_consent_channel` skipped). |
| 6b | If consent **yes** | `form_otp` with `seah_focal_stage = complainant_otp` (still **phone-only** for sensitive `seah_intake`), then `form_contact` with `seah_focal_stage = complainant_contact` (consent + name + email only), then **`form_seah_focal_point_2`**. |
| 7 | `form_seah_focal_point_2` | Project, narrative loop, focal risk fields (skipped when `seah_project_identification == not_adb_project`), conditional **`seah_contact_consent_channel`**, **`seah_focal_referred_to_support`**. |
| 8 | Submit | `action_submit_seah` → `done`. |

### `form_seah_focal_point_2` slots (validator-driven)

Aligned with **`ValidateFormSeahFocalPoint2.required_slots`**:

- Always: `seah_project_identification`, `sensitive_issues_new_detail`, `seah_focal_referred_to_support`.
- Unless `not_adb_project`: `seah_focal_survivor_risks`, `seah_focal_mitigation_measures`, `seah_focal_other_at_risk_parties`, `seah_focal_project_risk`, `seah_focal_reputational_risk`.
- **`seah_contact_consent_channel`**: only if consent to report ≠ `no` **and** complainant has phone or email (not skipped).

Project values match victim form: **`cannot_specify`**, **`not_adb_project`**, free text (see `form_seah_2` parity).

### `action_prepare_seah_focal_complainant_capture`

Defined in **`form_seah_focal_point.py`**: copies **`complainant_phone` → `seah_focal_phone`**, **`complainant_full_name` → `seah_focal_full_name`**, **`complainant_municipality` → `seah_focal_city`**, **`complainant_village` → `seah_focal_village`**, then clears the listed complainant slots so the **complainant** pass can refill them.

---

## Implementation scope (maintenance)

In scope for future edits to this path:

- Conditional copy in **`utterance_mapping_rasa.py`** / buttons in **`mapping_buttons.py`**.
- Policy gaps in **`04`** (focal OTP / roster) and **`00`**.
- Tests in **`05`**.

Out of scope:

- Ticketing back-office (`xx`).
- Non-focal victim path (see **`01`**).

---

## Test requirements

- Unit tests for required-slot ordering and conditional branching.
- Unit tests for each new validator (identity mode, consent channel, date parsing, phone/email normalization).
- Regression tests to confirm removed/deprecated slots are no longer requested in focal-point flow.
- Integration test covering full focal-point path from role selection to acknowledgment.

---

## Questions for 95% implementation confidence

Answer each item directly in this file so implementation can proceed with minimal ambiguity.
Suggested answer format:
- `Decision:` your chosen option
- `Rationale:` short note (optional)

### Already decided (captured in this spec)

1. **Phone handling** reuses **`form_otp`** + shared complainant slots; for `seah_intake` + `grievance_sensitive_issue`, OTP verification slots are **not** required (**phone-only** — see `04`). **Roster-based focal OTP** remains a future policy item if required by `00`.
2. If consent-to-report is **`no`**, the orchestrator opens **`form_seah_focal_point_2`** directly (skips complainant phone/email capture and skips `seah_contact_consent_channel` via validator rules); user still completes **project / narrative / referred-to-support** (and minimal fields when `not_adb_project`).
3. Focal assessment fields live in **`form_seah_focal_point_2`** (parallel to victim **`form_seah_2`** narrative pattern, not the same active loop).
4. `sensitive_issues_new_detail` loop semantics match **`form_seah_2`** (restart / add more / submit).

### Open questions (still need answers)

1. Confirm canonical stored enum for project option:
   - `not_sure` (PDF wording) vs existing `cannot_specify`.
   - Recommendation: **Use `not_sure`** for v2 alignment with the updated flow, with backward-compatible mapper from `cannot_specify`.
   - Decision: cannot_specify
   - Rationale:

2. Should `seah_focal_learned_when` accept:
   - date only (`YYYY-MM-DD`) or
   - datetime?
   - Recommendation: **Date only (`YYYY-MM-DD`)** for simpler validation and consistent intake granularity.
   - Decision: we need to accept free text and the officer in charge will validate manually
   - Rationale: no friction

3. Should future-contact consent question still be asked when both phone and email are skipped?
   - Recommendation: **Yes**, still ask and store consent intent as `none` where relevant.
   - Decision: NO 
   - Rationale: shorter flow

4. For referral-to-support question, should we require extra detail when answer is `No`?
   - Recommendation: **No mandatory extra detail** in chatbot; keep intake non-probing.
   - Decision: NO
   - Rationale:

5. Confirm final slot names above, or provide naming preferences before implementation.
   - Recommendation: **Keep current proposed names + shared-slot reuse pattern** to minimize translation overhead and reduce implementation churn.
   - Decision: follow reco
   - Rationale:

---

## Delivery checklist

- Update this file once stakeholder answers finalize open questions.
- Reflect finalized slot names in `01_seah_route_and_slots.md`.
- Update validation behavior docs in `04_seah_otp_and_validation.md` if OTP is removed or feature-flagged.
- Keep `05_seah_tests_and_regression.md` aligned with final focal-point behavior.

---

## Devil's Advocate Review (Resolved)

### Final decisions captured from review

1. **Exception policy is explicit**
   - `consent_to_report = No` skips complainant contact capture and **skips** `seah_contact_consent_channel`, but the user still completes **`form_seah_focal_point_2`** (project, narrative, referred-to-support, etc., subject to `not_adb_project` trimming in `required_slots`).

2. **Free-text date accepted**
   - `seah_focal_learned_when` remains free text.
   - No parsed companion field is required for this phase.

3. **Reset safety is mandatory**
   - A single dedicated action must perform copy/reset operations atomically before form transitions.
   - This action must include tests.

4. **Consent semantics standardized**
   - If contact-consent channel is not asked, store canonical `SKIP_VALUE`.

5. **OTP skip behavior required**
   - When `complainant_phone` is skipped in `form_otp`, related OTP slots are set skipped so the form can complete (`form_otp.py`).

6. **Not-ADB branch behavior**
   - When `seah_project_identification == not_adb_project`, **`ValidateFormSeahFocalPoint2`** omits the long focal-risk block; user still completes narrative / referred-to-support as required. Dedicated **referral-only terminal** (no DB write) is **not** implemented—submission still runs **`action_submit_seah`** unless product adds an early exit in `state_machine.py`.

7. **Localization ownership clarified**
   - This spec remains the functional source of truth for wording intent.
   - Runtime chatbot utterance/button mappings must be implemented in `backend/actions/utils/utterance_mapping_rasa.py` (not `backend/shared_functions/utterance_mapping_server.py`).

8. **Backward compatibility**
   - No migration mapping is required in this phase.

9. **Auditability extras**
   - No extra branch-path audit fields are required in this phase.

10. **Test gate scope**
   - Full additional branch-level integration gate is not mandatory for this phase.

---

## Changelog

- **2026-04-21:** Replaced draft “four form” decomposition with **implemented** `state_machine` sequence, `seah_focal_stage`, `action_prepare_seah_focal_complainant_capture` mapping (`municipality`/`village` → focal city/village), `form_seah_focal_point_2` conditional slots; fixed broken markdown; aligned “already decided” and devil’s advocate items with code and `04`; noted `not_adb_project` still submits via `action_submit_seah`.
