"""
Shared parsing + DB-write logic for location imports.

Consumed by:
  - CLI scripts (import_locations_json.py, import_locations_csv.py)
  - API upload endpoint (POST /api/v1/locations/import)

All functions accept in-memory data so no temp files are needed when called
from the API — the caller handles file I/O.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


# ── Deterministic location code scheme ───────────────────────────────────────

def loc_code(country: str, level: int, source_id: int) -> str:
    if level == 1:
        return f"{country}_P{source_id}"
    if level == 2:
        return f"{country}_D{source_id:03d}"
    if level == 3:
        return f"{country}_M{source_id:04d}"
    return f"{country}_L{level}_{source_id:05d}"


# ── JSON parsing ──────────────────────────────────────────────────────────────

def build_translation_index(data: list[dict]) -> dict[tuple[int, int], str]:
    """Index (level, source_id) → name from a nested province/district/muni JSON."""
    index: dict[tuple[int, int], str] = {}
    for prov in data:
        index[(1, prov["id"])] = prov["name"]
        for dist in prov.get("districts", []):
            index[(2, dist["id"])] = dist["name"]
            for muni in dist.get("municipalities", []):
                index[(3, muni["id"])] = muni["name"]
    return index


def parse_json(
    en_data: list[dict],
    extra_lang_data: dict[str, list[dict]],   # lang_code → parsed JSON list
    country: str,
    max_level: int = 3,
) -> tuple[list[dict], list[dict]]:
    """
    Parse nested province/district/municipality JSON into flat rows.
    Returns (location_rows, translation_rows).
    """
    translations: dict[str, dict[tuple[int, int], str]] = {
        "en": build_translation_index(en_data)
    }
    for lang, data in extra_lang_data.items():
        translations[lang] = build_translation_index(data)

    locations: list[dict] = []
    trans: list[dict] = []
    now = _now()

    for prov in en_data:
        if max_level < 1:
            break
        p_code = loc_code(country, 1, prov["id"])
        locations.append({
            "location_code": p_code, "country_code": country,
            "level_number": 1, "parent_location_code": None,
            "source_id": prov["id"], "is_active": True,
            "created_at": now, "updated_at": now,
        })
        for lang, idx in translations.items():
            name = idx.get((1, prov["id"]))
            if name:
                trans.append({"location_code": p_code, "lang_code": lang, "name": name.strip()})

        if max_level < 2:
            continue
        for dist in prov.get("districts", []):
            d_code = loc_code(country, 2, dist["id"])
            locations.append({
                "location_code": d_code, "country_code": country,
                "level_number": 2, "parent_location_code": p_code,
                "source_id": dist["id"], "is_active": True,
                "created_at": now, "updated_at": now,
            })
            for lang, idx in translations.items():
                name = idx.get((2, dist["id"]))
                if name:
                    trans.append({"location_code": d_code, "lang_code": lang, "name": name.strip()})

            if max_level < 3:
                continue
            for muni in dist.get("municipalities", []):
                m_code = loc_code(country, 3, muni["id"])
                locations.append({
                    "location_code": m_code, "country_code": country,
                    "level_number": 3, "parent_location_code": d_code,
                    "source_id": muni["id"], "is_active": True,
                    "created_at": now, "updated_at": now,
                })
                for lang, idx in translations.items():
                    name = idx.get((3, muni["id"]))
                    if name:
                        trans.append({"location_code": m_code, "lang_code": lang, "name": name.strip()})

    return locations, trans


# ── CSV parsing ───────────────────────────────────────────────────────────────

def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() not in ("false", "0", "no", "")


def detect_lang_columns(
    header: list[str],
    prefix: str,
    explicit: dict[str, str],
) -> dict[str, str]:
    """Return lang_code → csv_column_name mapping."""
    detected: dict[str, str] = {}
    for col in header:
        if col.startswith(prefix):
            lang = col[len(prefix):]
            if lang:
                detected[lang] = col
    detected.update(explicit)
    return detected


def parse_csv(
    content: str,
    *,
    country_default: str,
    code_col: str = "location_code",
    parent_col: str = "parent_location_code",
    level_col: str = "level_number",
    source_col: str = "source_id",
    active_col: str = "is_active",
    country_col: str = "country_code",
    lang_prefix: str = "name_",
    explicit_langs: dict[str, str] | None = None,
    max_level: int | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Parse a flat CSV string into (location_rows, translation_rows).
    Language columns are auto-detected by lang_prefix (default 'name_').
    """
    explicit_langs = explicit_langs or {}
    locations: list[dict] = []
    trans: list[dict] = []
    now = _now()

    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        raise ValueError("CSV appears empty — no header row found")

    header = list(reader.fieldnames)
    resolved_langs = detect_lang_columns(header, lang_prefix, explicit_langs)
    if not resolved_langs:
        log.warning("No language columns found with prefix %r — importing locations without translations", lang_prefix)

    skipped = 0
    for row_num, row in enumerate(reader, start=2):
        code = row.get(code_col, "").strip()
        if not code:
            skipped += 1
            continue

        raw_level = row.get(level_col, "").strip()
        try:
            level = int(raw_level)
        except (ValueError, TypeError):
            log.warning("Row %d (%s): invalid level %r — skipped", row_num, code, raw_level)
            skipped += 1
            continue

        if max_level is not None and level > max_level:
            skipped += 1
            continue

        country = row.get(country_col, "").strip() or country_default
        parent = row.get(parent_col, "").strip() or None

        raw_source = row.get(source_col, "").strip()
        source_id: int | None = None
        if raw_source:
            try:
                source_id = int(raw_source)
            except ValueError:
                pass

        is_active = _parse_bool(row.get(active_col, "true"))

        locations.append({
            "location_code": code, "country_code": country,
            "level_number": level, "parent_location_code": parent,
            "source_id": source_id, "is_active": is_active,
            "created_at": now, "updated_at": now,
        })
        for lang, col_name in resolved_langs.items():
            name = row.get(col_name, "").strip()
            if name:
                trans.append({"location_code": code, "lang_code": lang, "name": name})

    if skipped:
        log.info("Skipped %d row(s) (level filter or missing data)", skipped)

    return locations, trans


