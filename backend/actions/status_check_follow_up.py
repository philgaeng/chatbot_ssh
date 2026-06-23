"""Backward-compatible re-exports.

The status-check follow-up eligibility logic now lives in
``backend.actions.services.status_check.follow_up``. This module re-exports it so
existing imports (orchestrator state machine, tests) keep working.
"""

from backend.actions.services.status_check.follow_up import (
    FollowUpBlocker,
    follow_up_needs_otp_verification,
    get_follow_up_blocker,
    slots_have_valid_phone,
)

__all__ = [
    "FollowUpBlocker",
    "follow_up_needs_otp_verification",
    "get_follow_up_blocker",
    "slots_have_valid_phone",
]
