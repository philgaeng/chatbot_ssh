from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


LOCATION_LEVEL_SLOT_KEYS: List[Tuple[str, int]] = [
    ("complainant_province", 1),
    ("complainant_district", 2),
    ("complainant_municipality", 3),
    ("complainant_village", 4),
    ("complainant_ward", 5),
    ("complainant_address", 6),
]


def _normalize(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def resolve_location_payload(
    db_manager: Any,
    slots: Dict[str, Any],
    country_code: str = "NP",
) -> Dict[str, Any]:
    """
    Resolve location labels to ticketing location codes.

    Always returns a payload with level_n_name/level_n_code fields and
    non-blocking fallback behavior (free text preserved even when no mapping).
    """
    payload: Dict[str, Any] = {"country_code": country_code, "contact_id": slots.get("contact_id")}
    deepest_mapped_level = 0
    deepest_mapped_code: Optional[str] = None
    parent_code: Optional[str] = None
    had_any_name = False
    had_error = False

    for slot_key, level_number in LOCATION_LEVEL_SLOT_KEYS:
        name_key = f"level_{level_number}_name"
        code_key = f"level_{level_number}_code"
        slot_value = _normalize(slots.get(slot_key))
        payload[name_key] = slot_value
        payload[code_key] = None
        if slot_value:
            had_any_name = True

    for slot_key, level_number in LOCATION_LEVEL_SLOT_KEYS:
        candidate_name = payload[f"level_{level_number}_name"]
        if not candidate_name:
            continue
        try:
            if parent_code:
                rows = db_manager.execute_query(
                    """
                    SELECT l.location_code
                    FROM ticketing.locations l
                    JOIN ticketing.location_translations lt
                      ON lt.location_code = l.location_code
                    WHERE l.country_code = %s
                      AND l.level_number = %s
                      AND l.parent_location_code = %s
                      AND l.is_active = TRUE
                      AND LOWER(TRIM(lt.name)) = LOWER(TRIM(%s))
                    ORDER BY lt.lang_code = 'en' DESC, lt.lang_code
                    LIMIT 1
                    """,
                    (country_code, level_number, parent_code, candidate_name),
                    f"resolve_location_l{level_number}",
                )
            else:
                rows = db_manager.execute_query(
                    """
                    SELECT l.location_code
                    FROM ticketing.locations l
                    JOIN ticketing.location_translations lt
                      ON lt.location_code = l.location_code
                    WHERE l.country_code = %s
                      AND l.level_number = %s
                      AND l.is_active = TRUE
                      AND LOWER(TRIM(lt.name)) = LOWER(TRIM(%s))
                    ORDER BY lt.lang_code = 'en' DESC, lt.lang_code
                    LIMIT 1
                    """,
                    (country_code, level_number, candidate_name),
                    f"resolve_location_l{level_number}",
                )

            if rows:
                location_code = rows[0]["location_code"]
                payload[f"level_{level_number}_code"] = location_code
                parent_code = location_code
                deepest_mapped_level = level_number
                deepest_mapped_code = location_code
        except Exception:
            had_error = True

    if deepest_mapped_level == 0:
        resolution_status = "free_text_only"
    elif had_any_name and deepest_mapped_level < len(
        [1 for _, level_num in LOCATION_LEVEL_SLOT_KEYS if payload.get(f"level_{level_num}_name")]
    ):
        resolution_status = "mapped_partial"
    else:
        resolution_status = "mapped_full"

    if had_error and deepest_mapped_level == 0:
        resolution_status = "free_text_only"

    payload["location_code"] = deepest_mapped_code
    payload["location_resolution_status"] = resolution_status
    payload["location_deepest_mapped_level"] = deepest_mapped_level
    return payload
