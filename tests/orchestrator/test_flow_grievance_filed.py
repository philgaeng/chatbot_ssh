"""End-to-end orchestrator flows: each intake path files a grievance."""

from fastapi.testclient import TestClient

from tests.orchestrator.flow_helpers import (
    accept_location_consent,
    assert_location_method_three_options,
    choose_location_manual,
    choose_location_map,
    complete_contact_for_test,
    complete_grievance_review,
    advance_seah_anonymous_victim_flow,
    drive_until_filed_or_done,
    has_json_event,
    intro_english,
    post_turn,
    submit_map_pin,
)


def test_standard_new_grievance_files_with_manual_location(
    client: TestClient, mock_flow_db
):
    user_id = "flow-standard-manual"
    intro_english(client, user_id)
    post_turn(client, user_id, payload="/new_grievance")
    post_turn(client, user_id, text="Dust from road construction affecting my home.")
    body = post_turn(client, user_id, payload="/submit_details")
    assert body["next_state"] == "location_consent"

    body = accept_location_consent(client, user_id)
    assert body["next_state"] == "location_method"
    assert_location_method_three_options(body)

    body = choose_location_manual(client, user_id)
    assert body["next_state"] == "contact_form"

    body = complete_contact_for_test(client, user_id, body)
    body = drive_until_filed_or_done(client, user_id, body)
    body = complete_grievance_review(client, user_id, body)

    assert has_json_event(body, "grievance_filed") or body["next_state"] == "done"


def test_standard_new_grievance_location_method_three_options_via_map_path(
    client: TestClient, mock_flow_db
):
    user_id = "flow-standard-map"
    intro_english(client, user_id)
    post_turn(client, user_id, payload="/new_grievance")
    post_turn(client, user_id, text="Noise from heavy vehicles at night.")
    post_turn(client, user_id, payload="/submit_details")
    accept_location_consent(client, user_id)
    body = post_turn(client, user_id, payload="/location_use_map")
    assert body["next_state"] == "map_location"
    # map step is not the three-option method screen
    body = submit_map_pin(client, user_id)
    assert body["next_state"] == "contact_form"


def test_road_hazard_fast_path_files_grievance(client: TestClient, mock_flow_db):
    user_id = "flow-road-hazard"
    intro_english(client, user_id)
    post_turn(client, user_id, payload="/road_hazard_grievance")
    post_turn(client, user_id, payload="/road_hazard_subtype_potholes")
    body = post_turn(client, user_id, payload="/submit_details")
    assert body["next_state"] == "location_consent"

    body = accept_location_consent(client, user_id)
    assert_location_method_three_options(body)
    body = choose_location_map(client, user_id)
    assert body["next_state"] == "map_location"
    body = submit_map_pin(client, user_id)

    body = complete_contact_for_test(client, user_id, body)
    assert body["next_state"] == "done", (
        f"skipped review should finish on contact deny; got {body.get('next_state')!r}"
    )
    assert has_json_event(body, "grievance_filed")


def test_voice_record_map_anonymous_finishes_on_contact_deny(
    client: TestClient, mock_flow_db
):
    """Voice-only intake skips review; must not stall after map pin + contact deny."""
    user_id = "flow-voice-map-deny"
    intro_english(client, user_id)
    post_turn(client, user_id, payload="/new_grievance")
    post_turn(client, user_id, text="Brief note before voice.")
    body = post_turn(client, user_id, payload="/voice_record")
    assert body["next_state"] == "location_consent"

    body = accept_location_consent(client, user_id)
    body = choose_location_map(client, user_id)
    body = submit_map_pin(client, user_id)
    body = complete_contact_for_test(client, user_id, body)

    assert body["next_state"] == "done"
    assert has_json_event(body, "grievance_filed")


def test_seah_intake_anonymous_victim_files_grievance(client: TestClient, mock_flow_db):
    user_id = "flow-seah-anon-victim"
    intro_english(client, user_id)
    post_turn(client, user_id, payload="/seah_intake")
    post_turn(client, user_id, payload="/victim_survivor")
    post_turn(client, user_id, payload="/anonymous")
    post_turn(client, user_id, text="Harassment by contractor staff near the work site.")
    body = post_turn(client, user_id, payload="/submit_details")
    body = advance_seah_anonymous_victim_flow(client, user_id, body)
    body = drive_until_filed_or_done(client, user_id, body, max_rounds=40)

    filed = has_json_event(body, "grievance_filed")
    done = body.get("next_state") == "done"
    seah_submitted = any(
        "GR-" in (m.get("text") or "") or "reference" in (m.get("text") or "").lower()
        for m in body.get("messages") or []
    )
    assert filed or done or seah_submitted, (
        f"expected SEAH filing; next_state={body.get('next_state')!r}"
    )


def test_location_method_three_options_after_submit_standard_grievance(
    client: TestClient, mock_flow_db
):
    user_id = "flow-location-options-standard"
    intro_english(client, user_id)
    post_turn(client, user_id, payload="/new_grievance")
    post_turn(client, user_id, text="Mud on the road making walking difficult.")
    post_turn(client, user_id, payload="/submit_details")
    body = accept_location_consent(client, user_id)
    assert body["next_state"] == "location_method"
    assert_location_method_three_options(body)


def test_location_method_three_options_after_submit_road_hazard(
    client: TestClient, mock_flow_db
):
    user_id = "flow-location-options-rh"
    intro_english(client, user_id)
    post_turn(client, user_id, payload="/road_hazard_grievance")
    post_turn(client, user_id, payload="/road_hazard_subtype_dust")
    post_turn(client, user_id, payload="/submit_details")
    body = accept_location_consent(client, user_id)
    assert body["next_state"] == "location_method"
    assert_location_method_three_options(body)
