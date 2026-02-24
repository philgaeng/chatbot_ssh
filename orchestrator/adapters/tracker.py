"""
SessionTracker - adapter matching Rasa Tracker surface used by base_mixins,
base_classes, and form_grievance so existing Rasa actions can run without Rasa runtime.
"""

from typing import Any, Dict, Optional


class SessionTracker:
    """
    Provides the Tracker interface required by rasa_chatbot actions.
    Used by base_classes, base_mixins, and form_grievance.
    """

    def __init__(
        self,
        slots: Dict[str, Any],
        sender_id: str,
        latest_message: Optional[Dict[str, Any]] = None,
        active_loop: Optional[str] = None,
        requested_slot: Optional[str] = None,
    ) -> None:
        self._slots = dict(slots)
        self._sender_id = sender_id
        self._latest_message = latest_message or {}
        self._active_loop = active_loop
        self._requested_slot = requested_slot
        if requested_slot is not None and "requested_slot" not in self._slots:
            self._slots["requested_slot"] = requested_slot

    def get_slot(self, key: str) -> Any:
        """Return slot value; requested_slot uses _requested_slot when set."""
        if key == "requested_slot" and self._requested_slot is not None:
            return self._requested_slot
        return self._slots.get(key)

    @property
    def sender_id(self) -> str:
        return self._sender_id

    @property
    def slots(self) -> Dict[str, Any]:
        return self._slots

    @property
    def latest_message(self) -> Dict[str, Any]:
        """Actions use latest_message.get('text'), .get('intent', {}).get('name')."""
        return self._latest_message

    @property
    def active_loop(self) -> Optional[Dict[str, Any]]:
        """Returns {'name': active_loop} or None. Matches Rasa Tracker.active_loop."""
        return {"name": self._active_loop} if self._active_loop else None
