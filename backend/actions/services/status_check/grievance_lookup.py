"""Grievance ID normalization and lookup for status-check flows."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Text

from rasa_sdk import Tracker

from backend.services.db_debug_log import grievance_row_summary

logger = logging.getLogger(__name__)


def validate_grievance_id_format(text: Any) -> bool:
    """True when text contains a valid last-6 grievance ID segment (XX + 4 alnum)."""
    if not text:
        return False
    if text.endswith("-B") or text.endswith("-A"):
        text = text[:-2]
    text = re.sub(r"[^a-zA-Z0-9]", "", text).strip().upper()
    if len(text) < 6:
        return False
    text = text[-6:]
    return bool(re.match(r"^[A-Z]{2}[A-Z0-9]{4}$", text))


def standardize_grievance_id_response(text: Any) -> str:
    """Normalize user input to XX-XXXX (last six alphanumeric characters)."""
    logger.debug("standardize_grievance_id_response: text before standardization: %s", text)
    if text.endswith("-B") or text.endswith("-A"):
        text = text[:-2]
    logger.debug(
        "standardize_grievance_id_response: text after legacy grievance id format handling: %s",
        text,
    )
    text = re.sub(r"[^a-zA-Z0-9]", "", text).strip().upper()
    logger.debug(
        "standardize_grievance_id_response: text after alphanumeric characters handling: %s",
        text,
    )
    text = text[-6:]
    return text[:2] + "-" + text[2:]


def fetch_grievance_id_from_db(text: Any, db_manager: Any) -> Any:
    """Resolve full grievance_id from partial user input via DB lookup."""
    if validate_grievance_id_format(text):
        standardized = standardize_grievance_id_response(text)
        logger.debug("fetch_grievance_id_from_db: standardized: %s", standardized)
        return db_manager.get_grievance_id_by_last_6_characters(standardized)
    logger.debug("fetch_grievance_id_from_db: no grievance id found")
    return False


def collect_grievance_data_from_id(
    grievance_id: str,
    tracker: Tracker,
    db_manager: Any,
) -> Optional[Dict[Text, Any]]:
    """Load grievance dict from tracker cache or DB."""
    grievances = tracker.get_slot("list_grievance_id")
    if grievances:
        matches = [g for g in grievances if g.get("grievance_id") == grievance_id]
        logger.debug(
            "collect_grievance_data_from_id: grievance_id=%s tracker_list_matches=%d first=%s",
            grievance_id,
            len(matches),
            grievance_row_summary(matches[0]) if matches else "none",
        )
        grievance = matches[0] if matches else None
    else:
        grievance = db_manager.get_grievance_by_id(grievance_id)
    return grievance if grievance else None
