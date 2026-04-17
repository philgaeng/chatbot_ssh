# SEAH/SEIA Sensitive Flow Refactor Specification (April 20)

## Instructions Baseline

This spec follows `docs/Refactor specs/AGENT_INSTRUCTIONS.md` and uses the same naming convention used in `docs/Refactor specs/March 5` (numeric prefix).

## Objective

Define the end-to-end SEAH/SEIA complaint workflow so it:
- matches the agreed survivor-centered process from the April meeting notes,
- aligns with the SEAH one-pager form structure (`NEP-chatbot-SEAH-10Apr.pdf`),
- and separates SEAH handling from the general grievance mechanism in routing, storage, and notifications.

This spec is the source of truth for the refactor of:
- `backend/actions/forms/form_sensitive_issues.py`
- `backend/actions/utils/utterance_mapping_rasa.py`
- `backend/actions/utils/mapping_buttons.py`
- the state transitions around sensitive flow
- data persistence and notification behavior for SEAH/SEIA complaints.

## Spec Index

- `docs/Refactor specs/April20_seah/01_seah_route_and_slots.md`
- `docs/Refactor specs/April20_seah/02_seah_utterances_and_buttons.md`
- `docs/Refactor specs/April20_seah/03_seah_submission_and_storage.md`
- `docs/Refactor specs/April20_seah/04_seah_otp_and_validation.md`
- `docs/Refactor specs/April20_seah/05_seah_tests_and_regression.md`
- `docs/Refactor specs/April20_seah/06_seah_rollout_and_feature_flags.md`
- `docs/Refactor specs/April20_seah/xx-ticketing-sytem-seah.md` (ticketing-system scope)

---

## Current State Review (What exists now)

## `form_sensitive_issues.py` behavior

The current sensitive form is a short follow-up form with slots:
- `sensitive_issues_follow_up`
- `complainant_phone`
- `sensitive_issues_nickname` (conditional)
- `sensitive_issues_new_detail` (conditional)

It supports command-style pathways:
- `/exit` -> anonymous without phone
- `/anonymous_with_phone` -> anonymous with one phone number
- `/add_more_details` -> collect one more detail message
- `/not_sensitive_content` -> clear sensitive flags and revert to non-sensitive path

The form pre-fills many contact/location slots to skip the normal contact form in anonymous branches.

## Orchestration behavior

When `grievance_sensitive_issue = True`, state transitions from grievance form into `form_sensitive_issues`, then continues into `form_contact`.

After sensitive form completion, `action_outro_sensitive_issues` is sent for specific follow-up values and then the regular contact flow begins.

## Submission/notification behavior

`action_submit_grievance` currently:
- submits to the general grievance DB path (`submit_grievance_to_db`)
- generates regular confirmation text including grievance ID and timeline
- may send SMS confirmation when OTP is verified

This behavior is not compliant for SEAH/SEIA under the new requirements.

---

## Target Workflow (To-Be)

## Entry and route separation

1. User selects SEAH/SEIA route directly from main menu/intake entry.
2. SEAH route remains confidential and independent from general safeguards grievance route.
3. SEAH records are never inserted into general grievance tracker tables/views used by broad backend users.

## Intake sequence (confirmed order)

Required sequence for SEAH route:
1. Intro/consent text for SEAH channel (ADB SEAH team-provided content)
2. Identity choice:
   - identified name (free text), or
   - anonymous
3. `Are you the victim/survivor?`
   - Yes
   - No
   - No, I am the SEAH focal point
4. Contact number (optional to provide; allowed values include none)
5. Contact email (optional to provide; allowed values include none)
6. ADB project name/site (free text; `Cannot specify`; `Not an ADB project`)
7. Incident summary (free text)
8. SEAH focal point branch (only if user is focal point):
   - additional survivor/at-risk-party risks
   - mitigation measures already in place
   - other at-risk parties
   - risk to ADB project
   - reputational risk to ADB
   - **new:** when did focal point learn about incident?
9. Informed consent for follow-up contact:
   - yes via phone only
   - yes via email only
   - yes via both
   - no
