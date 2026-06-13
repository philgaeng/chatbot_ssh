from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import process

from backend.config.constants import CUT_OFF_FUZZY_MATCH_LOCATION, DIC_LOCATION_WORDS

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


_LEVEL_SUFFIX_KEY = {1: "province", 2: "district", 3: "municipality"}

_EXTRA_EN_SUFFIXES = (
    "Metropolitan City",
    "Sub-Metropolitan City",
    "Sub Metropolitan City",
    "Rural Municipality",
    " City",
)


def strip_admin_suffix(name: str, level_number: int) -> str:
    """Strip province/district/municipality suffix words (EN + NE) for fuzzy compare."""
    text = (name or "").strip()
    if not text:
        return ""

    suffix_key = _LEVEL_SUFFIX_KEY.get(level_number)
    if suffix_key:
        for lang_words in DIC_LOCATION_WORDS.get(suffix_key, {}).values():
            for word in lang_words:
                for variant in (word, word.title(), word.upper()):
                    text = text.replace(variant, " ")

    if level_number == 3:
        for extra in _EXTRA_EN_SUFFIXES:
            text = text.replace(extra, " ")

    return " ".join(text.split()).strip()


def _fetch_location_candidates(
    db_manager: Any,
    *,
    country_code: str,
    level_number: int,
    parent_code: Optional[str],
) -> List[Dict[str, str]]:
    try:
        if parent_code:
            rows = db_manager.execute_query(
                """
                SELECT l.location_code, lt.lang_code, lt.name
                FROM ticketing.locations l
                JOIN ticketing.location_translations lt
                  ON lt.location_code = l.location_code
                WHERE l.country_code = %s
                  AND l.level_number = %s
                  AND l.parent_location_code = %s
                  AND l.is_active = TRUE
                ORDER BY lt.lang_code = 'en' DESC, lt.lang_code, lt.name
                """,
                (country_code, level_number, parent_code),
                f"fetch_location_candidates_l{level_number}",
            )
        else:
            rows = db_manager.execute_query(
                """
                SELECT l.location_code, lt.lang_code, lt.name
                FROM ticketing.locations l
                JOIN ticketing.location_translations lt
                  ON lt.location_code = l.location_code
                WHERE l.country_code = %s
                  AND l.level_number = %s
                  AND l.is_active = TRUE
                ORDER BY lt.lang_code = 'en' DESC, lt.lang_code, lt.name
                """,
                (country_code, level_number),
                f"fetch_location_candidates_l{level_number}",
            )
    except Exception:
        return []

    # Prefer English row per location_code; keep all for fuzzy.
    return [dict(r) for r in rows or []]


def _resolve_location_code_by_name(
    db_manager: Any,
    *,
    country_code: str,
    level_number: int,
    candidate_name: str,
    parent_code: Optional[str],
) -> Optional[str]:
    """
    Resolve admin label → location_code: exact DB name first, then fuzzy on stripped names.
    """
    cleaned = _normalize(candidate_name)
    if not cleaned:
        return None

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
                (country_code, level_number, parent_code, cleaned),
                f"resolve_location_exact_l{level_number}",
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
                (country_code, level_number, cleaned),
                f"resolve_location_exact_l{level_number}",
            )
        if rows:
            return rows[0]["location_code"]
    except Exception:
        pass

    candidates = _fetch_location_candidates(
        db_manager,
        country_code=country_code,
        level_number=level_number,
        parent_code=parent_code,
    )
    if not candidates:
        return None

    needle = strip_admin_suffix(cleaned, level_number).lower()
    if not needle:
        needle = cleaned.lower()

    # Build unique options: stripped label → location_code (prefer en translation).
    options: Dict[str, str] = {}
    canonical_name: Dict[str, str] = {}
    for row in candidates:
        code = row["location_code"]
        label = row["name"] or ""
        stripped = strip_admin_suffix(label, level_number).lower() or label.lower()
        if stripped not in options:
            options[stripped] = code
        if row.get("lang_code") == "en" or code not in canonical_name:
            canonical_name[code] = label

    if not options:
        return None

    match = process.extractOne(
        needle,
        list(options.keys()),
        score_cutoff=CUT_OFF_FUZZY_MATCH_LOCATION,
    )
    if match:
        return options[match[0]]

    # Also try fuzzy on full (unstripped) DB names.
    full_options = { (r["name"] or "").lower(): r["location_code"] for r in candidates if r.get("name") }
    match_full = process.extractOne(
        cleaned.lower(),
        list(full_options.keys()),
        score_cutoff=CUT_OFF_FUZZY_MATCH_LOCATION,
    )
    if match_full:
        return full_options[match_full[0]]

    return None


