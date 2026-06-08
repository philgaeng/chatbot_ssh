"""Chatbot P2 (CB-01, CB-06, CB-08, CB-09) unit tests."""

import json

import pytest

from backend.actions.action_map_location import (
    build_map_filled_location_slots,
    location_skip_slot_updates,
    parse_map_pin_payload,
)
from backend.actions.forms.form_dust import (
    ActionStartDustGrievanceProcess,
    DUST_CATEGORY,
    DUST_DEFAULT_DESCRIPTION,
    ValidateFormDust,
    ValidateFormGrievance,
)
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


def test_dust_start_sets_story_and_category():
    action = ActionStartDustGrievanceProcess()
    assert DUST_CATEGORY == "Air Pollution"
    assert action.name() == "action_start_dust_grievance_process"


def test_dust_submit_skips_llm_classification(monkeypatch):
    form = ValidateFormDust()
    saved: dict = {}

    class FakeDb:
        def create_or_update_complainant(self, data):
            saved["complainant"] = data
            return True

        def create_or_update_grievance(self, data):
            saved["grievance"] = data
            return True

        def update_grievance(self, *_args, **_kwargs):
            raise AssertionError("dust path must not update grievance for LLM")

    async def _no_classification(*_args, **_kwargs):
        raise AssertionError("dust path must not trigger async classification")

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
                "story_main": "dust_grievance",
                "intake_fast_path": "dust",
                "grievance_categories": [DUST_CATEGORY],
                "flask_session_id": "sess-dust",
            }.get(k),
            "sender_id": "sess-dust",
        },
    )()

    import asyncio

    result = asyncio.run(
        form.validate_dust_new_detail("submit_details", None, tracker, {})
    )
    assert result.get("dust_new_detail") == "completed"
    assert result.get("grievance_classification_status") == "LLM_skipped"
    assert result.get("grievance_categories") == [DUST_CATEGORY]
    assert saved["grievance"]["grievance_classification_status"] == "LLM_skipped"
    assert saved["grievance"]["grievance_categories"] == [DUST_CATEGORY]


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
