"""
Form for adding missing contact/location info (Spec 13: Add missing info flow).

Loads complainant by status_check_grievance_id_selected, collects only empty fields,
reuses contact validation. Persists to DB only when user presses "I'm done" / "Save and continue".
"""

from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from backend.actions.forms.form_contact import ContactFormValidationAction
from backend.actions.base_classes.base_classes import BaseAction


class ValidateFormModifyContact(ContactFormValidationAction):
    """Form to add missing contact/location fields for an existing grievance."""

    def name(self) -> Text:
        return "validate_form_modify_contact"

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
        _, missing = self.get_missing_contact_fields(tracker)
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

    def _clear_selection_for_next(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Clear selection for next menu. DB persistence happens only on 'I'm done'."""
        result["modify_missing_field_selected"] = None
        return result

    def persist_all_contact_fields_to_complainant(
        self, slots: Dict[str, Any]
    ) -> None:
        """Persist all collected contact fields to complainant in DB. Called on 'I'm done'."""
        grievance_id = slots.get("status_check_grievance_id_selected")
        if not grievance_id:
            return
        complainant = self.db_manager.get_complainant_data_by_grievance_id(
            grievance_id
        )
        if not complainant:
            return
        cid = complainant["complainant_id"]
        skip_confirmed = {"complainant_municipality_confirmed", "complainant_village_confirmed"}
        for field in self.CONTACT_FIELDS_ORDER:
            if field in skip_confirmed:
                continue
            val = slots.get(field) or slots.get(self._SLOT_TO_DB.get(field, field))
            if val is None or val == self.SKIP_VALUE:
                continue
            if field == "complainant_municipality_temp" and not slots.get("complainant_municipality_confirmed"):
                continue
            if field == "complainant_village_temp" and not slots.get("complainant_village_confirmed"):
                continue
            self._persist_field(cid, field, val)

    async def validate_complainant_phone(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_phone(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_phone"):
            return self._clear_selection_for_next(result)
        return result or {}

    async def validate_complainant_full_name(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_full_name(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_full_name"):
            return self._clear_selection_for_next(result)
        return result or {}

    async def validate_complainant_province(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_province(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_province"):
            return self._clear_selection_for_next(result)
        return result or {}

    async def validate_complainant_district(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        raw = (slot_value or "").strip()
        if "modify_missing_done" in raw:
            return {"modify_missing_info_complete": True, "modify_missing_field_selected": None}
        result = await super().validate_complainant_district(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_district"):
            return self._clear_selection_for_next(result)
        return result or {}

    async def validate_complainant_municipality_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if isinstance(slot_value, str) and "modify_missing_done" in slot_value:
            return {
                "modify_missing_info_complete": True,
                "modify_missing_field_selected": None,
            }
        result = await super().validate_complainant_municipality_temp(
            slot_value, dispatcher, tracker, domain
        )
        return result or {}

    async def validate_complainant_municipality_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if isinstance(slot_value, str) and "modify_missing_done" in slot_value:
            return {
                "modify_missing_info_complete": True,
                "modify_missing_field_selected": None,
            }
        # Reuse the shared confirmation logic from ContactFormValidationAction.
        result = await super().validate_complainant_municipality_confirmed(
            slot_value, dispatcher, tracker, domain
        )
        # When municipality is confirmed, persist it to the complainant and
        # clear the selection for the next missing field.
        if result and result.get("complainant_municipality_confirmed") is True:
            return self._clear_selection_for_next(result)
        return result or {}

    async def validate_complainant_village_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if isinstance(slot_value, str) and "modify_missing_done" in slot_value:
            return {
                "modify_missing_info_complete": True,
                "modify_missing_field_selected": None,
            }
        result = await super().validate_complainant_village_temp(
            slot_value, dispatcher, tracker, domain
        )
        return result or {}

    async def validate_complainant_village_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if isinstance(slot_value, str) and "modify_missing_done" in slot_value:
            return {
                "modify_missing_info_complete": True,
                "modify_missing_field_selected": None,
            }
        result = await super().validate_complainant_village_confirmed(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_village_confirmed") is True:
            return self._clear_selection_for_next(result)
        return result or {}

    async def validate_complainant_ward(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if isinstance(slot_value, str) and "modify_missing_done" in slot_value:
            return {
                "modify_missing_info_complete": True,
                "modify_missing_field_selected": None,
            }
        result = await super().validate_complainant_ward(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_ward"):
            return self._clear_selection_for_next(result)
        return result or {}

    async def validate_complainant_address_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if isinstance(slot_value, str) and "modify_missing_done" in slot_value:
            return {
                "modify_missing_info_complete": True,
                "modify_missing_field_selected": None,
            }
        result = await super().validate_complainant_address_temp(
            slot_value, dispatcher, tracker, domain
        )
        if result and result.get("complainant_address_temp"):
            return self._clear_selection_for_next(result)
        return result or {}

    async def validate_complainant_email_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if isinstance(slot_value, str) and "modify_missing_done" in slot_value:
            return {
                "modify_missing_info_complete": True,
                "modify_missing_field_selected": None,
            }
        result = await super().validate_complainant_email_temp(
            slot_value, dispatcher, tracker, domain
        )
        if result and (result.get("complainant_email_temp") or result.get("complainant_email")):
            return self._clear_selection_for_next(result)
        return result or {}


class ActionAskFormModifyContactComplainantPhone(BaseAction):
    """Ask for phone number in the add-missing-info flow with modify-specific wording."""

    def name(self) -> Text:
        return "action_ask_form_modify_contact_complainant_phone"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        self._initialize_language_and_helpers(tracker)
        utterance = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []


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

        # Map slots to user-friendly field labels per language
        labels_en = {
            "complainant_phone": "your phone number",
            "complainant_full_name": "your full name",
            "complainant_province": "your province",
            "complainant_district": "your district",
            "complainant_municipality_temp": "your municipality",
            "complainant_village_temp": "your village",
            "complainant_ward": "your ward",
            "complainant_address_temp": "your address",
            "complainant_email_temp": "your email address",
            "default": "the missing contact information",
        }
        labels_ne = {
            "complainant_phone": "तपाईंको फोन नम्बर",
            "complainant_full_name": "तपाईंको पुरा नाम",
            "complainant_province": "तपाईंको प्रदेश",
            "complainant_district": "तपाईंको जिल्ला",
            "complainant_municipality_temp": "तपाईंको नगरपालिका",
            "complainant_village_temp": "तपाईंको गाउँ",
            "complainant_ward": "तपाईंको वार्ड",
            "complainant_address_temp": "तपाईंको ठेगाना",
            "complainant_email_temp": "तपाईंको इमेल ठेगाना",
            "default": "नभएको सम्पर्क जानकारी",
        }
        labels = labels_ne if getattr(self, "language_code", "en") == "ne" else labels_en
        field_label = labels.get(requested_slot or "", labels["default"])

        # Use template from utterance mapping and inject the field label
        utterance_template = self.get_utterance(1)
        try:
            utterance = utterance_template.format(field_label=field_label)
        except Exception:
            # Fallback to the raw template if formatting fails for any reason
            utterance = utterance_template

        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []
