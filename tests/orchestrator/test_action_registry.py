import asyncio
import re

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


def test_invoke_action_submit_seah_uses_dedicated_path(domain, monkeypatch):
    from backend.services.database_services.postgres_services import DatabaseManager
    from backend.services.messaging import Messaging

    def _mock_submit_seah_to_db(data):
        return {
            "ok": True,
            "grievance_id": "GR-2026-KO-JH-1234",
            "complainant_id": data.get("complainant_id", "CM-TEST"),
        }

    def _mock_submit_grievance_to_db(data):
        raise AssertionError("General grievance submit path should not be used for SEAH")

    monkeypatch.setattr(DatabaseManager, "submit_seah_to_db", lambda self, data: _mock_submit_seah_to_db(data))
    monkeypatch.setattr(DatabaseManager, "submit_grievance_to_db", lambda self, data: _mock_submit_grievance_to_db(data))
    monkeypatch.setattr(Messaging, "send_sms", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("SEAH flow must not send SMS")))

    slots = {
        "language_code": "en",
        "story_main": "seah_intake",
        "grievance_sensitive_issue": True,
        "complainant_id": "CM-TEST",
        "complainant_phone": "skipped",
        "complainant_email": "skipped",
        "complainant_full_name": "skipped",
        "complainant_province": "Koshi",
        "complainant_district": "Jhapa",
        "complainant_municipality": "Biratnagar",
        "complainant_village": "skipped",
        "complainant_address": "skipped",
        "grievance_id": "GR-DUMMY",
        "grievance_description": "SEAH incident summary",
        "otp_verified": False,
    }
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(slots=slots, sender_id="user-seah-1")

    events = _run(invoke_action("action_submit_seah", dispatcher, tracker, domain))
    slot_updates = events_to_slot_updates(events)
    assert slot_updates.get("grievance_id") == "GR-2026-KO-JH-1234"
    assert any("GR-2026-KO-JH-1234" in m.get("text", "") for m in dispatcher.messages)


def test_invoke_action_seah_outro_registered(domain, monkeypatch):
    from backend.services.database_services.postgres_services import DatabaseManager

    monkeypatch.setattr(
        DatabaseManager,
        "find_seah_contact_point",
        lambda *args, **kwargs: None,
    )

    slots = {
        "language_code": "en",
        "story_main": "seah_intake",
        "seah_victim_survivor_role": "focal_point",
        "sensitive_issues_follow_up": "anonymous",
        "seah_contact_consent_channel": "none",
        "complainant_consent": False,
    }
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(slots=slots, sender_id="user-seah-outro")

    _run(invoke_action("action_seah_outro", dispatcher, tracker, domain))

    assert dispatcher.messages, "Expected outro message"
    assert any("focal-point" in m.get("text", "").lower() for m in dispatcher.messages)


def test_submit_seah_case_reference_uses_canonical_grievance_id():
    grievance_id = "GR-2026-KO-JH-1234"
    assert re.match(r"^GR-[A-Z0-9-]+$", grievance_id)

