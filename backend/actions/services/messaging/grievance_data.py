"""Grievance data assembly from tracker slots and DB."""

from __future__ import annotations

import logging
import traceback
from typing import Any, Dict

from rasa_sdk import Tracker

from backend.config.constants import GRIEVANCE_FIELDS, USER_FIELDS

logger = logging.getLogger(__name__)


def collect_grievance_data_from_tracker(tracker: Tracker) -> Dict[str, Any]:
    return {
        k: tracker.get_slot(k)
        for k in tracker.slots
        if k in USER_FIELDS + GRIEVANCE_FIELDS
    }


def get_attached_files_info(grievance_id: str, db_manager: Any) -> Dict[str, Any]:
    try:
        files = db_manager.get_grievance_files(grievance_id)
        if not files:
            return {"has_files": False, "files_info": ""}
        files_info = "\nAttached files:\n" + "\n".join(
            f"- {file['file_name']} ({file['file_size']} bytes)" for file in files
        )
        return {"has_files": True, "files_info": files_info}
    except Exception as exc:
        logger.error("Error getting attached files info: %s", exc)
        logger.error("Traceback: %s", traceback.format_exc())
        raise Exception(f"Failed to get attached files info: {exc}") from exc
