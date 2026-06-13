"""Map-pin async geocode: Nominatim → ticketing location codes → DB update."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.shared_functions.geo_pin import (
    build_location_geo_json,
    format_location_display_label,
    parse_location_geo,
    slots_for_location_resolve,
)
from backend.shared_functions.location_mapping import (
    resolve_location_hierarchy_from_code,
    resolve_location_payload,
)
from backend.shared_functions.location_validator import ContactLocationValidator
from backend.shared_functions.reverse_geocode import (
    NominatimError,
    NominatimRateLimitError,
    NominatimUnavailableError,
    nominatim_reverse_geocode,
)

logger = logging.getLogger(__name__)

NOT_PROVIDED = "NOT_PROVIDED"


def _canonicalize_admin_names(
    raw: Dict[str, Optional[str]],
    *,
    lang_code: str = "en",
) -> Dict[str, Optional[str]]:
    """Fuzzy-match Nominatim labels to ticketing canonical names."""
    from backend.shared_functions.text_language import detect_app_language

    province_raw = raw.get("province")
    district_raw = raw.get("district")
    municipality_raw = raw.get("municipality")

    if not any((province_raw, district_raw, municipality_raw)):
        return {"province": None, "district": None, "municipality": None}

    try:
        validator = ContactLocationValidator()
    except Exception as exc:
        logger.warning("map_pin_geocode: validator init failed (%s); using raw names", exc)
        return dict(raw)

    province = None
    district = None
    municipality = None

    if province_raw:
        validator._initialize_constants(detect_app_language(province_raw, lang_code))
        province = validator.check_province(province_raw)

    if province and district_raw:
        validator._initialize_constants(detect_app_language(district_raw, lang_code))
        district = validator.check_district(district_raw, province)

    if province and district and municipality_raw:
        validator._initialize_constants(detect_app_language(municipality_raw, lang_code))
        municipality = validator.validate_municipality_input(
            municipality_raw,
            province,
            district,
        )

    return {
        "province": province or province_raw,
        "district": district or district_raw,
        "municipality": municipality or municipality_raw,
    }


def build_slots_from_geocode_names(
    names: Dict[str, Optional[str]],
    *,
    lat: float,
    lng: float,
) -> Dict[str, Any]:
    return {
        "complainant_province": names.get("province"),
        "complainant_district": names.get("district"),
        "complainant_municipality": names.get("municipality"),
        "location_pin_status": "map_pin",
        "geo_lat": lat,
        "geo_lng": lng,
    }


def resolve_map_pin_location_payload(
    db_manager: Any,
    lat: float,
    lng: float,
    *,
    lang_code: str = "en",
    country_code: str = "NP",
    respect_rate_limit: bool = True,
) -> Dict[str, Any]:
    """
    Reverse geocode a pin and resolve ticketing location codes.

    Nominatim + code matching always use English admin labels (stable OSM/DB mapping).
    Display names (level_* / complainant_*) use ``lang_code`` from DB translations.
    """
    raw = nominatim_reverse_geocode(
        lat,
        lng,
        lang_code="en",
        respect_rate_limit=respect_rate_limit,
    )
    names = _canonicalize_admin_names(raw, lang_code="en")
    slots = build_slots_from_geocode_names(names, lat=lat, lng=lng)
    slots["language_code"] = lang_code or "en"
    payload = resolve_location_payload(
        db_manager,
        slots_for_location_resolve(slots),
        country_code=country_code,
    )

    location_code = payload.get("location_code")
    if location_code:
        hierarchy = resolve_location_hierarchy_from_code(
            db_manager,
            location_code,
            lang_code=lang_code or "en",
        )
        for key, value in hierarchy.items():
            if value:
                payload[key] = value

    payload["complainant_province"] = payload.get("level_1_name") or names.get("province")
    payload["complainant_district"] = payload.get("level_2_name") or names.get("district")
    payload["complainant_municipality"] = payload.get("level_3_name") or names.get("municipality")
    return payload


def build_complainant_geocode_update(
    payload: Dict[str, Any],
    *,
    lat: float,
    lng: float,
    existing_location_geo: Optional[str] = None,
) -> Dict[str, Any]:
    """Merge geocode resolution into complainant + grievance display fields."""
    location_code = payload.get("location_code")
    geo_existing = parse_location_geo(existing_location_geo)
    updates: Dict[str, Any] = {
        "complainant_province": payload.get("complainant_province") or payload.get("level_1_name"),
        "complainant_district": payload.get("complainant_district") or payload.get("level_2_name"),
        "complainant_municipality": payload.get("complainant_municipality") or payload.get("level_3_name"),
        "country_code": payload.get("country_code") or "NP",
        "location_code": location_code,
        "location_resolution_status": payload.get("location_resolution_status") or "mapped_partial",
        "level_1_name": payload.get("level_1_name"),
        "level_2_name": payload.get("level_2_name"),
        "level_3_name": payload.get("level_3_name"),
        "level_4_name": payload.get("level_4_name"),
        "level_5_name": payload.get("level_5_name"),
        "level_6_name": payload.get("level_6_name"),
        "level_1_code": payload.get("level_1_code"),
        "level_2_code": payload.get("level_2_code"),
        "level_3_code": payload.get("level_3_code"),
        "level_4_code": payload.get("level_4_code"),
        "level_5_code": payload.get("level_5_code"),
        "level_6_code": payload.get("level_6_code"),
        "location_geo": build_location_geo_json(
            lat,
            lng,
            location_code=location_code or geo_existing.get("location_code"),
            source="map_pin",
        ),
    }

    display_label = format_location_display_label(
        {
            **updates,
            "location_pin_status": "map_pin",
            "geo_lat": lat,
            "geo_lng": lng,
        }
    )
    if display_label:
        updates["grievance_location"] = display_label
    return updates


def should_enqueue_map_pin_geocode(data: Dict[str, Any]) -> bool:
    if data.get("location_resolution_status") != "map_pin":
        return False
    geo = parse_location_geo(data.get("location_geo"))
    return geo.get("lat") is not None and geo.get("lng") is not None


def enqueue_map_pin_geocode(
    *,
    complainant_id: str,
    grievance_id: str,
    lat: float,
    lng: float,
    lang_code: str = "en",
) -> bool:
    """Queue async reverse geocode (non-fatal if Celery/Redis unavailable)."""
    try:
        from ticketing.tasks.location_geocode import reverse_geocode_map_pin

        reverse_geocode_map_pin.apply_async(
            kwargs={
                "complainant_id": complainant_id,
                "grievance_id": grievance_id,
                "lat": float(lat),
                "lng": float(lng),
                "lang_code": lang_code or "en",
            },
            queue="grm_geocode",
        )
        logger.info(
            "map_pin_geocode enqueued grievance_id=%s complainant_id=%s",
            grievance_id,
            complainant_id,
        )
        return True
    except Exception as exc:
        logger.warning(
            "map_pin_geocode enqueue failed (non-fatal) grievance_id=%s: %s",
            grievance_id,
            exc,
        )
        return False


def apply_map_pin_geocode_to_db(
    db_manager: Any,
    *,
    complainant_id: str,
    grievance_id: str,
    lat: float,
    lng: float,
    lang_code: str = "en",
    respect_rate_limit: bool = True,
) -> Dict[str, Any]:
    """
    Run geocode + DB update synchronously (used by Celery task and tests).

    Idempotent: skips when municipality already mapped at level 3.
    """
    complainant = db_manager.get_complainant_by_id(complainant_id) if complainant_id else None
    if complainant:
        level_3 = (complainant.get("level_3_code") or "").strip()
        mun = (complainant.get("complainant_municipality") or "").strip()
        if (
            level_3
            and level_3 not in (NOT_PROVIDED, "Not provided")
            and mun
            and mun not in (NOT_PROVIDED, "Not provided", "")
        ):
            return {"status": "skipped", "reason": "already_geocoded"}

    payload = resolve_map_pin_location_payload(
        db_manager,
        lat,
        lng,
        lang_code=lang_code,
        respect_rate_limit=respect_rate_limit,
    )
    updates = build_complainant_geocode_update(
        payload,
        lat=lat,
        lng=lng,
        existing_location_geo=(complainant or {}).get("location_geo"),
    )

    complainant_fields = {
        k: v
        for k, v in updates.items()
        if k != "grievance_location" and v is not None
    }
    if complainant_fields and complainant_id:
        db_manager.update_complainant(complainant_id, complainant_fields)

    grievance_location = updates.get("grievance_location")
    if grievance_location and grievance_id:
        db_manager.update_grievance(grievance_id, {"grievance_location": grievance_location})

    deepest = int(payload.get("location_deepest_mapped_level") or 0)
    return {
        "status": "ok",
        "location_code": payload.get("location_code"),
        "deepest_mapped_level": deepest,
        "municipality": updates.get("complainant_municipality"),
    }


def is_retryable_geocode_error(exc: BaseException) -> bool:
    return isinstance(exc, (NominatimRateLimitError, NominatimUnavailableError))
