# 01 - SEAH Route and Slots

## Objective

Document the **implemented** dedicated SEAH intake route (`story_main: seah_intake`), slot contract, and form sequence—especially the **victim / survivor / non–victim-survivor** path (everything that is **not** the focal-point branch).

This spec is a child of:

- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Follow:

- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Where behavior is defined (important)

- **Transitions** (which form runs next) are implemented in `backend/orchestrator/state_machine.py`, not only in Rasa stories.
- **Which slots are collected** for each active loop is determined at runtime by each form’s `ValidateForm*.required_slots()` (and validators), while `backend/orchestrator/config/domain.yml` `forms:` entries are **minimal placeholders** for training compatibility.
- **Ask actions** for SEAH-specific slots are registered in `backend/orchestrator/action_registry.py` and mapped in `backend/orchestrator/form_loop.py`.

---

## Entry route

- Intent: `start_seah_intake` (menu payload `/seah_intake` in `utterance_mapping_rasa.py`).
- When SEAH is enabled (`_is_seah_enabled()` in `state_machine.py`):
  - `story_main` → `seah_intake`
  - `grievance_sensitive_issue` → `True`
  - Active loop → `form_seah_1`

Dedicated SEAH intake can also be reached from the general grievance path when `grievance_sensitive_issue` is set after `form_grievance`; that path merges into the same `form_seah_1` behavior.

---

## Victim / survivor flow — form order (main SEAH path)

This is the path when `seah_victim_survivor_role` is **not** `focal_point` (includes `victim_survivor` and `not_victim_survivor`).

| Step | Form / module | Purpose |
|------|----------------|--------|
| 1 | `form_seah_1` → `backend/actions/forms/form_seah_1.py` | Sensitive framing, identity mode, role |
| 2a | `form_otp` → `backend/actions/forms/form_otp.py` | **Only if** `sensitive_issues_follow_up == "identified"` — collect **phone** (no OTP in this flow) |
| 2b | *(skip OTP)* | **If** identity is `anonymous` — go straight to contact |
| 3 | `form_contact` → `backend/actions/forms/form_contact.py` | Location (+ identity/contact for identified intakes per rules below) |
| 4 | `form_seah_2` → `backend/actions/forms/form_seah_2.py` | Project, incident narrative, optional informed contact channel |
| 5 | *(submit)* | `action_submit_seah` then terminal `done` |

**Identified reporter:** `form_seah_1` → `form_otp` (phone only) → `form_contact` → `form_seah_2` → submit.

**Anonymous reporter:** `form_seah_1` → `form_contact` (location only) → `form_seah_2` → submit (no `seah_contact_consent_channel` in `form_seah_2`).

---

## Form modules and slots (victim path)

### `form_seah_1` (`ValidateFormSeah1`)

| Slot | Meaning / values |
|------|-------------------|
| `sensitive_issues_follow_up` | `identified`, `anonymous`; skip payload normalized to `anonymous` |
| `seah_victim_survivor_role` | `victim_survivor`, `not_victim_survivor`, `focal_point` (focal hidden when anonymous) |

**Early exit:** If `grievance_sensitive_issue` becomes `False` (e.g. payload `not_sensitive_content`), `required_slots` returns `[]` and the form completes immediately.

**Side effects (anonymous):** Setting anonymous clears identity/OTP-related slots to `skipped` (`complainant_full_name`, `complainant_phone`, `otp_*`, etc.) in `validate_sensitive_issues_follow_up`.

**Focal point:** Choosing `focal_point` leaves the victim doc path; the state machine routes to `form_otp` → … → focal forms (`form_seah_focal_point_*`). See `07_seah_focal_point_flow.md` for that branch.

---

### `form_otp` (`ValidateFormOtp`) — SEAH identified only

For `story_main in (..., "seah_intake")` with `grievance_sensitive_issue is True`, `required_slots` returns **`["complainant_phone"]` only** — no `otp_consent`, `otp_input`, or `otp_status` collection. Phone skip still propagates OTP slots to skipped values (`validate_complainant_phone`).

After `form_otp` completes for `seah_intake`, the state machine always moves to **`form_contact`**.

---

### `form_contact` (`ValidateFormContact`)

Default for SEAH is full **location** chain plus **contact** slots. SEAH-specific overrides in `required_slots`:

| Condition | Required slots |
|-----------|----------------|
| `story_main == "seah_intake"` and `sensitive_issues_follow_up == "anonymous"` | Location slots only (`complainant_location_consent` through `complainant_address`); **no** `complainant_consent`, name, or email |
| `story_main == "seah_intake"` and `seah_focal_stage == "bootstrap_reporter_contact"` | Location + `complainant_consent` + `complainant_full_name` only (focal bootstrap) |
| `story_main == "seah_intake"` and `seah_focal_stage == "complainant_contact"` | `complainant_consent`, name, email chain only |
| Otherwise (identified victim path) | Full location + `complainant_consent`, `complainant_full_name`, `complainant_email_temp`, `complainant_email_confirmed` |

