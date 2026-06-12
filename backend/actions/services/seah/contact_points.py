"""SEAH contact-centre lookup and formatting."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from rasa_sdk import Tracker

logger = logging.getLogger(__name__)


def find_seah_contact_point(
    tracker: Tracker,
    db_manager: Any,
    *,
    action_name: str = "find_seah_contact_point",
) -> Optional[Dict[str, Any]]:
    try:
        return db_manager.find_seah_contact_point(
            province=tracker.get_slot("complainant_province"),
            district=tracker.get_slot("complainant_district"),
            municipality=tracker.get_slot("complainant_municipality"),
            ward=str(tracker.get_slot("complainant_ward") or ""),
            project_uuid=tracker.get_slot("project_uuid"),
        )
    except Exception as exc:
        logger.warning("%s: contact point lookup failed: %s", action_name, exc)
        return None


def format_seah_contact_point_block(row: Dict[str, Any], language_code: str) -> str:
    name = row.get("seah_center_name") or ""
    addr = row.get("address") or ""
    phone = row.get("phone") or ""
    days = row.get("opening_days") or ""
    hours = row.get("opening_hours") or ""
    if language_code == "ne":
        parts = [
            f"**{name}**" if name else "",
            f"ठेगाना: {addr}" if addr else "",
            f"फोन: {phone}" if phone else "",
            f"खुला दिन: {days}" if days else "",
            f"समय: {hours}" if hours else "",
        ]
    else:
        parts = [
            f"**{name}**" if name else "",
            f"Address: {addr}" if addr else "",
            f"Phone: {phone}" if phone else "",
            f"Opening days: {days}" if days else "",
            f"Opening hours: {hours}" if hours else "",
        ]
    return "\n".join(p for p in parts if p)
