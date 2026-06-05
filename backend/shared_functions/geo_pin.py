"""Complainant location geo + optional file metadata helpers (CB-06 / CB-08)."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

SKIP_VALUE = "slot_skipped"
NOT_PROVIDED = "NOT_PROVIDED"


def build_location_geo_json(
    lat: float,
    lng: float,
    *,
    location_code: Optional[str] = None,
    source: str = "map_pin",
) -> str:
    """Canonical JSON text for complainants.location_geo."""
    payload: Dict[str, Any] = {
        "source": source,
        "lat": round(float(lat), 6),
        "lng": round(float(lng), 6),
    }
    if location_code:
        payload["location_code"] = location_code
    return json.dumps(payload, ensure_ascii=False)


def parse_location_geo(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if text.startswith("{"):
            try:
                parsed = json.loads(text)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
    return {}


def _clean_label(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in (SKIP_VALUE, NOT_PROVIDED):
        return None
    return text


def format_location_display_label(slots: Dict[str, Any]) -> Optional[str]:
    """
    Human-readable location string for ticketing cache (grievance_location).
    Coordinates live on complainant.location_geo, not in this label.
    """
    pin_status = slots.get("location_pin_status")
    if pin_status == "skipped":
        return None

    if pin_status == "map_pin":
        parts = []
        for key in (
            "complainant_district",
            "complainant_province",
        ):
            label = _clean_label(slots.get(key))
            if label and label not in parts:
                parts.append(label)
        lat = slots.get("geo_lat")
        lng = slots.get("geo_lng")
        if lat is not None and lng is not None:
            parts.append(f"Map pin ({float(lat):.5f}, {float(lng):.5f})")
        return ", ".join(parts) if parts else None

    parts = []
    for key in (
        "complainant_village",
        "complainant_municipality",
        "complainant_district",
        "complainant_province",
        "complainant_address",
    ):
        label = _clean_label(slots.get(key))
        if label and label not in parts:
            parts.append(label)
    return ", ".join(parts) if parts else None


def slots_for_location_resolve(slots: Dict[str, Any]) -> Dict[str, Any]:
    """Strip skip placeholders before admin-name → location_code resolution."""
    cleaned = dict(slots)
    for key, value in list(cleaned.items()):
        if value == SKIP_VALUE or value == NOT_PROVIDED:
            cleaned[key] = None
    return cleaned


def apply_location_enrichment_for_submit(
    grievance_data: Dict[str, Any],
    *,
    geo_lat: Any,
    geo_lng: Any,
    location_pin_status: Optional[str],
    location_code: Optional[str],
) -> Dict[str, Any]:
    """
    Add complainant.location_geo and ticketing display text on submit.
    Does not write coordinates to grievances.grievance_location JSON blobs.
    """
    updates: Dict[str, Any] = {}
    pin_status = (location_pin_status or "").strip() or None

    if pin_status == "map_pin" and geo_lat is not None and geo_lng is not None:
        updates["location_geo"] = build_location_geo_json(
            float(geo_lat),
            float(geo_lng),
            location_code=location_code or grievance_data.get("location_code"),
            source="map_pin",
        )
        updates["location_resolution_status"] = "map_pin"
    elif pin_status == "skipped":
        updates["location_geo"] = None
        updates["location_resolution_status"] = "skipped"
    elif pin_status == "manual":
        updates["location_geo"] = None
        if not grievance_data.get("location_resolution_status"):
            updates["location_resolution_status"] = "manual"

    display_slots = {**grievance_data, **updates}
    display_slots["location_pin_status"] = pin_status
    display_slots["geo_lat"] = geo_lat
    display_slots["geo_lng"] = geo_lng
    label = format_location_display_label(display_slots)
    if label:
        updates["grievance_location"] = label

    return updates


def build_file_client_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize EXIF / client metadata for file_attachments.client_metadata."""
    entry: Dict[str, Any] = {"source": "client_upload"}
    for key in ("captured_at", "lat", "lng", "altitude", "exif_consent"):
        if metadata.get(key) is not None:
            entry[key] = metadata[key]
    return entry
