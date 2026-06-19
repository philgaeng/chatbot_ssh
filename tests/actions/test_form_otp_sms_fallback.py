"""OTP form: SMS failure must still show code in chat and verification buttons."""

import asyncio
from unittest.mock import patch

import pytest

from backend.actions.forms.form_otp import ActionAskOtpInput
from backend.orchestrator.action_registry import events_to_slot_updates
from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker


def run_async(coro):
    return asyncio.run(coro)


@pytest.fixture
def otp_input_action():
    return ActionAskOtpInput()


@pytest.fixture
def otp_tracker():
    return SessionTracker(
        slots={
            "language_code": "en",
            "complainant_phone": "9868387387",
            "otp_consent": True,
            "otp_status": None,
            "otp_resend_count": 0,
        },
        sender_id="otp-sms-fallback-test",
        latest_message={"text": "/affirm", "intent": {"name": "affirm"}},
        active_loop="form_otp",
        requested_slot="otp_input",
    )


def test_sms_failure_shows_chat_fallback_and_verification_buttons(
    otp_input_action, otp_tracker
):
    dispatcher = CollectingDispatcher()

    with patch(
        "backend.clients.messaging_api.send_sms",
        side_effect=RuntimeError("SMS delivery failed"),
    ):
        events = run_async(
            otp_input_action.run(dispatcher, otp_tracker, {"slots": {}})
        )

    texts = [m.get("text", "") for m in dispatcher.messages]
    assert any("Text messages are not available yet" in t for t in texts)
    assert any("verification code is" in t for t in texts)
    assert any(m.get("buttons") for m in dispatcher.messages)
    slot_updates = events_to_slot_updates(events)
    assert slot_updates.get("otp_number")
