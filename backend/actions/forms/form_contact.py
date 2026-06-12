import re
import logging
from typing import Any, Text, Dict, List, Optional, Union, Tuple
from datetime import datetime

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.types import DomainDict
from backend.actions.base_classes.base_classes import BaseAction, BaseContactForm, BaseFormValidationAction
from backend.actions.forms._contact_validation_delegates import ContactValidationDelegates
from backend.actions.services.contact import required_slots as contact_required_slots


class ContactFormValidationAction(
    ContactValidationDelegates,
    BaseContactForm,
    BaseFormValidationAction,
):
    """
    Shared location validation logic for complainant location fields.
    Validators delegate to backend.actions.services.contact.validators.
    Extractors use BaseFormValidationAction slot-extraction framework.
    """

    async def extract_complainant_province(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_province",
            tracker,
            dispatcher,
            domain
        )

    async def extract_complainant_district(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(  
            "complainant_district",
            tracker,
            dispatcher,
            domain
        )

    async def extract_complainant_municipality_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_municipality_temp",
            tracker,
            dispatcher,
            domain
        )

    async def extract_complainant_municipality_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # First check if we have a municipality to confirm
        if not tracker.get_slot("complainant_municipality_temp"):
            return {}

        return await self._handle_boolean_and_category_slot_extraction(
            "complainant_municipality_confirmed",
            tracker,
            dispatcher,
            domain
        )

    async def extract_complainant_village_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_village_temp",
            tracker,
            dispatcher,
            domain
        )

    async def extract_complainant_village_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # First check if we have a village to confirm
        if not tracker.get_slot("complainant_village_temp"):
            return {}

        return await self._handle_boolean_and_category_slot_extraction(
            "complainant_village_confirmed",
            tracker,
            dispatcher,
            domain
        )

    async def extract_complainant_ward(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_ward",
            tracker,
            dispatcher,
            domain
        )

    async def extract_complainant_address_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_address_temp",
            tracker,
            dispatcher,
            domain
        )

    async def extract_complainant_address_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_boolean_and_category_slot_extraction(
            "complainant_address_confirmed",
            tracker,
            dispatcher,
            domain
        )

    async def extract_complainant_location_consent(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        result = await self._handle_boolean_and_category_slot_extraction(
            "complainant_location_consent",
            tracker,
            dispatcher,
            domain
        )
        return result

    async def extract_complainant_consent(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_and_category_slot_extraction(
            "complainant_consent",
            tracker,
            dispatcher,
            domain
        )

    async def extract_complainant_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_full_name",
            tracker,
            dispatcher,
            domain
        )

    async def extract_complainant_email_temp(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        slot_value = await self._handle_slot_extraction(
            "complainant_email_temp",
            tracker,
            dispatcher,
            domain
        )
        return slot_value

    async def extract_complainant_email_confirmed(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_email_confirmed",
            tracker,
            dispatcher,
            domain
        )


class ValidateFormContact(ContactFormValidationAction):
    """Form validation action for contact details collection.
    Uses shared complainant location slots and ContactFormValidationAction for validation.
    ContactFormValidationAction provides the following slots:
    - complainant_province
    - complainant_district
    - complainant_municipality_temp
    - complainant_municipality_confirmed
    - complainant_village_temp
    - complainant_village_confirmed
    - complainant_ward
    - complainant_address_temp
    - complainant_address_confirmed
    - complainant_consent
    - complainant_full_name
    - complainant_email_temp
    - complainant_email_confirmed
    """
    
    def __init__(self):
        super().__init__()
        

    def name(self) -> Text:
        return "validate_form_contact"
    
    async def required_slots(self, 
                       domain_slots: List[Text], 
                       dispatcher: CollectingDispatcher, 
                       tracker: Tracker, 
                       domain: DomainDict) -> List[Text]:
        """
        This function is used to determine the required slots for the contact form.
        Note: Phone collection has been moved to form_otp.
        For status_check flow, use form_otp directly instead of form_contact.
        """
        self._initialize_language_and_helpers(tracker)
        return contact_required_slots.contact_required_slots(tracker)

