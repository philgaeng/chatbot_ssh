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


# ═════════════════════════════════════════════════════════════════════════════
# D-62 — the OTP expires, and it is erased once the number is verified
#
# Owner's decisions, 2026-08-27. Until then the OTP had NO expiry at all: six digits in a
# conversation slot compared with `==`, so validity was bounded by the session's lifetime
# rather than by a clock — which is not what "one-time password" implies to anyone reading
# it, and four documents reasoned about the control as though a window existed.
# ═════════════════════════════════════════════════════════════════════════════

from datetime import datetime, timedelta, timezone

from backend.config.constants import OTP_VALIDITY_SECONDS


def _stamp(seconds_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


def test_the_window_is_ten_minutes():
    """The owner's number, pinned so a silent change to the default is visible in a diff."""
    assert OTP_VALIDITY_SECONDS == 600


def test_a_fresh_code_is_not_expired():
    assert verification.is_expired(_stamp(0), ttl_seconds=600) is False
    assert verification.is_expired(_stamp(599), ttl_seconds=600) is False


def test_a_code_past_the_window_is_expired():
    assert verification.is_expired(_stamp(601), ttl_seconds=600) is True
    assert verification.is_expired(_stamp(3600), ttl_seconds=600) is True


def test_the_boundary_is_driven_by_an_injected_clock_not_by_sleeping():
    """The window is checked AT its edge, both sides, without a real 10-minute wait.

    ⚠ `now` is injected for exactly this. A TTL test that cannot address the clock ends up
    asserting the constant instead of the behaviour — the decorative shape this repository
    keeps rediscovering (D-42).
    """
    issued = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
    just_inside = issued + timedelta(seconds=600)
    just_outside = issued + timedelta(seconds=601)

    assert verification.is_expired(issued, ttl_seconds=600, now=just_inside) is False
    assert verification.is_expired(issued, ttl_seconds=600, now=just_outside) is True


def test_expiry_fails_closed_on_a_missing_or_unreadable_stamp():
    """No stamp means expired, not fresh.

    Failing open would turn any parse bug — or an OTP issued before this change shipped —
    into a code that never expires, which is the control silently not existing. The cost of
    failing closed is one resend.
    """
    assert verification.is_expired(None, ttl_seconds=600) is True
    assert verification.is_expired("", ttl_seconds=600) is True
    assert verification.is_expired("not-a-timestamp", ttl_seconds=600) is True
    assert verification.is_expired(12345, ttl_seconds=600) is True


def test_a_naive_stamp_is_read_as_utc_rather_than_rejected():
    """Datetimes are UTC by convention here (CLAUDE.md). A naive stamp is not a parse failure."""
    naive = datetime.now() .replace(tzinfo=None)  # noqa: E211 - explicit about the shape under test
    assert verification.is_expired(naive.isoformat(), ttl_seconds=600) is False


def test_a_correct_code_still_fails_once_it_has_expired():
    """The property the window exists for: expiry is checked independently of correctness.

    Asserted here at the helper level; the form applies it BEFORE `otp_matches`, so the digits
    being right does not rescue an old code.
    """
    code = "482915"
    assert verification.otp_matches(code, code) is True
    assert verification.is_expired(_stamp(601), ttl_seconds=600) is True


def test_the_form_checks_expiry_before_it_checks_the_code():
    """Ordering pin. If the match ran first, a stale-but-correct code would verify.

    Source-level: the two calls live in one function and their ORDER is the property, which a
    behavioural test would only catch by constructing a tracker for a path that already has
    several other branches.
    """
    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / "backend/actions/forms/form_otp.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))

    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "validate_otp_input"
    )
    expiry_lines = [
        n.lineno for n in ast.walk(fn)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "is_expired"
    ]
    match_lines = [
        n.lineno for n in ast.walk(fn)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "otp_matches"
    ]

    assert expiry_lines, "validate_otp_input no longer checks is_expired at all"
    assert match_lines, "validate_otp_input no longer checks otp_matches"
    assert min(expiry_lines) < min(match_lines), (
        "expiry must be checked BEFORE the code is matched, or a correct-but-stale code verifies"
    )


def test_the_code_is_erased_from_session_state_once_verified():
    """The second owner decision: the accepted secret does not linger after it has been used.

    Source-level for the same reason as the ordering pin — the success branch returns a dict and
    what matters is which keys it nulls.
    """
    import ast
    from pathlib import Path

    src = Path(__file__).resolve().parents[3] / "backend/actions/forms/form_otp.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef) and n.name == "validate_otp_input"
    )

    # ⚠ Scoped to the dict whose otp_status is literally "verified". The first version of this
    # test matched ANY dict containing an otp_status key, and a mutation proved it decorative:
    # deleting `"otp_number": None` from the verified branch left it green, because the EXPIRED
    # branch clears the same keys and satisfied the assertion on its behalf. Second time this
    # session that testing-the-neighbourhood-not-the-thing has bitten; both times a mutation
    # caught it and nothing else would have.
    verified_dicts = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Dict):
            continue
        for k, v in zip(node.keys, node.values):
            if (
                isinstance(k, ast.Constant)
                and k.value == "otp_status"
                and isinstance(v, ast.Constant)
                and v.value == "verified"
            ):
                verified_dicts.append(node)

    assert verified_dicts, "no dict setting otp_status='verified' found in validate_otp_input"

    cleared = set()
    for node in verified_dicts:
        for k, v in zip(node.keys, node.values):
            if (
                isinstance(k, ast.Constant)
                and isinstance(v, ast.Constant)
                and v.value is None
            ):
                cleared.add(k.value)

    assert "otp_number" in cleared, (
        "the verified branch must set otp_number to None — an accepted OTP left in the slot is a "
        "spent secret kept for nothing"
    )
    assert "otp_issued_at" in cleared, "clear the stamp with the code it belongs to"
