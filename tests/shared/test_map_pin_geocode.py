"""Unit tests for map-pin reverse geocode (Nominatim parsing + enqueue helpers)."""

import json

import pytest

from backend.shared_functions.geo_pin import build_location_geo_json
from backend.shared_functions.map_pin_geocode import (
    build_complainant_geocode_update,
    build_slots_from_geocode_names,
    should_enqueue_map_pin_geocode,
)
from backend.shared_functions.reverse_geocode import parse_nominatim_admin_address


def test_parse_nominatim_admin_address_metropolitan():
    address = {
        "city": "Kathmandu Metropolitan City",
        "county": "Kathmandu",
        "state": "Bagamati Province",
        "country_code": "np",
    }
    parsed = parse_nominatim_admin_address(address)
    assert parsed["province"] == "Bagamati Province"
    assert parsed["district"] == "Kathmandu"
    assert parsed["municipality"] == "Kathmandu Metropolitan City"


def test_parse_nominatim_admin_address_nagar():
    address = {
        "municipality": "Belbari",
        "county": "Morang",
        "state": "Koshi Province",
        "country_code": "np",
    }
    parsed = parse_nominatim_admin_address(address)
    assert parsed["municipality"] == "Belbari"
    assert parsed["district"] == "Morang"


def test_should_enqueue_map_pin_geocode_true():
    data = {
        "location_resolution_status": "map_pin",
        "location_geo": build_location_geo_json(27.7172, 85.324),
    }
    assert should_enqueue_map_pin_geocode(data) is True


def test_should_enqueue_map_pin_geocode_false_when_manual():
    data = {
        "location_resolution_status": "mapped_full",
        "location_geo": build_location_geo_json(27.7172, 85.324),
    }
    assert should_enqueue_map_pin_geocode(data) is False


def test_build_complainant_geocode_update_includes_municipality():
    payload = {
        "country_code": "NP",
        "location_code": "P3_KAT_KMC",
        "location_resolution_status": "mapped_full",
        "level_1_name": "Bagmati",
        "level_2_name": "Kathmandu",
        "level_3_name": "Kathmandu Metropolitan City",
        "level_1_code": "P3",
        "level_2_code": "P3_KAT",
        "level_3_code": "P3_KAT_KMC",
        "complainant_province": "Bagmati",
        "complainant_district": "Kathmandu",
        "complainant_municipality": "Kathmandu Metropolitan City",
    }
    updates = build_complainant_geocode_update(payload, lat=27.7172, lng=85.324)
    assert updates["complainant_municipality"] == "Kathmandu Metropolitan City"
    assert updates["level_3_code"] == "P3_KAT_KMC"
    geo = json.loads(updates["location_geo"])
    assert geo["lat"] == pytest.approx(27.7172)
    assert "Kathmandu" in updates["grievance_location"]


def test_build_slots_from_geocode_names():
    slots = build_slots_from_geocode_names(
        {"province": "Koshi Province", "district": "Morang", "municipality": "Belbari"},
        lat=26.58,
        lng=87.45,
    )
    assert slots["complainant_municipality"] == "Belbari"
    assert slots["location_pin_status"] == "map_pin"