10. End-screen acknowledgment and referral/services text (ADB SEAH team-provided)

## Survivor-centered constraints

- No probing investigative follow-up in chatbot intake.
- Keep only mandatory initial assessment fields.
- Detailed facts (exact timing, witness details, relationship details, granular location, etc.) are deferred to investigator-led process.

## Not-an-ADB project branch

If user selects `Not an ADB project`:
- do not route into standard grievance tracking,
- show external referral/support message supplied by SEAH team,
- preserve confidential handling of already entered sensitive info,
- still allow submission to SEAH confidential intake log if policy requires triage record.

---

## Mandatory Field Policy

Within SEAH process design, all form steps are mandatory to pass through, but each disclosure-type field must include a non-disclosing answer option.

Implementation rule:
- Mandatory = chatbot must ask each required step.
- Non-forcing = each step includes allowed values such as `anonymous`, `none`, `NA`, `cannot specify`, or `I do not want to provide`.

This preserves structure without coercing disclosure.

---

## Focal Point Validation Requirements

## Identity verification

For users selecting `I am the SEAH focal point`:
1. collect first name + last name,
2. validate against internal SEAH focal point table,
3. if no match:
   - allow retry, or
   - allow skip with fallback capture of phone/email for later verification and roster update process.

## Authentication approach

- Do not expose focal point roster/list to end users.
- Preferred method: OTP to registered phone for focal point validation.
- Birthdate-based validation is not preferred.

---

## Data Architecture and Access Controls

## Storage segregation (required)

Implement SEAH-specific persistence (same DB instance is acceptable) using dedicated entities, e.g.:
- `complainant_seah`
- `grievance_seah`
- `grievance_seah_status_history`
- optional focal-point assessment table if normalized design is preferred

General rules:
- No write of SEAH complaint payloads into general `grievances` tracker tables used by non-SEAH users.
- No inclusion of SEAH complaints in standard status-check APIs or UI lists.
- Restrict read/write access by role to designated SEAH users.

## Admin/reviewer auth hardening

- Dedicated SEAH back-office access requires 2FA/MFA.
- OTP can be phase-1 implementation.
- Future option: authenticator/passkey support.

---

## Notifications and Communications Policy

## Disallowed for SEAH route

- No SMS notifications.
- No grievance/case number via SMS.
- No standard chatbot status notification channel behavior for SEAH submissions.
- No user-initiated follow-up/modify flow in chatbot for SEAH.

## Required for SEAH route

- On-screen submission confirmation only.
- Include referral/service information in confirmation screen.
- Follow-up contact is investigator-managed based on consent captured in intake.

---

## Gap Analysis: Current vs Required

1. **Flow scope mismatch**
   - Current `form_sensitive_issues` is a short post-detection follow-up, not a full SEAH intake form.
   - Required: dedicated full SEAH intake route with ordered mandatory steps and focal-point branch.

2. **Data segregation missing**
   - Current submission path uses general grievance submission/storage pipeline.
   - Required: SEAH-specific tables and role-restricted access path.

3. **Notification non-compliance**
   - Current code supports SMS confirmation (`_send_grievance_recap_sms`).
   - Required: no SMS for SEAH under any condition.

4. **Follow-up/modify policy mismatch**
   - Existing architecture supports status checks/modifications for general grievances.
   - Required: SEAH route excludes user follow-up/modify flow.

5. **Focal point verification missing**
   - No dedicated focal point lookup/validation/OTP branch in current sensitive form.
   - Required: controlled focal point validation process.

6. **Project triage branch incomplete**
   - Current flow has no explicit `Not an ADB project` referral branch in sensitive route.
   - Required: referral messaging and distinct handling.

---

## Refactor Requirements (Implementation Checklist)

## A. Conversational flow and slots

- Replace/expand `form_sensitive_issues` into full SEAH intake form sequence.
- Add explicit slots for:
  - identity mode (identified/anonymous)
  - victim-survivor role response
  - project identification with `cannot_specify` and `not_adb_project`
  - incident summary
  - follow-up consent channel
  - focal-point fields including `focal_point_learned_when`
