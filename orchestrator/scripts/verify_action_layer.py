#!/usr/bin/env python3
"""
Verify Agent 2 deliverables: action_start_grievance_process runs with adapters,
dispatcher.messages and return events are correct.
"""
import asyncio
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _REPO_ROOT)

from backend.config.constants import DEFAULT_VALUES
from orchestrator.adapters import CollectingDispatcher, SessionTracker
from orchestrator.action_registry import invoke_action, events_to_slot_updates


# Minimal domain for spike (actions use domain for slot types, etc.)
DOMAIN = {
    "slots": {
        "grievance_id": {"type": "text"},
        "complainant_id": {"type": "text"},
        "story_main": {"type": "categorical"},
        "grievance_sensitive_issue": {"type": "bool"},
        "complainant_province": {"type": "text"},
        "complainant_district": {"type": "text"},
        "complainant_office": {"type": "text"},
    }
}


async def main():
    # Initial slots (default province/district for ID generation)
    slots = {
        "complainant_province": DEFAULT_VALUES["DEFAULT_PROVINCE"],
        "complainant_district": DEFAULT_VALUES["DEFAULT_DISTRICT"],
        "language_code": "en",
    }
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(
        slots=slots,
        sender_id="test-session-123",
        latest_message={},
    )

    events = await invoke_action(
        "action_start_grievance_process",
        dispatcher,
        tracker,
        DOMAIN,
    )

    # Check dispatcher.messages
    assert len(dispatcher.messages) >= 1, "Expected at least one message"
    json_msg = next(
        (m for m in dispatcher.messages if "json_message" in m),
        None,
    )
    assert json_msg is not None, "Expected json_message (grievance_id_set)"
    data = json_msg["json_message"].get("data", {})
    assert data.get("event_type") == "grievance_id_set", "Expected event_type grievance_id_set"
    grievance_id = data.get("grievance_id")
    assert grievance_id, "Expected grievance_id in json_message"

    # Check events (SlotSet for grievance_id, complainant_id, story_main, grievance_sensitive_issue)
    slot_updates = events_to_slot_updates(events)
    assert "grievance_id" in slot_updates, "Expected SlotSet grievance_id"
    assert slot_updates["grievance_id"] == grievance_id, "grievance_id should match json_message"
    assert "complainant_id" in slot_updates, "Expected SlotSet complainant_id"
    assert slot_updates["story_main"] == "new_grievance", "Expected story_main=new_grievance"
    assert slot_updates.get("grievance_sensitive_issue") is False, "Expected grievance_sensitive_issue=False"

    print("✓ action_start_grievance_process: dispatcher.messages and events correct")
    print(f"  - json_message event_type: {data.get('event_type')}")
    print(f"  - grievance_id: {grievance_id}")
    print(f"  - slot_updates: {slot_updates}")


if __name__ == "__main__":
    asyncio.run(main())
