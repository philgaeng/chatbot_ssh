"""Chatbot P2 (CB-01, CB-06, CB-08, CB-09) unit tests."""

import json

import pytest

from backend.actions.action_map_location import (
    build_map_filled_location_slots,
    location_skip_slot_updates,
    parse_map_pin_payload,
)
from backend.actions.forms.form_road_hazard import (
    ActionStartDustGrievanceProcess,
    ActionStartRoadHazardGrievanceProcess,
    DUST_CATEGORY,
    DUST_DEFAULT_DESCRIPTION,
    ROAD_HAZARD_SUBTYPES,
    ValidateFormRoadHazard,
    category_key_for_subtype,
    derive_category_key,
    normalize_road_hazard_subtype,
)
from backend.actions.forms.form_grievance import ValidateFormGrievance
from backend.orchestrator.state_machine import derive_intent
from backend.shared_functions.geo_pin import (
    apply_location_enrichment_for_submit,
    build_file_client_metadata,
    build_location_geo_json,
    format_location_display_label,
)
def test_derive_intent_map_pin_set():
    assert derive_intent("", '/map_pin_set{"lat":27.71,"lng":85.32}') == "map_pin_set"


def test_derive_intent_location_use_map():
    assert derive_intent("", "/location_use_map") == "location_use_map"


def test_derive_intent_location_open_map():
    assert derive_intent("", "/location_open_map") == "location_open_map"


def test_derive_intent_road_hazard_grievance():
    assert derive_intent("", "/road_hazard_grievance") == "road_hazard_grievance"


def test_parse_map_pin_payload():
    coords = parse_map_pin_payload('/map_pin_set{"lat":27.5,"lng":85.3}')
    assert coords["lat"] == pytest.approx(27.5)
    assert coords["lng"] == pytest.approx(85.3)


def test_build_location_geo_json():
    raw = build_location_geo_json(27.5, 85.3, location_code="P1_MOR")
    data = json.loads(raw)
    assert data["lat"] == pytest.approx(27.5)
    assert data["lng"] == pytest.approx(85.3)
    assert data["location_code"] == "P1_MOR"
    assert data["source"] == "map_pin"


def test_build_map_filled_location_slots():
    slots = build_map_filled_location_slots(
        27.5, 85.3, province="Koshi", district="Morang", location_code="P1_MOR"
    )
    assert slots["complainant_ward"] == "slot_skipped"
    assert slots["complainant_municipality"] == "slot_skipped"
    assert slots["complainant_province"] == "Koshi"
    assert slots["location_pin_status"] == "map_pin"
    assert "Map pin" in slots["complainant_address"]


def test_location_skip_slot_updates():
    skipped = location_skip_slot_updates()
    assert skipped["complainant_location_consent"] is False
    assert skipped["location_pin_status"] == "skipped"


def test_apply_location_enrichment_for_submit_map_pin():
    enriched = apply_location_enrichment_for_submit(
        {"complainant_district": "Morang"},
        geo_lat=27.5,
        geo_lng=85.3,
        location_pin_status="map_pin",
        location_code="P1_MOR",
    )
    assert enriched["location_resolution_status"] == "map_pin"
    geo = json.loads(enriched["location_geo"])
    assert geo["lat"] == pytest.approx(27.5)
    assert "Map pin" in enriched["grievance_location"]


def test_format_location_display_label_manual():
    label = format_location_display_label(
        {
            "location_pin_status": "manual",
            "complainant_district": "Morang",
            "complainant_province": "Koshi",
        }
    )
    assert label == "Morang, Koshi"


def test_build_file_client_metadata():
    meta = build_file_client_metadata({"lat": 1.0, "lng": 2.0, "exif_consent": True})
    assert meta["lat"] == 1.0
    assert meta["source"] == "client_upload"