Phone collection for SEAH is **not** in this form; it was moved to `form_otp` for flows that need it.

---

### `form_seah_2` (`ValidateFormSeah2`)

| Slot | Meaning / values |
|------|-------------------|
| `seah_project_identification` | Free text (≥2 chars), or `cannot_specify`, or `not_adb_project`; skip → `cannot_specify` |
| `seah_not_adb_project` | Boolean set alongside project identification |
| `sensitive_issues_new_detail` | Drives `grievance_description` / `grievance_description_status` (free text, `restart`, `add_more_details`, `submit_details`, completion) |
| `seah_contact_consent_channel` | `phone`, `email`, `both`, `none` — **omitted from required slots when anonymous** |

**Early exit:** If `grievance_sensitive_issue` is `False`, `required_slots` returns `[]`.

---

## Slot contract summary (victim path)

| Concept | Slots |
|--------|--------|
| Story / flags | `story_main`, `grievance_sensitive_issue` |
| Identity mode | `sensitive_issues_follow_up` (`identified` / `anonymous`) |
| Role | `seah_victim_survivor_role` |
| Phone (identified) | `complainant_phone` via `form_otp` |
| Location + identity | `complainant_*` per `form_contact` rules |
| Project / branch | `seah_project_identification`, `seah_not_adb_project` |
| Incident text | `grievance_description`, `grievance_description_status`, `sensitive_issues_new_detail` |
| Informed contact channel | `seah_contact_consent_channel` (non-anonymous only) |

Canonical skip value (project standard): **`skipped`** / `slot_skipped` as used in validators and state machine slot resets.

---

## Files (implemented)

| Area | Files |
|------|--------|
| Routing / sequencing | `backend/orchestrator/state_machine.py` |
| Form validation + dynamic slots | `backend/actions/forms/form_seah_1.py`, `form_seah_2.py`, `form_contact.py`, `form_otp.py` |
| Focal-only | `backend/actions/forms/form_seah_focal_point.py` (not victim path) |
| Ask-action wiring | `backend/orchestrator/form_loop.py`, `backend/orchestrator/action_registry.py` |
| Training surface | `backend/orchestrator/config/domain.yml`, `backend/orchestrator/config/source/stories/stories.yml` |

---

## Scope notes (unchanged intent)

**In scope for this doc:** victim/survivor route ordering, slot names, reuse of contact + OTP forms, anonymous vs identified differences.

**Out of scope:** persistence schema, ticketing, focal-point narrative (see focal spec), copy/utterance text.

---

## Acceptance criteria (aligned with current code)

1. User can enter dedicated SEAH route from the main menu when SEAH is enabled.
2. Victim path runs **`form_seah_1` → (`form_otp` if identified) → `form_contact` → `form_seah_2` → submit** (anonymous skips OTP and trims contact / consent-channel steps as above).
3. Focal-point-only steps are **not** in `form_seah_1` / `form_seah_2` for victims; they use separate focal forms after different OTP/contact staging.
4. `not_adb_project` / `cannot_specify` are carried on `seah_project_identification` with `seah_not_adb_project` for the non-ADB branch.
5. Non-SEAH stories remain separate; shared forms apply SEAH rules only when `story_main == "seah_intake"` (and focal stages where set).

---

## Test requirements

- Unit tests for `ValidateFormSeah1`, `ValidateFormSeah2`, `ValidateFormContact.required_slots` under `seah_intake` + anonymous/identified.
- State-machine or integration tests for: identified (OTP form phone-only → contact → SEAH2), anonymous (contact location-only → SEAH2), and `not_adb_project` / narrative loop on `sensitive_issues_new_detail`.
- Regression: `new_grievance` / `grievance_submission` contact → OTP behavior unchanged.

---

## Delivery checklist

- [x] Slot/action doc updated (this file).
- Note for downstream specs (`03`, `04`, `05`): submission reads `grievance_description`, `seah_*`, `complainant_*`, and `story_main == seah_intake`.

---

## Devil’s advocate — risks and edge cases

1. **`not_sensitive_content` exit:** `form_seah_1` can complete with `grievance_sensitive_issue: False` while `sensitive_issues_follow_up` / `seah_victim_survivor_role` may never be set. The state machine still branches on identity/role like a normal completion; the user may be pushed into **contact** without a clear “you’re not in SEAH anymore” story state. Product/engineering should define an explicit terminal or `story_main` reset.

