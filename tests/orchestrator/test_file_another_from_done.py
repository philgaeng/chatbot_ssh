"""CB-04: restart intake from done state without closing the browser tab."""

from backend.orchestrator.session_store import create_session, save_session


def _session_at_done(user_id: str, *, seah: bool = False):
    session = create_session(user_id)
    session["state"] = "done"
    session["slots"]["language_code"] = "en"
    session["slots"]["grievance_id"] = "GRM-OLD-001"
    if seah:
        session["slots"]["story_main"] = "seah_intake"
        session["slots"]["grievance_sensitive_issue"] = True
    else:
        session["slots"]["story_main"] = "new_grievance"
    save_session(session)
    return session


def test_new_grievance_from_done_starts_form(client):
    user_id = "test-file-another-standard"
    _session_at_done(user_id, seah=False)

    resp = client.post(
        "/message",
        json={"user_id": user_id, "payload": "/new_grievance", "channel": "webchat-rest"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["next_state"] == "form_grievance"
    assert body["close_controls_mode"] == "session"
    new_ids = []
    for m in body.get("messages", []):
        data = (m.get("json_message") or {}).get("data") or {}
        if data.get("event_type") == "grievance_id_set" and data.get("grievance_id"):
            new_ids.append(data["grievance_id"])
    assert new_ids, "expected new grievance_id_set after file-another restart"
    assert new_ids[0] != "GRM-OLD-001"


def test_seah_intake_from_done_when_enabled(client, monkeypatch):
    monkeypatch.setenv("ENABLE_SEAH_DEDICATED_FLOW", "true")
    user_id = "test-file-another-seah"
    _session_at_done(user_id, seah=True)

    resp = client.post(
        "/message",
        json={"user_id": user_id, "payload": "/seah_intake", "channel": "webchat-rest"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["next_state"] == "form_seah_1"
    assert body["close_controls_mode"] == "browser"