@pytest.mark.parametrize(
    "subtype,generic_name",
    [
        ("dust", "Dust"),
        ("flood_landslide", "Flood and Landslide"),
        ("potholes", "Potholes"),
        ("accident", "Accident"),
        ("animal_on_road", "Animal on Road"),
        ("others", "Others"),
    ],
)
def test_category_key_for_subtype_matches_derive(subtype, generic_name):
    expected = derive_category_key("Road Hazard", generic_name)
    assert category_key_for_subtype(subtype) == expected


def test_normalize_road_hazard_subtype_payload():
    assert normalize_road_hazard_subtype("/road_hazard_subtype_potholes") == "potholes"
    assert normalize_road_hazard_subtype("potholes") == "potholes"


def test_dust_start_sets_story_and_category():
    action = ActionStartDustGrievanceProcess()
    assert DUST_CATEGORY == "Road Hazard - Dust"
    assert action.name() == "action_start_dust_grievance_process"


def test_road_hazard_start_action_name():
    action = ActionStartRoadHazardGrievanceProcess()
    assert action.name() == "action_start_road_hazard_grievance_process"


def test_road_hazard_submit_skips_llm_classification(monkeypatch):
    form = ValidateFormRoadHazard()
    saved: dict = {}
    dispatched: list = []
    subtype = "potholes"
    category = category_key_for_subtype(subtype)
    package_id = "6a52c606-100d-4853-b181-c8868b8a7688"

    def _capture_dispatch(tracker, grievance_data=None, **kw):
        dispatched.append(
            {
                "grievance_data": dict(grievance_data or {}),
                "tracker_package": tracker.get_slot("package_id"),
                **kw,
            }
        )

    monkeypatch.setattr(
        "backend.actions.forms.intake_submit.dispatch_grievance_from_tracker",
        _capture_dispatch,
    )

    class FakeDb:
        def create_or_update_complainant(self, data):
            saved["complainant"] = data
            return True

        def create_or_update_grievance(self, data):
            saved["grievance"] = data
            return True

        def update_grievance(self, *_args, **_kwargs):
            raise AssertionError("road hazard path must not update grievance for LLM")

    async def _no_classification(*_args, **_kwargs):
        raise AssertionError("road hazard path must not trigger async classification")

    form.db_manager = FakeDb()
    monkeypatch.setattr(form, "_trigger_async_classification", _no_classification)
    tracker = type(
        "T",
        (),
        {
            "get_slot": lambda self, k: {
                "grievance_id": "G-RH-1",
                "complainant_id": "C-1",
                "grievance_description": "Pothole on KL Road",
                "story_main": "road_hazard_grievance",
                "intake_fast_path": "road_hazard",
                "road_hazard_subtype": subtype,
                "grievance_categories": [category],
                "flask_session_id": "sess-rh",
                "package_id": package_id,
                "location_code": "P1_MOR",
                "project_code": "KL_ROAD",
            }.get(k),
            "sender_id": "sess-rh",
        },
    )()

    import asyncio

    result = asyncio.run(
        form.validate_road_hazard_new_detail("submit_details", None, tracker, {})
    )
    assert result.get("road_hazard_new_detail") == "completed"
    assert result.get("grievance_classification_status") == "LLM_skipped"
    assert result.get("grievance_categories") == [category]
    assert saved["grievance"]["grievance_classification_status"] == "LLM_skipped"
    assert saved["grievance"]["grievance_categories"] == [category]
    assert len(dispatched) == 1
    assert dispatched[0]["tracker_package"] == package_id
    assert dispatched[0]["grievance_data"]["grievance_id"] == "G-RH-1"


