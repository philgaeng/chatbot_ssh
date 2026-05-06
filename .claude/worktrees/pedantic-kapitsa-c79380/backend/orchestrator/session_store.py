"""
In-memory session store for the orchestrator.

Session structure: user_id, state, active_loop, requested_slot, slots, updated_at
Initial session: state=intro, slots from flow logic spec.
"""

from datetime import datetime
from typing import Any, Dict, Optional

# Default slot values for initial session (from 04_flow_logic.md)
DEFAULT_SLOTS: Dict[str, Any] = {
    "language_code": None,
    "complainant_province": "Koshi",
    "complainant_district": "Jhapa",
    "story_main": None,
    "grievance_id": None,
    "complainant_id": None,
    "grievance_sensitive_issue": False,
    "grievance_description": None,
    "grievance_new_detail": None,
    "grievance_description_status": None,
    "requested_slot": None,
    "skip_validation_needed": None,
    "skipped_detected_text": None,
}


def _initial_slots(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build initial slots dict, optionally overriding defaults from config."""
    slots = DEFAULT_SLOTS.copy()
    if overrides:
        slots.update(overrides)
    return slots


def create_session(user_id: str, slot_defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a new session for a user.

    Args:
        user_id: User identifier
        slot_defaults: Optional overrides for default slot values (e.g. from config)

    Returns:
        Session dict with state=intro, initial slots
    """
    slots = _initial_slots(slot_defaults)
    return {
        "user_id": user_id,
        "state": "intro",
        "active_loop": None,
        "requested_slot": None,
        "slots": slots,
        "updated_at": datetime.utcnow(),
    }


# In-memory store: user_id -> session
_sessions: Dict[str, Dict[str, Any]] = {}


def get_session(user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session for user_id, or None if not found."""
    return _sessions.get(user_id)


def save_session(session: Dict[str, Any]) -> None:
    """Persist session. Updates updated_at."""
    session["updated_at"] = datetime.utcnow()
    _sessions[session["user_id"]] = session
