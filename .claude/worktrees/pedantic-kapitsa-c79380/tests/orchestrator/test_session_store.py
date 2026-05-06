from backend.orchestrator import session_store


def test_create_session_defaults():
    session = session_store.create_session("user-1")
    assert session["user_id"] == "user-1"
    assert session["state"] == "intro"
    slots = session["slots"]
    assert slots["language_code"] is None
    assert "complainant_province" in slots


def test_get_and_save_session_roundtrip():
    session = session_store.create_session("user-2")
    session_store.save_session(session)

    loaded = session_store.get_session("user-2")
    assert loaded is not None
    assert loaded["user_id"] == "user-2"


def test_sessions_are_isolated_per_user():
    s1 = session_store.create_session("user-A")
    s2 = session_store.create_session("user-B")
    session_store.save_session(s1)
    session_store.save_session(s2)

    assert session_store.get_session("user-A")["user_id"] == "user-A"
    assert session_store.get_session("user-B")["user_id"] == "user-B"

