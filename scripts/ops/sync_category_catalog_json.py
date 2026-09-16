#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""
D-58 — the grievance taxonomy is authored twice, and the copies had drifted for two months.

    python scripts/ops/sync_category_catalog_json.py           # rewrite the JSON from the CSV
    python scripts/ops/sync_category_catalog_json.py --check   # report only, exit 1 on drift

**The two files.**

  * `backend/dev-resources/grievances_categorization_v1.1.csv` — the authored taxonomy. Read by
    `backend/config/constants.py` and `dev-scripts/seed_reference_data.py`.
  * `ticketing/constants/grievance_categories_default.json` — the bundled default catalog, loaded
    by `load_default_catalog()` and pushed into `public.grievance_classification_taxonomy` by
    `sync_categories_to_public_taxonomy()` (DELETE + INSERT).

**What went wrong.** They are not generated from each other and nothing pinned them, so both were
edited independently. By 2026-08-27 they disagreed on 64 fields:

  * D-49 (`1d794c6c`) repaired `high_priority` on four categories — **in the CSV only**. The
    ticketing seeder rewrites the taxonomy table from the JSON, so in every environment seeded that
    way the repair never landed. `Environmental - Air Pollution` (the dust complaint) and
    `Gender - Gender Discrimination And Harrassment` (the SEAH route) — the two the benchmark test
    names as the ones that matter — were still `high_priority=False`.
  * D-51 (`71a91b8a`) rewrote the six Road Hazard categories — **in the CSV only**. The JSON kept
    the June text, down to `सडक खतरा` where the CSV says `सडक जोखिम`.
  * `Gender - Gender Discrimination And Harrassment` carried the literal string `"True"` as its
    `description` in the JSON: a column-shift artefact of whatever produced the file, and the same
    class of bug as the ragged CSV rows D-49 found.

`tests/backend/test_benchmark_set.py::test_the_seeded_taxonomy_matches_the_authored_csv` caught the
`high_priority` half of that — it had been failing every CI run on the branch since 2026-08-23. It
could not catch the other 58 fields, because it compares the *database* to the CSV and nothing
compared the two authored files. `tests/repo/test_category_catalog_sources.py` now does, importing
this script so there is one definition of the comparison rather than a mirror of it.

**Direction of the sync, and why.** The CSV wins. It is what the benchmark test calls "the authored
CSV", it holds the newest deliberate edits (D-49 and D-51, both August), and its Road Hazard text is
the version those categories were specified with.

**What the CSV does not carry, and is preserved here.** `intake_route` (`new_grievance`,
`road_hazard_grievance`, `seah_intake`) exists only in the JSON, so it is carried across per
category rather than regenerated. `follow_up_question_extra` exists only in the CSV and is left
there: it is not in the catalog's `_STRING_FIELDS`, so `normalize_category_entry()` would drop it.

**The real fix is one source, not two in sync.** This script makes the copies agree and the pin
keeps them agreeing; it does not remove the second copy. Collapsing them — teaching
`load_default_catalog()` to read the CSV, which needs an `intake_route` column — is a deliberate
change to a shared chatbot/ticketing boundary and is logged for a follow-up sprint.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = REPO_ROOT / "backend" / "dev-resources" / "grievances_categorization_v1.1.csv"
JSON_PATH = REPO_ROOT / "ticketing" / "constants" / "grievance_categories_default.json"

# The fields both files carry. Mirrors `_STRING_FIELDS` in
# ticketing/services/grievance_categories_catalog.py — pinned by
# tests/repo/test_category_catalog_sources.py, which compares this tuple to that one.
SHARED_STRING_FIELDS: tuple[str, ...] = (
    "generic_grievance_name",
    "generic_grievance_name_ne",
    "short_description",
    "short_description_ne",
    "classification",
    "classification_ne",
    "description",
    "description_ne",
    "follow_up_question_description",
    "follow_up_question_description_ne",
    "follow_up_question_quantification",
    "follow_up_question_quantification_ne",
)

# Key order of a JSON entry, preserved so a re-sync produces a minimal diff.
ENTRY_FIELD_ORDER: tuple[str, ...] = (
    ("category_key",) + SHARED_STRING_FIELDS + ("high_priority", "intake_route")
)

# Only present in the JSON; carried across a sync rather than regenerated.
JSON_ONLY_FIELDS: tuple[str, ...] = ("intake_route",)


