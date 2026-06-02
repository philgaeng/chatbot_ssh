# 02 - SEAH Utterances and Buttons

## Objective

Document where SEAH intake **copy and button payloads** live and how they map to forms/actions implemented per `01` and `07`.

This spec is a child of:

- `docs/Refactor specs/April20_seah/00_seah_sensitive_flow_spec.md`

Authoritative routing and slot order:

- `docs/Refactor specs/April20_seah/01_seah_route_and_slots.md`
- `docs/Refactor specs/April20_seah/07_seah_focal_point_flow.md`
- `docs/Refactor specs/April20_seah/08_seah_outro_and_project_catalog.md` (planned **`action_seah_outro`** / project-picker copy keys)

Follow:

- `docs/Refactor specs/AGENT_INSTRUCTIONS.md`

---

## Source-of-truth files (implemented)

| Purpose | Path |
|--------|------|
| Utterances + per-form/per-action keys | `backend/actions/utils/utterance_mapping_rasa.py` |
| Reusable button groups (payloads) | `backend/actions/utils/mapping_buttons.py` |
| Ask actions | `backend/orchestrator/action_registry.py` + `backend/orchestrator/form_loop.py` |

**Note:** `utterance_mapping_rasa.py` nests focal prompts under the key **`form_seah_focal_point`** (shared block for `form_seah_focal_point_1` and `form_seah_focal_point_2` ask actions). Active loops in the orchestrator are still `form_seah_focal_point_1` / `form_seah_focal_point_2`.

---

## Implemented utterance map keys (SEAH-related)

### `form_seah_1`

| Ask action | Purpose |
|------------|---------|
| `action_ask_form_seah_1_sensitive_issues_follow_up` | Intro + identified / anonymous (`BUTTONS_SEAH_IDENTITY_MODE`) |
| `action_ask_form_seah_1_seah_victim_survivor_role` | Victim / not victim / focal (`BUTTONS_SEAH_VICTIM_SURVIVOR_ROLE`) |

### `form_seah_2`

| Ask action | Purpose |
|------------|---------|
| `action_ask_form_seah_2_seah_project_identification` | Project name or `cannot_specify` / `not_adb_project` (`BUTTONS_SEAH_PROJECT_IDENTIFICATION`) |
| `action_ask_form_seah_2_sensitive_issues_new_detail` | Incident summary + add-more loop (`BUTTONS_SKIP`, `BUTTONS_GRIEVANCE_SUBMISSION`) |
| `action_ask_form_seah_2_seah_contact_consent_channel` | Informed contact channel (`BUTTONS_SEAH_CONTACT_CONSENT_CHANNEL`) — **not** asked for anonymous victim path |

### `form_seah_focal_point` block (utterance tree key)

| Ask action | Purpose |
|------------|---------|
| `action_ask_form_seah_focal_point_1_seah_focal_learned_when` | When focal learned of incident (free text) |
| `action_ask_form_seah_focal_point_1_seah_focal_reporter_consent_to_report` | Complainant consent to report (`BUTTONS_SEAH_YES_NO`) |
| `action_ask_form_seah_focal_point_1_sensitive_issues_follow_up` | Complainant identified / anonymous (`BUTTONS_SEAH_IDENTITY_MODE`) |
| `action_ask_form_seah_focal_point_2_seah_project_identification` | Project (`BUTTONS_SEAH_PROJECT_IDENTIFICATION`) |
| `action_ask_form_seah_focal_point_2_sensitive_issues_new_detail` | Same pattern as victim narrative loop |
| `action_ask_form_seah_focal_point_2_seah_focal_*` | Focal risk / mitigation / parties / project risk / reputational risk prompts |
| `action_ask_form_seah_focal_point_2_seah_contact_consent_channel` | Conditional per `ValidateFormSeahFocalPoint2.required_slots` |
| `action_ask_form_seah_focal_point_2_seah_focal_referred_to_support` | Referral to support (`BUTTONS_SEAH_YES_NO`) |
| `action_outro_sensitive_issues` | Placeholder outro / not-ADB messaging (`BUTTONS_CLEAN_WINDOW_OPTIONS`) — **reuse** key name from legacy sensitive flow |

