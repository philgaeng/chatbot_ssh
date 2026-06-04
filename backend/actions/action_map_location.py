"""Map pin intake actions (CB-06)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher

from backend.actions.base_classes.base_classes import BaseAction
from backend.actions.base_classes.base_mixins import SKIP_VALUE
from backend.shared_functions.geo_pin import build_pin_patch, merge_grievance_location_blob
from backend.shared_functions.location_mapping import resolve_location_code_to_names

MAP_COORDINATES = "map_coordinates"


def location_skip_slot_updates() -> Dict[str, Any]:
    """Skip all location fields when the user declines location consent."""
    return {
        "complainant_location_consent": False,
        "complainant_province": SKIP_VALUE,
        "complainant_district": SKIP_VALUE,
        "complainant_municipality_temp": SKIP_VALUE,
        "complainant_municipality": SKIP_VALUE,
        "complainant_municipality_confirmed": False,
        "complainant_village": SKIP_VALUE,
        "complainant_village_temp": SKIP_VALUE,
        "complainant_village_confirmed": False,
        "complainant_ward": SKIP_VALUE,
        "complainant_address_temp": SKIP_VALUE,
        "complainant_address": SKIP_VALUE,
        "complainant_address_confirmed": False,
        "location_pin_status": "skipped",
    }


def build_map_filled_location_slots(
    lat: float,
    lng: float,
    *,
    province: Optional[str] = None,
    district: Optional[str] = None,
) -> Dict[str, Any]:
    """Prefill contact-form location slots from a map pin (ward=0, filler=map_coordinates)."""
    filler = MAP_COORDINATES
    coord_address = f"{lat:.5f}, {lng:.5f}"
    return {
        "complainant_location_consent": True,
        "complainant_province": province or filler,
        "complainant_district": district or filler,
        "complainant_municipality_temp": filler,
        "complainant_municipality": filler,
        "complainant_municipality_confirmed": True,
        "complainant_village_temp": filler,
        "complainant_village": filler,
        "complainant_village_confirmed": True,
        "complainant_ward": 0,
        "complainant_address_temp": coord_address,
        "complainant_address": coord_address,
        "complainant_address_confirmed": True,
        "location_pin_status": "set",
        "geo_lat": lat,
        "geo_lng": lng,
    }


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
    """Apply lat/lng from client payload into slots + grievance_location blob."""

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

        location_code = tracker.get_slot("location_code")
        names = (
            resolve_location_code_to_names(self.db_manager, location_code, self.language_code or "en")
            if location_code
            else {}
        )
        patch = build_pin_patch(float(lat), float(lng), location_code)
        if names.get("province_name"):
            patch["province_name"] = names["province_name"]
        if names.get("district_name"):
            patch["district_name"] = names["district_name"]

        grievance_id = tracker.get_slot("grievance_id")
        if grievance_id:
            existing = None
            try:
                row = self.db_manager.get_grievance_by_id(grievance_id)
                existing = (row or {}).get("grievance_location")
            except Exception:
                existing = None
            merged = merge_grievance_location_blob(existing, patch)
            self.db_manager.update_grievance(
                grievance_id,
                {"grievance_location": merged},
            )

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
