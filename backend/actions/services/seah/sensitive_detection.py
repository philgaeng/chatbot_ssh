"""Sensitive-content keyword detection and utterance dispatch."""

from __future__ import annotations

import logging
from typing import Any, Dict, Text

from rasa_sdk.executor import CollectingDispatcher

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


def dispatch_sensitive_content_utterances(
    dispatcher: CollectingDispatcher,
    language_code: str,
    utterances_and_buttons: Dict[str, Any],
) -> None:
    for i in range(1, len(utterances_and_buttons["utterances"]) + 1):
        dispatcher.utter_message(
            text=utterances_and_buttons["utterances"][i][language_code]
        )
    buttons = utterances_and_buttons["buttons"][1][language_code]
    dispatcher.utter_message(buttons=buttons)
