"""Status-check follow-up phone eligibility (single source of truth).

The eligibility rule (no phone on file, or phone not OTP-verified only while SMS
is live) lives here so the chatbot flow and any other caller share one source.
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Optional

from rasa_sdk import Tracker

from backend.config.constants import DEFAULT_VALUES
from backend.config.sms_config import normalize_nepal_mobile, resolve_sms_config

FollowUpBlocker = Literal["no_phone", "not_verified"]


def slots_have_valid_phone(slots: Mapping[str, object]) -> bool:
    phone = slots.get("complainant_phone")
    if not phone:
        return False
    skip = DEFAULT_VALUES.get("SKIP_VALUE", "/skip")
    if str(phone) in (skip, "/skip", "skip"):
        return False
    try:
        normalize_nepal_mobile(str(phone))
        return True
    except ValueError:
        return False


def get_follow_up_blocker(slots: Mapping[str, object]) -> Optional[FollowUpBlocker]:
    """Return why follow-up cannot complete, or None when it may proceed."""
    if not slots_have_valid_phone(slots):
        return "no_phone"
    if resolve_sms_config().enabled and slots.get("otp_status") != "verified":
        return "not_verified"
    return None


def follow_up_needs_otp_verification(slots: Mapping[str, object]) -> bool:
    return get_follow_up_blocker(slots) == "not_verified"


def get_follow_up_phone_issue(
    tracker: Tracker,
    helpers: Any = None,
    *,
    skip_value: str = "/skip",
) -> Optional[FollowUpBlocker]:
    return get_follow_up_blocker(dict(tracker.current_slot_values()))
