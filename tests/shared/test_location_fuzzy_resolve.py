"""Fuzzy admin-name → location_code resolution for map pins."""

import pytest

from backend.shared_functions.location_mapping import (
    strip_admin_suffix,
    _resolve_location_code_by_name,
)


def test_strip_admin_suffix_municipality_en():
    assert strip_admin_suffix("Kathmandu Metropolitan City", 3) == "Kathmandu"
    assert strip_admin_suffix("Belbari Municipality", 3) == "Belbari"


def test_strip_admin_suffix_province_en():
    assert strip_admin_suffix("Bagamati Province", 1) == "Bagamati"
    assert strip_admin_suffix("Koshi Province", 1) == "Koshi"


@pytest.fixture(scope="module")
def db_manager():
    from backend.services.database_services.postgres_services import db_manager as dm

    rows = dm.execute_query(
        "SELECT COUNT(*) AS n FROM ticketing.locations WHERE country_code = 'NP'",
        (),
        "test_fuzzy_locations_ready",
    )
    if not rows or int(rows[0].get("n") or 0) < 100:
        pytest.skip("ticketing.locations not seeded")
    return dm


def test_fuzzy_resolve_kathmandu_municipality(db_manager):
    province_code = _resolve_location_code_by_name(
        db_manager,
        country_code="NP",
        level_number=1,
        candidate_name="Bagmati",
        parent_code=None,
    )
    assert province_code == "P3"

    district_code = _resolve_location_code_by_name(
        db_manager,
        country_code="NP",
        level_number=2,
        candidate_name="Kathmandu",
        parent_code=province_code,
    )
    assert district_code == "P3_KAT"

    # Validator-style stripped label must resolve to full metro code.
    muni_code = _resolve_location_code_by_name(
        db_manager,
        country_code="NP",
        level_number=3,
        candidate_name="Kathmandu",
        parent_code=district_code,
    )
    assert muni_code == "P3_KAT_KAT"


def test_fuzzy_resolve_belbari_municipality(db_manager):
    province_code = _resolve_location_code_by_name(
        db_manager,
        country_code="NP",
        level_number=1,
        candidate_name="Koshi Province",
        parent_code=None,
    )
    assert province_code == "P1"

    district_code = _resolve_location_code_by_name(
        db_manager,
        country_code="NP",
        level_number=2,
        candidate_name="Morang",
        parent_code=province_code,
    )
    assert district_code == "P1_MOR"

    muni_code = _resolve_location_code_by_name(
        db_manager,
        country_code="NP",
        level_number=3,
        candidate_name="Belbari",
        parent_code=district_code,
    )
    assert muni_code == "P1_MOR_BEL"
