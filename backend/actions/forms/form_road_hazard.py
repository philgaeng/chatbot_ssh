"""CB-09: road hazard fast-path intake (subtype picker, preset category, map + photos)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseAction, BaseFormValidationAction
from backend.actions.forms.form_grievance import ValidateFormGrievance
from backend.actions.forms.intake_submit import complete_road_hazard_intake_submit

ROAD_HAZARD_CLASSIFICATION = "Road Hazard"


def derive_category_key(classification: str, generic_grievance_name: str) -> str:
    """Match ticketing.services.grievance_categories_catalog.derive_category_key."""
    return (
        f"{classification.replace('-', ' ').title()} - "
        f"{generic_grievance_name.replace('-', ' ').title()}"
    )

ROAD_HAZARD_SUBTYPES: Dict[str, Dict[str, str]] = {
    "dust": {
        "generic_name": "Dust",
        "label_en": "Dust",
        "label_ne": "धुलो",
        "payload": "/road_hazard_subtype_dust",
    },
    "flood_landslide": {
        "generic_name": "Flood and Landslide",
        "label_en": "Flood and Landslide",
        "label_ne": "बाढी र पहिरो",
        "payload": "/road_hazard_subtype_flood_landslide",
    },
    "potholes": {
        "generic_name": "Potholes",
        "label_en": "Potholes",
        "label_ne": "खाडल",
        "payload": "/road_hazard_subtype_potholes",
    },
    "accident": {
        "generic_name": "Accident",
        "label_en": "Accident",
        "label_ne": "दुर्घटना",
        "payload": "/road_hazard_subtype_accident",
    },
    "animal_on_road": {
        "generic_name": "Animal on Road",
        "label_en": "Animal on Road",
        "label_ne": "सडकमा जनावर",
        "payload": "/road_hazard_subtype_animal_on_road",
    },
    "others": {
        "generic_name": "Others",
        "label_en": "Others",
        "label_ne": "अन्य",
        "payload": "/road_hazard_subtype_others",
    },
}

SUBTYPE_PAYLOAD_PREFIX = "road_hazard_subtype_"

DUST_SUBTYPE = "dust"


def category_key_for_subtype(subtype: str) -> str:
    info = ROAD_HAZARD_SUBTYPES[subtype]
    return derive_category_key(ROAD_HAZARD_CLASSIFICATION, info["generic_name"])


def default_description_for_subtype(subtype: str) -> str:
    label = ROAD_HAZARD_SUBTYPES[subtype]["label_en"]
    return (
        f"Road hazard ({label.lower()}) report filed via the fast path "
        "(location and photos to follow)."
    )


DUST_CATEGORY = category_key_for_subtype(DUST_SUBTYPE)
DUST_DEFAULT_DESCRIPTION = default_description_for_subtype(DUST_SUBTYPE)


def normalize_road_hazard_subtype(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None
    if raw.startswith("/"):
        raw = raw.lstrip("/")
    if raw.startswith(SUBTYPE_PAYLOAD_PREFIX):
        raw = raw[len(SUBTYPE_PAYLOAD_PREFIX) :]
    if raw in ROAD_HAZARD_SUBTYPES:
        return raw
    return None


def is_road_hazard_intake(tracker) -> bool:
    """True when the session is on the road-hazard fast path."""
    return (
        tracker.get_slot("story_main") in ("road_hazard_grievance", "dust_grievance")
        or tracker.get_slot("intake_fast_path") in ("road_hazard", "dust")
    )


def is_dust_intake(tracker) -> bool:
    """Backward-compatible alias for road-hazard fast path checks."""
    return is_road_hazard_intake(tracker)


def _road_hazard_start_slot_sets(*, prefill_subtype: Optional[str] = None) -> List[SlotSet]:
    slots: List[SlotSet] = [
        SlotSet("story_main", "road_hazard_grievance"),
        SlotSet("grievance_sensitive_issue", False),
        SlotSet("intake_fast_path", "road_hazard"),
        SlotSet("road_hazard_description_status", None),
        SlotSet("road_hazard_new_detail", None),
    ]
    if prefill_subtype:
        slots.extend(
            [
                SlotSet("road_hazard_subtype", prefill_subtype),
                SlotSet("grievance_categories", [category_key_for_subtype(prefill_subtype)]),
                SlotSet("grievance_description", default_description_for_subtype(prefill_subtype)),
            ]
        )
    else:
        slots.extend(
            [
                SlotSet("road_hazard_subtype", None),
                SlotSet("grievance_categories", []),
                SlotSet("grievance_description", None),
            ]
        )
    return slots


class ActionStartRoadHazardGrievanceProcess(BaseAction):
    """Start road hazard fast path: IDs, then subtype picker."""

    def name(self) -> Text:
        return "action_start_road_hazard_grievance_process"

    async def execute_action(self, dispatcher, tracker, domain):
        return await self._start(dispatcher, tracker, prefill_subtype=None)

    async def _start(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        *,
        prefill_subtype: Optional[str],
    ) -> List[SlotSet]:
        BaseFormValidationAction.message_display_list_cat = True
        set_id_data = {
            "complainant_province": tracker.get_slot("complainant_province") or self.province,
            "complainant_district": tracker.get_slot("complainant_district") or self.district,
            "complainant_office": tracker.get_slot("complainant_office") or None,
            "source": "bot",
        }
        complainant_id = self.db_manager.generate_complainant_id(set_id_data)
        grievance_id = self.db_manager.generate_grievance_id(set_id_data)
        dispatcher.utter_message(
            json_message={
                "data": {
                    "grievance_id": grievance_id,
                    "complainant_id": complainant_id,
                    "event_type": "grievance_id_set",
                }
            }
        )
        return [
            SlotSet("grievance_id", grievance_id),
            SlotSet("complainant_id", complainant_id),
            *_road_hazard_start_slot_sets(prefill_subtype=prefill_subtype),
        ]


class ActionStartDustGrievanceProcess(ActionStartRoadHazardGrievanceProcess):
    """Backward-compatible entry: road hazard with Dust pre-selected."""

    def name(self) -> Text:
        return "action_start_dust_grievance_process"

    async def execute_action(self, dispatcher, tracker, domain):
        return await self._start(dispatcher, tracker, prefill_subtype=DUST_SUBTYPE)


class ValidateFormRoadHazard(ValidateFormGrievance):
    """Subtype picker, then optional note or File as is."""

    def name(self) -> Text:
        return "validate_form_road_hazard"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        if tracker.get_slot("road_hazard_new_detail") == "completed":
            return []
        if not tracker.get_slot("road_hazard_subtype"):
            return ["road_hazard_subtype"]
        return ["road_hazard_new_detail"]

    def _default_description(self, tracker: Tracker) -> str:
        subtype = tracker.get_slot("road_hazard_subtype") or DUST_SUBTYPE
        return default_description_for_subtype(subtype)

    def _preset_categories(self, tracker: Tracker) -> List[str]:
        subtype = tracker.get_slot("road_hazard_subtype") or DUST_SUBTYPE
        return [category_key_for_subtype(subtype)]

    def _update_description(self, current_text: str, new_text: str) -> str:
        if new_text.startswith("/"):
            new_text = ""
        updated = current_text + "\n" + new_text if current_text else new_text
        return updated.strip()

    async def extract_road_hazard_subtype(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "road_hazard_subtype",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_road_hazard_subtype(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        subtype = normalize_road_hazard_subtype(slot_value)
        if not subtype:
            return {}
        return {
            "road_hazard_subtype": subtype,
            "grievance_categories": [category_key_for_subtype(subtype)],
            "grievance_description": default_description_for_subtype(subtype),
            "road_hazard_description_status": None,
        }

    async def extract_road_hazard_new_detail(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "road_hazard_new_detail",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_road_hazard_new_detail(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        try:
            expected = {"restart", "add_more_details", "submit_details"}
            normalized = slot_value.strip() if isinstance(slot_value, str) else slot_value
            default_desc = self._default_description(tracker)
            preset = self._preset_categories(tracker)

            if isinstance(normalized, str) and not normalized:
                description = tracker.get_slot("grievance_description") or default_desc
                slots = await complete_road_hazard_intake_submit(
                    self,
                    tracker,
                    dispatcher,
                    domain,
                    description,
                    preset_categories=preset,
                )
                return {"road_hazard_new_detail": "completed", **slots}

            if normalized == "restart":
                return {
                    "road_hazard_new_detail": None,
                    "grievance_description": default_desc,
                    "road_hazard_description_status": "restart",
                }

            if normalized == "add_more_details":
                return {
                    "road_hazard_new_detail": None,
                    "road_hazard_description_status": "add_more_details",
                }

            if normalized == "submit_details":
                description = (tracker.get_slot("grievance_description") or "").strip()
                if not description:
                    description = default_desc
                self.logger.info(
                    "road_hazard_submit_details grievance_id=%s subtype=%s description_len=%s",
                    tracker.get_slot("grievance_id"),
                    tracker.get_slot("road_hazard_subtype"),
                    len(description),
                )
                slots = await complete_road_hazard_intake_submit(
                    self,
                    tracker,
                    dispatcher,
                    domain,
                    description,
                    preset_categories=preset,
                )
                return {"road_hazard_new_detail": "completed", **slots}

            if normalized and normalized not in expected:
                updated = self._update_description(
                    tracker.get_slot("grievance_description") or default_desc,
                    normalized,
                )
                return {
                    "road_hazard_new_detail": None,
                    "grievance_description": updated,
                    "road_hazard_description_status": "show_options",
                }

            return {}
        except Exception as e:
            self.logger.error(f"Error in validate_road_hazard_new_detail: {e}")
            raise Exception(f"Error in validate_road_hazard_new_detail: {e}") from e


# Backward-compatible form validator name
ValidateFormDust = ValidateFormRoadHazard


class ActionAskRoadHazardSubtype(BaseAction):
    def name(self) -> Text:
        return "action_ask_road_hazard_subtype"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        if tracker.get_slot("road_hazard_subtype"):
            return []
        utterance = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []


class ActionAskRoadHazardNewDetail(BaseAction):
    def name(self) -> Text:
        return "action_ask_road_hazard_new_detail"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        if tracker.get_slot("road_hazard_new_detail") == "completed":
            return []
        if not tracker.get_slot("road_hazard_subtype"):
            return []

        subtype = tracker.get_slot("road_hazard_subtype")
        default_desc = default_description_for_subtype(subtype)
        status = tracker.get_slot("road_hazard_description_status")

        if not status:
            utterance = self.get_utterance(1).format(
                subtype_label=ROAD_HAZARD_SUBTYPES[subtype]["label_en"]
            )
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            dispatcher.utter_message(
                json_message={"data": {"event_type": "disable_voice_note"}}
            )

        if status == "restart":
            dispatcher.utter_message(text=self.get_utterance(2))

        if status == "add_more_details":
            dispatcher.utter_message(text=self.get_utterance(3))

        if status == "show_options":
            description = tracker.get_slot("grievance_description") or default_desc
            utterance = self.get_utterance(4).format(grievance_description=description)
            buttons = self.get_buttons(4)
            dispatcher.utter_message(text=utterance, buttons=buttons)

        return []


class ActionAskDustNewDetail(ActionAskRoadHazardNewDetail):
    def name(self) -> Text:
        return "action_ask_dust_new_detail"
