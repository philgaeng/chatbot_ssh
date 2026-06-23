"""SEAH project picker buttons and validation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from rasa_sdk import Tracker

from backend.actions.utils.mapping_buttons import BUTTONS_SEAH_PROJECT_IDENTIFICATION

logger = logging.getLogger(__name__)


def parse_project_pick_uuid(slot_value: Any) -> Optional[str]:
    if not isinstance(slot_value, str):
        return None
    raw = slot_value.strip().lstrip("/")
    match = re.match(r"^project_pick\s*(\{.*\})\s*$", raw, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    pid = data.get("id") or data.get("project_uuid")
    if isinstance(pid, str) and len(pid.strip()) >= 8:
        return pid.strip()
    return None


def project_button_title(row: Dict[str, Any], language_code: str) -> str:
    if language_code == "ne" and row.get("name_local"):
        title = str(row["name_local"]).strip()
    else:
        title = (str(row.get("name_en") or row.get("name_local") or "Project")).strip()
    if len(title) > 40:
        title = title[:37] + "..."
    return title


def build_seah_project_identification_buttons(
    tracker: Tracker,
    db_manager: Any,
    *,
    max_projects: int = 12,
) -> List[Dict[str, str]]:
    language_code = tracker.get_slot("language_code") or "en"
    lang = language_code if language_code in BUTTONS_SEAH_PROJECT_IDENTIFICATION else "en"
    fallback = list(
        BUTTONS_SEAH_PROJECT_IDENTIFICATION.get(lang)
        or BUTTONS_SEAH_PROJECT_IDENTIFICATION["en"]
    )

    province = tracker.get_slot("complainant_province")
    district = tracker.get_slot("complainant_district")
    table_manager = getattr(db_manager, "table", db_manager)
    try:
        rows = table_manager.list_active_projects_for_geo(
            province=province,
            district=district,
            limit=max_projects,
        )
    except Exception:
        rows = []

    if not rows:
        try:
            rows = table_manager.execute_query(
                """
                SELECT project_uuid, name_en, name_local, adb
                FROM projects
                WHERE inactive_at IS NULL
                ORDER BY name_en NULLS LAST
                LIMIT %s
                """,
                (int(max_projects),),
                operation="list_active_projects_global",
            )
        except Exception:
            rows = []

    project_buttons: List[Dict[str, str]] = []
    for row in rows or []:
        uuid = row.get("project_uuid")
        if not uuid:
            continue
        title = project_button_title(row, lang)
        project_buttons.append(
            {"title": title, "payload": f'/project_pick{{"id":"{uuid}"}}'}
        )
    return project_buttons + fallback


def validate_seah_project_identification_value(
    slot_value: Any,
    db_manager: Any,
    *,
    skip_value: str,
    language_code: Optional[str] = None,
) -> Dict[str, Any]:
    if slot_value is None:
        return {"seah_project_identification": None}

    value = slot_value.strip() if isinstance(slot_value, str) else slot_value
    if isinstance(value, str):
        value = value.lstrip("/")

    if value in ("skip", skip_value):
        value = "cannot_specify"

    if value in ("yes", "no"):
        normalized = "yes" if value == "yes" else "no"
        return {
            "seah_project_identification": normalized,
            "seah_not_adb_project": normalized == "no",
            "project_uuid": None,
        }

    if value in ("cannot_specify", "not_adb_project"):
        return {
            "seah_project_identification": value,
            "seah_not_adb_project": value == "not_adb_project",
            "project_uuid": None,
        }

    pick = parse_project_pick_uuid(str(slot_value)) if slot_value is not None else None
    if pick:
        table_manager = getattr(db_manager, "table", db_manager)
        row = table_manager.get_active_project_by_uuid(pick)
        if not row:
            return {"seah_project_identification": None}
        lang = language_code or "en"
        if lang == "ne" and row.get("name_local"):
            display = str(row["name_local"]).strip()
        else:
            display = (str(row.get("name_en") or row.get("name_local") or "")).strip() or pick
        adb = row.get("adb")
        if adb is None:
            adb = True
        return {
            "seah_project_identification": display,
            "project_uuid": pick,
            "seah_not_adb_project": not bool(adb),
        }

    if isinstance(value, str) and len(value) >= 2:
        return {
            "seah_project_identification": value,
            "seah_not_adb_project": False,
            "project_uuid": None,
        }

    return {"seah_project_identification": None}
