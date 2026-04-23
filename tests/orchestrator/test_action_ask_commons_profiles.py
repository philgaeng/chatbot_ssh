import asyncio

from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker
from backend.orchestrator.action_registry import invoke_action


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _invoke(action_name, slots, domain):
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(slots=slots, sender_id="ask-profile-test")
    _run(invoke_action(action_name, dispatcher, tracker, domain))
    assert dispatcher.messages, f"Expected message from {action_name}"
    return dispatcher.messages[-1]


def test_grievance_profile_keeps_generic_prompt(domain):
    msg = _invoke(
        "action_ask_complainant_consent",
        {"language_code": "en", "story_main": "new_grievance"},
        domain,
    )
    assert "Would you like to provide your contact information?" in msg["text"]


def test_seah_victim_profile_uses_victim_wording(domain):
    msg = _invoke(
        "action_ask_complainant_consent",
        {
            "language_code": "en",
            "story_main": "seah_intake",
            "seah_victim_survivor_role": "victim_survivor",
        },
        domain,
    )
    assert "confidential SEAH follow-up" in msg["text"]


def test_seah_other_profile_uses_reporting_person_wording(domain):
    msg = _invoke(
        "action_ask_complainant_phone",
        {
            "language_code": "en",
            "story_main": "seah_intake",
            "seah_victim_survivor_role": "not_victim_survivor",
        },
        domain,
    )
    assert "reporting person" in msg["text"]


def test_seah_focal_reporter_profile_uses_reporter_wording(domain):
    msg = _invoke(
        "action_ask_complainant_full_name",
        {
            "language_code": "en",
            "story_main": "seah_intake",
            "seah_victim_survivor_role": "focal_point",
            "seah_focal_stage": "bootstrap_reporter_contact",
            "grievance_sensitive_issue": "skipped",
        },
        domain,
    )
    assert "SEAH focal point" in msg["text"]
    assert "reporting person" in msg["text"]


def test_seah_focal_complainant_profile_uses_affected_person_wording(domain):
    msg = _invoke(
        "action_ask_complainant_location_consent",
        {
            "language_code": "en",
            "story_main": "seah_intake",
            "seah_victim_survivor_role": "focal_point",
            "seah_focal_stage": "complainant_contact",
        },
        domain,
    )
    assert "affected person's grievance location details" in msg["text"]


def test_unknown_seah_role_falls_back_to_generic_prompt(domain):
    msg = _invoke(
        "action_ask_complainant_phone",
        {
            "language_code": "en",
            "story_main": "seah_intake",
            "seah_victim_survivor_role": "unknown_role",
        },
        domain,
    )
    assert "Please enter your contact phone number." in msg["text"]
