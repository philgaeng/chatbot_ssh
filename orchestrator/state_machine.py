"""
State machine: drives all flows from flow.yaml.

New grievance: intro -> main_menu -> form_grievance -> contact_form -> otp_form
    -> submit_grievance -> grievance_review -> done.
Status check: intro -> main_menu -> status_check_form (form_status_check_1 ->
    form_otp | form_status_check_2 | form_status_check_skip) -> done.
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

# Lazy form instances
_FORM = None
_STATUS_FORM_1 = None
_STATUS_FORM_2 = None
_CONTACT_FORM = None
_OTP_FORM = None
_REVIEW_FORM = None
_STATUS_FORM_SKIP = None


def _get_form() -> Any:
    global _FORM
    if _FORM is None:
        from rasa_chatbot.actions.forms.form_grievance import ValidateFormGrievance
        _FORM = ValidateFormGrievance()
    return _FORM


def _get_status_form_1() -> Any:
    global _STATUS_FORM_1
    if _STATUS_FORM_1 is None:
        from rasa_chatbot.actions.forms.form_status_check import ValidateFormStatusCheck1
        _STATUS_FORM_1 = ValidateFormStatusCheck1()
    return _STATUS_FORM_1


def _get_status_form_2() -> Any:
    global _STATUS_FORM_2
    if _STATUS_FORM_2 is None:
        from rasa_chatbot.actions.forms.form_status_check import ValidateFormStatusCheck2
        _STATUS_FORM_2 = ValidateFormStatusCheck2()
    return _STATUS_FORM_2


def _get_contact_form() -> Any:
    global _CONTACT_FORM
    if _CONTACT_FORM is None:
        from rasa_chatbot.actions.forms.form_contact import ValidateFormContact
        _CONTACT_FORM = ValidateFormContact()
    return _CONTACT_FORM


def _get_otp_form() -> Any:
    global _OTP_FORM
    if _OTP_FORM is None:
        from rasa_chatbot.actions.forms.form_otp import ValidateFormOtp
        _OTP_FORM = ValidateFormOtp()
    return _OTP_FORM


def _get_review_form() -> Any:
    global _REVIEW_FORM
    if _REVIEW_FORM is None:
        from rasa_chatbot.actions.forms.form_grievance_complainant_review import ValidateFormGrievanceComplainantReview
        _REVIEW_FORM = ValidateFormGrievanceComplainantReview()
    return _REVIEW_FORM


def _get_status_form_skip() -> Any:
    global _STATUS_FORM_SKIP
    if _STATUS_FORM_SKIP is None:
        from rasa_chatbot.actions.forms.form_status_check_skip import ValidateFormSkipStatusCheck
        _STATUS_FORM_SKIP = ValidateFormSkipStatusCheck()
    return _STATUS_FORM_SKIP

# Payload -> intent mapping (from 04_flow_logic.md)
PAYLOAD_TO_INTENT = {
    "set_english": "set_english",
    "set_nepali": "set_nepali",
    "new_grievance": "new_grievance",
    "check_status": "start_status_check",
    "start_status_check": "start_status_check",
    "route_status_check_phone": "route_status_check_phone",
    "route_status_check_grievance_id": "route_status_check_grievance_id",
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


def build_latest_message(text: str, payload: Optional[str], intent: str) -> Dict[str, Any]:
    """
    Build latest_message dict for tracker.

    Rasa-style extract/validate logic relies on latest_message['text'] containing
    either the raw user text or the command payload (e.g. \"/submit_details\").
    When the client sends both (e.g. button label as text and /slot_confirmed as payload),
    prefer the payload so the form sees the slash-command and not the label (which can
    be misclassified e.g. as skip).
    """
    if payload and payload.strip().startswith("/"):
        msg_text = payload.strip()
    else:
        msg_text = text or (payload or "")
    return {"text": msg_text, "intent": {"name": intent}}


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
    latest_message = build_latest_message(text, payload, intent)
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
                next_state = "contact_form"
                session["active_loop"] = "form_contact"
                session["requested_slot"] = None
        elif intent == "start_status_check":
            ask_dispatcher = CollectingDispatcher()
            events = await invoke_action(
                "action_start_status_check",
                ask_dispatcher,
                tracker,
                domain,
            )
            slot_updates = events_to_slot_updates(events)
            dispatcher.messages.extend(ask_dispatcher.messages)
            session["slots"].update(slot_updates)
            session["active_loop"] = "form_status_check_1"
            session["requested_slot"] = None
            next_state = "status_check_form"
            # First form prompt: run form loop with no user input
            session_copy = dict(session)
            session_copy["slots"] = dict(session["slots"])
            form_status_1 = _get_status_form_1()
            msgs, form_updates, completed = await run_form_turn(
                form_status_1, session_copy, None, domain
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
            next_state = "contact_form"
            session["active_loop"] = "form_contact"
            session["requested_slot"] = None
            session["slots"].update(slot_updates)
            contact_form = _get_contact_form()
            msgs2, form_updates2, _ = await run_form_turn(
                contact_form, session, None, domain
            )
            dispatcher.messages.extend(msgs2)
            slot_updates.update(form_updates2)

    elif state == "contact_form":
        user_input = latest_message if (text or payload) else None
        form = _get_contact_form()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            next_state = "otp_form"
            session["active_loop"] = "form_otp"
            session["requested_slot"] = None
            session["slots"].update(slot_updates)
            otp_form = _get_otp_form()
            msgs2, form_updates2, _ = await run_form_turn(
                otp_form, session, None, domain
            )
            dispatcher.messages.extend(msgs2)
            slot_updates.update(form_updates2)

    elif state == "otp_form":
        user_input = latest_message if (text or payload) else None
        form = _get_otp_form()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            story_main = session.get("slots", {}).get("story_main")
            if story_main == "status_check":
                next_state = "status_check_form"
                session["active_loop"] = "form_status_check_2"
                session["requested_slot"] = None
            else:
                session["slots"].update(slot_updates)
                session["active_loop"] = None
                session["requested_slot"] = None
                ask_dispatcher = CollectingDispatcher()
                tracker_submit = SessionTracker(
                    slots=session["slots"],
                    sender_id=session.get("user_id", "default"),
                    latest_message=latest_message,
                    active_loop=None,
                    requested_slot=None,
                )
                events = await invoke_action(
                    "action_submit_grievance",
                    ask_dispatcher,
                    tracker_submit,
                    domain,
                )
                slot_updates = events_to_slot_updates(events)
                dispatcher.messages.extend(ask_dispatcher.messages)
                next_state = "grievance_review"
                session["active_loop"] = "form_grievance_complainant_review"
                session["requested_slot"] = None
                session["slots"].update(slot_updates)
                retrieve_dispatcher = CollectingDispatcher()
                retrieve_tracker = SessionTracker(
                    slots=session["slots"],
                    sender_id=session.get("user_id", "default"),
                    latest_message=latest_message,
                    active_loop=None,
                    requested_slot=None,
                )
                retrieve_events = await invoke_action(
                    "action_retrieve_classification_results",
                    retrieve_dispatcher,
                    retrieve_tracker,
                    domain,
                )
                if retrieve_events:
                    retrieve_updates = events_to_slot_updates(retrieve_events)
                    session["slots"].update(retrieve_updates)
                    slot_updates.update(retrieve_updates)
                dispatcher.messages.extend(retrieve_dispatcher.messages)
                review_form = _get_review_form()
                msgs_review, form_updates_review, _ = await run_form_turn(
                    review_form, session, None, domain
                )
                dispatcher.messages.extend(msgs_review)
                slot_updates.update(form_updates_review)

    elif state == "submit_grievance":
        ask_dispatcher = CollectingDispatcher()
        events = await invoke_action(
            "action_submit_grievance",
            ask_dispatcher,
            tracker,
            domain,
        )
        slot_updates = events_to_slot_updates(events)
        dispatcher.messages.extend(ask_dispatcher.messages)
        next_state = "grievance_review"
        session["active_loop"] = "form_grievance_complainant_review"
        session["requested_slot"] = None
        session["slots"].update(slot_updates)
        retrieve_dispatcher = CollectingDispatcher()
        retrieve_tracker = SessionTracker(
            slots=session["slots"],
            sender_id=session.get("user_id", "default"),
            latest_message=latest_message,
            active_loop=None,
            requested_slot=None,
        )
        retrieve_events = await invoke_action(
            "action_retrieve_classification_results",
            retrieve_dispatcher,
            retrieve_tracker,
            domain,
        )
        if retrieve_events:
            retrieve_updates = events_to_slot_updates(retrieve_events)
            session["slots"].update(retrieve_updates)
            slot_updates.update(retrieve_updates)
        dispatcher.messages.extend(retrieve_dispatcher.messages)
        review_form = _get_review_form()
        msgs_review, form_updates_review, _ = await run_form_turn(
            review_form, session, None, domain
        )
        dispatcher.messages.extend(msgs_review)
        slot_updates.update(form_updates_review)

    elif state == "grievance_review":
        user_input = latest_message if (text or payload) else None
        form = _get_review_form()
        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)
        if completed:
            next_state = "done"
            session["active_loop"] = None
            session["requested_slot"] = None

    elif state == "status_check_form":
        user_input = latest_message if (text or payload) else None
        active_loop = session.get("active_loop", "form_status_check_1")

        if active_loop == "form_status_check_1":
            form = _get_status_form_1()
        elif active_loop == "form_otp":
            form = _get_otp_form()
        elif active_loop == "form_status_check_2":
            form = _get_status_form_2()
        elif active_loop == "form_status_check_skip":
            form = _get_status_form_skip()
        else:
            form = _get_status_form_1()

        msgs, form_updates, completed = await run_form_turn(
            form, session, user_input, domain
        )
        dispatcher.messages.extend(msgs)
        slot_updates.update(form_updates)

        if completed:
            slots_after = dict(session.get("slots", {}))
            slots_after.update(slot_updates)
            story_route = slots_after.get("story_route")

            if active_loop == "form_status_check_1":
                if story_route == "route_status_check_phone":
                    session["active_loop"] = "form_otp"
                    session["requested_slot"] = None
                    session["slots"].update(slot_updates)
                    otp_form = _get_otp_form()
                    msgs2, form_updates2, _ = await run_form_turn(
                        otp_form, session, None, domain
                    )
                    dispatcher.messages.extend(msgs2)
                    slot_updates.update(form_updates2)
                elif story_route == "route_status_check_grievance_id":
                    session["active_loop"] = "form_status_check_2"
                    session["requested_slot"] = None
                    session["slots"].update(slot_updates)
                    status_form_2 = _get_status_form_2()
                    msgs2, form_updates2, _ = await run_form_turn(
                        status_form_2, session, None, domain
                    )
                    dispatcher.messages.extend(msgs2)
                    slot_updates.update(form_updates2)
                elif story_route and "skip" in str(story_route).lower():
                    session["active_loop"] = "form_status_check_skip"
                    session["requested_slot"] = None
                else:
                    next_state = "done"
                    session["active_loop"] = None
                    session["requested_slot"] = None
            elif active_loop == "form_otp":
                session["active_loop"] = "form_status_check_2"
                session["requested_slot"] = None
                session["slots"].update(slot_updates)
                status_form_2 = _get_status_form_2()
                msgs2, form_updates2, _ = await run_form_turn(
                    status_form_2, session, None, domain
                )
                dispatcher.messages.extend(msgs2)
                slot_updates.update(form_updates2)
            elif active_loop == "form_status_check_2":
                ask_dispatcher = CollectingDispatcher()
                events = await invoke_action(
                    "action_status_check_request_follow_up",
                    ask_dispatcher,
                    SessionTracker(
                        slots=slots_after,
                        sender_id=session.get("user_id", "default"),
                        latest_message=latest_message,
                        active_loop=None,
                        requested_slot=None,
                    ),
                    domain,
                )
                slot_updates.update(events_to_slot_updates(events))
                dispatcher.messages.extend(ask_dispatcher.messages)
                next_state = "done"
                session["active_loop"] = None
                session["requested_slot"] = None
            elif active_loop == "form_status_check_skip":
                ask_dispatcher = CollectingDispatcher()
                await invoke_action(
                    "action_skip_status_check_outro",
                    ask_dispatcher,
                    SessionTracker(
                        slots=slots_after,
                        sender_id=session.get("user_id", "default"),
                        latest_message=latest_message,
                        active_loop=None,
                        requested_slot=None,
                    ),
                    domain,
                )
                dispatcher.messages.extend(ask_dispatcher.messages)
                next_state = "done"
                session["active_loop"] = None
                session["requested_slot"] = None
            else:
                next_state = "done"
                session["active_loop"] = None
                session["requested_slot"] = None

    elif state == "done":
        pass

    session["slots"].update(slot_updates)
    session["state"] = next_state

    expected = "buttons" if next_state in ("intro", "main_menu") else "text"
    form_states = (
        "form_grievance", "contact_form", "otp_form", "grievance_review", "status_check_form"
    )
    if next_state in form_states and session.get("requested_slot"):
        expected = "text"

    return (dispatcher.messages, next_state, expected)
