"""CB-07 Phase A: submit chat confirmation is three bubbles + grievance_filed event."""

from backend.actions.action_submit_grievance import ActionSubmitGrievance
from backend.orchestrator.adapters import CollectingDispatcher


def test_emit_chat_filed_confirmation_three_messages():
    action = ActionSubmitGrievance()
    action.language_code = "en"
    dispatcher = CollectingDispatcher()
    grievance_data = {"grievance_id": "B-GR-20260604-TEST-4E92"}

    action._emit_chat_filed_confirmation(dispatcher, grievance_data)

    texts = [m.get("text") for m in dispatcher.messages if m.get("text")]
    assert len(texts) == 3
    assert "filed successfully" in texts[0].lower()
    assert "B-GR-20260604-TEST-4E92" in texts[1]
    assert "on record" in texts[2].lower() or "continue" in texts[2].lower()

    filed_events = [
        (m.get("json_message") or {}).get("data", {})
        for m in dispatcher.messages
        if (m.get("json_message") or {}).get("data", {}).get("event_type")
        == "grievance_filed"
    ]
    assert filed_events
    assert filed_events[0].get("grievance_id") == "B-GR-20260604-TEST-4E92"
