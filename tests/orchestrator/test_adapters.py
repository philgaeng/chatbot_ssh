from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker


def test_collecting_dispatcher_text_and_buttons():
    d = CollectingDispatcher()
    d.utter_message(text="hello")
    d.utter_message(text="choose", buttons=[{"title": "A", "payload": "/a"}])

    assert len(d.messages) == 2
    assert d.messages[0]["text"] == "hello"
    assert d.messages[1]["text"] == "choose"
    assert d.messages[1]["buttons"][0]["title"] == "A"


def test_collecting_dispatcher_json_message():
    d = CollectingDispatcher()
    payload = {"data": {"grievance_id": "G-1", "event_type": "grievance_id_set"}}
    d.utter_message(json_message=payload)

    assert len(d.messages) == 1
    msg = d.messages[0]
    assert "json_message" in msg
    assert msg["json_message"]["data"]["grievance_id"] == "G-1"


def test_session_tracker_basic_slots_and_latest_message():
    slots = {"language_code": "en", "foo": "bar"}
    latest = {"text": "hi", "intent": {"name": "greet"}}
    t = SessionTracker(slots=slots, sender_id="user-1", latest_message=latest)

    assert t.sender_id == "user-1"
    assert t.get_slot("language_code") == "en"
    assert t.get_slot("missing") is None
    assert t.latest_message["text"] == "hi"
    assert t.latest_message["intent"]["name"] == "greet"


def test_session_tracker_requested_slot_and_active_loop():
    slots = {}
    t = SessionTracker(
        slots=slots,
        sender_id="user-1",
        latest_message={},
        active_loop="form_grievance",
        requested_slot="grievance_new_detail",
    )

    assert t.get_slot("requested_slot") == "grievance_new_detail"
    assert t.active_loop == {"name": "form_grievance"}

