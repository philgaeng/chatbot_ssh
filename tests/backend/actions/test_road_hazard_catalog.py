"""Characterization tests for the extracted road-hazard catalog helpers."""

import pytest

from backend.actions.services.road_hazard.catalog import (
    DUST_CATEGORY,
    DUST_DEFAULT_DESCRIPTION,
    DUST_SUBTYPE,
    ROAD_HAZARD_SUBTYPES,
    category_key_for_subtype,
    default_description_for_subtype,
    derive_category_key,
    normalize_road_hazard_subtype,
)


def test_subtype_catalog_keys():
    assert set(ROAD_HAZARD_SUBTYPES) == {
        "dust",
        "flood_landslide",
        "potholes",
        "accident",
        "animal_on_road",
        "others",
    }


def test_derive_category_key_titles_and_joins():
    assert derive_category_key("Road Hazard", "Dust") == "Road Hazard - Dust"
    assert (
        derive_category_key("road-hazard", "flood-and-landslide")
        == "Road Hazard - Flood And Landslide"
    )


@pytest.mark.parametrize("subtype", list(ROAD_HAZARD_SUBTYPES))
def test_category_key_for_subtype_matches_derive(subtype):
    generic = ROAD_HAZARD_SUBTYPES[subtype]["generic_name"]
    assert category_key_for_subtype(subtype) == derive_category_key("Road Hazard", generic)


def test_dust_constants():
    assert DUST_SUBTYPE == "dust"
    assert DUST_CATEGORY == "Road Hazard - Dust"
    assert DUST_CATEGORY == category_key_for_subtype("dust")
    assert DUST_DEFAULT_DESCRIPTION == default_description_for_subtype("dust")
    assert "fast path" in DUST_DEFAULT_DESCRIPTION


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("potholes", "potholes"),
        ("/road_hazard_subtype_potholes", "potholes"),
        ("road_hazard_subtype_dust", "dust"),
        ("  dust  ", "dust"),
        ("", None),
        ("unknown", None),
        (None, None),
        (123, None),
    ],
)
def test_normalize_road_hazard_subtype(raw, expected):
    assert normalize_road_hazard_subtype(raw) == expected
