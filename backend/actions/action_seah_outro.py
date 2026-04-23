"""Post-submit SEAH outro (spec 08)."""
from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseAction
from backend.actions.utils.mapping_buttons import BUTTONS_SEAH_OUTRO


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
        variant = self.resolve_seah_outro_variant(slots)
        language_code = tracker.get_slot("language_code") or "en"

        row = self.find_seah_contact_point(tracker)

        contact_block = ""
        events: List[Dict[Text, Any]] = []
        if row:
            contact_block = "\n\n" + self.format_seah_contact_point_block(row, language_code)
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
        # Always include Close Session (and clean-window actions) for every outro variant.
        buttons = BUTTONS_SEAH_OUTRO.get(language_code, BUTTONS_SEAH_OUTRO["en"])
        dispatcher.utter_message(text=full_text, buttons=buttons)
        return events
