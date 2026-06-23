"""Pure OTP code generation and verification helpers.

Reusable, tracker-free helpers extracted from ValidateFormOtp / ActionAskOtpInput
so the form keeps its conversation flow while the OTP computation stays testable
on its own.
"""

from __future__ import annotations

from random import randint
from typing import Any


def generate_otp_code(length: int = 6) -> str:
    """Generate a numeric OTP string of ``length`` digits."""
    return "".join(str(randint(0, 9)) for _ in range(length))


def is_valid_otp_format(value: Any) -> bool:
    """True when ``value`` is an all-digit string of length 6."""
    return bool(value and str(value).isdigit() and len(str(value)) == 6)


def otp_matches(input_otp: Any, expected_otp: Any) -> bool:
    """True when a non-empty input OTP equals the expected OTP."""
    return bool(input_otp and expected_otp and input_otp == expected_otp)
