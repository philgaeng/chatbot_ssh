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

CSV format (column names are configurable via flags above):

    location_code,country_code,level_number,parent_location_code,source_id,name_en,name_ne
    NP_P1,NP,1,,1,Koshi Province,कोशी प्रदेश
    NP_D001,NP,2,NP_P1,1,Bhojpur,भोजपुर
    NP_M0001,NP,3,NP_D001,1,Shadanand Municipality,शदानन्द नगरपालिका

Language columns are auto-detected by the 'name_' prefix (or whatever --lang-prefix is set to).
Extracted lang_code = column_name[len(prefix):], e.g. 'name_en' → 'en', 'name_ne' → 'ne'.

You can also specify individual language columns explicitly:
    --lang en name_english --lang ne name_nepali

Idempotent: uses ON CONFLICT DO NOTHING / DO UPDATE so safe to re-run.
"""
from __future__ import annotations

import argparse
import csv
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


def _parse_bool(value: str) -> bool:
    return value.strip().lower() not in ("false", "0", "no", "")


def detect_lang_columns(
    header: list[str],
    prefix: str,
    explicit: dict[str, str],
) -> dict[str, str]:
    """
    Returns mapping: lang_code → csv_column_name.
    Starts with auto-detected prefix columns, then adds/overrides with explicit mappings.
    """
    detected: dict[str, str] = {}
    for col in header:
        if col.startswith(prefix):
            lang = col[len(prefix):]
            if lang:
                detected[lang] = col
    detected.update(explicit)
    return detected


def load_csv(
    path: str,
    *,
    code_col: str,
    parent_col: str,
    level_col: str,
    source_col: str,
    active_col: str,
    country_col: str,
    country_default: str,
    lang_cols: dict[str, str],  # lang_code → csv column name; filled in after header read
    lang_prefix: str,
    explicit_langs: dict[str, str],
    max_level: int | None,
) -> tuple[list[dict], list[dict]]:
    """
    Reads the CSV and returns (location_rows, translation_rows).
    """
    locations: list[dict] = []
    trans: list[dict] = []
    now = _now()

    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV file appears empty: {path}")

        header = list(reader.fieldnames)
        log.info("CSV columns: %s", header)

        # Resolve language columns from header
        resolved_langs = detect_lang_columns(header, lang_prefix, explicit_langs)
        if resolved_langs:
            log.info("Language columns detected: %s", resolved_langs)
        else:
            log.warning(
                "No language columns found (prefix=%r). Locations will be imported "
                "without any translations.", lang_prefix
            )

        skipped = 0
        for row_num, row in enumerate(reader, start=2):  # 2 = first data row
            # Required: location_code
            code = row.get(code_col, "").strip()
            if not code:
                log.warning("Row %d: missing %r — skipped", row_num, code_col)
                skipped += 1
                continue

            # level_number
            raw_level = row.get(level_col, "").strip()
            try:
                level = int(raw_level)
            except (ValueError, TypeError):
                log.warning("Row %d (%s): invalid %r=%r — skipped", row_num, code, level_col, raw_level)
                skipped += 1
                continue

            if max_level is not None and level > max_level:
                skipped += 1
                continue

            # country_code
            country = row.get(country_col, "").strip() or country_default

            # parent
            parent = row.get(parent_col, "").strip() or None

            # source_id
            raw_source = row.get(source_col, "").strip()
            source_id: int | None = None
            if raw_source:
                try:
                    source_id = int(raw_source)
                except ValueError:
                    log.warning("Row %d (%s): non-integer %r=%r — set to None", row_num, code, source_col, raw_source)

            # is_active
            raw_active = row.get(active_col, "true")
            is_active = _parse_bool(str(raw_active))

            locations.append({
                "location_code":        code,
                "country_code":         country,
                "level_number":         level,
                "parent_location_code": parent,
                "source_id":            source_id,
                "is_active":            is_active,
                "created_at":           now,
                "updated_at":           now,
            })

            for lang, col_name in resolved_langs.items():
                name = row.get(col_name, "").strip()
                if name:
                    trans.append({
                        "location_code": code,
                        "lang_code":     lang,
                        "name":          name,
                    })

    if skipped:
        log.info("Skipped %d row(s) (level filter or missing code/level)", skipped)
    return locations, trans


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

    location_rows, trans_rows = load_csv(
        csv_path,
        code_col=code_col,
        parent_col=parent_col,
        level_col=level_col,
        source_col=source_col,
        active_col=active_col,
        country_col=country_col,
        country_default=country,
        lang_cols={},         # placeholder; resolved inside load_csv
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
        # Ensure country row exists
        if not db.get(Country, country):
            raise ValueError(
                f"Country '{country}' not found in ticketing.countries. "
                "Run migration f1a3e9c72b05 first, or insert the country manually."
            )

        batch = 500
        inserted_locs = upserted_trans = 0

        # Locations (upsert)
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

        # Translations (upsert)
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
    parser = argparse.ArgumentParser(
        description="Import locations from a flat CSV into ticketing DB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--country",      default="NP",               help="Default country code when csv has no country column (default: NP)")
    parser.add_argument("--csv",          required=True,              help="Path to the CSV file")
    parser.add_argument("--code-col",     default="location_code",    help="Column name for location_code (default: location_code)")
    parser.add_argument("--parent-col",   default="parent_location_code", help="Column name for parent_location_code")
    parser.add_argument("--level-col",    default="level_number",     help="Column name for level_number")
    parser.add_argument("--source-col",   default="source_id",        help="Column name for source_id (optional)")
    parser.add_argument("--active-col",   default="is_active",        help="Column name for is_active (default: true if missing)")
    parser.add_argument("--country-col",  default="country_code",     help="Column name for country_code (falls back to --country)")
    parser.add_argument("--lang-prefix",  default="name_",            help="Column prefix for language columns, e.g. 'name_' matches name_en, name_ne (default: name_)")
    parser.add_argument("--lang",         action="append", nargs=2, metavar=("CODE", "COLUMN"),
                        help="Explicit language column: --lang en english_name  (repeatable, overrides prefix detection)")
    parser.add_argument("--max-level",    type=int, default=None,     help="Skip rows with level_number > this value (default: no limit)")
    parser.add_argument("--dry-run",      action="store_true",        help="Preview without writing to DB")
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
