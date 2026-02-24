"""
Form loop driver: required_slots -> extract -> validate -> apply -> ask or complete.
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
from orchestrator.action_registry import invoke_action


async def run_form_turn(
    form: Any,
    session: Dict[str, Any],
    user_input: Optional[Dict[str, Any]],
    domain: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], bool]:
    """
    Run one form turn.

    Args:
        form: ValidateFormGrievance instance
        session: Session dict with slots, requested_slot, active_loop
        user_input: {"text": str, "intent": {"name": str}} or None for first ask
        domain: Domain dict with slots

    Returns:
        (messages, slot_updates, completed)
    """
    # Stub _trigger_async_classification for spike (no Celery)
    async def _stub_async_classification(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {}

    if hasattr(form, "_trigger_async_classification"):
        form._trigger_async_classification = _stub_async_classification

    slots = session.get("slots", {})
    domain_slots = list(domain.get("slots", {}).keys())
    dispatcher = CollectingDispatcher()
    tracker = SessionTracker(
        slots=slots,
        sender_id=session.get("user_id", "default"),
        latest_message=user_input or {},
        active_loop=session.get("active_loop"),
        requested_slot=session.get("requested_slot"),
    )

    required = await form.required_slots(domain_slots, dispatcher, tracker, domain)
    if not required:
        return (dispatcher.messages, {}, True)

    next_slot = _first_empty(required, slots)
    if next_slot is None:
        return (dispatcher.messages, {}, True)

    slot_updates: Dict[str, Any] = {}
    tracker._requested_slot = next_slot
    slots["requested_slot"] = next_slot

    if user_input and user_input.get("text"):
        raw = await form.extract_grievance_new_detail(dispatcher, tracker, domain)
        slot_value = raw.get("grievance_new_detail") if raw else None
        if slot_value is not None:
            slot_updates = await form.validate_grievance_new_detail(
                slot_value, dispatcher, tracker, domain
            )
        if slot_updates:
            slots.update(slot_updates)
            tracker._slots.update(slot_updates)

    required_after = await form.required_slots(
        domain_slots, dispatcher, tracker, domain
    )
    completed = len(required_after) == 0

    if not completed and not slot_updates.get("skip_validation_needed"):
        ask_dispatcher = CollectingDispatcher()
        ask_tracker = SessionTracker(
            slots=slots,
            sender_id=tracker.sender_id,
            latest_message=tracker.latest_message,
            active_loop=session.get("active_loop"),
            requested_slot=next_slot,
        )
        await invoke_action(
            "action_ask_grievance_new_detail",
            ask_dispatcher,
            ask_tracker,
            domain,
        )
        dispatcher.messages.extend(ask_dispatcher.messages)

    if completed:
        slot_updates["requested_slot"] = None
        slot_updates["active_loop"] = None

    return (dispatcher.messages, slot_updates, completed)


def _first_empty(required: List[str], slots: Dict[str, Any]) -> Optional[str]:
    """First slot in required that is empty/None."""
    for s in required:
        v = slots.get(s)
        if v is None or v == "":
            return s
    return None