### `form_otp` (shared; SEAH uses subset)

SEAH **sensitive** intake uses **`ValidateFormOtp.required_slots`** → phone only for `seah_intake` when `grievance_sensitive_issue` is true. Utterances under `utterance_mapping_rasa['form_otp']` still apply where `action_ask_otp_consent` / `action_ask_otp_input` run (e.g. other stories). For SEAH phone-only turns, the user sees phone collection prompts from the shared OTP ask path as invoked by the form loop.

### Main menu entry

- English/Nepali main menu buttons use payload **`/seah_intake`** (see `utterance_mapping_rasa.py` `BUTTONS_MAIN_MENU` variants).

---

## Implemented button constants (SEAH-related)

Defined in `mapping_buttons.py` (non-exhaustive; grep `BUTTONS_SEAH` for full set):

| Constant | Typical payloads / use |
|----------|-------------------------|
| `BUTTONS_SEAH_IDENTITY_MODE` | `/identified`, `/anonymous`, `/skip` → normalized in validators |
| `BUTTONS_SEAH_VICTIM_SURVIVOR_ROLE` | `/victim_survivor`, `/not_victim_survivor`, `/focal_point` (focal removed in UI when anonymous) |
| `BUTTONS_SEAH_PROJECT_IDENTIFICATION` | `/cannot_specify`, `/not_adb_project`, skip |
| `BUTTONS_SEAH_CONTACT_CONSENT_CHANNEL` | `/phone`, `/email`, `/both`, `/none` |
| `BUTTONS_SEAH_YES_NO` | Yes/No style answers for focal questions |
| `BUTTONS_GRIEVANCE_SUBMISSION` | `/submit_details`, `/add_more_details`, `/restart` (shared with grievance detail loop) |

Payloads must stay aligned with **`validate_*`** methods in `form_seah_1.py`, `form_seah_2.py`, `form_seah_focal_point.py`.

---

## Content requirements (policy)

- Support **`en`** and **`ne`** in mappings (stakeholder decision: translations maintained in `utterance_mapping_rasa.py`).
- Survivor-centered language; avoid investigative probing in intake copy.
- Non-disclosure paths: `skipped` / skip payloads per validators (`01`).
- SEAH intro utterances currently include **`REPLACE_ME`** markers until final ADB SEAH text is dropped in.
- On-screen submit confirmation for SEAH is partly implemented in **`ActionSubmitSeah`** (reference string); richer outro may extend `action_outro_sensitive_issues` or dedicated action—coordinate with `03`.

---

## Acceptance criteria

1. All **active** SEAH ask actions used in `form_loop.py` resolve utterances in both languages (or intentional English-only where no `ne` key yet—should be avoided for launch).
2. Button payloads for SEAH choices match validator expectations (`01`, `07`).
3. No missing-key runtime errors on happy-path SEAH victim and focal flows.
4. Copy direction matches `00`; unresolved strings flagged **`REPLACE_ME`** in repo.

---

## Test requirements

- Mapping existence tests for keys listed above (extend `05` patterns).
- Smoke: start SEAH in `en` and `ne` from menu (language locked at session start per `00`).

---

## Delivery checklist

- [ ] List new/changed keys in each PR touching `utterance_mapping_rasa.py` or `mapping_buttons.py`.
- [ ] Replace `REPLACE_ME` SEAH strings when content owners supply final text.
- [ ] After project-picker UX (future), add buttons/utterances for that step and update this doc.

---

## Changelog

- **2026-04-21:** Rewrote to match codebase: file paths, `form_seah_*` / focal / OTP key inventory, `mapping_buttons` constants, `REPLACE_ME` and test notes; aligned with `01` / `07`.
- **2026-04-22:** Cross-link **`08`** for future post-submit outro and project-picker utterance keys.
