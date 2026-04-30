import re
import logging
from typing import Any, Text, Dict, List, Optional, Union, Tuple
from datetime import datetime

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.types import DomainDict
from backend.actions.base_classes.base_classes import BaseAction, BaseContactForm, BaseFormValidationAction


  #-----------------------------------------------------------------------------
 ######################## ValidateFormContact Actions ########################
 #-----------------------------------------------------------------------------


class ContactFormValidationAction(BaseContactForm, BaseFormValidationAction):
    """
    Shared location validation logic for complainant location fields.
    
    Validates:
    - complainant_province
    - complainant_district  
    - complainant_municipality_temp
    - complainant_municipality_confirmed
    - complainant_village_temp
    - complainant_village_confirmed
    - complainant_ward
    - complainant_address_temp
    - complainant_address_confirmed
    
    Can be used by any form that collects location information:
    - ValidateFormContact
    - ValidateFormStatusCheckSkip
    - Any future forms that need location data
    """

    def _merge_seah_contact_provided_from_partial(
        self, tracker: Tracker, partial: Dict[str, Any]
    ) -> Dict[str, Any]:
        merged = self.seah_contact_provided_update(
            tracker.get_slot("story_main"),
            dict(tracker.current_slot_values()),
            partial,
        )
        merged.update(
            self.upsert_active_party_payload(
                dict(tracker.current_slot_values()),
                partial,
            )
        )
        return merged

    # ========== Province ==========
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
        
    async def validate_complainant_province(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            return {"complainant_province": None}
        
        # Check if the province is valid
        if not self.helpers.check_province(slot_value):
            message = self.get_utterance(2)
            message = message.format(slot_value=slot_value)
            dispatcher.utter_message(text=message)
            return {"complainant_province": None}
        
        result = self.helpers.check_province(slot_value).title()
        message = self.get_utterance(3) 
        message = message.format(slot_value=slot_value, result=result)
        dispatcher.utter_message(text=message)
        
        return {"complainant_province": result}
    
    # ========== District ==========
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
        
    async def validate_complainant_district(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            return {"complainant_district": None}
            
        province = tracker.get_slot("complainant_province").title()
        if not self.helpers.check_district(slot_value, province):
            message = self.get_utterance(2)
            message = message.format(slot_value=slot_value)
            dispatcher.utter_message(text=message)
            return {"complainant_district": None}
            
        result = self.helpers.check_district(slot_value, province).title()
        message = self.get_utterance(3)
        message = message.format(slot_value=slot_value, result=result)
        dispatcher.utter_message(text=message)
        
        return {"complainant_district": result}
    
    # ========== Municipality ==========
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
        
    async def validate_complainant_municipality_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # Deal with the slot_skipped case
        if slot_value == self.SKIP_VALUE:
            return {
                "complainant_municipality_temp": self.SKIP_VALUE,
                "complainant_municipality": self.SKIP_VALUE,
                "complainant_municipality_confirmed": False
            }
        
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            return {"complainant_municipality_temp": None}
                
        # Validate municipality input with rapidfuzz
        validated_municipality = self.helpers.validate_municipality_input(
            slot_value, 
            tracker.get_slot("complainant_province"),
            tracker.get_slot("complainant_district")
        )
        
        if validated_municipality:
            return {"complainant_municipality_temp": validated_municipality}
        else:
            return {
                "complainant_municipality_temp": None,
                "complainant_municipality": None,
                "complainant_municipality_confirmed": None
            }
                
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
    
    async def validate_complainant_municipality_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if slot_value == True:
            # Save the municipality to the slot
            result = {
                "complainant_municipality_confirmed": True,
                "complainant_municipality": tracker.get_slot("complainant_municipality_temp")
            }
        elif slot_value == False:
            result = {
                "complainant_municipality_confirmed": None,
                "complainant_municipality_temp": None,
                "complainant_municipality": None
            }
        else:
            result = {}
        
        self.logger.debug(f"Validate complainant_municipality_confirmed: {result}")
        return result
    
    # ========== Village ==========
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
    
    async def validate_complainant_village_temp(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            result = {
                "complainant_village_temp": self.SKIP_VALUE,
                "complainant_village_confirmed": False,
                "complainant_village": self.SKIP_VALUE,
                "complainant_ward": self.SKIP_VALUE
            }
            return result
        
        try:
            slot_value = slot_value.title().strip()
            # First validate string length
            if not self.helpers.validate_string_length(slot_value, min_length=2):
                message = self.get_utterance(1)
                dispatcher.utter_message(text=message)
                result = {"complainant_village_temp": None}
                return result
        except Exception as e:
            self.logger.error(f"Error validating complainant_village - cannot validate string length: {e}")
            result = {"complainant_village_temp": None}
            return result
        
        try:
            complainant_municipality = tracker.get_slot("complainant_municipality")
            self.logger.debug(f"complainant_municipality: {complainant_municipality}")
            # Validate the village name with the municipality name using fuzzy matching
            validated_village, validated_ward = self.helpers.validate_village_input(
                slot_value, 
                tracker.get_slot("complainant_municipality")
            )
            self.logger.debug(f"output of validate_village_input: {validated_village} {validated_ward}")
        except Exception as e:
            self.logger.error(f"Error validating complainant_village - cannot validate village name using fuzzy matching: {e}")
            result = {"complainant_village": None}
            return result
        
        try:
            if validated_village and validated_village == slot_value:
                result = {
                    "complainant_village_temp": validated_village,
                    "complainant_village_confirmed": True,
                    "complainant_village": validated_village,
                    "complainant_ward": validated_ward
                }
            elif validated_village and validated_village != slot_value:
                result = {
                    "complainant_village_temp": validated_village,
                    "complainant_ward": validated_ward
                }
            else:
                result = {
                    "complainant_village_temp": slot_value,
                    "complainant_village_confirmed": False,
                    "complainant_village": slot_value
                }
                
            self.logger.debug(f"Validate complainant_village: {result}")
        except Exception as e:
            self.logger.error(f"Error validating complainant_village - validate_village_input {validated_village} {validated_ward}: {e}")
            result = {"complainant_village_temp": None}
        
        return result
    
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
    
    async def validate_complainant_village_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if slot_value == True:
            # Save the village to the slot
            result = {
                "complainant_village_confirmed": True,
                "complainant_village": tracker.get_slot("complainant_village_temp"),
                "complainant_ward": tracker.get_slot("complainant_ward")
            }
        elif slot_value == False:
            result = {
                "complainant_village_confirmed": False,
                "complainant_village": tracker.get_slot("complainant_village_temp"),
                "complainant_ward": None
            }
        else:
            result = {}
        
        self.logger.debug(f"Validate complainant_village_confirmed: {result}")
        return result
    
    # ========== Ward ==========
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

    async def validate_complainant_ward(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            result = {"complainant_ward": self.SKIP_VALUE}
        else:
            raw = str(slot_value).strip()
            if not raw.isdigit():
                result = {"complainant_ward": None}
            else:
                result = {"complainant_ward": raw}

        self.logger.debug(f"Validate complainant_ward: {result}")
        return result
    
    # ========== Address ==========
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
    
    async def validate_complainant_address_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate complainant_address value."""
        if slot_value == self.SKIP_VALUE:
            result = {"complainant_address_temp": self.SKIP_VALUE}
            return result
            
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            result = {"complainant_address_temp": None}
            return result
        
        result = {"complainant_address_temp": slot_value}
        self.logger.debug(f"Validate complainant_address_temp: {result}")
        return result

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

    async def validate_complainant_address_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # Handle rejection of address confirmation
        if slot_value == False:
            message = self.get_utterance(1)
            dispatcher.utter_message(text="Please enter your correct village and address")
            result = {
                "complainant_village": None,
                "complainant_address": None,
                "complainant_address_temp": None,
                "complainant_address_confirmed": None
            }
            return result
        
        # Check if we have a confirmation
        if slot_value == True:
            address = tracker.get_slot("complainant_address_temp")
            result = {
                "complainant_address": address,
                "complainant_address_confirmed": True
            }
            result.update(self._merge_seah_contact_provided_from_partial(tracker, result))
            return result
        
        return {}

    
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
    
    async def validate_complainant_location_consent(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate complainant_location_consent value."""
        if slot_value is True:
            result = {"complainant_location_consent": True}
        elif slot_value is False:
            result = {"complainant_location_consent": False,
                    "complainant_municipality_temp":self.SKIP_VALUE,
                    "complainant_municipality":self.SKIP_VALUE,
                    "complainant_municipality_confirmed": False,
                    "complainant_village":self.SKIP_VALUE,
                    "complainant_village_temp":self.SKIP_VALUE,
                    "complainant_village_confirmed": False,
                    "complainant_ward":self.SKIP_VALUE,
                    "complainant_address_temp":self.SKIP_VALUE,
                    "complainant_address":self.SKIP_VALUE,
                    "complainant_address_confirmed": False}
        self.logger.debug(f"Validate complainant_location_consent: {result}")
        return result
    
    # Location validation methods (province, district, municipality, village, ward, address)
    # are now inherited from LocationValidationMixin
    
    async def extract_complainant_consent(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_and_category_slot_extraction(
            "complainant_consent",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_complainant_consent(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        
        if slot_value == False:
            result = {"complainant_consent": False,
                    "complainant_full_name": self.SKIP_VALUE,
                    "complainant_email_temp": self.SKIP_VALUE,
                    "complainant_email_confirmed": self.SKIP_VALUE
                    }

        elif slot_value == True:
            result = {"complainant_consent": True,
                    "complainant_full_name": None,
                    "complainant_email_temp": None,
                    "complainant_email_confirmed": None
                    }
        else:
            return {}
        self.logger.debug(f"Validate complainant_consent: {result['complainant_consent']}")
        result.update(self._merge_seah_contact_provided_from_partial(tracker, result))
        return result
        

    async def extract_complainant_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_full_name",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_complainant_full_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        is_focal_reporter_name_stage = (
            tracker.get_slot("story_main") == "seah_intake"
            and tracker.get_slot("seah_focal_stage") == "bootstrap_reporter_contact"
        )
        is_skip = isinstance(slot_value, str) and self.SKIP_VALUE in slot_value

        if is_skip and is_focal_reporter_name_stage:
            result = {"complainant_full_name": None}
        elif is_skip:
            result = {"complainant_full_name": self.SKIP_VALUE}
        
        elif not slot_value or slot_value.startswith('/'):
            result = {"complainant_full_name": None}

        elif len(slot_value)<3:
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            result = {"complainant_full_name": None}
        
        else :
            result = {"complainant_full_name": slot_value}
            
        self.logger.debug(f"Validate complainant_full_name: {result['complainant_full_name']}")
        result.update(self._merge_seah_contact_provided_from_partial(tracker, result))
        return result
    
    async def extract_complainant_email_temp(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        slot_value = await self._handle_slot_extraction(
            "complainant_email_temp",
            tracker,
            dispatcher,
            domain
        )
        return slot_value
    
    async def validate_complainant_email_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        language = self.language_code
        #deal with the slot_skipped case
        if slot_value == self.SKIP_VALUE:
            result = {"complainant_email_temp": self.SKIP_VALUE,
                    "complainant_email_confirmed": False,
                    "complainant_email": self.SKIP_VALUE
                    }
            self.logger.debug(f"Validate complainant_email_temp: {result['complainant_email_temp']}")
            result.update(self._merge_seah_contact_provided_from_partial(tracker, result))
            return result
        
        
        extracted_email = self.helpers.email_extract_from_text(slot_value)
        if not extracted_email:
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            result = {"complainant_email_temp": None}
            self.logger.debug(f"Validate complainant_email_temp: {result['complainant_email_temp']}")
            result.update(self._merge_seah_contact_provided_from_partial(tracker, result))
            return result
        
        # Use consistent validation methods
        if not self.helpers.email_is_valid_format(extracted_email):
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            result = {"complainant_email_temp": None}
            self.logger.debug(f"Validate complainant_email_temp: invalid format")
            result.update(self._merge_seah_contact_provided_from_partial(tracker, result))
            return result

        # Check for Nepali email domain (includes Gmail, Yahoo, Outlook - commonly used in Nepal)
        is_nepal_domain = self.helpers.email_is_valid_nepal_domain(extracted_email)
        self.logger.debug(
            f"email_is_valid_nepal_domain({extracted_email}) = {is_nepal_domain}"
        )
        if not is_nepal_domain:
            # Keep the email in slot but ask user to confirm non-Nepali domain
            result = {"complainant_email_temp": extracted_email,
                    "complainant_email_confirmed": None}
        else:
            # All validations pass (e.g. gmail.com, yahoo.com, .com.np)
            result = {"complainant_email_temp": extracted_email,
                    "complainant_email_confirmed": True,
                    "complainant_email": extracted_email}
        self.logger.debug(f"Validate complainant_email_temp: {result.get('complainant_email_temp')}")
        result.update(self._merge_seah_contact_provided_from_partial(tracker, result))
        return result
    
    async def extract_complainant_email_confirmed(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_email_confirmed",
            tracker,
            dispatcher,
            domain
        )
    async def validate_complainant_email_confirmed(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        """Validate the user's confirmation of their email address.
        
        This function handles three possible responses:
        - slot_skipped: User chose to skip providing an email
        - slot_confirmed: User confirmed their non-Nepali email domain is correct
        - slot_edited: User wants to edit their email and try again
        
        Args:
            slot_value: The value received from the user's response
            dispatcher: The dispatcher used to send messages to the user
            tracker: The conversation tracker
            domain: The bot's domain configuration
            
        Returns:
            Dict containing updates to the relevant email slots based on user's choice
        """
        if slot_value == self.SKIP_VALUE:
            result = {"complainant_email_confirmed": self.SKIP_VALUE}
        elif slot_value in ("slot_confirmed", "/slot_confirmed"):
            result = {"complainant_email_confirmed": True}
        elif slot_value in ("slot_edited", "/slot_edited"):
            result = {"complainant_email_temp": None,
                    "complainant_email_confirmed": None}
        else:
            result = {}
        if result:
            self.logger.debug(f"Validate complainant_email_confirmed: {result.get('complainant_email_confirmed')}")
            result.update(self._merge_seah_contact_provided_from_partial(tracker, result))
        return result
    
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
        story_main = tracker.get_slot("story_main")
        sensitive_issues_follow_up = tracker.get_slot("sensitive_issues_follow_up")
        seah_focal_stage = tracker.get_slot("seah_focal_stage")
        seah_role = tracker.get_slot("seah_victim_survivor_role")
        
        required_slots_location = ["complainant_location_consent", 
                      "complainant_province",
                      "complainant_district",
                      "complainant_municipality_temp", 
                      "complainant_municipality_confirmed", 
                      "complainant_village_temp",
                      "complainant_village_confirmed",
                      "complainant_ward",
                      "complainant_address_temp", 
                      "complainant_address_confirmed",
                      "complainant_address"
                      ]
        required_slots_location_seah = [
                      "complainant_province",
                      "complainant_district",
                      "complainant_municipality_temp",
                      "complainant_municipality_confirmed",
                      ]
        required_slots_location_seah_municipality_only = [
                      "complainant_province",
                      "complainant_district",
                      "complainant_municipality_temp",
                      "complainant_municipality_confirmed",
                      ]
        required_slots_contact = ["complainant_consent", "complainant_full_name", "complainant_email_temp", "complainant_email_confirmed"]

        # Focal reporter bootstrap: name only; consent defaults True in state_machine;
        # location is collected in complainant_contact (affected person).
        if story_main == "seah_intake" and seah_focal_stage == "bootstrap_reporter_contact":
            return ["complainant_full_name"]

        # Focal flow no longer collects complainant profile/contact fields in chatbot.
        if story_main == "seah_intake" and seah_focal_stage == "complainant_contact":
            return []

        # In anonymous dedicated SEAH intake, do not ask identity/contact questions.
        if story_main == "seah_intake" and sensitive_issues_follow_up == "anonymous":
            if seah_role in {"victim_survivor", "not_victim_survivor"}:
                return required_slots_location_seah_municipality_only
            return required_slots_location_seah

        # In SEAH intake, skip location-consent question and go directly to location fields.
        if story_main == "seah_intake":
            if seah_role in {"victim_survivor", "not_victim_survivor"}:
                return required_slots_location_seah_municipality_only + required_slots_contact
            return required_slots_location_seah + required_slots_contact

        return required_slots_location + required_slots_contact

