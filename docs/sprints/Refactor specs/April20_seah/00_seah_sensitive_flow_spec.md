# SEAH/SEIA Sensitive Flow Refactor Specification (April 20)

## Instructions Baseline

This spec follows `docs/Refactor specs/AGENT_INSTRUCTIONS.md` and uses the same naming convention used in `docs/Refactor specs/March 5` (numeric prefix).

## Objective

Define the end-to-end SEAH/SEIA complaint workflow so it:
- matches the agreed survivor-centered process from the April meeting notes,
- aligns with the SEAH one-pager form structure (`NEP-chatbot-SEAH-10Apr.pdf`),
- and separates SEAH handling from the general grievance mechanism in routing, storage, and notifications.

This spec is the parent policy document for SEAH/SEIA intake. **Authoritative routing and slot contracts** for the implemented bot are documented in child specs and code:

- `backend/actions/forms/form_seah_1.py`, `form_seah_2.py`, `form_seah_focal_point.py`
- `backend/actions/forms/form_contact.py`, `backend/actions/forms/form_otp.py`
- `backend/orchestrator/state_machine.py` (form sequencing)
- `backend/actions/utils/utterance_mapping_rasa.py`, `mapping_buttons.py`
- `backend/actions/action_submit_grievance.py` (`ActionSubmitSeah`), `backend/services/database_services/postgres_services.py` (`submit_seah_to_db`)

## Spec Index

- `docs/Refactor specs/April20_seah/01_seah_route_and_slots.md` (victim path + slots; runtime source of truth)
- `docs/Refactor specs/April20_seah/07_seah_focal_point_flow.md` (focal-point path + staging)
- `docs/Refactor specs/April20_seah/02_seah_utterances_and_buttons.md`
- `docs/Refactor specs/April20_seah/03_seah_submission_and_storage.md`
- `docs/Refactor specs/April20_seah/04_seah_otp_and_validation.md`
- `docs/Refactor specs/April20_seah/08_seah_outro_and_project_catalog.md` (post-submit outro variants + project picker / DB catalog)
- `docs/Refactor specs/April20_seah/05_seah_tests_and_regression.md`
- `docs/Refactor specs/April20_seah/06_seah_rollout_and_feature_flags.md`
- `docs/Refactor specs/April20_seah/xx-ticketing-sytem-seah.md` (ticketing-system scope)

---

## Implementation status (aligned with `01`, `07`, and codebase)

The following are **implemented** in the current branch:

- Dedicated menu route `start_seah_intake` / `story_main: seah_intake` when SEAH is enabled (`state_machine.py`).
- **Victim / non–focal-point path:** `form_seah_1` → (`form_otp` phone-only if identified) → `form_contact` → `form_seah_2` → `action_submit_seah` (see `01`).
- **Focal-point path:** `form_seah_1` → staged `form_otp` / `form_contact` / `form_seah_focal_point_1` / `form_seah_focal_point_2` with `seah_focal_stage` and `action_prepare_seah_focal_complainant_capture` (see `07`).
- Sensitive follow-up from **general grievance** still merges into `form_seah_1` when `grievance_sensitive_issue` is set after `form_grievance`.
- **Submission:** `ActionSubmitSeah` → `submit_seah_to_db` → tables `complainants_seah`, `grievances_seah` (not general grievance insert for final SEAH submit).
- **Complainant-facing SMS recap:** not invoked on `ActionSubmitSeah` (on-screen confirmation with `seah_public_ref` only).
- **OTP behavior for `seah_intake` + sensitive:** `ValidateFormOtp.required_slots` collects **`complainant_phone` only** (no OTP verification step on that branch); see `04` and `01`.

Product PDF order may differ slightly from question order in code (e.g. project vs narrative order in `form_seah_2`); child spec `01` reflects **code order**.

---

## Current state review

### Legacy (pre–dedicated-SEAH) behavior

Older builds used `form_sensitive_issues.py` as a short post–grievance-detection follow-up. That module is **not** the dedicated SEAH route anymore; sensitive **grievance** detection still feeds `form_seah_1` from `form_grievance` when the user flags a sensitive issue there.

### Implemented orchestration (now)

- **Dedicated SEAH:** `state_machine.py` sets `story_main` / `grievance_sensitive_issue` and drives `form_seah_*`, `form_contact`, `form_otp` per `01` and `07`.
- **Training YAML:** `domain.yml` lists minimal `required_slots` per form; **runtime** slot lists come from each `ValidateForm*.required_slots()` implementation.