- Keep non-disclosing options for every required step.
- Remove command-centric sensitive shortcuts as primary behavior for SEAH route.

## B. Routing/state machine

- Add dedicated `seah_intake` route from main menu.
- Keep separate from general sensitive-content-detection branch.
- Ensure SEAH submission terminal state does not transition to general grievance status-check flow.

## C. Persistence layer

- Add SEAH-specific repository/service methods for create/update.
- Implement dedicated DB tables and migrations for SEAH entities.
- Ensure `action_submit_grievance` is not used for SEAH finalization; create `action_submit_seah` (or equivalent).

## D. Notification layer

- Add explicit guardrail in SEAH submission path disabling SMS/email templates from standard grievance path unless SEAH policy allows specific controlled email.
- Provide dedicated on-screen confirmation utterance for SEAH.

## E. Access control and auth

- Introduce role-scoped SEAH retrieval endpoints/queries.
- Enforce 2FA requirement for SEAH admin/reviewer interfaces (phase 1 OTP acceptable).

## F. Content placeholders (external dependencies)

Await final text from SEAH team for:
- intro consent text,
- `Not an ADB project` referral text,
- end-of-flow acknowledgment/referral content.

---

## Acceptance Criteria

1. A SEAH complaint can be completed end-to-end without entering general grievance tracker storage.
2. No SMS is sent for SEAH complaints.
3. Submission confirmation appears on-screen with referral/support content.
4. Intake asks all mandatory SEAH fields in required order with non-disclosure options.
5. Focal point branch appears only when focal point role selected.
6. Focal point validation does not disclose roster and supports OTP-based verification path.
7. SEAH records are visible only to authorized SEAH roles.
8. SEAH complaints cannot be retrieved/modified through standard status-check flow.

---

## Out of Scope (for this refactor increment)

- Full investigation workflow tooling after intake
- Advanced MFA/passkey rollout beyond initial OTP if change request is pending
- Final referral content authoring (provided by SEAH team)

---

## Notes for Implementation Planning

- Keep the existing sensitive-content detector for generic grievance safety handling, but do not conflate it with the dedicated SEAH intake route.
- If backward compatibility is needed, preserve current `form_sensitive_issues` behavior behind a feature flag while introducing the new SEAH route.
- Add regression tests for both:
  - legacy sensitive detection flow, and
  - new dedicated SEAH intake flow.

---

## Open Questions for Stakeholder Answers (Please confirm before work split)

Answer format suggestion: copy each item and respond with one of `DECIDED`, `TBD`, or `OUT OF SCOPE` plus your selected option.

### A. Scope and route behavior

1. Should the dedicated SEAH route be exposed as a **separate main menu item** immediately, or initially only as an internal route for controlled pilots? INITIALLY - we are starting a new branch for this feature
2. Should legacy `grievance_sensitive_issue` auto-detection continue to route into current sensitive fallback while new SEAH route is built, or should it be hard-switched to new SEAH flow at launch? - DECIDED Hard swithed in the new branch
3. For `Not an ADB project`, should we:
   - A) end immediately with referral text only, or
   - B) still save a minimal confidential triage record? 
   DECIDED
4. Should users be allowed to upload files in SEAH intake at this stage? TBD

### B. Mandatory fields and allowed skip semantics

5. Confirm the exact mandatory question list for v1 (including focal-point-only fields).
6. For each mandatory field, confirm canonical non-disclosure values (`anonymous`, `none`, `NA`, `cannot specify`, `prefer not to say`) to standardize storage. ECIDD "skipped" like the rest of the project
7. For contact details, confirm policy:
   - A) ask both phone and email, each skippable independently, or
   - B) require at least one contact method unless anonymous?
   DECIDED A
8. Should complainant name and focal-point name be stored as free text, or split into first/last name slots in the chatbot? DECIDED - free text like the current complainant_full_name

### C. Focal point verification

9. Confirm focal-point verification timing:
   - A) validate immediately during intake, or
   - B) allow intake completion then verify asynchronously.
   DECIDED A
