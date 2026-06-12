"""Hydrate complainant slots from DB by grievance_id."""

from __future__ import annotations

from typing import Any, List, Optional, Text

from rasa_sdk.events import SlotSet


def get_complainant_slot_events_from_grievance(
    grievance_id: Optional[Text],
    db_manager: Any,
    helpers: Any,
) -> List[SlotSet]:
    if not grievance_id:
        return [
            SlotSet("complainant_phone", None),
            SlotSet("status_check_complainant_phone_valid", False),
        ]

    complainant_data = db_manager.get_complainant_data_by_grievance_id(grievance_id)
    if not complainant_data:
        return [
            SlotSet("complainant_phone", None),
            SlotSet("status_check_complainant_phone_valid", False),
        ]

    fields = [
        "complainant_id",
        "complainant_phone",
        "complainant_email",
        "complainant_full_name",
        "complainant_gender",
        "complainant_province",
        "complainant_district",
        "complainant_municipality",
        "complainant_village",
        "complainant_address",
    ]

    events: List[SlotSet] = [
        SlotSet(name, complainant_data.get(name))
        for name in fields
        if name in complainant_data
    ]

    phone = complainant_data.get("complainant_phone")
    is_valid = bool(phone and helpers.is_valid_phone(phone))
    events.append(SlotSet("status_check_complainant_phone_valid", is_valid))
    return events
