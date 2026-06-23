"""Multi-party SEAH intake slot payloads."""

from __future__ import annotations

from typing import Any, Dict, Text

PARTY_SLOT_BY_ROLE: Dict[str, str] = {
    "victim_survivor": "party_victim_survivor",
    "witness": "party_witness",
    "relative": "party_relative",
    "seah_focal_point": "party_seah_focal_point",
    "other_reporter": "party_other_reporter",
}


def slot_nonempty(value: Any, *, default_values: Dict[str, Any]) -> bool:
    skip_values = {
        None,
        "",
        default_values.get("SKIP_VALUE"),
        "slot_skipped",
        "skipped",
    }
    if value in skip_values:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def normalize_party_role(role: Any) -> str:
    if not isinstance(role, str):
        return "victim_survivor"
    value = role.strip().lstrip("/")
    if value in PARTY_SLOT_BY_ROLE:
        return value
    if value == "focal_point":
        return "seah_focal_point"
    if value == "not_victim_survivor":
        return "relative"
    return "victim_survivor"


def derive_active_party_role(slots: Dict[Text, Any]) -> str:
    explicit = slots.get("active_party_role")
    if explicit:
        return normalize_party_role(explicit)
    return normalize_party_role(slots.get("seah_victim_survivor_role"))


def build_party_payload_from_slots(
    slots: Dict[Text, Any],
    *,
    default_values: Dict[str, Any],
) -> Dict[str, Any]:
    keys = [
        "complainant_full_name",
        "complainant_phone",
        "complainant_email",
        "complainant_province",
        "complainant_district",
        "complainant_municipality",
        "complainant_village",
        "complainant_ward",
        "complainant_address",
        "complainant_consent",
        "otp_verified",
    ]
    payload: Dict[str, Any] = {}
    for key in keys:
        value = slots.get(key)
        if slot_nonempty(value, default_values=default_values):
            payload[key] = value
    return payload


def upsert_active_party_payload(
    current_slots: Dict[str, Any],
    updates: Dict[str, Any],
    *,
    default_values: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(current_slots)
    merged.update(dict(updates))
    role = derive_active_party_role(merged)
    payload = build_party_payload_from_slots(merged, default_values=default_values)
    if not payload:
        return {"active_party_role": role}

    role_slot = PARTY_SLOT_BY_ROLE[role]
    party_contacts = dict(merged.get("party_contacts") or {})
    party_contacts[role] = payload
    return {
        "active_party_role": role,
        "party_contacts": party_contacts,
        role_slot: payload,
    }