10. If focal point not found in roster, should fallback path:
   - A) ask retry then collect contact for offline verification, or
   - B) continue as non-focal complainant path.
   DECIDED A
11. Confirm OTP channel for focal-point verification (SMS, voice, email OTP, or internal admin approval only).
DECICED SMS
12. Confirm whether failed OTP attempts should block submission or allow submission tagged `unverified_focal_point`.
DECIDED allow submission tagged `unverified_focal_point`

### D. Data model and storage segregation

13. Confirm target storage model:
   - A) dedicated SEAH tables in same database, or
   - B) separate physical database.
   DECIDED B
14. Confirm minimum SEAH tables required in v1 (e.g., `complainant_seah`, `grievance_seah`, `grievance_seah_status_history`, `seah_focal_point_assessment`, `seah_referral_events`).
DECIDED - copy the grievances and complainant tables of the main flow
15. Should SEAH records have a dedicated case ID format (for example `SEAH-YYYY-######`)?
DECIDE YES
16. Confirm encryption requirements for SEAH fields at rest (which columns must be encrypted vs masked).
DECIDED - same than main flow

### E. Access control and audit

Moved to `docs/Refactor specs/April20_seah/xx-ticketing-sytem-seah.md`.

### F. Notifications and communications

21. Confirm no-SMS policy applies to:
   - A) complainant-facing messages only, or
   - B) all SEAH-related outbound SMS including internal alerts.
   DECIDED A
22. Should internal SEAH team notifications be sent (email/in-app queue/webhook), and if yes through which channel?
Moved to `docs/Refactor specs/April20_seah/xx-ticketing-sytem-seah.md`.
23. Confirm final on-screen submission copy owner and approval process (who signs off final text).
I dont understand the question clarify if it pertains to chatbot or tiketing system
24. Should end-screen include a case reference visible to user, or avoid showing any persistent identifier?
DECIDED Show the case reference and close after 30 s with a timer on screen

### G. Referral and support content

25. Confirm ownership and deadline for final referral text (intro and end-of-flow).
out of scope - we can write our best guess for the text and translate later
26. Should referral resources vary by language only, or also by district/province/project context? 
DECIDED - we use utterance_mapping for all the utterances in englsih and nepali. Locations and phone numbers should be stored in db
27. If user is in immediate danger, do we need an urgent safety branch message and hotline priority block?
TBD

### H. Follow-up, status check, and modifications

28. Confirm SEAH status-check policy:
   - A) completely disabled for end users, or
   - B) limited one-way “received” confirmation only.
   DECIEDED - A
29. Confirm SEAH modification policy:
   - A) no chatbot modification at all, or
   - B) allow narrow corrections before final submit.
   DECIDED A
30. Should investigators have a separate internal workflow endpoint for follow-up updates outside chatbot?
Moved to `docs/Refactor specs/April20_seah/xx-ticketing-sytem-seah.md`.

### I. Localization and UX details

31. Which languages are in-scope for SEAH v1 (`en`, `ne`, others)?
DECIDED - en and ne
32. Should language be locked at start of SEAH flow or switchable mid-flow?
Decided same behavior as normal flow - loacked at start
33. Confirm consent wording review requirement (legal/safeguards review gate before deployment).
TBD
### J. Delivery and rollout strategy

34. Preferred rollout:
   - A) feature-flagged incremental release, or
   - B) full cutover.
   DECIDED In a new branch - incremental release
35. Confirm migration/backfill need for previously flagged sensitive grievances in general tables.
DECODED no need as it is test only
36. Confirm test sign-off checklist owners (product, safeguards/SEAH, engineering, QA).
DECIDED seems good

### K. Remaining blocking questions (new)

37. Should the timer-based auto-close after confirmation (30s) be:
   - A) mandatory in v1 UX, or
   - B) optional and controlled by frontend config?
   DECIDED B - 
38. For case reference visibility, should the user-facing reference be:
   - A) the real SEAH case ID, or
   - B) a public-safe reference token mapped internally to case ID?
 DECIDED B   
39. For focal point OTP via SMS (already decided), confirm sender policy:
   - A) existing SMS sender identity, or
   - B) dedicated SEAH sender identity/number.
   we can reuse the service
