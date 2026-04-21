"""Post-submit SEAH outro (spec 08)."""
from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseAction
from backend.actions.utils.seah_outro_logic import (
    format_contact_point_block,
    resolve_seah_outro_variant,
)


class ActionSeahOutro(BaseAction):
    def name(self) -> Text:
        return "action_seah_outro"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        self._initialize_language_and_helpers(tracker)
        slots = dict(tracker.current_slot_values())
        variant = resolve_seah_outro_variant(slots)
        language_code = tracker.get_slot("language_code") or "en"

        row = None
        try:
            row = self.db_manager.find_seah_contact_point(
                province=tracker.get_slot("complainant_province"),
                district=tracker.get_slot("complainant_district"),
                municipality=tracker.get_slot("complainant_municipality"),
                ward=str(tracker.get_slot("complainant_ward") or ""),
                project_uuid=tracker.get_slot("project_uuid"),
            )
        except Exception as e:
            self.logger.warning(f"action_seah_outro: contact point lookup failed: {e}")

        contact_block = ""
        events: List[Dict[Text, Any]] = []
        if row:
            contact_block = "\n\n" + format_contact_point_block(row, language_code)
            cid = row.get("seah_contact_point_id")
            if cid:
                events.append(SlotSet("seah_contact_point_id", cid))

        order = {
            "focal_default": 1,
            "victim_limited_contact": 2,
            "victim_contact_ok": 3,
            "not_victim_anonymous": 4,
            "not_victim_identified": 5,
        }
        idx = order.get(variant, 2)
        body = self.get_utterance(idx)
        full_text = body + contact_block
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=full_text, buttons=buttons)
        return events
