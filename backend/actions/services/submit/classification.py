"""Classification status resolution on grievance submit."""

from __future__ import annotations

from typing import Any, Dict

from rasa_sdk import Tracker

from backend.config.classification_status import (
    COMPLAINANT_CONFIRMED,
    LLM_SKIPPED,
    normalize_classification_status,
)


def classification_status_for_submit(
    tracker: Tracker,
    grievance_data: Dict[str, Any],
    *,
    db_manager: Any,
    skip_value: str,
    not_provided: str,
    llm_classification_enabled: bool,
    grievance_classification_status: Dict[str, str],
) -> str:
    slot_status = tracker.get_slot("grievance_classification_status")
    cm = grievance_classification_status.get("complainant_confirmed", COMPLAINANT_CONFIRMED)
    if slot_status == cm:
        return COMPLAINANT_CONFIRMED
    cat_st = tracker.get_slot("grievance_categories_status")
    sum_st = tracker.get_slot("grievance_summary_status")
    if cat_st == cm and sum_st == cm:
        return COMPLAINANT_CONFIRMED
    normalized = normalize_classification_status(slot_status)
    if normalized and normalized not in (skip_value, not_provided, "pending"):
        return normalized
    if not llm_classification_enabled:
        return LLM_SKIPPED
    from backend.actions.forms.form_road_hazard import is_road_hazard_intake

    if is_road_hazard_intake(tracker):
        return LLM_SKIPPED
    gid = tracker.get_slot("grievance_id")
    if gid:
        row = db_manager.get_grievance_by_id(gid) or {}
        db_status = normalize_classification_status(row.get("grievance_classification_status"))
        if db_status:
            return db_status
    return "pending"
