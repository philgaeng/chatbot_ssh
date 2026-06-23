"""Pure map-pin location helpers (payload parsing + contact-slot prefills).

Extracted from ``backend.actions.action_map_location`` so the Rasa actions keep
only their dispatch flow. These functions are pure (no Rasa/tracker dependency).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from backend.actions.base_classes.base_mixins import SKIP_VALUE


def location_skip_slot_updates() -> Dict[str, Any]:
    """Skip all location fields when the user declines location consent."""
    return {
        "complainant_location_consent": False,
        "complainant_province": SKIP_VALUE,
        "complainant_district": SKIP_VALUE,
        "complainant_municipality_temp": SKIP_VALUE,
        "complainant_municipality": SKIP_VALUE,
        "complainant_municipality_confirmed": True,
        "complainant_village": SKIP_VALUE,
        "complainant_village_temp": SKIP_VALUE,
        "complainant_village_confirmed": True,
        "complainant_ward": SKIP_VALUE,
        "complainant_address_temp": SKIP_VALUE,
        "complainant_address": SKIP_VALUE,
        "complainant_address_confirmed": True,
        "location_pin_status": "skipped",
    }


def build_map_filled_location_slots(
    lat: float,
    lng: float,
    *,
    province: Optional[str] = None,
    district: Optional[str] = None,
    location_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Prefill contact-form slots after a map pin.
    Coordinates persist on submit as complainant.location_geo (not grievance_location).
    """
    address_label = f"Map pin ({lat:.5f}, {lng:.5f})"
    updates: Dict[str, Any] = {
        "complainant_location_consent": True,
        "complainant_province": province or SKIP_VALUE,
        "complainant_district": district or SKIP_VALUE,
        "complainant_municipality_temp": SKIP_VALUE,
        "complainant_municipality": SKIP_VALUE,
        "complainant_municipality_confirmed": True,
        "complainant_village_temp": SKIP_VALUE,
        "complainant_village": SKIP_VALUE,
        "complainant_village_confirmed": True,
        "complainant_ward": SKIP_VALUE,
        "complainant_address_temp": address_label,
        "complainant_address": address_label,
        "complainant_address_confirmed": True,
        "location_pin_status": "map_pin",
        "geo_lat": lat,
        "geo_lng": lng,
    }
    if location_code:
        updates["location_code"] = location_code
    return updates


def parse_map_pin_payload(payload: str) -> Dict[str, float]:
    """Parse /map_pin_set{\"lat\":..,\"lng\":..} style payloads."""
    raw = (payload or "").strip().lstrip("/")
    if raw.startswith("map_pin_set"):
        raw = raw[len("map_pin_set") :].strip()
    brace = raw.find("{")
    if brace < 0:
        raise ValueError("invalid map pin payload")
    data = json.loads(raw[brace:])
    return {"lat": float(data["lat"]), "lng": float(data["lng"])}
