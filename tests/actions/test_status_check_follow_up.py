"""Status-check follow-up: phone-only when SMS off; OTP when SMS on."""

import pytest

from backend.actions.status_check_follow_up import (
    follow_up_needs_otp_verification,
    get_follow_up_blocker,
    slots_have_valid_phone,
)


@pytest.fixture
def base_slots():
    return {
        "complainant_phone": "9868387387",
        "otp_status": None,
    }


def test_valid_phone_detected(base_slots):
    assert slots_have_valid_phone(base_slots) is True


def test_follow_up_allowed_without_otp_when_sms_disabled(monkeypatch, base_slots):
    monkeypatch.setenv("SMS_ENABLED", "false")
    assert get_follow_up_blocker(base_slots) is None


def test_follow_up_requires_otp_when_sms_enabled(monkeypatch, base_slots):
    monkeypatch.setenv("SMS_ENABLED", "true")
    assert get_follow_up_blocker(base_slots) == "not_verified"
    assert follow_up_needs_otp_verification(base_slots) is True


def test_follow_up_allowed_when_sms_enabled_and_otp_verified(monkeypatch, base_slots):
    monkeypatch.setenv("SMS_ENABLED", "true")
    base_slots["otp_status"] = "verified"
    assert get_follow_up_blocker(base_slots) is None


def test_follow_up_blocked_without_phone(monkeypatch, base_slots):
    monkeypatch.setenv("SMS_ENABLED", "false")
    base_slots["complainant_phone"] = None
    assert get_follow_up_blocker(base_slots) == "no_phone"
