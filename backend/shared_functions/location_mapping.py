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


def resolve_location_code_to_names(
    db_manager: Any,
    location_code: str,
    lang_code: str = "en",
) -> Dict[str, Optional[str]]:
    """Resolve a ticketing location_code to its district + province names.

    Best-effort: returns whatever can be resolved. Never raises.
    Output keys: district_code, district_name, province_code, province_name.

    Notes:
    - Designed for QR-scan pre-fill where the token resolves to a district code
      (level 2 in NP). When the supplied code is at a different level we still
      best-effort fill whichever names we can find for the code itself and its
      parent.
    """
    result: Dict[str, Optional[str]] = {
        "district_code": None,
        "district_name": None,
        "province_code": None,
        "province_name": None,
    }

    cleaned = _normalize(location_code)
    if not cleaned:
        return result

    try:
        rows = db_manager.execute_query(
            """
            SELECT
                l.location_code,
                l.parent_location_code,
                l.level_number,
                COALESCE(lt_pref.name, lt_en.name) AS name,
                COALESCE(parent_pref.name, parent_en.name) AS parent_name,
                p.location_code AS parent_code
            FROM ticketing.locations l
            LEFT JOIN ticketing.location_translations lt_pref
              ON lt_pref.location_code = l.location_code AND lt_pref.lang_code = %s
            LEFT JOIN ticketing.location_translations lt_en
              ON lt_en.location_code = l.location_code AND lt_en.lang_code = 'en'
            LEFT JOIN ticketing.locations p
              ON p.location_code = l.parent_location_code
            LEFT JOIN ticketing.location_translations parent_pref
              ON parent_pref.location_code = p.location_code AND parent_pref.lang_code = %s
            LEFT JOIN ticketing.location_translations parent_en
              ON parent_en.location_code = p.location_code AND parent_en.lang_code = 'en'
            WHERE l.location_code = %s
              AND l.is_active = TRUE
            LIMIT 1
            """,
            (lang_code, lang_code, cleaned),
            "resolve_location_code_to_names",
        )
    except Exception:
        return result

    if not rows:
        return result

    row = rows[0]
    level = row.get("level_number")

    # Level 2 = district in Nepal. Anything else is best-effort.
    if level == 2:
        result["district_code"] = row.get("location_code")
        result["district_name"] = row.get("name")
        result["province_code"] = row.get("parent_code")
        result["province_name"] = row.get("parent_name")
    elif level == 1:
        result["province_code"] = row.get("location_code")
        result["province_name"] = row.get("name")
    else:
        result["district_code"] = row.get("location_code")
        result["district_name"] = row.get("name")
        result["province_code"] = row.get("parent_code")
        result["province_name"] = row.get("parent_name")

    return result


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
