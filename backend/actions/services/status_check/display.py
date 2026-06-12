"""Grievance summary text for user display."""

from __future__ import annotations

import logging
from typing import Any, Dict

from backend.actions.utils import language as language_helpers
from backend.services.db_debug_log import grievance_row_summary

logger = logging.getLogger(__name__)


def prepare_grievance_text_for_display(
    grievance: Dict[str, Any],
    *,
    language_code: str,
    display_only_short: bool = True,
) -> str:
    key_mapping_language = {
        "grievance_id": {"en": "grievance_id", "ne": "गुनासो ID"},
        "grievance_categories": {"en": "Grievance categories", "ne": "गुनासो श्रेणी"},
        "grievance_status": {"en": "Grievance status", "ne": "गुनासो स्थिति"},
        "grievance_timeline": {"en": "Grievance timeline", "ne": "गुनासो टाइमलाइन"},
    }
    key_mapping_language_long = {
        "grievance_description": {"en": "Grievance description", "ne": "गुनासो विवरण"},
        "grievance_summary": {"en": "Grievance summary", "ne": "गुनासो सारांश"},
        "grievance_status_update_date": {
            "en": "Grievance status update date",
            "ne": "गुनासो स्थिति अपडेट गरिएको",
        },
        "grievance_creation_date": {
            "en": "Grievance creation date",
            "ne": "गुनासो सिर्जना गरिएको",
        },
    }

    if not display_only_short:
        key_mapping_language.update(key_mapping_language_long)

    utterance = []
    logger.debug("prepare_grievance_text_for_display: %s", grievance_row_summary(grievance))
    for key in key_mapping_language:
        if key in grievance:
            value = grievance[key]
            denomination = key_mapping_language[key][language_code]
            if key == "grievance_status":
                value = language_helpers.status_and_description_in_language(
                    value, language_code
                )
            if value:
                utterance.append(f"{denomination}: {value}")
    logger.debug(
        "prepare_grievance_text_for_display: utterance_lines=%d chars=%d",
        len(utterance),
        sum(len(line) for line in utterance),
    )
    return "\n".join(utterance)
