"""
Import locations from paired EN/NE JSON files into ticketing.locations + location_translations.

Usage (from repo root, with ticketing DB env vars set):
    python -m ticketing.seed.import_locations_json \\
        --country NP \\
        --en  backend/dev-resources/location_dataset/en_cleaned.json \\
        --ne  backend/dev-resources/location_dataset/ne_cleaned.json \\
        [--max-level 3]   # default 3: Province/District/Municipality (skip Wards)
        [--dry-run]

Idempotent: uses ON CONFLICT DO UPDATE so safe to re-run.

Location code scheme (deterministic from source IDs):
    Province     → NP_P{province_id}           e.g. NP_P1
    District     → NP_D{district_id:03d}       e.g. NP_D001
    Municipality → NP_M{municipality_id:04d}   e.g. NP_M0001

Core parsing/upsert logic lives in location_import_core.py.
To add a new country: supply your own en/local JSON files and set --country XX.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from ticketing.seed.location_import_core import parse_json, upsert_locations

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def load_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run(
    country: str,
    en_path: str,
    extra_langs: dict[str, str],  # lang_code → file path
    max_level: int,
    dry_run: bool,
) -> None:
    log.info("Loading EN data from %s", en_path)
    en_data = load_json(en_path)

    extra_lang_data: dict[str, list[dict]] = {}
    for lang, path in extra_langs.items():
        log.info("Loading %s data from %s", lang, path)
        extra_lang_data[lang] = load_json(path)

    location_rows, trans_rows = parse_json(en_data, extra_lang_data, country, max_level)
    log.info("Collected %d location nodes, %d translation rows", len(location_rows), len(trans_rows))

    if dry_run:
        log.info("DRY RUN — not writing to DB")
        for r in location_rows[:5]:
            log.info("  location: %s", r)
        for r in trans_rows[:5]:
            log.info("  translation: %s", r)
        return

    # DB write
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from ticketing.models.base import SessionLocal
    from ticketing.models.country import Country

    db = SessionLocal()
    try:
        if not db.get(Country, country):
            raise ValueError(
                f"Country '{country}' not found in ticketing.countries. "
                "Run migration f1a3e9c72b05 first, or insert the country manually."
            )
        counts = upsert_locations(location_rows, trans_rows, db)
        db.commit()
        log.info("Done — %d locations upserted, %d translations upserted",
                 counts["locations"], counts["translations"])
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
