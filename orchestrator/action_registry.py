"""
Action registry: invoke Rasa actions with adapters and parse events to slot updates.
"""

import asyncio
import os
import sys
from typing import Any, Dict, List

# Ensure project root and rasa_chatbot are on path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_RASA_DIR = os.path.join(_REPO_ROOT, "rasa_chatbot")
if _RASA_DIR not in sys.path:
    sys.path.insert(0, _RASA_DIR)

from orchestrator.adapters import CollectingDispatcher, SessionTracker

# Action class mapping (lazy import to avoid circular deps and heavy startup)
_ACTIONS: Dict[str, Any] = {}


def _get_action(action_name: str) -> Any:
    """Lazy-load action instances."""
    if not _ACTIONS:
        from rasa_chatbot.actions.generic_actions import (
            ActionIntroduce,
            ActionSetEnglish,
            ActionSetNepali,
            ActionMainMenu,
        )
        from rasa_chatbot.actions.forms.form_grievance import (
            ActionStartGrievanceProcess,
            ActionAskGrievanceNewDetail,
        )
        _ACTIONS["action_introduce"] = ActionIntroduce()
        _ACTIONS["action_set_english"] = ActionSetEnglish()
        _ACTIONS["action_set_nepali"] = ActionSetNepali()
        _ACTIONS["action_main_menu"] = ActionMainMenu()
        _ACTIONS["action_start_grievance_process"] = ActionStartGrievanceProcess()
        _ACTIONS["action_ask_grievance_new_detail"] = ActionAskGrievanceNewDetail()
    return _ACTIONS.get(action_name)


def events_to_slot_updates(events: List[Any]) -> Dict[str, Any]:
    """Extract SlotSet events to {slot_name: value}."""
    result: Dict[str, Any] = {}
    for e in events or []:
        if hasattr(e, "as_dict"):
            d = e.as_dict()
        elif isinstance(e, dict):
            d = e
        else:
            continue
        if d.get("event") == "slot":
            result[d["name"]] = d.get("value")
    return result


async def invoke_action(
    action_name: str,
    dispatcher: CollectingDispatcher,
    tracker: SessionTracker,
    domain: Dict[str, Any],
) -> List[Any]:
    """
    Invoke action by name. Returns list of events (SlotSet, etc.).
    dispatcher.messages contains any utterances.
    """
    action = _get_action(action_name)
    if not action:
        raise ValueError(f"Unknown action: {action_name}")
    return await action.run(dispatcher, tracker, domain)
