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
