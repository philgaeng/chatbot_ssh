# 01 — SEAH Intake Flow (as-built)

**Status:** As-built, July 2026 — verified against code on `integration/seah-claude`.
**Sources consolidated:** `docs/sprints/archive/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`, `01_seah_route_and_slots.md`, `04_seah_otp_and_validation.md`, `07_seah_focal_point_flow.md`, `08_seah_outro_and_project_catalog.md`; `docs/sprints/archive/Refactor specs/May5_seah/04_action_ask_commons_flow_profiles.md`, `09_updated_seah_workflow.md`; `docs/sprints/archive/Refactor specs/March 5/14_sensible_content_detection_and_flow..md`.
Where those specs conflict with code, this doc describes **code**. Items not implemented are marked **Planned**.

Storage/privacy model is in [02_vault_privacy_and_reveal.md](02_vault_privacy_and_reveal.md). Decisions and rationale are in [03_seah_decision_log.md](03_seah_decision_log.md).

---

## 1. Principles (survivor-centered, locked)

1. **Mandatory but skippable.** Every intake step is asked, but every disclosure-type field carries a non-disclosing option (canonical skip value `skipped` / `SKIP_VALUE`), except the fields explicitly marked mandatory below (focal reporter phone, focal incident summary).
2. **No probing.** The chatbot collects only initial-assessment fields; investigation (witnesses, perpetrator identity, exact dates, dedup) happens outside the bot.
3. **No complainant-facing SMS** on the SEAH path — `ActionSubmitSeah` sends no SMS and no OTP SMS is triggered (phone is collected without verification, §5).
4. **No end-user status check or modification** for SEAH cases (policy; see gap note in §10).
5. **One reference:** the canonical `grievance_id` is shown on-screen after submit and is the only case reference (legacy `seah_public_ref` removed in phase 2).
6. **Confidential handling end-to-end:** `case_sensitivity = 'seah'`, narrative goes to the PII vault, SEAH tickets visible only to SEAH roles (doc 02).

---

## 2. Entry routes

| Entry | Mechanism |
|-------|-----------|
| Main menu | Payload `/seah_intake` → intent `start_seah_intake`. Gated by `_is_seah_enabled()` (`ENABLE_SEAH_DEDICATED_FLOW`) in `backend/orchestrator/state_machine.py`. `action_start_seah_intake` mints/reuses `grievance_id` + `complainant_id`, sets `story_main = seah_intake`, `grievance_sensitive_issue = True`, opens `form_seah_1`. |
| Sensitive-content detection from general grievance | When `form_grievance` completes with `grievance_sensitive_issue = True`, the state machine routes into `form_seah_1` (merge path). Detection policy in §9. |

`domain.yml` form entries are training placeholders only; **runtime slot lists come from each `ValidateForm*.required_slots()`** and sequencing from `state_machine.py`.

---

## 3. Form sequence by path

`form_seah_1` asks **role first**, then anonymity (order changed from the April20 spec):

1. `seah_victim_survivor_role` — `victim_survivor` | `not_victim_survivor` | `focal_point` (buttons `BUTTONS_SEAH_VICTIM_SURVIVOR_ROLE`).
2. Branch-specific follow-ups (below).

Answering `not_sensitive_content` at the anonymity question sets `grievance_sensitive_issue = False`, all SEAH forms return `required_slots = []`, and the flow exits (decided: user lands back at main menu).

### 3.1 Victim/survivor path (`victim_survivor`)

```
form_seah_1  (role → anonymity)
→ form_otp   (phone only, optional — both anonymous and identified; no OTP)
→ form_contact (location: province → district → municipality only; + consent/name/email if identified)
→ form_seah_2 (project link → incident narrative → contact channel if reachable)
→ action_submit_seah → action_seah_outro → done
```

- `sensitive_issues_follow_up` = `identified` | `anonymous` (skip ⇒ `anonymous`). Sets `seah_anonymous_route` (bool). `identified` prefills `complainant_consent = True`.
- **Anonymous** route clears `complainant_full_name` to skipped but **still offers the phone question** via `form_otp` (user can stay anonymous yet leave a callback number). Contact form then collects **municipality-level location only** (no ward/village/address, no name/email).
- **Identified** route: phone (optional) via `form_otp`, then municipality-level location + `complainant_consent` + `complainant_full_name` + email chain (`complainant_email_temp`/`_confirmed`) in `form_contact`.
- **Planned / deviation:** the May5 workflow doc asked for an email question in the anonymous flow; as-built, anonymous collects phone (optional) but **no email**.

### 3.2 Witness / other-person path (`not_victim_survivor`)

Inside `form_seah_1`:

1. `seah_witness_victim_consent_to_file` — "Did the victim-survivor agree that you file this complaint?" (`yes`/`no`).
2. `yes` → anonymity question, then the **same** chain as the victim path (OTP-phone → contact → `form_seah_2` → submit). Contact details collected are the **reporter's own** (ask-profile wording, §6).
3. `no` → `seah_witness_immediate_danger` (`yes`/`no`). Answering it triggers the **witness exit without filing**: `seah_witness_exit_without_filing = True`, the bot utters a thank-you plus support-service referral and the state machine ends the session (`done`) with **no submission**.
   - Support message (`backend/actions/services/seah/witness_exit.py`): if any location slot is known, real support centres are resolved from `seah_service_providers` (recommendation + details blocks); otherwise a fallback pointing to `https://nwchelpline.gov.np`.
   - **Note (as-built):** both `yes` and `no` on immediate danger currently produce the same support-referral exit; there is no separate urgent-safety branch (**Planned/TBD**, decision G-27 in the log).

### 3.3 Focal-point path (`focal_point`)

Choosing focal point forces `sensitive_issues_follow_up = identified`, `seah_anonymous_route = False` (no anonymity question), and stages via `seah_focal_stage`:

```
form_seah_1 (role = focal_point)
→ form_contact  stage=bootstrap_reporter_contact  (reporter full name ONLY — name before phone)
→ form_otp      stage=bootstrap_reporter_otp      (reporter phone — MANDATORY, skip rejected)
→ form_seah_focal_point_1  stage=focal_point_1    (seah_focal_learned_when only)
→ form_seah_focal_point_2  stage=focal_point_2    (project, summary, risk block, referred-to-support)
→ action_submit_seah → action_seah_outro → done
```

Per the May5 workflow update, the focal flow **no longer collects complainant (victim) profiling fields**: complainant consent-to-report, complainant name/phone/email, complainant location, and the follow-up contact-channel question were all **removed from the focal path**. Validators for `seah_focal_reporter_consent_to_report` and complainant identity remain in `form_seah_focal_point.py` for compatibility, and `action_prepare_seah_focal_complainant_capture` (copies reporter data into `seah_focal_phone`/`seah_focal_full_name`/`seah_focal_city`/`seah_focal_village` and clears shared slots) is still registered, but neither is on the active sequence; the `complainant_contact`/`complainant_otp` stages are dead branches.

`ValidateFormSeahFocalPoint1`: `seah_focal_learned_when` is a **button enum** — `learned_within_24h` | `learned_24_to_72h` | `learned_3_to_7d` | `learned_over_7d` | `skipped` (the earlier "free text date" decision was superseded).

`ValidateFormSeahFocalPoint2.required_slots` (always, including `not_adb_project`):

| Slot | Type / values |
|------|----------------|
| `seah_project_identification` | see §4 |
| `sensitive_issues_new_detail` | incident summary — **mandatory, min 8 chars, no Skip button** |
| `seah_focal_survivor_risks` | multi-select: retaliation/intimidation/job threat, personal safety, trauma, free text; **Done** (`/selection_done`) ends selection, **Skip** replaces "None" |
| `seah_focal_mitigation_measures` | multi-select: referral to support services, police/legal information, free text |
| `seah_focal_other_at_risk_parties` | multi-select: witnesses, family members, project workers, community members, free text |
| `seah_focal_project_risk` | free text or skip |
| `seah_focal_referred_to_support` | `yes` / `no` / skip — "did you refer the complainant to proper support?" |

Multi-select values are stored `" | "`-joined; accumulators live in `<slot>_selected`. `seah_focal_reputational_risk` has a validator but is **not** in the required list (question dropped from the active flow). **Planned:** focal roster lookup + SMS OTP verification (`seah_focal_lookup_status` / `seah_focal_verification_status` are pass-through payload fields only; no roster match is wired).

---

## 4. Project identification

`backend/actions/services/seah/project_identification.py`, shared by `form_seah_2` and `form_seah_focal_point_2`:

- **Current ask (as-built):** static yes/no buttons — "Is the alleged perpetrator employed by an ADB project?" `yes`/`no` normalize onto `seah_project_identification` with `seah_not_adb_project = (answer == no)` and `project_uuid = None`.
- **Retained validator capabilities:** `/project_pick{"id":"<uuid>"}` payloads resolve against the `projects` table (`list_active_projects_for_geo` by province/district, fallback global list, `inactive_at IS NULL`), setting `project_uuid`, display name (en/ne), and `seah_not_adb_project` from the row's `adb` flag; free text (≥ 2 chars) and `cannot_specify` / `not_adb_project` also accepted; skip ⇒ `cannot_specify`. The dynamic project-picker buttons are implemented but **commented out** in the ask actions ("kept for quick restore").
- `not_adb_project` does **not** short-circuit the flow — submission still runs `action_submit_seah`.
- `projects` table is created by app DDL in `backend/services/database_services/base_manager.py` (no Alembic migration owns it yet — **tech debt**).

