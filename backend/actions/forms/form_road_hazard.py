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
from backend.actions.grievance_intake.ensure_records import (
    grievance_id_set_json,
    resolve_intake_slot_ids,
)
from backend.actions.services.road_hazard.catalog import (
    DUST_CATEGORY,
    DUST_DEFAULT_DESCRIPTION,
    DUST_SUBTYPE,
    ROAD_HAZARD_CLASSIFICATION,
    ROAD_HAZARD_SUBTYPES,
    SUBTYPE_PAYLOAD_PREFIX,
    category_key_for_subtype,
    default_description_for_subtype,
    derive_category_key,
    normalize_road_hazard_subtype,
)

__all__ = [
    "DUST_CATEGORY",
    "DUST_DEFAULT_DESCRIPTION",
    "DUST_SUBTYPE",
    "ROAD_HAZARD_CLASSIFICATION",
    "ROAD_HAZARD_SUBTYPES",
    "SUBTYPE_PAYLOAD_PREFIX",
    "category_key_for_subtype",
    "default_description_for_subtype",
    "derive_category_key",
    "normalize_road_hazard_subtype",
    "is_road_hazard_intake",
    "is_dust_intake",
    "ActionStartRoadHazardGrievanceProcess",
    "ActionStartDustGrievanceProcess",
    "ValidateFormRoadHazard",
    "ValidateFormDust",
    "ActionAskRoadHazardSubtype",
    "ActionAskRoadHazardNewDetail",
    "ActionAskDustNewDetail",
]


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
        self._initialize_language_and_helpers(tracker)
        grievance_id, complainant_id = resolve_intake_slot_ids(
            self.db_manager,
            existing_grievance_id=tracker.get_slot("grievance_id"),
            existing_complainant_id=tracker.get_slot("complainant_id"),
            complainant_province=tracker.get_slot("complainant_province") or self.province,
            complainant_district=tracker.get_slot("complainant_district") or self.district,
            complainant_office=tracker.get_slot("complainant_office"),
            reuse_existing=tracker.get_slot("story_main") is None,
        )
        dispatcher.utter_message(json_message=grievance_id_set_json(grievance_id, complainant_id))
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
