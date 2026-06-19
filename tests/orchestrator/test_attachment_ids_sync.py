"""Orchestrator attachment_ids_sync after early file upload."""

import pytest
from fastapi.testclient import TestClient

from backend.orchestrator.main import app
from backend.orchestrator.session_store import create_session, get_session, save_session


@pytest.fixture
def orch_client():
    return TestClient(app)


def test_attachment_ids_sync_without_story_main_returns_main_menu(orch_client):
    user_id = "attach-sync-user-1"
    session = create_session(user_id)
    session["state"] = "main_menu"
    session["slots"]["language_code"] = "en"
    save_session(session)

    r = orch_client.post(
        "/message",
        json={
            "user_id": user_id,
            "payload": "/attachment_ids_sync",
            "metadata": {
                "attachment_sync": {
                    "grievance_id": "GR-EARLY-001-B",
                    "complainant_id": "CP-EARLY-001-B",
                }
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["next_state"] == "main_menu"
    updated = get_session(user_id)
    assert updated["slots"]["grievance_id"] == "GR-EARLY-001-B"
    assert updated["slots"]["complainant_id"] == "CP-EARLY-001-B"
    assert any("saved" in (m.get("text") or "").lower() for m in body.get("messages", []))


def test_attachment_ids_sync_before_language_stays_intro(orch_client):
    user_id = "attach-sync-user-intro"
    session = create_session(user_id)
    session["state"] = "intro"
    session["slots"]["complainant_district"] = "Jhapa"
    session["slots"]["complainant_province"] = "Koshi"
    save_session(session)

    r = orch_client.post(
        "/message",
        json={
            "user_id": user_id,
            "payload": "/attachment_ids_sync",
            "metadata": {
                "attachment_sync": {
                    "grievance_id": "GR-EARLY-INTRO-B",
                    "complainant_id": "CP-EARLY-INTRO-B",
                }
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["next_state"] == "intro"
    assert not any(
        "Hello! Welcome to the Grievance Management Chatbot." in (m.get("text") or "")
        for m in body.get("messages", [])
    )

    r2 = orch_client.post(
        "/message",
        json={"user_id": user_id, "payload": "/set_english"},
    )
    assert r2.status_code == 200
    texts = [m.get("text", "") for m in r2.json().get("messages", []) if m.get("text")]
    assert any("Hello! Welcome to the Grievance Management Chatbot." in t for t in texts)
    assert r2.json()["next_state"] == "main_menu"


def test_set_english_from_main_menu_without_language(orch_client):
    user_id = "attach-sync-user-lang"
    session = create_session(user_id)
    session["state"] = "main_menu"
    session["slots"]["complainant_district"] = "Jhapa"
    session["slots"]["complainant_province"] = "Koshi"
    save_session(session)

    r = orch_client.post(
        "/message",
        json={"user_id": user_id, "payload": "/set_english"},
    )
    assert r.status_code == 200
    texts = [m.get("text", "") for m in r.json().get("messages", []) if m.get("text")]
    assert any("Hello! Welcome to the Grievance Management Chatbot." in t for t in texts)
    assert get_session(user_id)["slots"]["language_code"] == "en"


def test_attachment_ids_sync_with_story_main_keeps_state(orch_client):
    user_id = "attach-sync-user-2"
    session = create_session(user_id)
    session["state"] = "form_grievance"
    session["slots"]["story_main"] = "new_grievance"
    session["active_loop"] = "form_grievance"
    save_session(session)

    r = orch_client.post(
        "/message",
        json={
            "user_id": user_id,
            "payload": "/attachment_ids_sync",
            "metadata": {
                "attachment_sync": {
                    "grievance_id": "GR-FLOW-001-B",
                    "complainant_id": "CP-FLOW-001-B",
                }
            },
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["next_state"] == "form_grievance"
    updated = get_session(user_id)
    assert updated["slots"]["grievance_id"] == "GR-FLOW-001-B"


def test_new_grievance_reuses_synced_ids(orch_client):
    user_id = "attach-sync-user-3"
    session = create_session(user_id)
    session["state"] = "main_menu"
    session["slots"]["grievance_id"] = "GR-REUSE-001-B"
    session["slots"]["complainant_id"] = "CP-REUSE-001-B"
    session["slots"]["language_code"] = "en"
    # story_main unset — early attachment before choosing a flow
    assert session["slots"].get("story_main") is None
    save_session(session)

    r = orch_client.post(
        "/message",
        json={"user_id": user_id, "payload": "/new_grievance"},
    )
    assert r.status_code == 200
    updated = get_session(user_id)
    assert updated["slots"]["grievance_id"] == "GR-REUSE-001-B"
    assert updated["slots"]["complainant_id"] == "CP-REUSE-001-B"
    assert updated["slots"]["story_main"] == "new_grievance"
