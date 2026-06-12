"""Status-check follow-up phone eligibility."""

from __future__ import annotations

from typing import Any, Literal, Optional

from rasa_sdk import Tracker


def get_follow_up_phone_issue(
    tracker: Tracker,
    helpers: Any,
    *,
    skip_value: str,
) -> Optional[Literal["no_phone", "not_verified"]]:
    if tracker.get_slot("otp_status") == "verified":
        return None
    complainant_phone = tracker.get_slot("complainant_phone")
    if not complainant_phone or complainant_phone == skip_value:
        return "no_phone"
    if not helpers.is_valid_phone(complainant_phone):
        return "no_phone"
    return "not_verified"
