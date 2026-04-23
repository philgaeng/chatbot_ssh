"""SEAH anonymous + sensitive: OTP hop should ask for phone (no silent completion)."""

import asyncio

from backend.orchestrator.form_loop import run_form_turn
from backend.actions.forms.form_otp import ValidateFormOtp


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_otp_form_seah_sensitive_anonymous_prompts_for_phone(domain):
    """
    Sensitive SEAH intake asks complainant_phone in OTP form. Anonymous flow should
    still enter the OTP hop and prompt for phone (same as identified flow) rather than
    silently completing.
    """
    form = ValidateFormOtp()
    session = {
        "user_id": "u",
        "active_loop": "form_otp",
        "requested_slot": None,
        "slots": {
            "language_code": "en",
            "story_main": "seah_intake",
            "grievance_sensitive_issue": True,
            "complainant_phone": None,
            "otp_consent": None,
            "otp_input": None,
            "otp_status": None,
        },
    }
    messages, slot_updates, completed = _run(
        run_form_turn(form=form, session=session, user_input=None, domain=domain)
    )
    assert completed is False
    assert messages, "OTP form should ask for phone when anonymous route has no phone yet"