def resolve_location_hierarchy_from_code(
    db_manager: Any,
    location_code: str,
    lang_code: str = "en",
) -> Dict[str, Any]:
    """Walk parents from deepest code; return level_n_name/code fields for all ancestors."""
    payload: Dict[str, Any] = {}
    code = _normalize(location_code)
    if not code:
        return payload

    try:
        rows = db_manager.execute_query(
            """
            WITH RECURSIVE chain AS (
                SELECT location_code, parent_location_code, level_number
                FROM ticketing.locations
                WHERE location_code = %s AND is_active = TRUE
              UNION ALL
                SELECT l.location_code, l.parent_location_code, l.level_number
                FROM ticketing.locations l
                JOIN chain c ON l.location_code = c.parent_location_code
                WHERE l.is_active = TRUE
            )
            SELECT
                c.level_number,
                c.location_code,
                COALESCE(lt_pref.name, lt_en.name) AS name
            FROM chain c
            LEFT JOIN ticketing.location_translations lt_pref
              ON lt_pref.location_code = c.location_code AND lt_pref.lang_code = %s
            LEFT JOIN ticketing.location_translations lt_en
              ON lt_en.location_code = c.location_code AND lt_en.lang_code = 'en'
            ORDER BY c.level_number
            """,
            (code, lang_code),
            "resolve_location_hierarchy_from_code",
        )
    except Exception:
        return payload

    for row in rows or []:
        level = int(row.get("level_number") or 0)
        if level <= 0:
            continue
        payload[f"level_{level}_name"] = row.get("name")
        payload[f"level_{level}_code"] = row.get("location_code")

    return payload


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
            location_code = _resolve_location_code_by_name(
                db_manager,
                country_code=country_code,
                level_number=level_number,
                candidate_name=candidate_name,
                parent_code=parent_code,
            )
            if location_code:
                payload[f"level_{level_number}_code"] = location_code
                parent_code = location_code
                deepest_mapped_level = level_number
                deepest_mapped_code = location_code
        except Exception:
            had_error = True

    if deepest_mapped_code and deepest_mapped_level >= 1:
        hierarchy = resolve_location_hierarchy_from_code(
            db_manager,
            deepest_mapped_code,
            lang_code=slots.get("language_code") or "en",
        )
        for key, value in hierarchy.items():
            if value and not payload.get(key):
                payload[key] = value

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


def resolve_pin_to_location_code(
    db_manager: Any,
    lat: float,
    lng: float,
    country_code: str = "NP",
) -> Optional[str]:
    """
    Best-effort: map pin to nearest ticketing location_code (district level).
    Returns None when geodata is unavailable — pin coords are still stored on grievance.
    """
    try:
        rows = db_manager.execute_query(
            """
            SELECT location_code
            FROM ticketing.locations
            WHERE country_code = %s
              AND level_number = 2
              AND is_active = TRUE
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            ORDER BY (
              (latitude - %s) * (latitude - %s) + (longitude - %s) * (longitude - %s)
            )
            LIMIT 1
            """,
            (country_code, lat, lat, lng, lng),
            "resolve_pin_to_location_code",
        )
        if rows:
            return rows[0].get("location_code")
    except Exception:
        pass
    return None
