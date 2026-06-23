"""Pure road-hazard subtype catalog + category/description/parsing helpers.

Extracted from ``backend.actions.forms.form_road_hazard`` so the Rasa form keeps
only its conversation flow. Everything here is pure (no Rasa/tracker dependency)
and safe to reuse from forms, the orchestrator, or tests.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

ROAD_HAZARD_CLASSIFICATION = "Road Hazard"

SUBTYPE_PAYLOAD_PREFIX = "road_hazard_subtype_"

DUST_SUBTYPE = "dust"

ROAD_HAZARD_SUBTYPES: Dict[str, Dict[str, str]] = {
    "dust": {
        "generic_name": "Dust",
        "label_en": "Dust",
        "label_ne": "धुलो",
        "payload": "/road_hazard_subtype_dust",
    },
    "flood_landslide": {
        "generic_name": "Flood and Landslide",
        "label_en": "Flood and Landslide",
        "label_ne": "बाढी र पहिरो",
        "payload": "/road_hazard_subtype_flood_landslide",
    },
    "potholes": {
        "generic_name": "Potholes",
        "label_en": "Potholes",
        "label_ne": "खाडल",
        "payload": "/road_hazard_subtype_potholes",
    },
    "accident": {
        "generic_name": "Accident",
        "label_en": "Accident",
        "label_ne": "दुर्घटना",
        "payload": "/road_hazard_subtype_accident",
    },
    "animal_on_road": {
        "generic_name": "Animal on Road",
        "label_en": "Animal on Road",
        "label_ne": "सडकमा जनावर",
        "payload": "/road_hazard_subtype_animal_on_road",
    },
    "others": {
        "generic_name": "Others",
        "label_en": "Others",
        "label_ne": "अन्य",
        "payload": "/road_hazard_subtype_others",
    },
}


def derive_category_key(classification: str, generic_grievance_name: str) -> str:
    """Match ticketing.services.grievance_categories_catalog.derive_category_key."""
    return (
        f"{classification.replace('-', ' ').title()} - "
        f"{generic_grievance_name.replace('-', ' ').title()}"
    )


def category_key_for_subtype(subtype: str) -> str:
    info = ROAD_HAZARD_SUBTYPES[subtype]
    return derive_category_key(ROAD_HAZARD_CLASSIFICATION, info["generic_name"])


def default_description_for_subtype(subtype: str) -> str:
    label = ROAD_HAZARD_SUBTYPES[subtype]["label_en"]
    return (
        f"Road hazard ({label.lower()}) report filed via the fast path "
        "(location and photos to follow)."
    )


def normalize_road_hazard_subtype(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.startswith("/"):
        raw = raw.lstrip("/")
    if raw.startswith(SUBTYPE_PAYLOAD_PREFIX):
        raw = raw[len(SUBTYPE_PAYLOAD_PREFIX) :]
    if raw in ROAD_HAZARD_SUBTYPES:
        return raw
    return None


DUST_CATEGORY = category_key_for_subtype(DUST_SUBTYPE)
DUST_DEFAULT_DESCRIPTION = default_description_for_subtype(DUST_SUBTYPE)
