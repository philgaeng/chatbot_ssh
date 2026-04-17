from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"


def test_full_happy_path_flow(client: TestClient):
    user_id = "orchestrator-e2e-1"

    # 1) Intro
    r1 = client.post("/message", json={"user_id": user_id, "text": ""})
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["next_state"] in ("intro", "main_menu")

    # 2) Set English
    r2 = client.post(
        "/message", json={"user_id": user_id, "payload": "/set_english"}
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["next_state"] in ("main_menu", "form_grievance")

    # 3) New grievance
    r3 = client.post(
        "/message", json={"user_id": user_id, "payload": "/new_grievance"}
    )
    assert r3.status_code == 200
    body3 = r3.json()
    assert body3["next_state"] == "form_grievance"
    # expect a custom json_message with grievance_id_set at some point
    assert isinstance(body3["messages"], list)

    # 4) Grievance text
    r4 = client.post(
        "/message",
        json={
            "user_id": user_id,
            "text": "My complaint is about delayed services",
        },
    )
    assert r4.status_code == 200
    body4 = r4.json()
    assert body4["next_state"] == "form_grievance"

    # 5) Submit details -> should move into contact_form (new grievance flow)
    r5 = client.post(
        "/message", json={"user_id": user_id, "payload": "/submit_details"}
    )
    assert r5.status_code == 200
    body5 = r5.json()
    assert body5["next_state"] == "contact_form"
    assert len(body5["messages"]) > 0, "contact_form first ask should be in response"


def test_status_check_entry_flow(client: TestClient):
    user_id = "orchestrator-status-1"

    # 1) Intro
    r1 = client.post("/message", json={"user_id": user_id, "text": ""})
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["next_state"] in ("intro", "main_menu")

    # 2) Set English
    r2 = client.post(
        "/message",
        json={"user_id": user_id, "payload": "/set_english"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["next_state"] in ("main_menu", "form_grievance", "status_check_form")

    # 3) Start status check from main menu
    r3 = client.post(
        "/message",
        json={"user_id": user_id, "payload": "/check_status"},
    )
    assert r3.status_code == 200
    body3 = r3.json()
    assert body3["next_state"] in ("status_check_form", "done")
    assert isinstance(body3["messages"], list)
    # At this point we should be in the status_check_form flow and expecting a method choice
    if body3["next_state"] == "status_check_form":
        assert any("buttons" in m for m in body3["messages"])


def test_sensitive_content_flow_goes_to_form_sensitive_issues(client: TestClient):
    """When grievance text triggers sensitive content (keyword), Submit details -> form_sensitive_issues then contact_form."""
    user_id = "orchestrator-sensitive-1"

    # 1) Intro
    r1 = client.post("/message", json={"user_id": user_id, "text": ""})
    assert r1.status_code == 200
    # 2) Set English
    r2 = client.post("/message", json={"user_id": user_id, "payload": "/set_english"})
    assert r2.status_code == 200
    # 3) New grievance
    r3 = client.post("/message", json={"user_id": user_id, "payload": "/new_grievance"})
    assert r3.status_code == 200
    assert r3.json()["next_state"] == "form_grievance"

    # 4) Grievance text that triggers sensitive content (sexual harassment keyword path)
    r4 = client.post(
        "/message",
        json={
            "user_id": user_id,
            "text": "I experienced unwanted sexual contact and sexual harassment",
        },
    )
    assert r4.status_code == 200
    assert r4.json()["next_state"] == "form_grievance"

    # 5) Submit details -> should move to form_sensitive_issues (not contact_form)
    r5 = client.post(
        "/message", json={"user_id": user_id, "payload": "/submit_details"}
    )
    assert r5.status_code == 200
    body5 = r5.json()
    assert body5["next_state"] == "form_sensitive_issues", (
        f"Expected form_sensitive_issues, got {body5['next_state']}"
    )


def test_seah_intake_entry_from_main_menu(client: TestClient):
    user_id = "orchestrator-seah-entry-1"

    client.post("/message", json={"user_id": user_id, "text": ""})
    client.post("/message", json={"user_id": user_id, "payload": "/set_english"})

    response = client.post(
        "/message",
        json={"user_id": user_id, "payload": "/seah_intake"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["next_state"] == "form_sensitive_issues"
    assert isinstance(body["messages"], list)


def test_seah_intake_entry_from_main_menu_nepali(client: TestClient):
    user_id = "orchestrator-seah-entry-ne-1"

    client.post("/message", json={"user_id": user_id, "text": ""})
    client.post("/message", json={"user_id": user_id, "payload": "/set_nepali"})

    response = client.post(
        "/message",
        json={"user_id": user_id, "payload": "/seah_intake"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["next_state"] == "form_sensitive_issues"
    assert isinstance(body["messages"], list)


def test_seah_intake_flag_disabled_keeps_legacy_menu_flow(client: TestClient, monkeypatch):
    monkeypatch.setenv("ENABLE_SEAH_DEDICATED_FLOW", "false")
    user_id = "orchestrator-seah-flag-off-1"

    client.post("/message", json={"user_id": user_id, "text": ""})
    client.post("/message", json={"user_id": user_id, "payload": "/set_english"})
    response = client.post("/message", json={"user_id": user_id, "payload": "/seah_intake"})

    assert response.status_code == 200
    body = response.json()
    assert body["next_state"] == "main_menu"

