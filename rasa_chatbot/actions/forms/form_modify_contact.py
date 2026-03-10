"""
Form for adding missing contact/location info (Spec 13: Add missing info flow).

Loads complainant by status_check_grievance_id_selected, collects only empty fields,
reuses contact validation, and persists to DB after each field.
"""

from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from rasa_chatbot.actions.forms.form_contact import ContactFormValidationAction
from rasa_chatbot.actions.base_classes.base_classes import BaseAction


# Order of fields per Spec 13; we only ask for those that are missing
MODIFY_MISSING_FIELDS_ORDER = [
    "complainant_phone",
    "complainant_full_name",
    "complainant_province",
    "complainant_district",
    "complainant_municipality_temp",
    "complainant_village_temp",
    "complainant_ward",
    "complainant_address_temp",
    "complainant_email_temp",
]


def _is_empty(val: Any, skip_value: str) -> bool:
    return val is None or val == "" or val == skip_value


class ValidateFormModifyContact(ContactFormValidationAction):
    """Form to add missing contact/location fields for an existing grievance."""

    def name(self) -> Text:
        return "validate_form_modify_contact"

    def _get_complainant_and_missing(
        self, tracker: Tracker
    ) -> tuple[Optional[Dict], List[Text]]:
        """Load complainant and return list of missing field names in order."""
        grievance_id = tracker.get_slot("status_check_grievance_id_selected")
        if not grievance_id:
            return None, []

        complainant = self.db_manager.get_complainant_data_by_grievance_id(grievance_id)
        if not complainant:
            return None, []

        # Use slots (may have loaded complainant) merged with DB
        slots = dict(tracker.slots)
        for k, v in complainant.items():
            if k not in slots or slots[k] is None:
                slots[k] = v

        missing: List[Text] = []
        for field in MODIFY_MISSING_FIELDS_ORDER:
            val = slots.get(field)
            if _is_empty(val, self.SKIP_VALUE):
                missing.append(field)
        return complainant, missing

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        if tracker.get_slot("modify_missing_info_complete"):
            return []
        _, missing = self._get_complainant_and_missing(tracker)
        if not missing:
            return []  # Zero-missing: form completes, show "all complete" in state_machine
        return missing

    # Map slot names to DB column names for update_complainant
    _SLOT_TO_DB = {
        "complainant_municipality_temp": "complainant_municipality",
        "complainant_village_temp": "complainant_village",
        "complainant_address_temp": "complainant_address",
        "complainant_email_temp": "complainant_email",
    }

    def _persist_field(
        self, complainant_id: str, field: str, value: Any
    ) -> None:
        """Persist a single field to complainant in DB."""
        if not complainant_id or value is None:
            return
        db_field = self._SLOT_TO_DB.get(field, field)
        try:
            self.db_manager.update_complainant(complainant_id, {db_field: value})
        except Exception as e:
            self.logger.error(f"Failed to update complainant {complainant_id} field {db_field}: {e}")

    def _persist_and_clear_selection(
        self, tracker: Tracker, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """After validate, persist the field and clear selection for next menu."""
        grievance_id = tracker.get_slot("status_check_grievance_id_selected")
        complainant = self.db_manager.get_complainant_data_by_grievance_id(grievance_id) if grievance_id else None
        if complainant:
            for field in MODIFY_MISSING_FIELDS_ORDER:
                val = result.get(field) or result.get(
                    self._SLOT_TO_DB.get(field, field)
                )
                if val is not None and val != self.SKIP_VALUE:
                    self._persist_field(complainant["complainant_id"], field, val)
                    break
        result["modify_missing_field_selected"] = None
        return result

    async def validate_complainant_phone(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if raw.startswith("/") and "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_phone(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_phone"):
            return self._persist_and_clear_selection(tracker, result)
        return result or {}

    async def validate_complainant_full_name(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if raw.startswith("/") and "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_full_name(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_full_name"):
            return self._persist_and_clear_selection(tracker, result)
        return result or {}

    async def validate_complainant_province(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if raw.startswith("/") and "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_province(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_province"):
            return self._persist_and_clear_selection(tracker, result)
        return result or {}

    async def validate_complainant_district(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if raw.startswith("/") and "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_district(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_district"):
            return self._persist_and_clear_selection(tracker, result)
        return result or {}

    async def validate_complainant_municipality_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if raw.startswith("/") and "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_municipality_temp(
            slot_value, dispatcher, tracker, domain
        )
        if result and "complainant_municipality_temp" in result and result.get("complainant_municipality_temp"):
            return self._persist_and_clear_selection(tracker, result)
        return result or {}

    async def validate_complainant_village_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if raw.startswith("/") and "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_village_temp(
            slot_value, dispatcher, tracker, domain
        )
        if result and "complainant_village_temp" in result and result.get("complainant_village_temp"):
            return self._persist_and_clear_selection(tracker, result)
        return result or {}

    async def validate_complainant_ward(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if raw.startswith("/") and "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_ward(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_ward"):
            return self._persist_and_clear_selection(tracker, result)
        return result or {}

    async def validate_complainant_address_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if raw.startswith("/") and "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_address_temp(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_address_temp"):
            return self._persist_and_clear_selection(tracker, result)
        return result or {}

    async def validate_complainant_email_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if raw.startswith("/") and "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_email_temp(
            slot_value, dispatcher, tracker, domain
        )
        if result and (result.get("complainant_email_temp") or result.get("complainant_email")):
            return self._persist_and_clear_selection(tracker, result)
        return result or {}


class ActionAskModifyMissingField(BaseAction):
    """Ask for a missing field with modify-specific prompt and [Skip] [I'm done] buttons."""

    def name(self) -> Text:
        return "action_ask_modify_missing_field"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        self._initialize_language_and_helpers(tracker)
        requested_slot = tracker.get_slot("requested_slot")
        # Delegate to the existing contact ask action for the specific slot
        # We use utterance 1 for all; form_modify_contact can define per-field prompts
        utterance = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []
