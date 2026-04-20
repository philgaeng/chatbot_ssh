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

- `docs/Refactor specs/April20_seah/NEP-chatbot-v2.pdf` (updated flow)
- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md` (prior decisions)
- `backend/actions/forms/form_seah_focal_point.py` (current implementation to refactor)

When these conflict, prioritize:
1. PDF flow for question order and required field coverage.
2. `00` decisions for policy behaviors (OTP, skip semantics, etc.).
3. Existing code only where it does not conflict with 1 and 2.

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

## Implementation scope for this spec

In scope:
- Split focal-point intake into four forms with explicit handoff order.
- Reuse existing regular SEAH complainant slots where possible.
- Derive focal-point phone via OTP-style collection flow (copy/adapt from `form_otp` logic) to avoid extra manual questions.
- Add focal-point-specific utterances/buttons and `action_ask_*` conditions.
- Ensure slot values normalize to project canonical skip semantics (`skipped`) while preserving user option meanings.

Out of scope:
- Ticketing-system ownership, assignment, and back-office workflows.
- Final legal copy authoring for intro/ack messages.
- Non-focal SEAH branch redesign.

---

## Proposed form decomposition (draft)

### Step 1: reuse `form_otp` + `form_contact` for focal-point reporter bootstrap

Purpose:
- Reuse existing validated collection paths instead of creating `form_seah_focal_point_contact`.
- Capture focal-point reporter details with minimal new logic.

Bootstrap collection strategy:
- Use `form_otp` for phone capture/validation only.
- Use `form_contact` for name/location capture.
- In this bootstrap step, these shared slots represent the focal-point reporter (temporarily), not the complainant.
- Immediately before activating each reused form, pre-fill non-required slots with `SKIP_VALUE` so only intended questions are asked.

Bootstrap slot mapping to focal-point slots (copy before reset):
- `complainant_phone` -> `seah_focal_phone`
- `complainant_full_name` -> `seah_focal_full_name`
- `grievance_city` -> `seah_focal_city` (or mapped city slot used in project)
- `grievance_village` -> `seah_focal_village` (or mapped village/locality slot used in project)

Reset step (required):
- After copy, reset temporary shared slots (`complainant_*` and location slots used in bootstrap) to `None` so they can be reused for actual complainant capture later.
- Before launching `form_contact` for actual complainant capture, pre-fill non-target contact slots with `SKIP_VALUE` again to constrain asked questions to this spec.

### Form 2: `form_seah_focal_point_1`

Purpose:
- Collect focal-point-only first block.

Slots:
- `seah_focal_learned_when` (ISO date string)
- `seah_focal_reporter_consent_to_report` (`yes`/`no`)
- `sensitive_issues_follow_up` (`identified`/`anonymous`) for complainant identity mode

### Form 3: reuse `form_otp` then `form_contact`

Purpose:
- Reuse standard complainant/contact capture for the actual complainant after bootstrap slots were copied and reset.

Complainant phone collection:
- Use `form_otp` again to collect/validate `complainant_phone`.
- Before activating this `form_otp` run, pre-fill OTP auth slots (`otp_consent`, `otp_status`, `otp_input`, `otp_number`, `otp_resend_count`) with `SKIP_VALUE`/safe defaults so OTP authentication is not triggered.

Reused slots for `form_contact`:
- `complainant_full_name` (text or `skipped`)
- `complainant_email` (email or `skipped`)

Implementation note:
- Prefer adding focal-point-specific utterance keys and conditional `action_ask_*` behavior over introducing a new mixin refactor in this phase.
- In this codebase, this should be done in `backend/actions/utils/utterance_mapping_rasa.py` which is server-side API messaging.
- Keep `form_contact` slot collection shared; route persistence to `seah_complainant`/SEAH tables at submission time.
- Add a pre-launch action that sets irrelevant `form_contact` slots to `SKIP_VALUE` before activating the form, then keeps only the target slots as `None`.

### Form 4: reuse `form_seah_2` pattern for focal-point final block

Purpose:
- Collect the remainder of focal-point assessment and SEAH incident intake.
- Reuse the same iterative detail flow behavior already implemented in `backend/actions/forms/form_seah_2.py`.

Slots:
- `seah_project_identification` (`text`/`not_sure`/`not_adb_project`)
- 'sensitive_issues_new_detail` (reuse `form_seah_2` restart/add-more/submit detail loop behavior)
- `seah_focal_survivor_risks` (multi-select or free text, supports `none`)
- `seah_focal_mitigation_measures` (multi-select or free text, supports `none`)
- `seah_focal_other_at_risk_parties` (multi-select or free text, supports `none`)
- `seah_focal_project_risk` (`project_delay`/text/`none`)
- `seah_focal_reputational_risk` (`yes`/`none`)
- `seah_contact_consent_channel` (`phone`/`email`/`both`/`none`)
- `seah_focal_referred_to_support`
- `

Reporter type is derived from the existing role slot (`seah_victim_survivor_role = focal_point`), so we should not duplicate that with additional reporter-role slots.

Note: Focal-point reporter identification (name, phone, city, village) is intentionally retained even though the latest PDF under-specifies it. OTP roster-specific focal slots are not needed when reusing the main `form_otp` flow.

---

## Recommended implementation pattern

Recommendation for this phase:
- Use **form split + shared slots + conditional utterances/action asks**.
- Do **not** introduce mixin extraction yet.

Why:
- Existing `form_seah_1.py` and `form_seah_2.py` already use the same pattern and can be extended quickly.
- Lower risk for current branch timeline and easier regression coverage.
- Mixin extraction can be a follow-up refactor once behavior is stable.


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

1. Focal-point roster OTP verification path is not used; phone handling reuses main `form_otp`.
2. If consent-to-report is `No`, jump directly to `seah_focal_referred_to_support`, then acknowledgment.
3. Legacy risk fields are in scope via reuse of `form_seah_2` final-block behavior.
4. `sensitive_issues_new_detail` remains in use (same loop semantics as `form_seah_2`).

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
   - `consent_to_report = No` is an intentional exception to the "ask all mandatory steps" rule.
   - In this branch, flow short-circuits to `seah_focal_referred_to_support` then acknowledgment.

2. **Free-text date accepted**
   - `seah_focal_learned_when` remains free text.
   - No parsed companion field is required for this phase.

3. **Reset safety is mandatory**
   - A single dedicated action must perform copy/reset operations atomically before form transitions.
   - This action must include tests.

4. **Consent semantics standardized**
   - If contact-consent channel is not asked, store canonical `SKIP_VALUE`.

5. **OTP skip behavior required**
   - When `complainant_phone` is skipped in reused `form_otp`, OTP-related slots must remain non-triggering.

6. **Not-ADB branch behavior**
   - If `seah_project_identification = not_adb_project`, short-circuit to referral/ack path.

7. **Localization ownership clarified**
   - This spec remains the functional source of truth for wording intent.
   - Runtime chatbot utterance/button mappings must be implemented in `backend/actions/utils/utterance_mapping_rasa.py` (not `backend/shared_functions/utterance_mapping_server.py`).

8. **Backward compatibility**
   - No migration mapping is required in this phase.

9. **Auditability extras**
   - No extra branch-path audit fields are required in this phase.

10. **Test gate scope**
   - Full additional branch-level integration gate is not mandatory for this phase.
