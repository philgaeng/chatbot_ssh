"""Status-check follow-up eligibility (phone + optional OTP when SMS is live)."""

from __future__ import annotations

from typing import Literal, Mapping, Optional

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
