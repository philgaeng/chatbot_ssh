"""SEAH anonymous + sensitive: OTP hop would complete silently (regression guard)."""

import asyncio

from backend.config.constants import DEFAULT_VALUES
from backend.orchestrator.form_loop import run_form_turn
from backend.actions.forms.form_otp import ValidateFormOtp


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_otp_form_seah_sensitive_skipped_phone_completes_without_messages(domain):
    """
    Sensitive SEAH intake asks only for complainant_phone in OTP form. Anonymous flow
    prefills phone to skip, so the OTP form has nothing to ask and returns no bot
    messages — the orchestrator must not rely on this hop for anonymous (see
    state_machine form_seah_1 completed -> anonymous branch).
    """
    form = ValidateFormOtp()
    skip = DEFAULT_VALUES["SKIP_VALUE"]
    session = {
        "user_id": "u",
        "active_loop": "form_otp",
        "requested_slot": None,
        "slots": {
            "language_code": "en",
            "story_main": "seah_intake",
            "grievance_sensitive_issue": True,
            "complainant_phone": skip,
            "otp_consent": None,
            "otp_input": None,
            "otp_status": None,
        },
    }
    messages, slot_updates, completed = _run(
        run_form_turn(form=form, session=session, user_input=None, domain=domain)
    )
    assert completed is True
    assert messages == []
