"""Load grievances by complainant phone for status-check slot updates."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Text

from rasa_sdk import Tracker

from backend.actions.services.status_check import name_matching

logger = logging.getLogger(__name__)


def retrieve_grievances_by_phone(
    tracker: Tracker,
    db_manager: Any,
    *,
    phone: Optional[Text] = None,
    skip_value: str,
    not_provided: str,
    action_name: str = "retrieve_grievances_by_phone",
) -> Dict[Text, Any]:
    """Return slot updates after looking up grievances for a phone number.

    When called from validate_complainant_phone, pass phone= so the just-validated
    value is used (tracker does not have complainant_phone set yet).
    """
    complainant_phone = phone if phone is not None else tracker.get_slot("complainant_phone")

    logger.info(
        "%s: retrieve_grievances_by_phone entry | phone=%s",
        action_name,
        complainant_phone,
    )

    if not complainant_phone or complainant_phone == skip_value:
        logger.info("%s: Phone skipped or not provided", action_name)
        return {
            "status_check_retrieve_grievances": skip_value,
            "story_route": skip_value,
        }

    try:
        list_grievances_by_phone = db_manager.get_grievance_by_complainant_phone(
            complainant_phone
        )
    except Exception as exc:
        logger.exception(
            "%s: get_grievance_by_complainant_phone failed for phone=%s: %s",
            action_name,
            complainant_phone,
            exc,
        )
        raise

    logger.info(
        "%s: get_grievance_by_complainant_phone returned %s grievances",
        action_name,
        len(list_grievances_by_phone),
    )

    if len(list_grievances_by_phone) == 0:
        logger.debug("%s: No grievances found for phone", action_name)
        return {
            "status_check_retrieve_grievances": True,
            "status_check_complainant_phone_valid": "no_phone_found",
            "list_grievances_by_phone": [],
            "complainant_phone": None,
        }

    list_grievances_by_phone = name_matching.convert_grievance_datetime_to_string(
        list_grievances_by_phone
    )

    slots_to_set: Dict[Text, Any] = {
        "status_check_retrieve_grievances": True,
        "list_grievances_by_phone": list_grievances_by_phone,
        "status_check_complainant_phone_valid": True,
    }

    if len(list_grievances_by_phone) == 1:
        grievance_id_selected = list_grievances_by_phone[0]["grievance_id"]
        logger.debug("%s: Single grievance found: %s", action_name, grievance_id_selected)
        slots_to_set["status_check_grievance_id_selected"] = grievance_id_selected
        return slots_to_set

    list_complainant_full_names = name_matching.extract_unique_full_names_from_list(
        list_grievances_by_phone,
        not_provided=not_provided,
    )

    if len(list_complainant_full_names) == 0:
        logger.debug("%s: Multiple grievances, all without names", action_name)
        slots_to_set.update(
            {
                "status_check_complainant_full_name": not_provided,
                "list_grievance_id": list_grievances_by_phone,
            }
        )
    elif len(list_complainant_full_names) == 1:
        logger.debug(
            "%s: Multiple grievances, same name: %s",
            action_name,
            list_complainant_full_names[0],
        )
        slots_to_set.update(
            {
                "status_check_complainant_full_name": list_complainant_full_names[0],
                "list_grievance_id": list_grievances_by_phone,
            }
        )
    else:
        logger.debug(
            "%s: Multiple grievances, different names: %s",
            action_name,
            list_complainant_full_names,
        )
        slots_to_set["complainant_list_full_names"] = list_complainant_full_names

    return slots_to_set
