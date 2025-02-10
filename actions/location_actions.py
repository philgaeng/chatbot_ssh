# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
import logging
from typing import Any, Text, Dict, List
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from twilio.rest import Client
from actions.helpers import LocationValidator  # Add this import
from .constants import QR_PROVINCE, QR_DISTRICT, DISTRICT_LIST  # Import the constants


logger = logging.getLogger(__name__)



# Action to prepopulate location based on QR code
class ActionPrepopulateLocation(Action):
    def name(self) -> Text:
        return "action_prepopulate_location"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        qr_code = tracker.get_slot("qr_code")  # Assume this is pre-set
        location_mapping = {
            "QR001": {"user_district": "Kathmandu", "user_municipality": "KMC"},
            "QR002": {"user_district": "Bhaktapur", "user_municipality": "Bhaktapur"},
        }
        prepopulated = location_mapping.get(qr_code, {})

        if prepopulated:
            dispatcher.utter_message(response="utter_prepopulate_location_success", 
                                      district=prepopulated.get("user_district"), 
                                      municipality=prepopulated.get("user_municipality"))
        else:
            dispatcher.utter_message(response="utter_prepopulate_location_failure")

        return [
            SlotSet("user_district", prepopulated.get("user_district")),
            SlotSet("user_municipality", prepopulated.get("user_municipality")),
        ]

class ActionAskLocation(Action):
    def name(self) -> str:
        return "action_ask_location"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        dispatcher.utter_message(
            response="utter_ask_location",
            buttons=[
                {"title": "Yes", "payload": "/start_location_process"},
                {"title": "Skip", "payload": "/ask_contact_details"},
                {"title": "Exit", "payload": "/goodbye"}
            ]
        )
        return []
    
######### Municipality

class ActionConfirmMunicipality(Action):
    def name(self) -> str:
        return "action_confirm_municipality"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # province = tracker.get_slot("user_province")
        # district = tracker.get_slot("user_district")
        municipality = tracker.get_slot("user_municipality")
        # ward = tracker.get_slot("user_ward")
        # village = tracker.get_slot("user_village")
        # address = tracker.get_slot("user_address")

        confirmation_message = (
            f"""we updated your municipality name to {municipality}
            \n Is this correct?"""
        )
        
        dispatcher.utter_message(text=confirmation_message,
                                 buttons=[
                                         {"title": "Yes", "payload": "/Agree"},
                                         {"title": "Modify", "payload": "/modify_municipality"},
                                         {"title": "Exit", "payload": "/exit_grievance_process"}
                                     ])
        
        return []

class ActionResetMunicipalitySlots(Action):
    def name(self) -> str:
        return "action_reset_municipality_slots"

    def run(self, dispatcher, tracker, domain):
        """Resets all location-related slots before the form starts."""
        return [
            # SlotSet("user_province", None),
            # SlotSet("user_district", None),
            SlotSet("user_municipality", None),
            # SlotSet("user_ward", None),
            # SlotSet("user_village", None),
            # SlotSet("user_address", None),
        ]
        


class ValidateMunicipalityForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_municipality_form"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:

        municipality_string = tracker.latest_message.get("text", "").strip().lower()
        
        # Create instance of LocationValidator
        location_validator = LocationValidator()

        # Validate municipality using the validator
        if not municipality_string or municipality_string.startswith("/"):
            dispatcher.utter_message(text="Please enter a valid municipality name.")
            logger.debug("🚨 Invalid municipality detected, resetting slot")
            return [SlotSet("user_municipality", None), SlotSet("requested_slot", "user_municipality")]
        
        if not location_validator.validate_location(municipality_string, qr_province = QR_PROVINCE, qr_district = QR_DISTRICT):
            dispatcher.utter_message(text=f"Please enter a valid municipality name. \n {location_validator.validate_municipality(municipality_string)} is not a valid municipality name in {qr_province}, {qr_district}")
            logger.debug("🚨 Invalid municipality detected, resetting slot")
            return [SlotSet("user_municipality", None), SlotSet("requested_slot", "user_municipality")]
        
        municipality = location_validator.validate_location(municipality_string, qr_province = QR_PROVINCE, qr_district = QR_DISTRICT)["municipality"].title()
        
        # if municipality != municipality_string.strip().title():
        #     dispatcher.utter_message(text=f"We updated your municipality name to {municipality}")
        
        logger.debug(f"✅ DEBUG: municipality slot set to: {municipality}")
        return [SlotSet("user_municipality", municipality)]

    ########### Address and Village
    
