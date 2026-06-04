"""Unit tests for TP-14 classification status helpers."""

from ticketing.constants.classification import (
    COMPLAINANT_CONFIRMED,
    LLM_FAILED,
    LLM_GENERATED,
    LLM_SKIPPED,
    OFFICER_CONFIRMED,
    classification_validated,
    normalize_classification_status,
    officer_validation_required,
)


def test_normalize_legacy_codes():
    assert normalize_classification_status("slot_skipped") == LLM_SKIPPED
    assert normalize_classification_status("LLM_error") == LLM_FAILED


def test_officer_validation_required():
    assert officer_validation_required(LLM_GENERATED) is True
    assert officer_validation_required(LLM_FAILED) is True
    assert officer_validation_required(LLM_SKIPPED) is True
    assert officer_validation_required(COMPLAINANT_CONFIRMED) is False
    assert officer_validation_required(OFFICER_CONFIRMED) is False
    assert officer_validation_required("pending") is False


def test_classification_validated():
    assert classification_validated(COMPLAINANT_CONFIRMED) is True
    assert classification_validated(OFFICER_CONFIRMED) is True
    assert classification_validated(LLM_GENERATED) is False
