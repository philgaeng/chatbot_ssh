"""CB-07 Phase A: submit chat confirmation (no categorization at submit)."""

from backend.actions.action_submit_grievance import ActionSubmitGrievance
from backend.orchestrator.adapters import CollectingDispatcher


def test_emit_chat_filed_confirmation_two_messages_no_categories():
    action = ActionSubmitGrievance()
    action.language_code = "en"
    dispatcher = CollectingDispatcher()
    grievance_data = {"grievance_id": "B-GR-20260604-TEST-4E92"}

    action._emit_chat_filed_confirmation(dispatcher, grievance_data)

    texts = [m.get("text") for m in dispatcher.messages if m.get("text")]
    assert len(texts) == 2
    assert "filed successfully" in texts[0].lower()
    assert "B-GR-20260604-TEST-4E92" in texts[0]
    assert "on record" in texts[1].lower()
    assert "attachments" in texts[1].lower()
    assert "review categories" not in " ".join(texts).lower()

    filed_events = [
        (m.get("json_message") or {}).get("data", {})
        for m in dispatcher.messages
        if (m.get("json_message") or {}).get("data", {}).get("event_type")
        == "grievance_filed"
    ]
    assert filed_events
    assert filed_events[0].get("grievance_id") == "B-GR-20260604-TEST-4E92"


def test_emit_chat_filed_confirmation_dust_single_message():
    from unittest.mock import MagicMock

    action = ActionSubmitGrievance()
    action.language_code = "en"
    dispatcher = CollectingDispatcher()
    grievance_data = {"grievance_id": "B-GR-20260605-KOJH-1D6C"}
    tracker = MagicMock()
    tracker.get_slot.side_effect = lambda name: {
        "story_main": "dust_grievance",
        "intake_fast_path": "dust",
    }.get(name)

    action._emit_chat_filed_confirmation(dispatcher, grievance_data, tracker=tracker)

    texts = [m.get("text") for m in dispatcher.messages if m.get("text")]
    assert len(texts) == 1
    assert "filed successfully" in texts[0].lower()
    assert "B-GR-20260605-KOJH-1D6C" in texts[0]
    assert "on record" not in " ".join(texts).lower()
