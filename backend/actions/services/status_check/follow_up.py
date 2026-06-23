"""Status-check follow-up phone eligibility.

The eligibility rule (no phone on file, or phone not OTP-verified only while SMS
is live) is owned by ``backend.actions.status_check_follow_up`` so the chatbot
flow and any other caller share a single source of truth.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from rasa_sdk import Tracker

from backend.actions.status_check_follow_up import get_follow_up_blocker


def get_follow_up_phone_issue(
    tracker: Tracker,
    helpers: Any = None,
    *,
    skip_value: str = "/skip",
) -> Optional[Literal["no_phone", "not_verified"]]:
    return get_follow_up_blocker(dict(tracker.current_slot_values()))
