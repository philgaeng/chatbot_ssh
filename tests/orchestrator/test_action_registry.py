import asyncio

from backend.orchestrator.adapters import CollectingDispatcher, SessionTracker
from backend.orchestrator.action_registry import invoke_action, events_to_slot_updates


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_invoke_action_start_grievance_process_sets_slots(domain):
    slots = {
        "complainant_province": "Koshi",
        "complainant_district": "Jhapa",
        "language_code": "en",
    }
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(slots=slots, sender_id="user-1")

    events = _run(
        invoke_action(
            "action_start_grievance_process",
            dispatcher,
            tracker,
            domain,
        )
    )

    # Should have a json_message with grievance_id_set
    msg = next(
        (m for m in dispatcher.messages if "json_message" in m),
        None,
    )
    assert msg is not None
    data = msg["json_message"]["data"]
    assert data["event_type"] == "grievance_id_set"
    grievance_id = data["grievance_id"]
    assert grievance_id

    slot_updates = events_to_slot_updates(events)
    assert slot_updates["grievance_id"] == grievance_id
    assert "complainant_id" in slot_updates
    assert slot_updates["story_main"] == "new_grievance"
    assert slot_updates["grievance_sensitive_issue"] is False


def test_invoke_unknown_action_raises(domain):
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(slots={}, sender_id="user-1")

    try:
        _run(invoke_action("action_does_not_exist", dispatcher, tracker, domain))
    except ValueError as e:
        assert "Unknown action" in str(e)
    else:
        assert False, "Expected ValueError for unknown action"


def test_invoke_action_start_status_check_sets_story_main(domain):
    slots = {
        "language_code": "en",
        "story_main": None,
    }
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(slots=slots, sender_id="user-status-1")

    events = _run(
        invoke_action(
            "action_start_status_check",
            dispatcher,
            tracker,
            domain,
        )
    )

    slot_updates = events_to_slot_updates(events)
    assert slot_updates.get("story_main") == "status_check"


def test_invoke_action_ask_status_check_method_sends_buttons(domain):
    slots = {
        "language_code": "en",
    }
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(slots=slots, sender_id="user-status-2")

    _run(
        invoke_action(
            "action_ask_status_check_method",
            dispatcher,
            tracker,
            domain,
        )
    )

    assert dispatcher.messages, "Expected at least one message"
    last = dispatcher.messages[-1]
    assert "text" in last
    assert "buttons" in last and len(last["buttons"]) > 0

