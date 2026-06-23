"""DB storage normalization for submit payloads."""

from __future__ import annotations

from typing import Any, Dict


def normalize_skip_and_null_for_db(
    grievance_data: Dict[str, Any],
    *,
    skip_value: str,
    not_provided: str,
) -> Dict[str, Any]:
    for key, value in grievance_data.items():
        if value == skip_value or value is None:
            grievance_data[key] = not_provided
    return grievance_data


def merge_role_party_payloads(grievance_data: Dict[str, Any]) -> Dict[str, Any]:
    role_slot_map = {
        "victim_survivor": "party_victim_survivor",
        "witness": "party_witness",
        "relative": "party_relative",
        "seah_focal_point": "party_seah_focal_point",
        "other_reporter": "party_other_reporter",
    }
    raw = grievance_data.get("party_contacts")
    party_contacts: Dict[str, Any] = raw if isinstance(raw, dict) else {}
    for role_key, slot_name in role_slot_map.items():
        slot_payload = grievance_data.get(slot_name)
        if isinstance(slot_payload, dict) and slot_payload:
            party_contacts[role_key] = slot_payload
    grievance_data["party_contacts"] = party_contacts
    return grievance_data
