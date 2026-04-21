"""SEAH post-submit outro: variant resolution and contact snapshot (spec 08)."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Text

from backend.config.constants import DEFAULT_VALUES
from backend.shared_functions.helpers_repo import helpers_repo

SKIP_VALUES = frozenset(
    {
        None,
        "",
        DEFAULT_VALUES.get("SKIP_VALUE"),
        "slot_skipped",
        "skipped",
    }
)


def _slot_nonempty(value: Any) -> bool:
    if value in SKIP_VALUES:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def compute_seah_contact_provided(slots: Mapping[Text, Any]) -> bool:
    """True if complainant left a validated phone or email (spec 08)."""
    phone = slots.get("complainant_phone")
    if isinstance(phone, str) and _slot_nonempty(phone) and helpers_repo.is_valid_phone(phone):
        return True
    email = slots.get("complainant_email")
    if isinstance(email, str) and _slot_nonempty(email) and helpers_repo.email_is_valid_format(email.strip()):
        return True
    return False


def seah_contact_provided_update(
    story_main: Any,
    current_slots: Mapping[str, Any],
    updates: Mapping[str, Any],
) -> Dict[str, bool]:
    """Slot fragment for dual-write of seah_contact_provided during SEAH intake."""
    if story_main != "seah_intake":
        return {}
    merged = dict(current_slots)
    merged.update(dict(updates))
    return {"seah_contact_provided": compute_seah_contact_provided(merged)}


def resolve_seah_outro_variant(slots: Mapping[Text, Any]) -> Text:
    """
    Return utterance key suffix for action_seah_outro (spec 08 B0).

    Values: focal_default | victim_limited_contact | victim_contact_ok |
            not_victim_anonymous | not_victim_identified
    """
    role = slots.get("seah_victim_survivor_role")
    if role == "focal_point":
        return "focal_default"

    anonymous_route = slots.get("seah_anonymous_route")
    # Back-compat until slot always set: infer from sensitive_issues_follow_up
    if anonymous_route is None:
        anonymous_route = slots.get("sensitive_issues_follow_up") == "anonymous"
    elif isinstance(anonymous_route, str):
        anonymous_route = anonymous_route.lower() in ("true", "anonymous", "1", "yes")

    contact_ok = slots.get("seah_contact_provided")
    if contact_ok is None:
        contact_ok = compute_seah_contact_provided(slots)
    consent = slots.get("complainant_consent")
    channel = slots.get("seah_contact_consent_channel")

    if role == "victim_survivor":
        if (
            anonymous_route
            or not contact_ok
            or consent is False
            or channel in (None, "none", "email")
        ):
            return "victim_limited_contact"
        if contact_ok and consent is not False and channel in ("phone", "both"):
            return "victim_contact_ok"
        return "victim_limited_contact"

    if role == "not_victim_survivor":
        if anonymous_route:
            return "not_victim_anonymous"
        return "not_victim_identified"

    return "victim_limited_contact"


def format_contact_point_block(row: Mapping[str, Any], language_code: str) -> str:
    """Build user-visible block from seah_contact_points row."""
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