40. For English/Nepali utterances, confirm translation source of truth:
   - A) maintain directly in `utterance_mapping_rasa.py`, or
   - B) load from DB/content table and sync to runtime mappings.
   DECIDED A
41. Confirm data retention period for SEAH intake records in chatbot-owned storage.
TBD - not relevant for demo
42. Confirm whether SEAH records should be excluded from non-production logs/analytics exports by default.
TBD - not relevant for demo

---

## Branching and Testing Instructions (Explicit)

These instructions are mandatory for implementation of this spec.

### Branch setup

1. Do not implement on `main`.
2. Create a dedicated branch for this feature set, recommended:
   - `feat/seah-sensitive-intake`
3. Keep implementation on the single feature branch by default to reduce merge overhead.
4. Create only one optional support branch when needed:
   - `feat/seah-sensitive-intake-tests` (use only if test work lags behind implementation)
5. Merge to `main` only after review and green checks.

### Required tests per PR

Every PR under this spec must include and pass:

1. **Unit tests**
   - form slot extraction/validation for SEAH intake
   - focal point branch logic and OTP decision handling
   - no-SMS guardrail for SEAH complainant-facing flow
2. **State-machine/integration tests**
   - routing into dedicated SEAH flow from main menu
   - `Not an ADB project` branch behavior
   - submission path does not call general grievance submit
3. **Regression tests**
   - legacy non-SEAH grievance flow still works
   - existing sensitive detection fallback behavior (if feature flag keeps it)
4. **Content mapping tests**
   - utterance keys exist in `backend/actions/utils/utterance_mapping_rasa.py`
   - button mappings exist in `backend/actions/utils/mapping_buttons.py`
5. **Negative tests**
   - SEAH flow does not emit complainant SMS recap
   - SEAH flow not exposed in standard status-check endpoints

### Suggested validation commands

- `pytest backend -k "seah or sensitive or grievance"`
- `pytest backend/orchestrator/scripts`
- project-standard Docker validation path (as defined in team workflow)

---

## Implementation Split for Parallel Agent Work

The work should still be split into numbered specs, but development should remain lightweight:
- Default: execute most work on `feat/seah-sensitive-intake`.
- Optional parallel branch only for test catch-up if needed.

### Proposed spec files

1. `01_seah_route_and_slots.md`
   - Main menu route, form slots, branching, focal-point conditional questions.
2. `02_seah_utterances_and_buttons.md`
   - All copy keys and button payloads in:
     - `backend/actions/utils/utterance_mapping_rasa.py`
     - `backend/actions/utils/mapping_buttons.py`
3. `03_seah_submission_and_storage.md`
   - Dedicated submit action and storage path separation from general grievance flow.
4. `04_seah_otp_and_validation.md`
   - Focal-point lookup + OTP verification behavior and fallback tagging (`unverified_focal_point`).
5. `05_seah_tests_and_regression.md`
   - Unit, integration, and regression coverage, including no-SMS assertions.
6. `06_seah_rollout_and_feature_flags.md`
   - Branch rollout strategy, feature flags, and cutover checklist.

### Parallel execution plan (agent assignment)

- **Primary agent (main branch):**
  - Executes `01`, `02`, `03`, and `04` sequentially in `feat/seah-sensitive-intake`.
- **Optional QA agent (test branch):**
  - Executes `05` in `feat/seah-sensitive-intake-tests` only if tests become a bottleneck.
- **Rollout owner:**
  - Completes `06` on the main feature branch before merge.

### Dependency order

1. Complete `01` first to lock slot and route contract.
2. Complete `02` next to stabilize user-facing content and buttons.
3. Complete `03`, then `04`, with aligned slot/action contracts.
4. Run `05` continuously; if delayed, move it to optional test branch.
5. Finalize `06` once implementation and tests are stable.

### Merge cadence

1. Prefer small, frequent commits on `feat/seah-sensitive-intake`.
2. If optional test branch is used, merge it back before final regression run.
3. Merge `feat/seah-sensitive-intake` to `main` after final checks and approvals.