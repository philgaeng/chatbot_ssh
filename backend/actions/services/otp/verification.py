# SPDX-License-Identifier: Apache-2.0

"""Pure OTP code generation and verification helpers.

Reusable, tracker-free helpers extracted from ValidateFormOtp / ActionAskOtpInput
so the form keeps its conversation flow while the OTP computation stays testable
on its own.
"""

from __future__ import annotations

from datetime import datetime, timezone
from random import randint
from typing import Any, Optional


def generate_otp_code(length: int = 6) -> str:
    """Generate a numeric OTP string of ``length`` digits."""
    return "".join(str(randint(0, 9)) for _ in range(length))


def is_valid_otp_format(value: Any) -> bool:
    """True when ``value`` is an all-digit string of length 6."""
    return bool(value and str(value).isdigit() and len(str(value)) == 6)


def otp_matches(input_otp: Any, expected_otp: Any) -> bool:
    """True when a non-empty input OTP equals the expected OTP."""
    return bool(input_otp and expected_otp and input_otp == expected_otp)


def issued_at_stamp() -> str:
    """UTC ISO-8601 stamp for when an OTP was generated.

    Stored beside the code so verification can age it. Kept here rather than in the form so the
    whole lifecycle — generate, stamp, expire, match — is testable without a tracker.
    """
    return datetime.now(timezone.utc).isoformat()


def is_expired(issued_at: Any, *, ttl_seconds: int, now: Optional[datetime] = None) -> bool:
    """True when an OTP issued at ``issued_at`` is older than ``ttl_seconds``.

    ⚠ **Fails CLOSED — an unreadable or missing stamp counts as expired.** The alternative
    (treat unknown as fresh) turns any parse bug into an OTP that never expires, which is the
    control silently not existing. Rejecting costs the complainant one resend; failing open costs
    the property this function was added for.

    ⚠ ``now`` is injected so the tests can drive the boundary instead of sleeping. Do not remove it:
    a TTL test that cannot address the clock ends up asserting the constant rather than the
    behaviour, which is the decorative shape this repository keeps rediscovering.
    """
    if not issued_at:
        return True
    if isinstance(issued_at, datetime):
        stamped = issued_at
    else:
        try:
            stamped = datetime.fromisoformat(str(issued_at))
        except (TypeError, ValueError):
            return True
    if stamped.tzinfo is None:
        stamped = stamped.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return (current - stamped).total_seconds() > ttl_seconds
