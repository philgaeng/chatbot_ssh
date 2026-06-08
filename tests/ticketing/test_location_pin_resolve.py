"""District centroids and map-pin → location_code resolution."""

import pytest

from ticketing.constants.nepal_district_centroids import NEPAL_DISTRICT_CENTROIDS


def test_nepal_district_centroids_has_77_districts():
    assert len(NEPAL_DISTRICT_CENTROIDS) == 77
    assert "P3_KAT" in NEPAL_DISTRICT_CENTROIDS
    assert "P1_MOR" in NEPAL_DISTRICT_CENTROIDS


@pytest.fixture(scope="module")
def db_manager():
    from backend.services.database_services.postgres_services import db_manager as dm

    rows = dm.execute_query(
        """
        SELECT COUNT(*) AS n
        FROM ticketing.locations
        WHERE country_code = 'NP'
          AND level_number = 2
          AND latitude IS NOT NULL
        """,
        (),
        "test_location_coords_ready",
    )
    if not rows or int(rows[0].get("n") or 0) < 77:
        pytest.skip("ticketing.locations latitude/longitude not seeded — run migrate_ticketing")
    return dm


def test_resolve_pin_to_location_code_kathmandu_valley(db_manager):
    from backend.shared_functions.location_mapping import resolve_pin_to_location_code

    code = resolve_pin_to_location_code(db_manager, 27.72259, 85.33167)
    assert code == "P3_KAT"


def test_resolve_pin_to_location_code_morang(db_manager):
    from backend.shared_functions.location_mapping import resolve_pin_to_location_code

    code = resolve_pin_to_location_code(db_manager, 26.58, 87.45)
    assert code == "P1_MOR"
