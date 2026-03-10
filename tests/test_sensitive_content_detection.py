"""
Tests for Agent 9: Sensitive content detection and flow.
- Keyword detector: only sexual_assault/harassment set action_required (sensitive form); land_issues/violence do not.
- helpers_repo: returns confidence and level as string.
"""
import pytest

from backend.shared_functions.keyword_detector import KeywordDetector
from backend.shared_functions.helpers_repo import HelpersRepo
from backend.sensitive_detection_store import set_result, get_result, clear_result


def test_keyword_detector_sexual_assault_sets_action_required():
    """Sensitive content (sexual/gender harassment) should set action_required for routing to sensitive form."""
    detector = KeywordDetector(language_code="en")
    # Use phrasing that matches sexual_assault/harassment at high level without triggering violence
    result = detector.detect_sensitive_content("I experienced unwanted sexual contact and sexual harassment")
    assert result.detected is True
    assert result.action_required is True
    assert result.category in ("sexual_assault", "harassment")


def test_keyword_detector_land_issues_does_not_set_action_required():
    """High priority (land issues) must NOT set action_required; no sensitive form."""
    detector = KeywordDetector(language_code="en")
    result = detector.detect_sensitive_content("I have a land dispute with my neighbor and was forced to leave")
    assert result.detected is True
    assert result.action_required is False
    assert result.category == "land_issues"


def test_keyword_detector_violence_does_not_set_action_required():
    """High priority (violence) must NOT set action_required; no sensitive form."""
    detector = KeywordDetector(language_code="en")
    # Use violence-only phrasing (no "threaten to kill" which matches harassment)
    result = detector.detect_sensitive_content("He hit me and punched me in the face")
    assert result.detected is True
    assert result.action_required is False
    assert result.category == "violence"


def test_helpers_repo_returns_confidence_and_level_string():
    """helpers_repo.detect_sensitive_content must return confidence and level as string."""
    repo = HelpersRepo()
    repo.init_language("en")
    result = repo.detect_sensitive_content("Someone kissed me without my consent", "en")
    assert "confidence" in result
    assert isinstance(result["confidence"], (int, float))
    assert "level" in result
    assert isinstance(result["level"], str)
    assert result["level"] in ("low", "medium", "high", "critical")
    assert "action_required" in result


def test_sensitive_detection_store_roundtrip():
    """Store and retrieve sensitive detection result by session_id and grievance_id."""
    clear_result(session_id="s1", grievance_id=None)
    clear_result(session_id=None, grievance_id="G-1")
    set_result(session_id="s1", grievance_id=None, result={"detected": True, "level": "high", "message": "excerpt", "grievance_sensitive_issue": True})
    r = get_result(session_id="s1", grievance_id=None)
    assert r is not None
    assert r["grievance_sensitive_issue"] is True
    assert r["level"] == "high"
    r2 = get_result(session_id="s1", grievance_id="G-1")
    assert r2 is not None
    assert r2["grievance_sensitive_issue"] is True
    set_result(session_id=None, grievance_id="G-1", result={"detected": False, "grievance_sensitive_issue": False})
    r3 = get_result(session_id=None, grievance_id="G-1")
    assert r3 is not None
    assert r3["grievance_sensitive_issue"] is False
    clear_result(session_id="s1", grievance_id=None)
    clear_result(session_id=None, grievance_id="G-1")
