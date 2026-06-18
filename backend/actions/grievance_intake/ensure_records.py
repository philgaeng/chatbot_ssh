"""Ensure grievance/complainant IDs and minimal DB rows for intake + attachments."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from backend.config.constants import DEFAULT_VALUES

_DEFAULT_PROVINCE = DEFAULT_VALUES["DEFAULT_PROVINCE"]
_DEFAULT_DISTRICT = DEFAULT_VALUES["DEFAULT_DISTRICT"]


def intake_location_defaults(
    *,
    complainant_province: Optional[str] = None,
    complainant_district: Optional[str] = None,
    complainant_office: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "complainant_province": complainant_province or _DEFAULT_PROVINCE,
        "complainant_district": complainant_district or _DEFAULT_DISTRICT,
        "complainant_office": complainant_office,
        "source": "bot",
    }


def resolve_intake_slot_ids(
    db_manager: Any,
    *,
    existing_grievance_id: Optional[str],
    existing_complainant_id: Optional[str],
    complainant_province: Optional[str] = None,
    complainant_district: Optional[str] = None,
    complainant_office: Optional[str] = None,
    reuse_existing: bool = False,
) -> Tuple[str, str]:
    """Return slot IDs for flow start.

    When ``reuse_existing`` is True (pre-flow attachment upload), keep IDs already
  in slots. Otherwise mint fresh IDs (new intake / file-another from ``done``).
    """
    loc = intake_location_defaults(
        complainant_province=complainant_province,
        complainant_district=complainant_district,
        complainant_office=complainant_office,
    )
    if reuse_existing and existing_grievance_id:
        grievance_id = existing_grievance_id
        complainant_id = existing_complainant_id or db_manager.generate_complainant_id(loc)
        return grievance_id, complainant_id

    grievance_id = db_manager.generate_grievance_id(loc)
    complainant_id = db_manager.generate_complainant_id(loc)
    return grievance_id, complainant_id


def ensure_intake_records_for_attachment(
    db_manager: Any,
    *,
    grievance_id: Optional[str] = None,
    complainant_id: Optional[str] = None,
    complainant_province: Optional[str] = None,
    complainant_district: Optional[str] = None,
    complainant_office: Optional[str] = None,
) -> Dict[str, str]:
    """Mint IDs if missing and ensure minimal rows exist for file FK."""
    loc = intake_location_defaults(
        complainant_province=complainant_province,
        complainant_district=complainant_district,
        complainant_office=complainant_office,
    )
    if not grievance_id:
        grievance_id = db_manager.generate_grievance_id(loc)
    if not complainant_id:
        complainant_id = db_manager.generate_complainant_id(loc)

    db_manager.create_or_update_complainant(
        {"complainant_id": complainant_id, **loc}
    )
    db_manager.create_or_update_grievance(
        {
            "grievance_id": grievance_id,
            "complainant_id": complainant_id,
            "grievance_description": "",
            **loc,
        }
    )
    return {"grievance_id": grievance_id, "complainant_id": complainant_id}


def grievance_id_set_json(grievance_id: str, complainant_id: str) -> Dict[str, Any]:
    return {
        "data": {
            "grievance_id": grievance_id,
            "complainant_id": complainant_id,
            "event_type": "grievance_id_set",
        }
    }
