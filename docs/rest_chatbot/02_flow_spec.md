# REST Chatbot Flow Spec

## 1) Flow Engine

Primary flow controller:

- `backend/orchestrator/state_machine.py::run_flow_turn(...)`

Supporting components:

- intent derivation + payload mapping in state machine
- form execution in `backend/orchestrator/form_loop.py`
- action invocation in `backend/orchestrator/action_registry.py`

## 2) Input Interpretation Rules

Slash payload priority:

- If request payload exists (or text starts with `/`), payload is treated as intent-driving command.
- Otherwise input is processed as free text.

Main payload-to-intent mapping:

- language: `/set_english`, `/set_nepali`
- main menu: `/new_grievance`, `/road_hazard_grievance`, `/start_status_check`, `/seah_intake`
- legacy payload only (not in menu): `/dust_grievance` → road hazard with Dust pre-selected
- road hazard subtypes: `/road_hazard_subtype_dust`, `/road_hazard_subtype_potholes`, etc.
- submission/review actions: `/submit_details`, `/add_more_details`
- status-check and modify paths: route/modify/cancel payloads

Unknown payloads route to neutral handling (`intent_slot_neutral`).

## 3) Session Reset Behavior

`/introduce...` is a hard reset trigger:

- Clears active flow state and loop metadata
- Resets slots to defaults
- Re-enters `intro` and emits intro prompts

This ensures refresh/reopen always starts from a clean flow.

## 4) Core State Topology

Top-level states:

- `intro`
- `main_menu`
- `form_grievance`
- `form_road_hazard` (CB-09 fast path; `form_dust` alias retained)
- `location_consent`, `location_method`, `map_location` (CB-06 pin path)
- `contact_form`
- `otp_form`
- `grievance_review`
- `status_check_form`
- `modify_grievance_menu`
- `add_more_info_flow`
- `add_missing_info_flow`
- `add_missing_info_otp_flow`
- `done`

SEAH-specific states:

- `form_seah_1`
- `form_seah_2`
- `form_seah_focal_point_1`
- `form_seah_focal_point_2`

## 5) Main User Journeys

### 5.1 New Grievance Flow

High-level path:

1. `intro` -> language set
2. `main_menu` -> `new_grievance`
3. `form_grievance` collects grievance details
4. `contact_form` collects contact/location context
5. `otp_form` verifies phone (unless consent rules skip it)
6. `action_submit_grievance` persists grievance + sends recap
7. `grievance_review` confirms categories/summary
8. `done` with grievance outro

#### Where the AI classification sits in that sequence (DPG-15b, verified 2026-08-19)

This ordering is load-bearing and was traced from the code rather than assumed, because a whole
ticket was drafted on the wrong version of it:

| Step | What happens to the classification |
|---|---|
| 3 · `form_grievance` submits details | The grievance row is written (`pending`), then the classification is **enqueued**. Intake never waits |
| 4 · `contact_form` | runs in the background |
| 5 · `otp_form` | still running — this step includes an **SMS round-trip** |
| 6 · `action_submit_grievance` | The grievance is persisted and **the ticket is dispatched to ticketing** with whatever summary exists at that moment |
| 7 · `grievance_review` | ⏱ **the only wait**: polls up to `CLASSIFICATION_WAIT_SECONDS` (30 s), then renders one of three messages — ready, not ready yet, or will not arrive |

Three consequences worth keeping in view:

- **The wait is already last.** Steps 4–5 give the classification (measured at 14–20.5 s) a long
  head start, so in the normal path step 7 finds it finished.
- ⚠ **Except on the short path.** `complainant_consent is False` makes `form_otp` require **no
  slots at all**, so steps 4–5 can collapse to seconds. The complainant most likely to reach the
  review before the classification does is the one who declined to share contact details.
- **A late classification is not lost.** It lands in the grievance row, and
  `ticketing/tasks/grievance_sync.py` back-fills the summary, categories and location onto the
  ticket **every two minutes** — so the officer sees it, and so does the complainant's later status
  check, whether or not step 7 ever showed it.

### 5.2 Status Check Flow

High-level path:

1. `main_menu` -> `start_status_check`
2. `form_status_check_1` chooses lookup route
3. Optional `otp_form` when phone route is used
4. `form_status_check_2` retrieves/chooses grievance
5. user chooses one of:
   - request follow-up
   - modify grievance
   - skip/outro

Modify branch includes:

- add pictures (frontend upload modal event)
- add more details
- add missing contact information

### 5.3 Road Hazard Fast Path (CB-09)

High-level path:

1. `main_menu` -> `/road_hazard_grievance` (or `/dust_grievance` with Dust pre-selected)
2. `form_road_hazard` — subtype picker (six options), then optional note / **File as is**
3. Preset `grievance_categories` to `Road Hazard - {subtype}` (no LLM classification)
4. `location_consent` -> pin (**CB-06**) or manual location fallback
5. Photo upload prompt after map pin (`open_upload_modal`); **CB-08** EXIF consent on upload
6. `contact_form` — optional contact (skippable)
7. `action_submit_grievance` + ticketing dispatch

### 5.4 Dedicated SEAH Flow

Enabled by `ENABLE_SEAH_DEDICATED_FLOW`.

Path:

1. `main_menu` -> `start_seah_intake`
2. `form_seah_1` intake routing and role logic
3. role-dependent branch:
   - standard seah form (`form_seah_2`)
   - focal-point forms (`form_seah_focal_point_1/2`)
4. contact + otp handling per role/consent rules
5. `action_submit_seah`
6. SEAH-specific outro and `done`

## 6) Form Loop Mechanics

Per-turn form process (`run_form_turn`):

1. Compute `required_slots`
2. Resolve first missing slot
3. Execute extract/validate methods for user input
4. Apply slot updates
5. Ask next slot via ask-action map
6. Mark form complete when no required slots remain

Ask action mapping is centralized and supports:

- generic slot ask actions
- form-specific overrides keyed by `(active_loop, slot)`

## 7) Action Execution Model

Actions are invoked through registry lazy-loading:

- keeps startup light
- avoids circular imports
- normalizes events to slot updates

This includes:

- intro/menu actions
- form ask actions
- submit actions
- status check/modify actions
- review/outro actions

## 8) State Exit and Completion Rules

Expected input type:

- `buttons` in menu-like states (`intro`, `main_menu`)
- `text` in form states with active requested slot

Flow completion:

- terminal state is `done`
- in `done`, selected payloads can still reopen modify-menu operations
- `/introduce...` from `done` resets to intro