### Submission / notification (now)

- **`action_submit_grievance`** remains for non-SEAH grievances (may still use SMS recap where configured).
- **`action_submit_seah`** persists via `submit_seah_to_db` and shows a **public reference** string; it does **not** send the standard grievance confirmation SMS path used after generic submit.

---

## Target workflow (product) vs implemented order

## Entry and route separation

1. User selects SEAH/SEIA route directly from main menu/intake entry.
2. SEAH route remains confidential and independent from general safeguards grievance route.
3. SEAH finalization uses **`submit_seah_to_db`** / dedicated tables (see `03`); payloads are not written through the **general** grievance create path for SEAH submit.

## Intake sequence — victim path (implemented; see `01`)

Order in **code** (may differ from one-pager line order; align copy in `02` as needed):

1. **SEAH intro + identity mode** (`form_seah_1`: `sensitive_issues_follow_up` — identified / anonymous).
2. **Victim/survivor role** (`form_seah_1`: `seah_victim_survivor_role` — includes focal-point option when not anonymous).
3. **Phone (identified only)** via **`form_otp`** — **phone slot only** for `seah_intake` + sensitive (no OTP verification step); anonymous skips this form.
4. **Location (+ contact for identified)** via **`form_contact`** with SEAH overrides (anonymous: location only; identified: location + consent + name + email).
5. **Project, incident narrative, informed contact channel** via **`form_seah_2`** (channel omitted when anonymous; project supports `cannot_specify` / `not_adb_project` + free text).
6. **Submit** → `action_submit_seah` → on-screen reference (`seah_public_ref`).

## Intake sequence — focal-point branch (implemented; see `07`)

After role `focal_point`, the bot stages **reporter** capture (`form_otp` / `form_contact` with `seah_focal_stage`), then **`form_seah_focal_point_1`** (learned when, consent to report, complainant identified/anonymous), optional second phone pass, **`form_seah_focal_point_2`** (project, narrative, focal risk fields, contact consent when applicable, referred-to-support), then **`action_submit_seah`**.

Focal-only assessment fields (risks, mitigation, etc.) live in **`form_seah_focal_point_2`**, not in victim `form_seah_2`.

## Product-facing items still driven by content (`02`)

- Intro / referral / not-ADB messaging: utterance keys (some `REPLACE_ME` placeholders).
- End-screen acknowledgment and referral/services text (ADB SEAH team or placeholders).

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

## Disallowed for SEAH route (policy — refine with stakeholder matrix **F**)

- No **complainant-facing** grievance recap SMS or case reference via SMS on **SEAH submit** (`ActionSubmitSeah` — see `03`).
- No standard **end-user** status notification channel behavior for SEAH submissions (stakeholder **H**).
- No user-initiated follow-up/modify flow in chatbot for SEAH.

**Implementation note:** Sensitive **`seah_intake`** phone collection uses **`form_otp`** with **phone-only** `required_slots`, so **OTP SMS** is not triggered on that branch (`04`). Other SMS use (internal ops) is out of chatbot submit path unless explicitly added.

## Required for SEAH route

- On-screen submission confirmation (includes **`seah_public_ref`** today; extended referral copy may still be `REPLACE_ME` — `02` / `03`).
- Follow-up contact is investigator-managed based on consent captured in intake (`seah_contact_consent_channel` when collected).

---

## Gap analysis (historical → status)

1. **Flow scope**
   - **Was:** short `form_sensitive_issues` only.
   - **Now:** dedicated `seah_intake` + `form_seah_1` / `form_seah_2` + shared `form_contact` / `form_otp`; focal `form_seah_focal_point_*` (`01`, `07`).

2. **Data segregation**
   - **Was:** general grievance pipeline only.
   - **Now:** `submit_seah_to_db` → `complainants_seah` / `grievances_seah` + JSON `seah_payload` (`03`). Role-restricted APIs / ticketing remain per `xx` spec.

3. **Complainant-facing SMS on submit**
   - **Was:** generic submit could send recap SMS.
   - **Now:** `ActionSubmitSeah` does not use grievance recap SMS; internal SMS policy remains per stakeholder decisions in **F** below.

4. **Follow-up / modify**
   - **Policy:** no end-user SEAH status-check/modify in chatbot (stakeholder **H**).
   - **Code:** keep SEAH terminal separate from general status-check flow (`01`).

5. **Focal-point “roster OTP” verification**
   - **Policy (`00` C):** roster match + SMS OTP for focal verification with `unverified_focal_point` fallback.
   - **Code today:** reporter/complainant phones are collected via shared **`form_otp`** with **phone-only** `required_slots` whenever `story_main == seah_intake` and `grievance_sensitive_issue` is true (`04`). **Roster lookup / focal OTP verification** is not fully implemented as originally written; slots such as `seah_focal_lookup_status` exist for future wiring—track in `04` / `07`.

6. **`Not an ADB project`**
   - **Now:** `seah_project_identification` + `seah_not_adb_project`; referral copy can be added/updated under `02` (utterances); submission still completes via `action_submit_seah` unless product adds an early terminal.

---

## Refactor requirements (implementation checklist — status)

## A. Conversational flow and slots

- [x] SEAH intake forms: `form_seah_1`, `form_seah_2`, `form_seah_focal_point_1` / `form_seah_focal_point_2` with explicit slots (identity, role, project, narrative, consent channel, focal fields).
- [x] Non-disclosure / skip semantics aligned with project `skipped` / `slot_skipped` patterns.
- [ ] Finalize copy (`REPLACE_ME` in `02`) and any product-only shortcuts (e.g. `not_sensitive_content` → main menu) in `state_machine` if required.

## B. Routing/state machine

- [x] Dedicated `seah_intake` from main menu; `_is_seah_enabled()` gate.
- [x] Sensitive grievance path can merge into `form_seah_1`.
- [x] SEAH submit ends in dedicated terminal (`action_submit_seah`), not general grievance review loop.

## C. Persistence layer

- [x] `submit_seah_to_db` + `complainants_seah` / `grievances_seah` (DDL in service when tables missing).
- [x] `ActionSubmitSeah` (not `action_submit_grievance`) for SEAH finalization.

## D. Notification layer

- [x] No grievance recap SMS from `ActionSubmitSeah`.
- [ ] Internal / ops notifications per ticketing spec (`xx`).

## E. Access control and auth

- [ ] Role-scoped SEAH retrieval APIs and back-office 2FA per `xx` / infra (out of chatbot repo scope may apply).

## F. Content placeholders (external dependencies)

Still applicable for final ADB SEAH-approved strings:

- intro consent text (`form_seah_1` utterances),
- `Not an ADB project` / referral blocks,
- end-of-flow acknowledgment (and optional 30s close UX on **frontend** per stakeholder decisions).

---

## Acceptance criteria

1. A SEAH complaint can be completed end-to-end without using the **general grievance** insert path for finalization (`submit_seah_to_db`).
2. **Complainant-facing** submit path does not send the standard grievance recap SMS from `ActionSubmitSeah` (aligns with stakeholder **F** “no complainant SMS” decision).
3. Submission confirmation appears **on-screen** with a **public reference** (`seah_public_ref`); richer referral/support copy may still use `REPLACE_ME` until finalized (`02`).
4. Intake collects mandatory SEAH fields with non-disclosure options per `01` / validators.
5. Focal-point-only forms appear only when `seah_victim_survivor_role == focal_point` (`07`).
6. **Focal roster + OTP verification** as originally specified (lookup, `unverified_focal_point`) is **not fully implemented** in code; phone collection reuses `form_otp` with **sensitive SEAH phone-only** behavior—see `04` / `07` for current vs target gap.
7. SEAH DB visibility to authorized roles is an **ops/DB** concern; schema exists in `postgres_services.py`.
8. SEAH complaints are not exposed through the **standard end-user** status-check chatbot flow (policy in **H**).

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
5. `07_seah_focal_point_flow.md`
   - Focal-point staging, `seah_focal_stage`, focal forms vs victim path.
6. `08_seah_outro_and_project_catalog.md`
   - Post-submit outro variants; DB-backed project catalog / picker.
7. `05_seah_tests_and_regression.md`
   - Unit, integration, and regression coverage, including no-SMS assertions.
8. `06_seah_rollout_and_feature_flags.md`
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

---

## Changelog

- **2026-04-21:** Aligned parent spec with implemented routing (`01`), focal staging (`07`), and codebase: replaced legacy `form_sensitive_issues` narrative, added implementation status, victim vs focal sequences, gap-analysis status, checklist checkboxes, and acceptance criteria notes (SEAH submit path, SMS, focal OTP gap).
- **2026-04-22:** Added spec index + proposed-spec list entry for **`08_seah_outro_and_project_catalog.md`** (outro variants + project catalog).