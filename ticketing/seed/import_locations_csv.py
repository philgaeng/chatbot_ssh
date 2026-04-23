"""
Import locations from a flat CSV file into ticketing.locations + location_translations.

Usage (from repo root, with ticketing DB env vars set):
    python -m ticketing.seed.import_locations_csv \\
        --country NP \\
        --csv  backend/dev-resources/location_dataset/locations.csv \\
        [--code-col     location_code]   # default: 'location_code'
        [--parent-col   parent_location_code]
        [--level-col    level_number]
        [--source-col   source_id]
        [--active-col   is_active]
        [--lang-prefix  name_]           # default: auto-detect 'name_*' columns
        [--max-level 3]                  # skip rows with level_number > max (default: no limit)
        [--dry-run]

CSV format example:

    location_code,level_number,parent_location_code,source_id,name_en,name_ne
    NP_P1,1,,1,Koshi Province,कोशी
    NP_D001,2,NP_P1,1,Bhojpur,भोजपुर
    NP_M0001,3,NP_D001,1,Shadanand Municipality,शदानन्द नगरपालिका

Language columns are auto-detected by the 'name_' prefix.
Download a pre-formatted template from GET /api/v1/locations/import/template.csv

Core parsing/upsert logic lives in location_import_core.py.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ticketing.seed.location_import_core import parse_csv, upsert_locations

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def run(
    country: str,
    csv_path: str,
    code_col: str,
    parent_col: str,
    level_col: str,
    source_col: str,
    active_col: str,
    country_col: str,
    lang_prefix: str,
    explicit_langs: dict[str, str],
    max_level: int | None,
    dry_run: bool,
) -> None:
    log.info("Loading CSV from %s", csv_path)

    with open(csv_path, encoding="utf-8-sig") as f:
        content = f.read()

    location_rows, trans_rows = parse_csv(
        content,
        country_default=country,
        code_col=code_col,
        parent_col=parent_col,
        level_col=level_col,
        source_col=source_col,
        active_col=active_col,
        country_col=country_col,
        lang_prefix=lang_prefix,
        explicit_langs=explicit_langs,
        max_level=max_level,
    )
    log.info("Parsed %d location rows, %d translation rows", len(location_rows), len(trans_rows))

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
    parser = argparse.ArgumentParser(
        description="Import locations from a flat CSV into ticketing DB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--country",      default="NP",                   help="Default country code (default: NP)")
    parser.add_argument("--csv",          required=True,                  help="Path to the CSV file")
    parser.add_argument("--code-col",     default="location_code",        help="Column name for location_code")
    parser.add_argument("--parent-col",   default="parent_location_code", help="Column name for parent_location_code")
    parser.add_argument("--level-col",    default="level_number",         help="Column name for level_number")
    parser.add_argument("--source-col",   default="source_id",            help="Column name for source_id (optional)")
    parser.add_argument("--active-col",   default="is_active",            help="Column name for is_active")
    parser.add_argument("--country-col",  default="country_code",         help="Column name for country_code (falls back to --country)")
    parser.add_argument("--lang-prefix",  default="name_",                help="Column prefix for language columns (default: name_)")
    parser.add_argument("--lang",         action="append", nargs=2, metavar=("CODE", "COLUMN"),
                        help="Explicit language column: --lang en english_name  (repeatable)")
    parser.add_argument("--max-level",    type=int, default=None,         help="Skip rows with level_number > this value")
    parser.add_argument("--dry-run",      action="store_true",            help="Preview without writing to DB")
    args = parser.parse_args()

    explicit_langs: dict[str, str] = {}
    if args.lang:
        for code, col in args.lang:
            explicit_langs[code] = col

    run(
        country=args.country,
        csv_path=args.csv,
        code_col=args.code_col,
        parent_col=args.parent_col,
        level_col=args.level_col,
        source_col=args.source_col,
        active_col=args.active_col,
        country_col=args.country_col,
        lang_prefix=args.lang_prefix,
        explicit_langs=explicit_langs,
        max_level=args.max_level,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
