"""REST webchat sends /introduce on load; sessions stuck in `done` must not return empty messages."""

from backend.orchestrator.session_store import create_session, save_session


def test_introduce_after_done_returns_intro(client):
    user_id = "test-intro-after-done-user"
    session = create_session(user_id)
    session["state"] = "done"
    session["slots"]["language_code"] = "en"
    save_session(session)

    resp = client.post(
        "/message",
        json={
            "user_id": user_id,
            "text": "",
            "payload": '/introduce{"flask_session_id": "flask-1"}',
            "channel": "webchat-rest",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["next_state"] == "intro"
    texts = [m.get("text") for m in body.get("messages", []) if m.get("text")]
    assert texts, "expected at least one text message from action_introduce"
    assert "language" in texts[0].lower() or "भाषा" in texts[0]


def test_introduce_from_inflight_form_resets_session(client):
    user_id = "test-intro-reset-inflight-user"
    session = create_session(user_id)
    session["state"] = "form_seah_1"
    session["active_loop"] = "form_seah_1"
    session["requested_slot"] = "sensitive_issues_follow_up"
    session["slots"]["language_code"] = "en"
    session["slots"]["story_main"] = "seah_intake"
    session["slots"]["grievance_sensitive_issue"] = True
    save_session(session)

    resp = client.post(
        "/message",
        json={
            "user_id": user_id,
            "text": '/introduce{"flask_session_id": "flask-2"}',
            "channel": "webchat-rest",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["next_state"] == "intro"
    texts = [m.get("text") for m in body.get("messages", []) if m.get("text")]
    assert texts, "expected intro text after reset"
    assert "language" in texts[0].lower() or "भाषा" in texts[0]
