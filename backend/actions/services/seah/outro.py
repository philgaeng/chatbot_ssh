"""SEAH outro utterance variant resolution."""

from __future__ import annotations

from typing import Any, Dict, Text

from backend.actions.services.seah.contact_channels import compute_seah_contact_provided


def resolve_seah_outro_variant(slots: Dict[Text, Any], helpers: Any) -> Text:
    role = slots.get("seah_victim_survivor_role")
    if role == "focal_point":
        return "focal_default"

    anonymous_route = slots.get("seah_anonymous_route")
    if anonymous_route is None:
        anonymous_route = slots.get("sensitive_issues_follow_up") == "anonymous"
    elif isinstance(anonymous_route, str):
        anonymous_route = anonymous_route.lower() in ("true", "anonymous", "1", "yes")

    contact_ok = slots.get("seah_contact_provided")
    if contact_ok is None:
        contact_ok = compute_seah_contact_provided(slots, helpers)
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
