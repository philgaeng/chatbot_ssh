from backend.actions.utils.mapping_buttons import (
    BUTTONS_SEAH_CONTACT_CONSENT_CHANNEL,
    BUTTONS_SEAH_IDENTITY_MODE,
    BUTTONS_SEAH_PROJECT_IDENTIFICATION,
    BUTTONS_SEAH_VICTIM_SURVIVOR_ROLE,
)
from backend.actions.utils.utterance_mapping_rasa import get_buttons_base, get_utterance_base


def test_seah_utterance_keys_exist_in_both_languages():
    form_name = "form_sensitive_issues"
    action_names = [
        "action_ask_sensitive_issues_follow_up",
        "action_ask_form_sensitive_issues_seah_victim_survivor_role",
        "action_ask_form_sensitive_issues_complainant_phone",
        "action_ask_form_sensitive_issues_seah_project_identification",
        "action_ask_sensitive_issues_new_detail",
        "action_ask_form_sensitive_issues_seah_contact_consent_channel",
        "action_ask_form_sensitive_issues_seah_focal_full_name",
        "action_ask_form_sensitive_issues_seah_focal_otp_input",
        "action_ask_form_sensitive_issues_seah_focal_survivor_risks",
        "action_ask_form_sensitive_issues_seah_focal_mitigation_measures",
        "action_ask_form_sensitive_issues_seah_focal_other_at_risk_parties",
        "action_ask_form_sensitive_issues_seah_focal_project_risk",
        "action_ask_form_sensitive_issues_seah_focal_reputational_risk",
        "action_ask_form_sensitive_issues_seah_focal_learned_when",
        "action_outro_sensitive_issues",
    ]

    for action_name in action_names:
        assert get_utterance_base(form_name, action_name, 1, "en")
        assert get_utterance_base(form_name, action_name, 1, "ne")


def test_seah_button_groups_have_payloads_for_both_languages():
    button_groups = [
        BUTTONS_SEAH_IDENTITY_MODE,
        BUTTONS_SEAH_VICTIM_SURVIVOR_ROLE,
        BUTTONS_SEAH_PROJECT_IDENTIFICATION,
        BUTTONS_SEAH_CONTACT_CONSENT_CHANNEL,
    ]
    for group in button_groups:
        assert group["en"], "English button group should not be empty"
        assert group["ne"], "Nepali button group should not be empty"
        for button in group["en"] + group["ne"]:
            assert button["payload"].startswith("/")


def test_seah_action_button_mappings_resolve():
    form_name = "form_sensitive_issues"
    action_names = [
        "action_ask_sensitive_issues_follow_up",
        "action_ask_form_sensitive_issues_seah_victim_survivor_role",
        "action_ask_form_sensitive_issues_seah_project_identification",
        "action_ask_form_sensitive_issues_seah_contact_consent_channel",
    ]
    for action_name in action_names:
        assert get_buttons_base(form_name, action_name, 1, "en")
        assert get_buttons_base(form_name, action_name, 1, "ne")
