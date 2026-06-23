"""Sensitive-content keyword detection and utterance dispatch."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher

from backend.shared_functions.seah_service_providers import (
    format_details_utterance,
    format_recommendation_utterance,
    resolve_location_codes,
)

logger = logging.getLogger(__name__)


def detect_sensitive_content_slots(
    helpers: Any,
    slot_value: str,
    language_code: str,
) -> Dict[Text, Any]:
    detection_result = helpers.detect_sensitive_content(slot_value, language_code)
    if detection_result.get("detected") and detection_result.get("action_required"):
        logger.info(
            "SENSITIVE CONTENT DETECTED: %s - %s",
            detection_result.get("category"),
            detection_result.get("level"),
        )
        return {
            "grievance_sensitive_issue": True,
            "sensitive_issues_category": detection_result.get("category"),
            "sensitive_issues_level": detection_result.get("level"),
            "sensitive_issues_message": detection_result.get("message"),
            "sensitive_issues_confidence": detection_result.get("confidence"),
        }
    return {}


def find_seah_service_providers_for_tracker(
    tracker: Tracker,
    db_manager: Any,
    *,
    action_name: str = "find_seah_service_providers_for_tracker",
) -> List[Dict[str, Any]]:
    """Resolve SEAH support centres from complainant location slots."""
    province = tracker.get_slot("complainant_province")
    district = tracker.get_slot("complainant_district")
    municipality = tracker.get_slot("complainant_municipality")
    codes = resolve_location_codes(province, district, municipality)
    try:
        return db_manager.find_seah_service_providers(
            municipality_code=tracker.get_slot("level_3_code") or codes.get("municipality_code"),
            municipality=municipality,
            district_code=tracker.get_slot("level_2_code") or codes.get("district_code"),
            district=district,
            province_code=tracker.get_slot("level_1_code") or codes.get("province_code"),
            province=province,
            location_code=tracker.get_slot("location_code"),
        )
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("%s: SEAH service provider lookup failed: %s", action_name, exc)
        return []


def build_sensitive_issues_utterance(
    utter_index: int,
    language_code: str,
    utterances_and_buttons: Dict[str, Any],
    tracker: Optional[Tracker] = None,
    db_manager: Any = None,
    *,
    action_name: str = "build_sensitive_issues_utterance",
) -> str:
    """Utterances 1-2 are location-aware (require tracker + db); 3-5 stay static."""
    static = utterances_and_buttons["utterances"][utter_index][language_code]
    if utter_index not in (1, 2) or tracker is None or db_manager is None:
        return static

    providers = find_seah_service_providers_for_tracker(
        tracker, db_manager, action_name=action_name
    )
    municipality = tracker.get_slot("complainant_municipality")
    district = tracker.get_slot("complainant_district")
    if utter_index == 1:
        return format_recommendation_utterance(
            providers,
            language_code,
            municipality=municipality,
            district=district,
        )
    return format_details_utterance(providers, language_code)


def dispatch_sensitive_content_utterances(
    dispatcher: CollectingDispatcher,
    language_code: str,
    utterances_and_buttons: Dict[str, Any],
    tracker: Optional[Tracker] = None,
    db_manager: Any = None,
    *,
    action_name: str = "dispatch_sensitive_content_utterances",
) -> None:
    for i in range(1, len(utterances_and_buttons["utterances"]) + 1):
        dispatcher.utter_message(
            text=build_sensitive_issues_utterance(
                i,
                language_code,
                utterances_and_buttons,
                tracker,
                db_manager,
                action_name=action_name,
            )
        )
    buttons = utterances_and_buttons["buttons"][1][language_code]
    dispatcher.utter_message(buttons=buttons)
