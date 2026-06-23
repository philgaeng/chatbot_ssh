"""Map pin intake actions (CB-06)."""

from __future__ import annotations

from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from backend.actions.base_classes.base_classes import BaseAction
from backend.actions.services.location.map_pin import (
    build_map_filled_location_slots,
    location_skip_slot_updates,
    parse_map_pin_payload,
)

__all__ = [
    "build_map_filled_location_slots",
    "location_skip_slot_updates",
    "parse_map_pin_payload",
    "ActionAskLocationMethod",
    "ActionAskMapLocation",
    "ActionOpenMapPicker",
    "ActionApplyMapPin",
]


class ActionAskLocationMethod(BaseAction):
    """Ask manual entry vs map (after location consent)."""

    def name(self) -> Text:
        return "action_ask_location_method"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text=self.get_utterance(1),
            buttons=self.get_buttons(1),
        )
        return []


class ActionAskMapLocation(BaseAction):
    """Map pin instructions + fallback buttons (does not open the modal)."""

    def name(self) -> Text:
        return "action_ask_map_location"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text=self.get_utterance(1),
            buttons=self.get_buttons(1),
        )
        return []


class ActionOpenMapPicker(BaseAction):
    """Open the Leaflet map modal (only after user chose Use the map / Open map)."""

    def name(self) -> Text:
        return "action_open_map_picker"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # Omit default_lat/lng so the web client centers on device GPS (mapPicker.js).
        dispatcher.utter_message(
            json_message={
                "data": {
                    "event_type": "open_map_picker",
                }
            }
        )
        return []


class ActionApplyMapPin(BaseAction):
    """Acknowledge map pin in-session; DB write happens on final submit."""

    def name(self) -> Text:
        return "action_apply_map_pin"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        lat = tracker.get_slot("geo_lat")
        lng = tracker.get_slot("geo_lng")
        if lat is None or lng is None:
            return [SlotSet("location_pin_status", "missing")]

        dispatcher.utter_message(
            json_message={
                "data": {
                    "event_type": "status_banner",
                    "banner_key": "map_saved",
                    "lat": f"{float(lat):.5f}",
                    "lng": f"{float(lng):.5f}",
                }
            }
        )

        filled = build_map_filled_location_slots(
            float(lat),
            float(lng),
            province=tracker.get_slot("complainant_province"),
            district=tracker.get_slot("complainant_district"),
            location_code=tracker.get_slot("location_code"),
        )
        return [SlotSet(k, v) for k, v in filled.items()]