2. **`not_victim_survivor` vs `victim_survivor`:** Both follow the **same** form chain into `form_seah_2`. If the product intent is different handling (e.g. signposting or shorter intake), that is not expressed in routing—only in copy/buttons on the role question.

3. **Anonymous + location:** Anonymous users still complete the **full location** form. For safety-sensitive users, collecting structured geography may feel heavier than “fully anonymous” messaging implies; consider whether minimum location or explicit “decline location” parity is needed.

4. **No OTP on SEAH sensitive path:** Identified SEAH users give a **phone** without OTP verification in this branch. That improves friction but weakens proof-of-possession vs the main grievance OTP path—downstream systems should not assume OTP-verified phone for `seah_intake`.

5. **`seah_contact_consent_channel` after narrative:** The informed-contact channel is collected **after** free-text incident entry in `form_seah_2`. Users may already have embedded contact details in `grievance_description`; channel consent does not erase prior text. Policy and redaction need to match.

6. **`grievance_description_status` coupling:** Incident collection is shared with grievance-style looping (`restart` / `add_more_details` / `submit_details`). Any change to the main grievance form behavior can unintentionally affect SEAH unless tests cover both.

7. **Dual source of truth:** Operators must remember that **`domain.yml` `required_slots` for forms are not authoritative**; the Python validators and `state_machine.py` are. Drift between training YAML and runtime can confuse debugging.

8. **Implementation footguns (worth fixing separately):** `ValidateFormContact.validate_complainant_ward` overwrites the validated ward result; `ActionAskOtpInput` uses a fragile `if not otp_status or otp_status == "resend" and resend_count < 3` condition (operator precedence). Neither blocks the SEAH phone-only path in the common case but they are correctness hazards for other OTP flows.

### Questions to pressure-test the flow

Use these in design review, QA planning, or policy sign-off. They deliberately mirror the risks above and a few adjacent gaps.

**Exit, consent, and framing**

- If someone says the content is **not sensitive**, where should they land next—main menu, grievance intake, or a dedicated “not SEAH” message—and who owns that decision?
MAIN MENU
- Does the first SEAH screen make it obvious that choosing **anonymous** still leads to **structured location** questions, and is that legally/safely defensible?
YES 
- Is **“anonymous”** in copy aligned with what we persist (location, narrative, optional channel)—i.e. are we over-promising anonymity?
IT WAS VETTED

**Role and routing**

- Should **“No, I am not the victim/survivor”** trigger the same depth of intake as **“Yes”**? If yes, why; if no, what should differ (routing, copy, caseworker queue)?
TBD  
- When the user is **not** the victim, do we need explicit consent that they may be reporting **on behalf of** someone else, or is the current slot set enough?
WILL BW VETTED LATER

**Identity, phone, and OTP**

- For **identified** SEAH intake, is **phone without OTP** acceptable to legal/compliance and to whoever triages cases—or should SEAH match the main grievance bar?
OTP is not mandatory because people may borrow a phone
- If the phone is wrong or shared (family phone, employer), what is the **fallback** for follow-up, and does the flow make that clear before submit?
THE COMPLAINANT SHOULD BE DIRECTED TO CONTACT THE CLOSEST SEAH CENTER - WE SHOULD CREATE A MOCK OUTRO FOR THAT CASE

**Location and contact**

- Is **full province → address** the minimum we need for SEAH operations, or could a lighter path exist for high-risk users?
SKIPPING IS ALWAYS POSSIBLE
- For **anonymous** users who decline or skip parts of location, do downstream reports still meet **minimum actionable** standards for the SEAH team?
TBD 

**Narrative vs channel consent**

- **Order:** Why is **informed contact channel** asked **after** the incident narrative? Would reversing order reduce accidental self-doxxing in free text?
- If `grievance_description` already contains a phone or email, does **`seah_contact_consent_channel`** still mean anything in audits—how do we document “consent scope”?
TBD

**Branches and data quality**

- For **“Not an ADB project”** / **“Cannot specify”**, do analytics and ops know how to treat cases differently—and does the bot copy set that expectation?
- Who consumes **`seah_not_adb_project`** vs raw `seah_project_identification`, and can they diverge in confusing ways?

**Direction:** structured project catalog + location-driven buttons + optional government-agency table — **all implementation questions and decisions** live in **`08_seah_outro_and_project_catalog.md`** (Part A).


**Shared machinery and maintenance**

- If a developer edits **`domain.yml` forms** without touching **Python `required_slots`**, how will CI or review catch **training/runtime drift**?
LETS INVESTIGATE I THINK THE YML FORMS ARE LEGACY DOCS - WHAT DO YOU RECOMMEND FOR DOCUMENTATION OF THE FLOWS?
- Who signs off when **`sensitive_issues_new_detail`** behavior changes in the main grievance flow so SEAH regression is guaranteed?
I NEED MORE DETAILS TO ANSWER

