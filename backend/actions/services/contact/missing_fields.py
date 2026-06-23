"""Missing contact fields for modify-contact flow (Spec 13)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Text, Tuple

from rasa_sdk import Tracker

CONTACT_FIELDS_ORDER: List[Text] = [
    "complainant_phone",
    "complainant_full_name",
    "complainant_province",
    "complainant_district",
    "complainant_municipality_temp",
    "complainant_municipality_confirmed",
    "complainant_village_temp",
    "complainant_village_confirmed",
    "complainant_ward",
    "complainant_address_temp",
    "complainant_email_temp",
]


def is_contact_field_empty(val: Any, skip_value: str) -> bool:
    return val is None or val == "" or val == skip_value


def has_meaningful_contact_persisted_value(val: Any, skip_value: str) -> bool:
    if is_contact_field_empty(val, skip_value):
        return False
    if isinstance(val, str) and val.strip().lower() in ("not provided", "n/a", "none"):
        return False
    return True


def get_missing_contact_fields(
    tracker: Tracker,
    db_manager: Any,
    *,
    skip_value: str,
) -> Tuple[Optional[Dict], List[Text]]:
    grievance_id = tracker.get_slot("status_check_grievance_id_selected")
    if not grievance_id:
        return None, []

    complainant = db_manager.get_complainant_data_by_grievance_id(grievance_id)
    if not complainant:
        return None, []

    slots = dict(tracker.slots)
    for key, value in complainant.items():
        if key not in slots or slots[key] is None:
            slots[key] = value

    missing: List[Text] = []
    for field in CONTACT_FIELDS_ORDER:
        if field == "complainant_municipality_temp":
            if has_meaningful_contact_persisted_value(
                slots.get("complainant_municipality"), skip_value
            ):
                continue
            if is_contact_field_empty(slots.get(field), skip_value):
                missing.append(field)
            continue
        if field == "complainant_municipality_confirmed":
            if has_meaningful_contact_persisted_value(
                slots.get("complainant_municipality"), skip_value
            ):
                continue
            if slots.get(field) is None:
                missing.append(field)
            continue
        if field == "complainant_village_temp":
            if has_meaningful_contact_persisted_value(
                slots.get("complainant_village"), skip_value
            ):
                continue
            if is_contact_field_empty(slots.get(field), skip_value):
                missing.append(field)
            continue
        if field == "complainant_village_confirmed":
            if has_meaningful_contact_persisted_value(
                slots.get("complainant_village"), skip_value
            ):
                continue
            if slots.get(field) is None:
                missing.append(field)
            continue
        if field == "complainant_address_temp":
            if has_meaningful_contact_persisted_value(
                slots.get("complainant_address"), skip_value
            ):
                continue
            if is_contact_field_empty(slots.get(field), skip_value):
                missing.append(field)
            continue
        if field == "complainant_email_temp":
            if has_meaningful_contact_persisted_value(
                slots.get("complainant_email"), skip_value
            ):
                continue
            if is_contact_field_empty(slots.get(field), skip_value):
                missing.append(field)
            continue

        if not has_meaningful_contact_persisted_value(slots.get(field), skip_value):
            missing.append(field)
    return complainant, missing
