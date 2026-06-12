"""Full-name matching and grievance list shaping for status-check flows."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

from rasa_sdk.executor import CollectingDispatcher

logger = logging.getLogger(__name__)


def select_grievances_from_full_name_list(
    full_name_matches: List[Any],
    list_grievances_by_phone: list,
    dispatcher: CollectingDispatcher | None = None,
) -> List[Dict[str, Any]]:
    """Filter grievances by matched full names; open cases first, then closed (newest first)."""
    del dispatcher  # reserved for future utterance hooks
    logger.debug(
        "select_grievances_from_full_name_list: full_name=%s list_len=%d",
        full_name_matches,
        len(list_grievances_by_phone),
    )
    matching_grievance_list = [
        grievance
        for grievance in list_grievances_by_phone
        if grievance["complainant_full_name"] in full_name_matches
    ]
    if not matching_grievance_list:
        return []

    not_closed = [
        grievance
        for grievance in matching_grievance_list
        if grievance.get("grievance_status")
        and grievance.get("grievance_status") not in ["CLOSED"]
    ]
    not_closed.sort(key=lambda x: x["grievance_creation_date"], reverse=True)
    closed = [
        grievance
        for grievance in matching_grievance_list
        if grievance["grievance_status"] in ["CLOSED"]
    ]
    closed.sort(key=lambda x: x["grievance_creation_date"], reverse=True)
    return not_closed + closed


def match_similar_full_names_in_list(
    list_full_names: list,
    helpers: Any,
) -> list:
    """Deduplicate full names that fuzzy-match via helpers.match_full_name_list."""
    unique_full_names = []
    remaining_names = list_full_names.copy()

    for full_name in list_full_names:
        if full_name not in unique_full_names:
            remaining_names = [name for name in remaining_names if name != full_name]
            if len(helpers.match_full_name_list(full_name, remaining_names)) == 0:
                unique_full_names.append(full_name)
    return unique_full_names


def convert_grievance_datetime_to_string(
    list_grievances: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Serialize datetime fields for JSON-safe slot storage."""
    serializable_grievances = []
    for grievance in list_grievances:
        serializable_grievance = {}
        for key, value in grievance.items():
            if hasattr(value, "isoformat"):
                serializable_grievance[key] = value.isoformat()
            else:
                serializable_grievance[key] = value
        serializable_grievances.append(serializable_grievance)
    return serializable_grievances


def extract_unique_full_names_from_list(
    list_grievances: List[Dict[str, Any]],
    *,
    not_provided: str,
) -> List[str]:
    """Distinct complainant names, longest first, excluding NOT_PROVIDED."""
    result = list(
        {
            grievance["complainant_full_name"]
            for grievance in list_grievances
            if grievance["complainant_full_name"] != not_provided
        }
    )
    result.sort(key=lambda x: len(x), reverse=True)
    return result
