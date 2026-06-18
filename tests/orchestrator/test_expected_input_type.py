"""Tests for orchestrator expected_input_type derivation."""

from fastapi.testclient import TestClient

from backend.orchestrator.state_machine import _derive_expected_input_type


def test_no_buttons_means_text():
    assert _derive_expected_input_type([{"text": "Hello"}]) == "text"
    assert _derive_expected_input_type([]) == "text"


def test_buttons_without_skip_means_buttons():
    messages = [
        {
            "text": "Choose one",
            "buttons": [
                {"title": "Yes", "payload": "/affirm"},
                {"title": "No", "payload": "/deny"},
            ],
        }
    ]
    assert _derive_expected_input_type(messages) == "buttons"


def test_buttons_with_skip_means_text():
    messages = [
        {
            "text": "Your address?",
            "buttons": [{"title": "Skip", "payload": "/skip"}],
        }
    ]
    assert _derive_expected_input_type(messages) == "text"


def test_skip_on_any_message_in_turn():
    messages = [
        {"text": "Main menu", "buttons": [{"title": "File", "payload": "/new_grievance"}]},
        {"text": "Or skip", "buttons": [{"title": "Skip", "payload": "/skip"}]},
    ]
    assert _derive_expected_input_type(messages) == "text"


def _walk_to_contact_province_ask(client: TestClient, user_id: str) -> None:
    steps = [
        {"text": ""},
        {"payload": "/set_english"},
        {"payload": "/new_grievance"},
        {"text": "dust on the road near my house"},
        {"payload": "/submit_details"},
        {"payload": "/affirm"},
        {"payload": "/location_manual_entry"},
    ]
    for body in steps:
        client.post("/message", json={"user_id": user_id, **body})


def test_api_intro_returns_buttons_expected_input_type(client: TestClient):
    user_id = "expected-input-intro-api"
    response = client.post("/message", json={"user_id": user_id, "text": ""})
    assert response.status_code == 200
    body = response.json()
    assert body["expected_input_type"] == "buttons"
    assert any(m.get("buttons") for m in body.get("messages", []))


def test_api_main_menu_returns_buttons_expected_input_type(client: TestClient):
    user_id = "expected-input-menu-api"
    client.post("/message", json={"user_id": user_id, "text": ""})
    response = client.post(
        "/message", json={"user_id": user_id, "payload": "/set_english"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["expected_input_type"] == "buttons"
    assert body["next_state"] == "main_menu"


def test_api_location_consent_returns_buttons_expected_input_type(client: TestClient):
    user_id = "expected-input-location-consent-api"
    client.post("/message", json={"user_id": user_id, "text": ""})
    client.post("/message", json={"user_id": user_id, "payload": "/set_english"})
    client.post("/message", json={"user_id": user_id, "payload": "/new_grievance"})
    client.post(
        "/message",
        json={"user_id": user_id, "text": "dust on the road near my house"},
    )
    response = client.post(
        "/message", json={"user_id": user_id, "payload": "/submit_details"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["next_state"] == "location_consent"
    assert body["expected_input_type"] == "buttons"


def test_api_skip_field_returns_text_expected_input_type(client: TestClient):
    user_id = "expected-input-skip-field-api"
    _walk_to_contact_province_ask(client, user_id)
    response = client.post(
        "/message", json={"user_id": user_id, "text": "Bagmati"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["next_state"] == "contact_form"
    assert body["expected_input_type"] == "text"
    payloads = [
        b.get("payload")
        for m in body.get("messages", [])
        for b in (m.get("buttons") or [])
    ]
    assert "/skip" in payloads
