"""Contact/location slot validators (form_contact logic)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher

from backend.actions.services.contact import seah_merge
from backend.actions.services.contact.utterances import contact_utterance
from backend.actions.utils import language as language_helpers

logger = logging.getLogger(__name__)


def validate_province(
    slot_value: Any,
    dispatcher: CollectingDispatcher,
    *,
    helpers: Any,
    skip_value: str,
    language_code: str,
) -> Dict[Text, Any]:
    if slot_value == skip_value:
        dispatcher.utter_message(text=contact_utterance("validate_complainant_province", language_code, 1))
        return {"complainant_province": None}
    if not helpers.check_province(slot_value):
        msg = contact_utterance("validate_complainant_province", language_code, 2).format(slot_value=slot_value)
        dispatcher.utter_message(text=msg)
        return {"complainant_province": None}
    result = helpers.check_province(slot_value).title()
    msg = contact_utterance("validate_complainant_province", language_code, 3).format(
        slot_value=slot_value, result=result
    )
    dispatcher.utter_message(text=msg)
    return {"complainant_province": result}


def validate_district(
    slot_value: Any,
    dispatcher: CollectingDispatcher,
    tracker: Tracker,
    *,
    helpers: Any,
    skip_value: str,
    language_code: str,
) -> Dict[Text, Any]:
    if slot_value == skip_value:
        dispatcher.utter_message(text=contact_utterance("validate_complainant_district", language_code, 1))
        return {"complainant_district": None}
    province = tracker.get_slot("complainant_province").title()
    if not helpers.check_district(slot_value, province):
        msg = contact_utterance("validate_complainant_district", language_code, 2).format(slot_value=slot_value)
        dispatcher.utter_message(text=msg)
        return {"complainant_district": None}
    result = helpers.check_district(slot_value, province).title()
    msg = contact_utterance("validate_complainant_district", language_code, 3).format(
        slot_value=slot_value, result=result
    )
    dispatcher.utter_message(text=msg)
    return {"complainant_district": result}


def validate_municipality_temp(
    slot_value: Any,
    tracker: Tracker,
    *,
    helpers: Any,
    skip_value: str,
) -> Dict[Text, Any]:
    if slot_value == skip_value:
        return {
            "complainant_municipality_temp": skip_value,
            "complainant_municipality": skip_value,
            "complainant_municipality_confirmed": False,
        }
    if not language_helpers.validate_string_length(slot_value, min_length=2):
        return {"complainant_municipality_temp": None}
    validated = helpers.validate_municipality_input(
        slot_value,
        tracker.get_slot("complainant_province"),
        tracker.get_slot("complainant_district"),
    )
    if validated:
        return {"complainant_municipality_temp": validated}
    return {
        "complainant_municipality_temp": None,
        "complainant_municipality": None,
        "complainant_municipality_confirmed": None,
    }


def validate_municipality_confirmed(
    slot_value: Any,
    tracker: Tracker,
) -> Dict[Text, Any]:
    if slot_value is True:
        return {
            "complainant_municipality_confirmed": True,
            "complainant_municipality": tracker.get_slot("complainant_municipality_temp"),
        }
    if slot_value is False:
        return {
            "complainant_municipality_confirmed": None,
            "complainant_municipality_temp": None,
            "complainant_municipality": None,
        }
    return {}


def validate_village_temp(
    slot_value: Text,
    dispatcher: CollectingDispatcher,
    tracker: Tracker,
    *,
    helpers: Any,
    skip_value: str,
    language_code: str,
) -> Dict[Text, Any]:
    if slot_value == skip_value:
        return {
            "complainant_village_temp": skip_value,
            "complainant_village_confirmed": False,
            "complainant_village": skip_value,
            "complainant_ward": skip_value,
        }
    try:
        slot_value = slot_value.title().strip()
        if not helpers.validate_string_length(slot_value, min_length=2):
            dispatcher.utter_message(
                text=contact_utterance("validate_complainant_village_temp", language_code, 1)
            )
            return {"complainant_village_temp": None}
    except Exception as exc:
        logger.error("validate_village_temp string length: %s", exc)
        return {"complainant_village_temp": None}

    try:
        validated_village, validated_ward = helpers.validate_village_input(
            slot_value, tracker.get_slot("complainant_municipality")
        )
    except Exception as exc:
        logger.error("validate_village_temp fuzzy: %s", exc)
        return {"complainant_village": None}

    try:
        if validated_village and validated_village == slot_value:
            return {
                "complainant_village_temp": validated_village,
                "complainant_village_confirmed": True,
                "complainant_village": validated_village,
                "complainant_ward": validated_ward,
            }
        if validated_village and validated_village != slot_value:
            return {
                "complainant_village_temp": validated_village,
                "complainant_ward": validated_ward,
            }
        return {
            "complainant_village_temp": slot_value,
            "complainant_village_confirmed": False,
            "complainant_village": slot_value,
        }
    except Exception as exc:
        logger.error("validate_village_temp result: %s", exc)
        return {"complainant_village_temp": None}


def validate_village_confirmed(slot_value: Any, tracker: Tracker) -> Dict[Text, Any]:
    if slot_value is True:
        return {
            "complainant_village_confirmed": True,
            "complainant_village": tracker.get_slot("complainant_village_temp"),
            "complainant_ward": tracker.get_slot("complainant_ward"),
        }
    if slot_value is False:
        return {
            "complainant_village_confirmed": False,
            "complainant_village": tracker.get_slot("complainant_village_temp"),
            "complainant_ward": None,
        }
    return {}


def validate_ward(slot_value: Any, *, skip_value: str) -> Dict[Text, Any]:
    if slot_value == skip_value:
        return {"complainant_ward": skip_value}
    raw = str(slot_value).strip()
    if not raw.isdigit():
        return {"complainant_ward": None}
    return {"complainant_ward": raw}


def validate_address_temp(
    slot_value: Any,
    dispatcher: CollectingDispatcher,
    *,
    skip_value: str,
    language_code: str,
) -> Dict[Text, Any]:
    if slot_value == skip_value:
        return {"complainant_address_temp": skip_value}
    if not language_helpers.validate_string_length(slot_value, min_length=2):
        dispatcher.utter_message(
            text=contact_utterance("validate_complainant_address_temp", language_code, 1)
        )
        return {"complainant_address_temp": None}
    return {"complainant_address_temp": slot_value}


def validate_address_confirmed(
    slot_value: Any,
    tracker: Tracker,
    dispatcher: CollectingDispatcher,
    *,
    language_code: str,
    helpers: Any,
    default_values: Dict[str, Any],
) -> Dict[Text, Any]:
    if slot_value is False:
        dispatcher.utter_message(text="Please enter your correct village and address")
        return {
            "complainant_village": None,
            "complainant_address": None,
            "complainant_address_temp": None,
            "complainant_address_confirmed": None,
        }
    if slot_value is True:
        result = {
            "complainant_address": tracker.get_slot("complainant_address_temp"),
            "complainant_address_confirmed": True,
        }
        result.update(
            seah_merge.merge_seah_contact_and_party_slots(
                tracker.get_slot("story_main"),
                dict(tracker.current_slot_values()),
                result,
                helpers=helpers,
                default_values=default_values,
            )
        )
        return result
    return {}


def validate_location_consent(slot_value: Any, *, skip_value: str) -> Dict[Text, Any]:
    if slot_value is True:
        return {"complainant_location_consent": True}
    if slot_value is False:
        return {
            "complainant_location_consent": False,
            "complainant_municipality_temp": skip_value,
            "complainant_municipality": skip_value,
            "complainant_municipality_confirmed": False,
            "complainant_village": skip_value,
            "complainant_village_temp": skip_value,
            "complainant_village_confirmed": False,
            "complainant_ward": skip_value,
            "complainant_address_temp": skip_value,
            "complainant_address": skip_value,
            "complainant_address_confirmed": False,
        }
    return {}


def validate_consent(
    slot_value: Any,
    tracker: Tracker,
    *,
    skip_value: str,
    helpers: Any,
    default_values: Dict[str, Any],
) -> Dict[Text, Any]:
    if slot_value is False:
        result = {
            "complainant_consent": False,
            "complainant_full_name": skip_value,
            "complainant_email_temp": skip_value,
            "complainant_email_confirmed": skip_value,
        }
    elif slot_value is True:
        result = {
            "complainant_consent": True,
            "complainant_full_name": None,
            "complainant_email_temp": None,
            "complainant_email_confirmed": None,
        }
    else:
        return {}
    result.update(
        seah_merge.merge_seah_contact_and_party_slots(
            tracker.get_slot("story_main"),
            dict(tracker.current_slot_values()),
            result,
            helpers=helpers,
            default_values=default_values,
        )
    )
    return result


def validate_full_name(
    slot_value: Any,
    dispatcher: CollectingDispatcher,
    tracker: Tracker,
    *,
    skip_value: str,
    language_code: str,
    helpers: Any,
    default_values: Dict[str, Any],
) -> Dict[Text, Any]:
    is_focal = (
        tracker.get_slot("story_main") == "seah_intake"
        and tracker.get_slot("seah_focal_stage") == "bootstrap_reporter_contact"
    )
    is_skip = isinstance(slot_value, str) and skip_value in slot_value

    if is_skip and is_focal:
        result = {"complainant_full_name": None}
    elif is_skip:
        result = {"complainant_full_name": skip_value}
    elif not slot_value or slot_value.startswith("/"):
        result = {"complainant_full_name": None}
    elif len(slot_value) < 3:
        dispatcher.utter_message(
            text=contact_utterance("validate_complainant_full_name", language_code, 1)
        )
        result = {"complainant_full_name": None}
    else:
        result = {"complainant_full_name": slot_value}

    result.update(
        seah_merge.merge_seah_contact_and_party_slots(
            tracker.get_slot("story_main"),
            dict(tracker.current_slot_values()),
            result,
            helpers=helpers,
            default_values=default_values,
        )
    )
    return result


def validate_email_temp(
    slot_value: Any,
    dispatcher: CollectingDispatcher,
    tracker: Tracker,
    *,
    skip_value: str,
    language_code: str,
    helpers: Any,
    default_values: Dict[str, Any],
) -> Dict[Text, Any]:
    if slot_value == skip_value:
        result = {
            "complainant_email_temp": skip_value,
            "complainant_email_confirmed": False,
            "complainant_email": skip_value,
        }
        result.update(
            seah_merge.merge_seah_contact_and_party_slots(
                tracker.get_slot("story_main"),
                dict(tracker.current_slot_values()),
                result,
                helpers=helpers,
                default_values=default_values,
            )
        )
        return result

    extracted = helpers.email_extract_from_text(slot_value)
    if not extracted:
        dispatcher.utter_message(
            text=contact_utterance("validate_complainant_email_temp", language_code, 1)
        )
        result = {"complainant_email_temp": None}
        result.update(
            seah_merge.merge_seah_contact_and_party_slots(
                tracker.get_slot("story_main"),
                dict(tracker.current_slot_values()),
                result,
                helpers=helpers,
                default_values=default_values,
            )
        )
        return result

    if not helpers.email_is_valid_format(extracted):
        dispatcher.utter_message(
            text=contact_utterance("validate_complainant_email_temp", language_code, 1)
        )
        result = {"complainant_email_temp": None}
        result.update(
            seah_merge.merge_seah_contact_and_party_slots(
                tracker.get_slot("story_main"),
                dict(tracker.current_slot_values()),
                result,
                helpers=helpers,
                default_values=default_values,
            )
        )
        return result

    if not helpers.email_is_valid_nepal_domain(extracted):
        result = {"complainant_email_temp": extracted, "complainant_email_confirmed": None}
    else:
        result = {
            "complainant_email_temp": extracted,
            "complainant_email_confirmed": True,
            "complainant_email": extracted,
        }
    result.update(
        seah_merge.merge_seah_contact_and_party_slots(
            tracker.get_slot("story_main"),
            dict(tracker.current_slot_values()),
            result,
            helpers=helpers,
            default_values=default_values,
        )
    )
    return result


def validate_email_confirmed(
    slot_value: Any,
    tracker: Tracker,
    *,
    skip_value: str,
    helpers: Any,
    default_values: Dict[str, Any],
) -> Dict[Text, Any]:
    if slot_value == skip_value:
        result = {"complainant_email_confirmed": skip_value}
    elif slot_value in ("slot_confirmed", "/slot_confirmed"):
        result = {"complainant_email_confirmed": True}
    elif slot_value in ("slot_edited", "/slot_edited"):
        result = {"complainant_email_temp": None, "complainant_email_confirmed": None}
    else:
        return {}
    result.update(
        seah_merge.merge_seah_contact_and_party_slots(
            tracker.get_slot("story_main"),
            dict(tracker.current_slot_values()),
            result,
            helpers=helpers,
            default_values=default_values,
        )
    )
    return result
