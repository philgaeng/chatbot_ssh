"""Shared grievance detail submit logic (standard + dust fast path)."""

from __future__ import annotations

from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseFormValidationAction
from backend.actions.grievance_intake.classification import trigger_async_classification
from backend.actions.grievance_intake.sensitive import get_sensitive_issue_slots_on_submit
from backend.actions.utils.ticketing_dispatch import dispatch_grievance_from_tracker


async def complete_grievance_details_intake(
    form: BaseFormValidationAction,
    tracker: Tracker,
    dispatcher: CollectingDispatcher,
    domain: DomainDict,
    grievance_description: str,
) -> Dict[Text, Any]:
    """Persist description, trigger sensitive detection outcome + async classification."""
    form._initialize_language_and_helpers(tracker)
    session_id = tracker.get_slot("flask_session_id") or tracker.sender_id
    grievance_id = tracker.get_slot("grievance_id")
    sensitive_slots = await get_sensitive_issue_slots_on_submit(
        form,
        grievance_description or "",
        session_id=session_id,
        grievance_id=grievance_id,
        dispatcher=dispatcher,
    )
    slots_to_set: Dict[Text, Any] = {
        "grievance_new_detail": "completed",
        "grievance_description": grievance_description,
        **sensitive_slots,
    }

    grievance_data = {
        "grievance_id": tracker.get_slot("grievance_id"),
        "complainant_id": tracker.get_slot("complainant_id"),
        "grievance_description": grievance_description,
        "complainant_province": tracker.get_slot("complainant_province"),
        "complainant_district": tracker.get_slot("complainant_district"),
        "complainant_office": tracker.get_slot("complainant_office"),
        "source": "bot",
    }
    grievance_data["grievance_classification_status"] = (
        form.GRIEVANCE_CLASSIFICATION_STATUS.get("pending", "pending")
    )
    form.db_manager.create_or_update_complainant(grievance_data)
    form.db_manager.create_or_update_grievance(grievance_data)

    try:
        dispatcher.utter_message(
            json_message={
                "data": {
                    "grievance_id": grievance_data.get("grievance_id"),
                    "event_type": "grievance_saved_in_db",
                }
            }
        )
    except Exception as e:
        form.logger.error(f"Failed to emit grievance_saved_in_db event: {e}")

    if form.LLM_CLASSIFICATION:
        classification_slots = await trigger_async_classification(
            form,
            tracker,
            dispatcher,
            grievance_description=grievance_description,
        )
        slots_to_set.update(classification_slots)
    else:
        from backend.config.classification_status import LLM_SKIPPED

        form.db_manager.update_grievance(
            grievance_id,
            {"grievance_classification_status": LLM_SKIPPED},
        )
        form.logger.info(
            "classification_trigger_skipped grievance_id=%s reason=LLM_CLASSIFICATION_false status=LLM_skipped",
            grievance_id,
        )
    return slots_to_set


async def complete_road_hazard_intake_submit(
    form: BaseFormValidationAction,
    tracker: Tracker,
    dispatcher: CollectingDispatcher,
    domain: DomainDict,
    grievance_description: str,
    *,
    preset_categories: List[str],
) -> Dict[Text, Any]:
    """Road hazard fast path: persist description + preset category; no LLM classification."""
    from backend.config.classification_status import LLM_SKIPPED

    form._initialize_language_and_helpers(tracker)
    session_id = tracker.get_slot("flask_session_id") or tracker.sender_id
    grievance_id = tracker.get_slot("grievance_id")
    sensitive_slots = await get_sensitive_issue_slots_on_submit(
        form,
        grievance_description or "",
        session_id=session_id,
        grievance_id=grievance_id,
        dispatcher=dispatcher,
    )
    categories = list(preset_categories or tracker.get_slot("grievance_categories") or [])

    slots_to_set: Dict[Text, Any] = {
        "grievance_new_detail": "completed",
        "grievance_description": grievance_description,
        "grievance_categories": categories,
        "grievance_classification_status": LLM_SKIPPED,
        "grievance_summary": "",
        "grievance_summary_status": form.SKIP_VALUE,
        "grievance_categories_status": form.SKIP_VALUE,
        **sensitive_slots,
    }

    grievance_data = {
        "grievance_id": tracker.get_slot("grievance_id"),
        "complainant_id": tracker.get_slot("complainant_id"),
        "grievance_description": grievance_description,
        "grievance_categories": categories,
        "grievance_summary": "",
        "complainant_province": tracker.get_slot("complainant_province"),
        "complainant_district": tracker.get_slot("complainant_district"),
        "complainant_office": tracker.get_slot("complainant_office"),
        "source": "bot",
        "grievance_classification_status": LLM_SKIPPED,
    }
    form.db_manager.create_or_update_complainant(grievance_data)
    form.db_manager.create_or_update_grievance(grievance_data)

    try:
        dispatcher.utter_message(
            json_message={
                "data": {
                    "grievance_id": grievance_data.get("grievance_id"),
                    "event_type": "grievance_saved_in_db",
                }
            }
        )
    except Exception as e:
        form.logger.error(f"Failed to emit grievance_saved_in_db event: {e}")

    form.logger.info(
        "road_hazard_intake_submitted grievance_id=%s classification=LLM_skipped categories=%s",
        grievance_id,
        categories,
    )

    # Same ticketing webhook as BaseActionSubmit (package_id / location from QR slots).
    dispatch_grievance_from_tracker(
        tracker,
        grievance_data,
        log=form.logger,
        is_seah=bool(sensitive_slots.get("grievance_sensitive_issue")),
    )

    return slots_to_set


async def complete_dust_intake_submit(
    form: BaseFormValidationAction,
    tracker: Tracker,
    dispatcher: CollectingDispatcher,
    domain: DomainDict,
    grievance_description: str,
    *,
    preset_categories: List[str],
) -> Dict[Text, Any]:
    """Backward-compatible alias."""
    return await complete_road_hazard_intake_submit(
        form,
        tracker,
        dispatcher,
        domain,
        grievance_description,
        preset_categories=preset_categories,
    )
