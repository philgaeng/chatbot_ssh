"""Characterization tests for the extracted map-pin location helpers."""

import pytest

from backend.actions.base_classes.base_mixins import SKIP_VALUE
from backend.actions.services.location.map_pin import (
    build_map_filled_location_slots,
    location_skip_slot_updates,
    parse_map_pin_payload,
)


def test_parse_map_pin_payload_with_prefix():
    coords = parse_map_pin_payload('/map_pin_set{"lat":27.5,"lng":85.3}')
    assert coords == {"lat": 27.5, "lng": 85.3}


def test_parse_map_pin_payload_bare_json():
    assert parse_map_pin_payload('{"lat":1,"lng":2}') == {"lat": 1.0, "lng": 2.0}


def test_parse_map_pin_payload_invalid_raises():
    with pytest.raises(ValueError):
        parse_map_pin_payload("/map_pin_set no-json")


def test_location_skip_slot_updates():
    skipped = location_skip_slot_updates()
    assert skipped["complainant_location_consent"] is False
    assert skipped["location_pin_status"] == "skipped"
    assert skipped["complainant_province"] == SKIP_VALUE


def test_build_map_filled_location_slots_defaults_and_label():
    slots = build_map_filled_location_slots(27.12345, 85.54321)
    assert slots["complainant_location_consent"] is True
    assert slots["location_pin_status"] == "map_pin"
    assert slots["geo_lat"] == 27.12345
    assert slots["geo_lng"] == 85.54321
    assert slots["complainant_address"] == "Map pin (27.12345, 85.54321)"
    assert slots["complainant_province"] == SKIP_VALUE
    assert "location_code" not in slots


def test_build_map_filled_location_slots_with_optional_fields():
    slots = build_map_filled_location_slots(
        1.0, 2.0, province="P1", district="D1", location_code="LC1"
    )
    assert slots["complainant_province"] == "P1"
    assert slots["complainant_district"] == "D1"
    assert slots["location_code"] == "LC1"
