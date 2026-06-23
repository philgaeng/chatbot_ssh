"""Phone validation for contact and OTP forms."""

from __future__ import annotations

import logging
from typing import Any, Dict

from rasa_sdk.executor import CollectingDispatcher

from backend.actions.services.contact.utterances import contact_utterance
from backend.config.constants import DEFAULT_VALUES

logger = logging.getLogger(__name__)


def validate_complainant_phone(
    slot_value: Any,
    dispatcher: CollectingDispatcher,
    *,
    helpers: Any,
    language_code: str,
    action_name: str,
    skip_value: str = DEFAULT_VALUES["SKIP_VALUE"],
) -> Dict[str, Any]:
    logger.info("%s - Validating phone: %s", action_name, slot_value)

    if skip_value in slot_value:
        logger.info("%s - Phone collection skipped", action_name)
        return {"complainant_phone": skip_value}

    if slot_value.startswith("/"):
        return {"complainant_phone": None, "complainant_phone_valid": False}

    if not helpers.is_valid_phone(slot_value):
        dispatcher.utter_message(text=contact_utterance("validate_complainant_phone", language_code, 1))
        logger.info("%s - Invalid phone format: %s", action_name, slot_value)
        return {"complainant_phone": None, "complainant_phone_valid": False}

    if helpers.is_philippine_phone(slot_value):
        dispatcher.utter_message(text="You entered a PH number for validation.")
        logger.info("%s - Philippine phone detected", action_name)
        return {
            "complainant_phone": helpers.is_philippine_phone(slot_value),
            "complainant_phone_valid": True,
        }

    logger.info("%s - Phone validated and standardized", action_name)
    return {
        "complainant_phone": helpers.standardize_phone(language_code, slot_value),
        "complainant_phone_valid": True,
    }
