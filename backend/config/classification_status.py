"""Grievance classification lifecycle codes (Option B — see docs/sprints/June5/04-classification-status-spec.md)."""

from __future__ import annotations

PENDING = "pending"
LLM_GENERATED = "LLM_generated"
LLM_FAILED = "LLM_failed"
LLM_SKIPPED = "LLM_skipped"
COMPLAINANT_CONFIRMED = "complainant_confirmed"
OFFICER_CONFIRMED = "officer_confirmed"

ACTIVE_CODES = frozenset({
    PENDING,
    LLM_GENERATED,
    LLM_FAILED,
    LLM_SKIPPED,
    COMPLAINANT_CONFIRMED,
    OFFICER_CONFIRMED,
})

# Legacy rows / session — treat like active codes where noted
LEGACY_LLM_ERROR = "LLM_error"
LEGACY_SLOT_SKIPPED = "slot_skipped"
LEGACY_REVIEWING = "REVIEWING"

OFFICER_VALIDATION_REQUIRED = frozenset({LLM_GENERATED, LLM_FAILED, LLM_SKIPPED, LEGACY_LLM_ERROR})


def normalize_classification_status(code: str | None) -> str | None:
    if not code:
        return code
    if code == LEGACY_SLOT_SKIPPED:
        return LLM_SKIPPED
    if code == LEGACY_LLM_ERROR:
        return LLM_FAILED
    return code


def officer_validation_required(code: str | None) -> bool:
    normalized = normalize_classification_status(code)
    return normalized in OFFICER_VALIDATION_REQUIRED


def classification_validated(code: str | None) -> bool:
    normalized = normalize_classification_status(code)
    return normalized in (COMPLAINANT_CONFIRMED, OFFICER_CONFIRMED)