---

## 5. Phone collection — no-OTP rule

`ValidateFormOtp.required_slots` (`backend/actions/forms/form_otp.py`): when `story_main ∈ {new_grievance, grievance_submission, seah_intake}` **and** `grievance_sensitive_issue is True`, required slots are **`["complainant_phone"]` only** — no `otp_consent`, `otp_input`, `otp_status`, hence **no OTP SMS** anywhere on the SEAH path.

- Rationale (stakeholder): survivors may be borrowing a phone; proof-of-possession must not gate intake. Downstream systems must **not** assume the SEAH phone is verified.
- Phone skip propagates skip values to all OTP slots so the form completes.
- **Focal exception:** at `seah_focal_stage = bootstrap_reporter_otp`, skip is rejected with "As a SEAH focal point, your phone number is required and cannot be skipped."
- Every phone/consent update recomputes `seah_contact_provided` and upserts the active **party payload** (§7 of doc 02): `party_contacts[role]` + `party_<role>` slots via `backend/actions/services/seah/party_payload.py` (roles: `victim_survivor`, `witness`, `relative`, `seah_focal_point`, `other_reporter`; chatbot currently sets `victim_survivor`, `relative` for not-victim, `seah_focal_point`).

## 5.1 Contact-channel consent

`seah_contact_consent_channel` (`phone` | `email` | `both` | `none`) is asked in `form_seah_2` **whenever at least one of phone/email holds a non-skipped value** — including the anonymous route when a phone was volunteered. Buttons are filtered to the channels actually available (`backend/actions/services/seah/contact_channels.py`). Not asked when no contact path exists (shorter flow, per decision). Not asked in the focal flow (complainant contact fields removed).

Slot split (from the April20 08 spec, **implemented**):

| Slot | Meaning |
|------|---------|
| `seah_anonymous_route` | bool, routing-only mirror of `sensitive_issues_follow_up == anonymous` |
| `seah_contact_provided` | bool — true iff validated phone or email exists |

---

## 6. Ask profiles (prompt wording)

`ProfileAwareAskAction` in `backend/actions/action_ask_commons.py` (**implemented** from May5 04):

- `_get_ask_profile(tracker)` → `grievance` | `seah-victim` | `seah-other` | `seah-focal` derived from `story_main` + `seah_victim_survivor_role` (no dedicated profile slot).
- `_get_focal_prompt_phase` → `reporter` (stages `bootstrap_reporter_*`, `focal_point_1`) vs `complainant` (legacy complainant stages, `focal_point_2`).
- Profile utterances live under `profile_utterances` keys in `utterance_mapping_rasa.py` (en + ne), falling back to the generic key. `seah-other` prompts clarify the details are the **reporter's**, not the victim's; `seah-focal` reporter-phase prompts name the focal person and suppress the skip buttons for the mandatory phone.

---

## 7. Submit and outro

### Submit (`ActionSubmitSeah`, `backend/actions/action_submit_grievance.py`)

- Collects grievance data + all `seah_*` slots, `seah_anonymous_route`, `seah_contact_provided`, `project_uuid`, `seah_contact_point_id`, party payloads → `db_manager.submit_seah_to_db(...)` (canonical tables + vault; details in doc 02).
- Fires the chatbot → ticketing webhook (`dispatch_grievance_from_tracker`, `is_seah=True`, `priority="HIGH"`, fire-and-forget).
- On-screen confirmation (en/ne): "Your confidential SEAH report has been filed successfully." + "Your reference number is **{grievance_id}**." + follow-up line (focal variant echoes the focal phone). Emits `grievance_filed` JSON event for the webchat filed-banner.
- **No SMS, no email** to the complainant.

### Outro (`ActionSeahOutro`, `backend/actions/action_outro.py`)

Chained by the state machine after every successful SEAH submit (`_append_seah_outro_after_submit_if_applicable`; requires `grievance_id`).

As-built variant logic (a simplification of the O1–O5 matrix from the April20 08 spec):

| Case | Behavior |
|------|----------|
| Focal point | Single focal acknowledgement utterance (index 7) — includes "refer the complainant to proper support" guidance. |
| All other roles | Thank-you utterance depends on `seah_contact_provided` (idx 5 contact / idx 4 no contact), then the **nearest support centre block**: first match from `seah_service_providers` (location-code aware), fallback `seah_contact_points` scored lookup (project_uuid > ward > municipality > district > province); matched id persisted to `seah_contact_point_id`. |

The full five-variant resolver (`resolve_seah_outro_variant` → `focal_default`, `victim_limited_contact`, `victim_contact_ok`, `not_victim_anonymous`, `not_victim_identified`) exists in `backend/actions/services/seah/outro.py` with the canonical predicates (anonymous / no contact / consent false / channel ∈ {none, email} ⇒ limited-contact) but the streamlined `ActionSeahOutro` currently keys copy off focal vs contact-provided only. Post-submit buttons: **Close browser** + **File another SEAH report** (`seah_post_submit_buttons`); the reference number is not repeated in the outro.

