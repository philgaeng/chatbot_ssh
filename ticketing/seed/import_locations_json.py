"""
Import locations from paired EN/NE JSON files into ticketing.locations + location_translations.

Usage (from repo root, with ticketing DB env vars set):
    python -m ticketing.seed.import_locations_json \\
        --country NP \\
        --en  backend/dev-resources/location_dataset/en_cleaned.json \\
        --ne  backend/dev-resources/location_dataset/ne_cleaned.json \\
        [--max-level 3]   # default 3: Province/District/Municipality (skip Wards)
        [--dry-run]

Idempotent: uses ON CONFLICT DO NOTHING / DO UPDATE so safe to re-run.

Location code scheme (deterministic from source IDs):
    Province     → NP_P{province_id}           e.g. NP_P1
    District     → NP_D{district_id:03d}       e.g. NP_D001
    Municipality → NP_M{municipality_id:04d}   e.g. NP_M0001

To add a new country: supply your own en/local JSON files and set --country XX.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


def _loc_code(country: str, level: int, source_id: int) -> str:
    if level == 1:
        return f"{country}_P{source_id}"
    if level == 2:
        return f"{country}_D{source_id:03d}"
    if level == 3:
        return f"{country}_M{source_id:04d}"
    return f"{country}_L{level}_{source_id:05d}"


def load_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_translation_index(data: list[dict]) -> dict[tuple[int, int], str]:
    """
    Returns a dict keyed by (level, source_id) → name.
    Walks province → district → municipality.
    """
    index: dict[tuple[int, int], str] = {}
    for prov in data:
        index[(1, prov["id"])] = prov["name"]
        for dist in prov.get("districts", []):
            index[(2, dist["id"])] = dist["name"]
            for muni in dist.get("municipalities", []):
                index[(3, muni["id"])] = muni["name"]
    return index


def collect_nodes(
    en_data: list[dict],
    translations: dict[str, dict[tuple[int, int], str]],
    country: str,
    max_level: int,
) -> tuple[list[dict], list[dict]]:
    """
    Returns (location_rows, translation_rows).
    """
    locations: list[dict] = []
    trans: list[dict] = []
    now = _now()

    for prov in en_data:
        if max_level < 1:
            break
        p_code = _loc_code(country, 1, prov["id"])
        locations.append({
            "location_code": p_code,
            "country_code": country,
            "level_number": 1,
            "parent_location_code": None,
            "source_id": prov["id"],
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        })
        for lang, idx in translations.items():
            name = idx.get((1, prov["id"]))
            if name:
                trans.append({"location_code": p_code, "lang_code": lang, "name": name.strip()})

        if max_level < 2:
            continue
        for dist in prov.get("districts", []):
            d_code = _loc_code(country, 2, dist["id"])
            locations.append({
                "location_code": d_code,
                "country_code": country,
                "level_number": 2,
                "parent_location_code": p_code,
                "source_id": dist["id"],
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            })
            for lang, idx in translations.items():
                name = idx.get((2, dist["id"]))
                if name:
                    trans.append({"location_code": d_code, "lang_code": lang, "name": name.strip()})

            if max_level < 3:
                continue
            for muni in dist.get("municipalities", []):
                m_code = _loc_code(country, 3, muni["id"])
                locations.append({
                    "location_code": m_code,
                    "country_code": country,
                    "level_number": 3,
                    "parent_location_code": d_code,
                    "source_id": muni["id"],
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                })
                for lang, idx in translations.items():
                    name = idx.get((3, muni["id"]))
                    if name:
                        trans.append({"location_code": m_code, "lang_code": lang, "name": name.strip()})

    return locations, trans


def run(
    country: str,
    en_path: str,
    extra_langs: dict[str, str],  # lang_code → file path
    max_level: int,
    dry_run: bool,
) -> None:
    log.info("Loading EN data from %s", en_path)
    en_data = load_json(en_path)

    translations: dict[str, dict[tuple[int, int], str]] = {
        "en": build_translation_index(en_data)
    }
    for lang, path in extra_langs.items():
        log.info("Loading %s data from %s", lang, path)
        translations[lang] = build_translation_index(load_json(path))

    location_rows, trans_rows = collect_nodes(en_data, translations, country, max_level)
    log.info("Collected %d location nodes, %d translation rows", len(location_rows), len(trans_rows))

    if dry_run:
        log.info("DRY RUN — not writing to DB")
        for r in location_rows[:5]:
            log.info("  location: %s", r)
        for r in trans_rows[:5]:
            log.info("  translation: %s", r)
        return

    # DB write
    import os
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ticketing.models.base import SessionLocal
    from ticketing.models.country import Country, Location, LocationTranslation

    db = SessionLocal()
    try:
        # Ensure country row exists
        if not db.get(Country, country):
            raise ValueError(
                f"Country '{country}' not found in ticketing.countries. "
                "Run migration f1a3e9c72b05 first, or insert the country manually."
            )

        batch = 500
        inserted_locs = upserted_trans = 0

        # Locations (upsert: insert ignore on conflict, update source_id/level/parent)
        for i in range(0, len(location_rows), batch):
            chunk = location_rows[i : i + batch]
            db.execute(
                __import__("sqlalchemy").text("""
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
                """),
                chunk,
            )
            inserted_locs += len(chunk)
            db.commit()

        # Translations (upsert: update name on conflict)
        for i in range(0, len(trans_rows), batch):
            chunk = trans_rows[i : i + batch]
            db.execute(
                __import__("sqlalchemy").text("""
                    INSERT INTO ticketing.location_translations (location_code, lang_code, name)
                    VALUES (:location_code, :lang_code, :name)
                    ON CONFLICT (location_code, lang_code) DO UPDATE SET name = EXCLUDED.name
                """),
                chunk,
            )
            upserted_trans += len(chunk)
            db.commit()

        log.info("Done — %d locations upserted, %d translations upserted", inserted_locs, upserted_trans)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import locations from JSON into ticketing DB")
    parser.add_argument("--country",   default="NP",  help="Country code (default: NP)")
    parser.add_argument("--en",        required=True, help="Path to English JSON file")
    parser.add_argument("--ne",        help="Path to Nepali JSON file (lang_code=ne)")
    parser.add_argument("--lang",      action="append", nargs=2, metavar=("CODE", "FILE"),
                        help="Additional language: --lang fr path/to/fr.json  (repeatable)")
    parser.add_argument("--max-level", type=int, default=3,
                        help="Max level to import (1=Province, 2=District, 3=Municipality). Default 3.")
    parser.add_argument("--dry-run",   action="store_true", help="Preview without writing")
    args = parser.parse_args()

    extra_langs: dict[str, str] = {}
    if args.ne:
        extra_langs["ne"] = args.ne
    if args.lang:
        for code, path in args.lang:
            extra_langs[code] = path

    run(
        country=args.country,
        en_path=args.en,
        extra_langs=extra_langs,
        max_level=args.max_level,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
