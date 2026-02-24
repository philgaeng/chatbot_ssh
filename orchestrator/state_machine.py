"""
State machine: intro -> main_menu -> form_grievance -> done.
"""

import os
import sys
from typing import Any, Dict, List, Optional, Tuple

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_RASA_DIR = os.path.join(_REPO_ROOT, "rasa_chatbot")
if _RASA_DIR not in sys.path:
    sys.path.insert(0, _RASA_DIR)

from orchestrator.adapters import CollectingDispatcher, SessionTracker
from orchestrator.action_registry import invoke_action, events_to_slot_updates
from orchestrator.form_loop import run_form_turn

# Lazy form instance
_FORM = None


def _get_form() -> Any:
    global _FORM
    if _FORM is None:
        from rasa_chatbot.actions.forms.form_grievance import ValidateFormGrievance
        _FORM = ValidateFormGrievance()
    return _FORM

# Payload -> intent mapping (from 04_flow_logic.md)
PAYLOAD_TO_INTENT = {
    "set_english": "set_english",
    "set_nepali": "set_nepali",
    "new_grievance": "new_grievance",
    "submit_details": "submit_details",
    "add_more_details": "add_more_details",
    "restart": "restart",
    "skip": "skip",
    "affirm_skip": "affirm",
    "deny_skip": "deny",
}


def derive_intent(text: str, payload: Optional[str]) -> str:
    """Derive intent from payload or text."""
    if payload:
        raw = payload.strip("/").strip() if payload.startswith("/") else payload
        return PAYLOAD_TO_INTENT.get(raw, "intent_slot_neutral")
    if text and text.strip().startswith("/"):
        raw = text.strip().lstrip("/").strip()
        return PAYLOAD_TO_INTENT.get(raw, raw or "intent_slot_neutral")
    return "intent_slot_neutral"


def build_latest_message(text: str, intent: str) -> Dict[str, Any]:
    """Build latest_message dict for tracker."""
    return {"text": text, "intent": {"name": intent}}


async def run_flow_turn(
    session: Dict[str, Any],
    text: str,
    payload: Optional[str],
    domain: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], str, str]:
    """
    Run one turn of the flow.

    Returns:
        (messages, next_state, expected_input_type)
    """
    intent = derive_intent(text, payload)
    latest_message = build_latest_message(text, payload or text)
    slots = session.get("slots", {})
    state = session.get("state", "intro")

    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(
        slots=slots,
        sender_id=session.get("user_id", "default"),
        latest_message=latest_message,
        active_loop=session.get("active_loop"),
        requested_slot=session.get("requested_slot"),
    )

    next_state = state
    slot_updates: Dict[str, Any] = {}

    if state == "intro":
        await invoke_action("action_introduce", dispatcher, tracker, domain)
        if intent in ("set_english", "set_nepali"):
            action_name = f"action_{intent}"  # action_set_english, action_set_nepali
            events = await invoke_action(
                action_name,
                CollectingDispatcher(),
                tracker,
                domain,
            )
            slot_updates = events_to_slot_updates(events)
            next_state = "main_menu"

    elif state == "main_menu":
        await invoke_action("action_main_menu", dispatcher, tracker, domain)
        if intent == "new_grievance":
            ask_dispatcher = CollectingDispatcher()
            events = await invoke_action(
                "action_start_grievance_process",
                ask_dispatcher,
                tracker,
                domain,
            )
            slot_updates = events_to_slot_updates(events)
            dispatcher.messages.extend(ask_dispatcher.messages)
            session["slots"].update(slot_updates)
            session["active_loop"] = "form_grievance"
            session["requested_slot"] = "grievance_new_detail"
            next_state = "form_grievance"
            # First form prompt: run form loop with no user input
            session_copy = dict(session)
            session_copy["slots"] = dict(session["slots"])
            form = _get_form()
            msgs, form_updates, completed = await run_form_turn(
                form, session_copy, None, domain
            )
            dispatcher.messages.extend(msgs)
            slot_updates.update(form_updates)
            if completed:
                next_state = "done"
                session["active_loop"] = None
                session["requested_slot"] = None

    elif state == "form_grievance":
        user_input = latest_message if (text or payload) else None
        form = _get_form()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            next_state = "done"
            session["active_loop"] = None
            session["requested_slot"] = None

    elif state == "done":
        pass

    session["slots"].update(slot_updates)
    session["state"] = next_state

    expected = "buttons" if next_state in ("intro", "main_menu", "form_grievance") else "text"
    if next_state == "form_grievance" and session.get("requested_slot"):
        expected = "text"

    return (dispatcher.messages, next_state, expected)