class ActionConfirmAddress(Action):
    def name(self) -> str:
        return "action_confirm_address"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict):
        # province = tracker.get_slot("user_province")
        # district = tracker.get_slot("user_district")
        # municipality = tracker.get_slot("user_municipality")
        # ward = tracker.get_slot("user_ward")
        village = tracker.get_slot("user_village")
        address = tracker.get_slot("user_address")

        confirmation_message = (
            f"Thank you for providing your location details:\n"
            # f"- Province: {province or 'Skipped'}\n"
            # f"- District: {district or 'Skipped'}\n"
            # f"- Municipality: {municipality or 'Skipped'}\n"
            # f"- Ward: {ward or 'Skipped'}\n"
            f"- Village: {village or 'Skipped'}\n"
            f"- Address: {address or 'Skipped'}\n\n"
            "Is this correct?"
        )
        
        dispatcher.utter_message(text=confirmation_message,
                                 buttons=[
                                         {"title": "Yes", "payload": "/submit_address"},
                                         {"title": "Modify", "payload": "/modify_address"},
                                         {"title": "Exit", "payload": "/exit_grievance_process"}
                                     ])
        
        return []

class ActionResetAddressSlots(Action):
    def name(self) -> str:
        return "action_reset_address_slots"

    def run(self, dispatcher, tracker, domain):
        """Resets all location-related slots before the form starts."""
        return [
            # # SlotSet("user_province", None),
            # # SlotSet("user_district", None),
            # SlotSet("user_municipality", None),
            # # SlotSet("user_ward", None),
            SlotSet("user_village", None),
            SlotSet("user_address", None),
        ]

class ValidateAddressForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_address_form"

    async def required_slots(
        self,
        slots_mapped_in_domain: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Text]:
        """A list of required slots that the form has to fill"""
        return ["user_village", "user_address"]

    def _is_skip_requested(self, text: str) -> bool:
        """Check if user wants to skip the current field"""
        return text.lower().strip() in ['skip', 'pass', 'next']

    # ✅ Extract village slot correctly
    async def extract_village(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        user_response = tracker.latest_message.get("text", "").strip()
        
        # Only extract input when village is the requested slot
        if tracker.get_slot("requested_slot") == "user_village":
            print(f"Extracting village. User response: {user_response}")
            if self._is_skip_requested(user_response):
                dispatcher.utter_message(text="Skipping village information.")
                return {"user_village": "Not provided"}
            return {"user_village": user_response}
        return {}

    # ✅ Extract address slot correctly
    async def extract_address(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        user_response = tracker.latest_message.get("text", "").strip()
        
        # Only extract input when address is the requested slot
        if tracker.get_slot("requested_slot") == "user_address":
            print(f"Extracting address. User response: {user_response}")
            if self._is_skip_requested(user_response):
                dispatcher.utter_message(text="Skipping address information.")
                return {"user_address": "Not provided"}
            return {"user_address": user_response}
        return {}

    # ✅ Validate village
    async def validate_user_village(self, value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        """Validate user_village value."""
        if value == "Not provided":
            return {"user_village": value}
            
        if not value or len(value) < 2:
            dispatcher.utter_message(text="Please provide a valid village name (or type 'skip' to skip).")
            return {"user_village": None}
        
        return {"user_village": value}

    # ✅ Validate address
    async def validate_user_address(self, value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        """Validate user_address value."""
        if value == "Not provided":
            return {"user_address": value}
            
        if not value or len(value) < 5:
            dispatcher.utter_message(text="Please provide a more detailed address (or type 'skip' to skip).")
            return {"user_address": None}
        
        return {"user_address": value}
