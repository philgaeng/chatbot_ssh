"""Unit tests for Nepal canonical location_code planning (LOCATION_CODES.md)."""

from ticketing.constants.nepal_canonical_locations import (
    apply_location_rename_map,
    plan_np_legacy_to_canonical_renames,
)


def test_plan_legacy_csv_rows_to_canonical():
    locs = [
        {
            "location_code": "NP_P1",
            "country_code": "NP",
            "level_number": 1,
            "parent_location_code": None,
            "source_id": 1,
        },
        {
            "location_code": "NP_D004",
            "country_code": "NP",
            "level_number": 2,
            "parent_location_code": "NP_P1",
            "source_id": 4,
        },
        {
            "location_code": "NP_D005",
            "country_code": "NP",
            "level_number": 2,
            "parent_location_code": "NP_P1",
            "source_id": 5,
        },
    ]
    trans = [
        {"location_code": "NP_P1", "lang_code": "en", "name": "Koshi Province"},
        {"location_code": "NP_D004", "lang_code": "en", "name": "Jhapa"},
        {"location_code": "NP_D005", "lang_code": "en", "name": "Morang"},
    ]
    rename = plan_np_legacy_to_canonical_renames(locs, trans)
    apply_location_rename_map(locs, trans, rename)

    assert rename["NP_P1"] == "P1"
    codes = {r["location_code"] for r in locs}
    assert "P1" in codes
    assert "P1_JHA" in codes
    assert "P1_MOR" in codes
    parents = {(r["location_code"], r.get("parent_location_code")) for r in locs if r["level_number"] != 1}
    assert ("P1_JHA", "P1") in parents or ("P1_MOR", "P1") in parents


def test_parse_json_style_np_is_stable():
    from ticketing.seed.location_import_core import parse_json

    en = [
        {
            "id": 1,
            "name": "Koshi Province",
            "districts": [
                {"id": 10, "name": "Bhojpur", "municipalities": [{"id": 100, "name": "Bhojpur Mun"}]},
            ],
        },
    ]
    rows, tran = parse_json(en, {}, "NP", max_level=3)
    codes = sorted(r["location_code"] for r in rows if r["level_number"] <= 3)
    assert "P1" in codes and "P1_BHO" in codes
    munis = [r["location_code"] for r in rows if r["level_number"] == 3]
    assert len(munis) == 1 and munis[0].startswith("P1_BHO_")
