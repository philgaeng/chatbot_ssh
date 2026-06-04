"""Classification status codes — keep in sync with backend/config/classification_status.py."""

from __future__ import annotations

PENDING = "pending"
LLM_GENERATED = "LLM_generated"
LLM_FAILED = "LLM_failed"
LLM_SKIPPED = "LLM_skipped"
COMPLAINANT_CONFIRMED = "complainant_confirmed"
OFFICER_CONFIRMED = "officer_confirmed"

LEGACY_LLM_ERROR = "LLM_error"
LEGACY_SLOT_SKIPPED = "slot_skipped"

OFFICER_VALIDATION_REQUIRED = frozenset({
    LLM_GENERATED,
    LLM_FAILED,
    LLM_SKIPPED,
    LEGACY_LLM_ERROR,
    LEGACY_SLOT_SKIPPED,
})


def normalize_classification_status(code: str | None) -> str | None:
    if not code:
        return code
    if code == LEGACY_SLOT_SKIPPED:
        return LLM_SKIPPED
    if code == LEGACY_LLM_ERROR:
        return LLM_FAILED
    return code


def officer_validation_required(code: str | None) -> bool:
    return normalize_classification_status(code) in OFFICER_VALIDATION_REQUIRED


def classification_validated(code: str | None) -> bool:
    n = normalize_classification_status(code)
    return n in (COMPLAINANT_CONFIRMED, OFFICER_CONFIRMED)
