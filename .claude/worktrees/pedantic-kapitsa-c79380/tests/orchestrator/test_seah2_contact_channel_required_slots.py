import asyncio

from backend.actions.forms.form_seah_2 import ValidateFormSeah2
from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker
from backend.config.constants import DEFAULT_VALUES


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_anonymous_route_with_phone_requires_contact_channel(domain):
    skip = DEFAULT_VALUES["SKIP_VALUE"]
    form = ValidateFormSeah2()
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(
        slots={
            "language_code": "en",
            "grievance_sensitive_issue": True,
            "story_main": "seah_intake",
            "sensitive_issues_follow_up": "anonymous",
            "complainant_phone": "9800000000",
            "complainant_email": skip,
        },
        sender_id="seah2-anon-with-phone",
    )
    required = _run(form.required_slots([], dispatcher, tracker, domain))
    assert "seah_contact_consent_channel" in required


def test_anonymous_route_without_contact_skips_contact_channel(domain):
    skip = DEFAULT_VALUES["SKIP_VALUE"]
    form = ValidateFormSeah2()
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(
        slots={
            "language_code": "en",
            "grievance_sensitive_issue": True,
            "story_main": "seah_intake",
            "sensitive_issues_follow_up": "anonymous",
            "complainant_phone": skip,
            "complainant_email": skip,
        },
        sender_id="seah2-anon-no-contact",
    )
    required = _run(form.required_slots([], dispatcher, tracker, domain))
    assert "seah_contact_consent_channel" not in required