# ── DB upsert (works with any SQLAlchemy Session) ─────────────────────────────

def upsert_locations(
    location_rows: list[dict],
    trans_rows: list[dict],
    db: Any,               # sqlalchemy.orm.Session
    batch_size: int = 500,
) -> dict[str, int]:
    """
    Upsert location_rows into ticketing.locations and trans_rows into
    ticketing.location_translations.  Uses the caller-supplied session
    (no new session created, no commit of caller's outer transaction).

    Returns {"locations": N, "translations": N}.
    """
    import sqlalchemy as sa

    loc_sql = sa.text("""
        INSERT INTO ticketing.locations
            (location_code, country_code, level_number, parent_location_code,
             source_id, is_active, created_at, updated_at)
        VALUES
            (:location_code, :country_code, :level_number, :parent_location_code,
             :source_id, :is_active, :created_at, :updated_at)
        ON CONFLICT (location_code) DO UPDATE SET
            level_number         = EXCLUDED.level_number,
            parent_location_code = EXCLUDED.parent_location_code,
            source_id            = EXCLUDED.source_id,
            is_active            = EXCLUDED.is_active,
            updated_at           = EXCLUDED.updated_at
    """)

    trans_sql = sa.text("""
        INSERT INTO ticketing.location_translations (location_code, lang_code, name)
        VALUES (:location_code, :lang_code, :name)
        ON CONFLICT (location_code, lang_code) DO UPDATE SET name = EXCLUDED.name
    """)

    inserted_locs = 0
    for i in range(0, len(location_rows), batch_size):
        db.execute(loc_sql, location_rows[i : i + batch_size])
        inserted_locs += len(location_rows[i : i + batch_size])
    db.flush()   # flush within caller's transaction; caller commits

    upserted_trans = 0
    for i in range(0, len(trans_rows), batch_size):
        db.execute(trans_sql, trans_rows[i : i + batch_size])
        upserted_trans += len(trans_rows[i : i + batch_size])
    db.flush()

    log.info("upsert_locations: %d locations, %d translations", inserted_locs, upserted_trans)
    return {"locations": inserted_locs, "translations": upserted_trans}


# ── Download templates ────────────────────────────────────────────────────────

CSV_TEMPLATE = """\
location_code,level_number,parent_location_code,source_id,name_en,name_local
XX_P1,1,,1,Province Name,स्थानीय नाम
XX_D001,2,XX_P1,1,District Name,जिल्लाको नाम
XX_M0001,3,XX_D001,1,Municipality Name,नगरपालिकाको नाम
"""

# Minimal nested JSON matching the Nepal source format (en_cleaned.json)
JSON_TEMPLATE: list[dict] = [
    {
        "id": 1,
        "name": "Province Name",
        "districts": [
            {
                "id": 1,
                "name": "District Name",
                "municipalities": [
                    {"id": 1, "name": "Municipality Name"},
                ],
            }
        ],
    }
]
