"""Characterization tests for OTP verification helpers."""

from backend.actions.services.otp import verification


def test_generate_otp_code_default_length_and_digits():
    code = verification.generate_otp_code()
    assert len(code) == 6
    assert code.isdigit()


def test_generate_otp_code_custom_length():
    assert len(verification.generate_otp_code(4)) == 4


def test_is_valid_otp_format_accepts_six_digits():
    assert verification.is_valid_otp_format("123456") is True


def test_is_valid_otp_format_rejects_wrong_length():
    assert verification.is_valid_otp_format("12345") is False
    assert verification.is_valid_otp_format("1234567") is False


def test_is_valid_otp_format_rejects_non_digits():
    assert verification.is_valid_otp_format("12a456") is False
    assert verification.is_valid_otp_format("") is False
    assert verification.is_valid_otp_format(None) is False


def test_otp_matches():
    assert verification.otp_matches("123456", "123456") is True


def test_otp_matches_mismatch():
    assert verification.otp_matches("123456", "654321") is False


def test_otp_matches_rejects_empty():
    assert verification.otp_matches("", "123456") is False
    assert verification.otp_matches("123456", None) is False
    assert verification.otp_matches(None, None) is False