**Security and abuse**

- Could someone use the **SEAH route** to flood or test the system with minimal friction (e.g. anonymous + location skips where allowed)? What rate limits or abuse signals apply specifically to `seah_intake`?
LEts define this during a security audit later

### Devil’s advocate — round 2 (after round-1 decisions)

New angles so the same flow is stressed from **operational**, **technical**, and **second-order** viewpoints. Add answers inline or in a decision log when ready.

**1. Session lifecycle and “half a report”**

- What happens if the user **drops off** after phone, after location, or after narrative—do partials create false workload, duplicate follow-ups, or privacy retention issues?
when the sessions closes, the data is cleared isnt it. only submitted sessions go through
- On **resume**, can they land in the wrong form state (e.g. OTP slot semantics from another story) without a hard reset of `story_main` + active loop?
No resume option as someone else may use the phone

**2. Language, literacy, and modality**

- Is the flow equally safe when the user **switches language** mid-intake (slot values vs utterances)?
the flow is only available in onr language - we are billigual for testing only
- Heavy reliance on **buttons** for legal-ish choices: what is the path for users who only type (accessibility, broken clients)?
accessibilty path to follow with voice intake

**3. Coercion and safety in real time**

- Nothing in the slot model detects **coerced** answers (someone beside the user). Should any step (e.g. channel consent) include slower friction or “safe word” patterns—or is that explicitly out of scope for v1?
this is for the seah investigator to find

**4. Duplication and cross-channel noise**

- If the same incident is filed **here and offline** (hotline, embassy, employer), do caseworkers have **dedup** signals, or does the bot always mint a new case?
this is for the investigator to document

**5. Evidence and limits of chat**

- The bot collects **text + structured fields** only. Are expectations set that **witnesses, documents, dates of incidents, or perpetrator identity** may still be required later—outside the bot?
YES the investigation is done outside of the bot

**6. Email / domain validation vs vulnerable users**

- Shared **email validation** (e.g. Nepal-domain heuristics) may block or confuse legitimate reporters using foreign or organizational mail. Is SEAH intake explicitly OK with that UX cost?
I can easily add any rmail finishing by .org


**7. Correlation of identifiers**

- **Phone** (early for identified) + **email** + **location** + **narrative** in one session increases **re-identification risk** if any subsystem leaks. Is the data-classification / access review written for that **combined** bundle, not field-by-field?
TBD

**8. Feature flag and version skew**

- If **`_is_seah_enabled()`** flips off during an outage, do users mid-flow get a **clean** fallback message, or silent routing to legacy paths?
- Deploy **order** (actions vs model vs state machine): can a partial deploy break SEAH without tripping generic health checks?
NA

**9. Implementation debt that becomes SEAH-specific under load**

- **`validate_complainant_ward`** logic and **`ActionAskOtpInput`** precedence: under retries or unusual `otp_status`, could a **non-SEAH** bug block or spam users who entered SEAH through a shared code path?
WILL BE TESTED

**10. Post-submit reality**

- After **`action_submit_seah`**, is the user told **concrete** next steps (SLA, reference ID, “we may not contact you if channel is none”)—and does that match what ops actually do?

**Direction:** distinct outro copy per role/contact profile — **cases, slot rules, and implementation checklist** in **`08_seah_outro_and_project_catalog.md`** (Part B).

### Round 2 — short question list (workshop prompts)

- Who owns **partial submissions** end-to-end?
- **Language switch:** tested on every SEAH boundary?
- **Button-only** choices: compliant with your accessibility standard?
- **Deduplication** vs new case: business rule documented?
- **Re-identification** risk register updated for the full slot bundle?
- **Flag-off / deploy skew:** playbooks written?
- **Submit UX:** reference ID + expectations always shown?

---

## Changelog

- **2026-04-21:** Rewrote to match implemented victim flow (`form_seah_1` → `form_otp` / `form_contact` → `form_seah_2`); devil’s advocate review; added “Questions to pressure-test the flow” (product, compliance, routing, consent ordering, ops, maintenance, abuse).
- **2026-04-21:** Devil’s advocate **round 2**: session/resume, language/modality, coercion, dedup, evidence limits, email UX, re-ID bundle risk, feature-flag/deploy skew, shared-code footguns under load, post-submit expectations.
- **2026-04-22:** Point project-catalog + post-submit outro work to new spec **`08_seah_outro_and_project_catalog.md`** (replaced long inline notes in devil’s advocate).
