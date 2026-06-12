"""SEAH contact-channel availability and button filtering."""

from __future__ import annotations

from typing import Any, Dict, List, Text


def get_available_seah_contact_channels(
    helpers: Any,
    phone_value: Any,
    email_value: Any,
) -> List[str]:
    has_phone = isinstance(phone_value, str) and helpers.is_valid_phone(phone_value)
    has_email = isinstance(email_value, str) and helpers.email_is_valid_format(
        email_value.strip()
    )
    channels: List[str] = []
    if has_phone:
        channels.append("phone")
    if has_email:
        channels.append("email")
    if has_phone and has_email:
        channels.append("both")
    channels.append("none")
    return channels


def build_seah_contact_channel_buttons(
    buttons: List[Dict[str, str]],
    phone_value: Any,
    email_value: Any,
    helpers: Any,
) -> List[Dict[str, str]]:
    allowed_channels = set(
        get_available_seah_contact_channels(helpers, phone_value, email_value)
    )
    payload_to_channel = {
        "/phone": "phone",
        "/email": "email",
        "/both": "both",
        "/none": "none",
    }
    filtered: List[Dict[str, str]] = []
    for button in buttons:
        payload = button.get("payload")
        channel = payload_to_channel.get(payload)
        if channel and channel not in allowed_channels:
            continue
        filtered.append(button)
    return filtered


def compute_seah_contact_provided(slots: Dict[Text, Any], helpers: Any) -> bool:
    channels = get_available_seah_contact_channels(
        helpers,
        phone_value=slots.get("complainant_phone"),
        email_value=slots.get("complainant_email"),
    )
    return bool(set(channels) & {"phone", "email", "both"})


def seah_contact_provided_update(
    story_main: Any,
    current_slots: Dict[str, Any],
    updates: Dict[str, Any],
    helpers: Any,
) -> Dict[str, bool]:
    if story_main != "seah_intake":
        return {}
    merged = dict(current_slots)
    merged.update(dict(updates))
    return {"seah_contact_provided": compute_seah_contact_provided(merged, helpers)}
