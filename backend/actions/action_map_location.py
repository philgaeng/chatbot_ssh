"""Map pin intake actions (CB-06)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from backend.actions.base_classes.base_classes import BaseAction
from backend.actions.base_classes.base_mixins import SKIP_VALUE


def location_skip_slot_updates() -> Dict[str, Any]:
    """Skip all location fields when the user declines location consent."""
    return {
        "complainant_location_consent": False,
        "complainant_province": SKIP_VALUE,
        "complainant_district": SKIP_VALUE,
        "complainant_municipality_temp": SKIP_VALUE,
        "complainant_municipality": SKIP_VALUE,
        "complainant_municipality_confirmed": True,
        "complainant_village": SKIP_VALUE,
        "complainant_village_temp": SKIP_VALUE,
        "complainant_village_confirmed": True,
        "complainant_ward": SKIP_VALUE,
        "complainant_address_temp": SKIP_VALUE,
        "complainant_address": SKIP_VALUE,
        "complainant_address_confirmed": True,
        "location_pin_status": "skipped",
    }


def build_map_filled_location_slots(
    lat: float,
    lng: float,
    *,
    province: Optional[str] = None,
    district: Optional[str] = None,
    location_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Prefill contact-form slots after a map pin.
    Coordinates persist on submit as complainant.location_geo (not grievance_location).
    """
    address_label = f"Map pin ({lat:.5f}, {lng:.5f})"
    updates: Dict[str, Any] = {
        "complainant_location_consent": True,
        "complainant_province": province or SKIP_VALUE,
        "complainant_district": district or SKIP_VALUE,
        "complainant_municipality_temp": SKIP_VALUE,
        "complainant_municipality": SKIP_VALUE,
        "complainant_municipality_confirmed": True,
        "complainant_village_temp": SKIP_VALUE,
        "complainant_village": SKIP_VALUE,
        "complainant_village_confirmed": True,
        "complainant_ward": SKIP_VALUE,
        "complainant_address_temp": address_label,
        "complainant_address": address_label,
        "complainant_address_confirmed": True,
        "location_pin_status": "map_pin",
        "geo_lat": lat,
        "geo_lng": lng,
    }
    if location_code:
        updates["location_code"] = location_code
    return updates


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
        dispatcher.utter_message(
            json_message={
                "data": {
                    "event_type": "open_map_picker",
                    "default_lat": 27.7172,
                    "default_lng": 85.324,
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

        utterance = self.get_utterance(1).format(
            lat=f"{float(lat):.5f}",
            lng=f"{float(lng):.5f}",
        )
        dispatcher.utter_message(text=utterance)

        filled = build_map_filled_location_slots(
            float(lat),
            float(lng),
            province=tracker.get_slot("complainant_province"),
            district=tracker.get_slot("complainant_district"),
            location_code=tracker.get_slot("location_code"),
        )
        return [SlotSet(k, v) for k, v in filled.items()]


def parse_map_pin_payload(payload: str) -> Dict[str, float]:
    """Parse /map_pin_set{\"lat\":..,\"lng\":..} style payloads."""
    raw = (payload or "").strip().lstrip("/")
    if raw.startswith("map_pin_set"):
        raw = raw[len("map_pin_set") :].strip()
    brace = raw.find("{")
    if brace < 0:
        raise ValueError("invalid map pin payload")
    data = json.loads(raw[brace:])
    return {"lat": float(data["lat"]), "lng": float(data["lng"])}