def derive_category_key(classification: str, generic_grievance_name: str) -> str:
    """Mirrors `ticketing.services.grievance_categories_catalog.derive_category_key`.

    Defined here so this script stays importable without SQLAlchemy or the ticketing models. The
    test pins the two implementations against each other over every real category, so a divergence
    fails the build rather than silently re-keying the catalog.
    """
    return (
        f"{classification.replace('-', ' ').title()} - "
        f"{generic_grievance_name.replace('-', ' ').title()}"
    )


def _csv_bool(value: Any) -> bool:
    return str(value or "").strip().lower() == "true"


def load_csv() -> dict[str, dict[str, Any]]:
    """Authored taxonomy, keyed by derived category_key."""
    with CSV_PATH.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    catalog: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = derive_category_key(row["classification"], row["generic_grievance_name"])
        if key in catalog:
            raise ValueError(f"duplicate category_key in the CSV: {key}")
        catalog[key] = row
    return catalog


def load_json() -> list[dict[str, Any]]:
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))["categories"]


def _json_key(entry: dict[str, Any]) -> str:
    return entry.get("category_key") or derive_category_key(
        entry.get("classification", ""), entry.get("generic_grievance_name", "")
    )


def differences() -> list[str]:
    """Every disagreement between the two files, as reader-facing lines. Empty means in sync."""
    csv_rows = load_csv()
    json_entries = load_json()
    json_by_key = {_json_key(entry): entry for entry in json_entries}

    out: list[str] = []
    for key in sorted(set(json_by_key) - set(csv_rows)):
        out.append(f"{key}: in the JSON, absent from the CSV")
    for key in sorted(set(csv_rows) - set(json_by_key)):
        out.append(f"{key}: in the CSV, absent from the JSON")

    for key in sorted(set(json_by_key) & set(csv_rows)):
        entry, row = json_by_key[key], csv_rows[key]
        for field in SHARED_STRING_FIELDS:
            in_json = str(entry.get(field) or "").strip()
            in_csv = str(row.get(field) or "").strip()
            if in_json != in_csv:
                out.append(f"{key}.{field}: json={in_json[:60]!r} csv={in_csv[:60]!r}")
        if bool(entry.get("high_priority")) != _csv_bool(row.get("high_priority")):
            out.append(
                f"{key}.high_priority: json={bool(entry.get('high_priority'))} "
                f"csv={_csv_bool(row.get('high_priority'))}"
            )
    return out


def build_entries() -> list[dict[str, Any]]:
    """The JSON the CSV implies: CSV values, JSON-only fields and entry order preserved."""
    csv_rows = load_csv()
    existing = {_json_key(entry): entry for entry in load_json()}

    # Existing order first, then any category the CSV added, so a sync reads as a minimal diff.
    ordered = [key for key in (_json_key(e) for e in load_json()) if key in csv_rows]
    ordered += [key for key in csv_rows if key not in existing]

    entries: list[dict[str, Any]] = []
    for key in ordered:
        row = csv_rows[key]
        entry: dict[str, Any] = {"category_key": key}
        for field in SHARED_STRING_FIELDS:
            entry[field] = str(row.get(field) or "")
        entry["high_priority"] = _csv_bool(row.get("high_priority"))
        for field in JSON_ONLY_FIELDS:
            if field in existing.get(key, {}):
                entry[field] = existing[key][field]
        entries.append({field: entry[field] for field in ENTRY_FIELD_ORDER if field in entry})
    return entries


def sync() -> list[str]:
    """Rewrite the JSON from the CSV. Returns the differences that were resolved."""
    resolved = differences()
    payload = json.dumps({"categories": build_entries()}, ensure_ascii=False, indent=2)
    JSON_PATH.write_text(payload + "\n", encoding="utf-8")
    return resolved


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    drift = differences()

    if not drift:
        print(f"in sync: {JSON_PATH.relative_to(REPO_ROOT)} matches the authored CSV")
        return 0

    print(f"{len(drift)} difference(s) between the authored CSV and the bundled JSON:")
    for line in drift[:40]:
        print(f"  {line}")
    if len(drift) > 40:
        print(f"  … and {len(drift) - 40} more")

    if check_only:
        print("\nFix: python scripts/ops/sync_category_catalog_json.py")
        return 1

    sync()
    missing_route = [
        entry["category_key"] for entry in load_json() if not entry.get("intake_route")
    ]
    print(f"\nrewrote {JSON_PATH.relative_to(REPO_ROOT)} from the authored CSV")
    if missing_route:
        print(
            "⚠ no intake_route for (the CSV cannot supply one — set it by hand): "
            + ", ".join(missing_route)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