def test_dust_submit_skips_llm_classification(monkeypatch):
    form = ValidateFormRoadHazard()
    saved: dict = {}

    class FakeDb:
        def create_or_update_complainant(self, data):
            saved["complainant"] = data
            return True

        def create_or_update_grievance(self, data):
            saved["grievance"] = data
            return True

        def update_grievance(self, *_args, **_kwargs):
            raise AssertionError("road hazard path must not update grievance for LLM")

    async def _no_classification(*_args, **_kwargs):
        raise AssertionError("road hazard path must not trigger async classification")

    form.db_manager = FakeDb()
    monkeypatch.setattr(form, "_trigger_async_classification", _no_classification)
    tracker = type(
        "T",
        (),
        {
            "get_slot": lambda self, k: {
                "grievance_id": "G-DUST-1",
                "complainant_id": "C-1",
                "grievance_description": DUST_DEFAULT_DESCRIPTION,
                "story_main": "road_hazard_grievance",
                "intake_fast_path": "road_hazard",
                "road_hazard_subtype": "dust",
                "grievance_categories": [DUST_CATEGORY],
                "flask_session_id": "sess-dust",
            }.get(k),
            "sender_id": "sess-dust",
        },
    )()

    import asyncio

    result = asyncio.run(
        form.validate_road_hazard_new_detail("submit_details", None, tracker, {})
    )
    assert result.get("road_hazard_new_detail") == "completed"
    assert result.get("grievance_classification_status") == "LLM_skipped"
    assert result.get("grievance_categories") == [DUST_CATEGORY]
    assert saved["grievance"]["grievance_classification_status"] == "LLM_skipped"
    assert saved["grievance"]["grievance_categories"] == [DUST_CATEGORY]


def test_validate_subtype_sets_category():
    form = ValidateFormRoadHazard()
    import asyncio

    tracker = type("T", (), {"get_slot": lambda self, k: None})()
    result = asyncio.run(
        form.validate_road_hazard_subtype(
            "/road_hazard_subtype_accident", None, tracker, {}
        )
    )
    assert result["road_hazard_subtype"] == "accident"
    assert result["grievance_categories"] == ["Road Hazard - Accident"]


def test_all_subtypes_defined():
    assert set(ROAD_HAZARD_SUBTYPES) == {
        "dust",
        "flood_landslide",
        "potholes",
        "accident",
        "animal_on_road",
        "others",
    }


def test_validate_voice_only_empty_text_triggers_voice_record(monkeypatch):
    form = ValidateFormGrievance()

    class FakeDb:
        def get_grievance_files(self, _gid):
            return [{"file_type": "audio"}]

        def create_or_update_complainant(self, _data):
            return True

        def create_or_update_grievance(self, _data):
            return True

    form.db_manager = FakeDb()
    tracker = type(
        "T",
        (),
        {
            "get_slot": lambda self, k: {
                "grievance_id": "G-1",
                "complainant_id": "C-1",
                "grievance_description": "",
                "story_main": "new_grievance",
                "flask_session_id": "sess-1",
            }.get(k),
            "sender_id": "sess-1",
        },
    )()

    import asyncio

    result = asyncio.run(form.validate_grievance_new_detail("", None, tracker, {}))
    assert result.get("grievance_new_detail") == "voice_record"
    assert result.get("grievance_classification_status") == "LLM_skipped"


def test_required_slots_completes_on_voice_record():
    form = ValidateFormGrievance()
    tracker = type(
        "T",
        (),
        {
            "get_slot": lambda self, k: "voice_record" if k == "grievance_new_detail" else None,
        },
    )()

    import asyncio

    slots = asyncio.run(form.required_slots([], None, tracker, {}))
    assert slots == []


def test_validate_voice_record_payload(monkeypatch):
    form = ValidateFormGrievance()

    class FakeDb:
        def get_grievance_files(self, _gid):
            return [{"file_type": "audio"}]

        def create_or_update_complainant(self, _data):
            return True

        def create_or_update_grievance(self, _data):
            return True

    form.db_manager = FakeDb()
    tracker = type(
        "T",
        (),
        {
            "get_slot": lambda self, k: {
                "grievance_id": "G-1",
                "complainant_id": "C-1",
                "grievance_description": "",
                "story_main": "new_grievance",
                "flask_session_id": "sess-1",
            }.get(k),
            "sender_id": "sess-1",
        },
    )()

    import asyncio

    result = asyncio.run(
        form.validate_grievance_new_detail("voice_record", None, tracker, {})
    )
    assert result.get("grievance_new_detail") == "voice_record"
