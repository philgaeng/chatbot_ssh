# SPDX-License-Identifier: Apache-2.0

"""Grievance classification lifecycle codes (Option B — see docs/sprints/June5/04-classification-status-spec.md)."""

from __future__ import annotations

ERROR_STATUS = "error"   # the value LLM_services puts in `status` when a call fails

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


def is_failed_classification(values: dict | None) -> bool:
    """
    Did this classification actually fail, whatever the dict claims?

    ⚠ **Measured 2026-08-18 (DPG-15), and the answer was surprising.** With `LLM_BASE_URL` on a
    dead port, `classify_and_summarize_grievance` returns its documented failure dict —
    `status="error"`, empty summary, empty categories — rather than raising. The Celery task's only
    guard was `if not values: raise`, and that dict is **truthy**. So the task took the success
    path: it overwrote `status` with `SUCCESS`, wrote `grievance_classification_status =
    LLM_generated` — a *success* code — and left `error: "Connection error."` sitting beside it,
    contradicted by the status next to it.

    The consequences: `LLM_failed` was unreachable on the one path that most needs it; the retry in
    the task's `except` branch never fired; the complainant waited out the 20-second poll and got an
    empty classification; and the row said the model had produced it. **A grievance mechanism that
    records a failed AI step as a completed one is worse than one with no AI at all**, because the
    failure is now invisible to the officer reviewing the queue.

    Verified end to end against the real database, not reasoned about — grievance `DPG15-c2b3e821`.

    Returns True when there is no result, when the result carries `status="error"`, or when it
    carries any `error` text. The caller raises, which is what puts the existing retry and the
    terminal `LLM_failed` write back in play.
    """
    if not values:
        return True
    if str(values.get("status", "")).strip().lower() == ERROR_STATUS:
        return True
    return bool(values.get("error"))


def is_empty_extraction(values: dict | None) -> bool:
    """
    Did this contact extraction produce anything at all?

    Lives beside `is_failed_classification` because both answer the one question the degraded-mode
    audit asks of every LLM call site: *did this enrichment actually produce something, and what
    happens to the complainant's data if it did not?*

    ⚠ **For contact extraction the answer used to be: their data is erased.** Verified against the
    real database with the endpoint on a dead port — `extract_contact_info` returns its documented
    `{field: ""}` sentinel, the task treated that as a result, and a stored phone number
    (`+9779841234567`) was overwritten with `""`. The complainant had typed it. The model was down.
    The number was gone, and the task reported SUCCESS.

    An empty extraction is never worth persisting: there is no case where writing `""` over a
    stored value is the behaviour anyone wanted. Losing the enrichment is recoverable; losing the
    phone number is how a grievance mechanism loses the ability to contact a complainant.
    """
    if not values:
        return True
    return not any(str(value or "").strip() for value in values.values())


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