### Support-centre reference data

- `seah_service_providers` (migration `pub009`): province/district/municipality (+codes), ward, `seah_center_name`, address, phone, opening days/hours, `is_active`, `sort_order`. Lookup + formatting helpers in `backend/shared_functions/seah_service_providers.py` and `backend/actions/services/seah/contact_points.py`; used in the outro, the witness exit, and the sensitive-detection referral utterances.
- `seah_contact_points`: older app-DDL table (created/seeded in `base_manager.py`), retained as outro fallback. **Tech debt:** two overlapping directories; neither `seah_contact_points` nor `projects` is migration-owned.

---

## 8. Persistent close controls (webchat UI contract)

From the May5 09 frontend contract, **implemented** in `channels/REST_webchat/`:

1. The orchestrator's `POST /message` response carries `close_controls_mode`: `"browser"` when `story_main == seah_intake` **or** `grievance_sensitive_issue` is truthy, else `"session"` (`backend/orchestrator/main.py`).
2. The webchat renders **persistent** Close controls in the bottom composer area (above the text input): Close Browser (`/nav_close_browser_tab`, browser mode) or Close Session (`/nav_clear`, session mode) — `updateCloseControlsVisibility()` in `app.js`.
3. Message-level close quick-replies are filtered by mode (`filterCloseQuickReplies`) to avoid duplicate button sets.
4. Payload handlers stay unchanged: `/nav_close_browser_tab` → close tab, `/nav_clear` → clear session (`modules/eventHandlers.js`). In browser mode, "file another" maps to `/seah_intake`.
5. **Safety note (unchanged):** Close Browser is *not* guaranteed erasure — conversation history may be visible on reopen; Close Session remains the reliable in-flow termination. There is **no resume** for SEAH sessions (shared-phone risk) and no 30s auto-close timer (frontend-optional, not implemented).

---

## 9. Sensitive-content detection (two-bucket policy)

Detection decides when a **general grievance** merges into the SEAH flow (§2). Policy from March5 14, **implemented**:

- **Bucket 1 — sensitive content** (gender/sexual harassment, `sexual_assault`, `harassment`): sets `grievance_sensitive_issue = True` → routes into `form_seah_1`.
- **Bucket 2 — high priority** (`land_issues`, `violence`): flagged for ADB follow-up (`grievance_high_priority`) but stays in the **normal** flow; never sets `grievance_sensitive_issue`.

Mechanics:

- Background LLM task `detect_sensitive_content_task` (`backend/task_queue/registered_tasks.py`) fires on each free-text grievance addition (`backend/actions/grievance_intake/sensitive.py`); result persisted so the orchestrator can read it on Submit details.
- Keyword fallback: `backend/shared_functions/keyword_detector.py` — `SENSITIVE_CONTENT_CATEGORIES = (sexual_assault, harassment)`, `HIGH_PRIORITY_CATEGORIES = (land_issues, violence)`; `action_required` only for sensitive bucket at CRITICAL/HIGH.
- Slot mapping + referral utterances: `backend/actions/services/seah/sensitive_detection.py` (referral utterances 1–2 are location-aware via `seah_service_providers`).
- The legacy `form_sensitive_issues` module is **superseded**: detection routes into the dedicated `form_seah_1`, not a separate short follow-up form.

---

## 10. Policy guards and known gaps

| Guard | As-built status |
|-------|------------------|
| No complainant SMS on SEAH submit | ✅ `ActionSubmitSeah` sends none; no OTP SMS possible on the branch (§5). |
| No SEAH in end-user status check | ⚠️ Policy decided (fully disabled), but `get_grievance_by_complainant_phone` (`grievance_manager.py`) has **no `case_sensitivity` filter** — a SEAH case filed with a phone number could surface in phone-based status check. **Gap — needs a `case_sensitivity != 'seah'` guard.** |
| No end-user modify flow for SEAH | ✅ No SEAH path enters the review/modify loop; SEAH submit goes straight to `done`. |
| SEAH visibility in ticketing | ✅ Non-SEAH roles get `WHERE is_seah = FALSE` at query level (`ticketing/api/routers/tickets.py`). |
| Feature flag | ✅ `ENABLE_SEAH_DEDICATED_FLOW` / `_is_seah_enabled()`; disabled flag returns a polite refusal instead of entering the flow. |
| Languages | en + ne, locked at flow start (same as all flows); all SEAH utterances/buttons live in `utterance_mapping_rasa.py` / `mapping_buttons.py`. |
| File uploads in SEAH intake | Not offered inside SEAH forms (TBD from stakeholder log). |
