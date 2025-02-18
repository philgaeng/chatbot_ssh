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
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from twilio.rest import Client
from .helpers import LocationValidator #add this import
from .constants import QR_PROVINCE, QR_DISTRICT, DISTRICT_LIST, USE_QR_CODE  # Import the constants
from .base_form import BaseFormValidationAction

logger = logging.getLogger(__name__)



# # Action to prepopulate location based on QR code
# class ActionPrepopulateLocation(Action):
#     def name(self) -> Text:
#         return "action_prepopulate_location"

#     def run(
#         self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
#     ) -> List[Dict[Text, Any]]:
#         if USE_QR_CODE:
#             qr_code = tracker.get_slot("qr_code")  # Assume this is pre-set
#             location_mapping = {
#                 "QR001": {"user_district": "Kathmandu", "user_municipality": "KMC"},
#                 "QR002": {"user_district": "Bhaktapur", "user_municipality": "Bhaktapur"},
#                 }
#             prepopulated = location_mapping.get(qr_code, {})
        
#         else:
#             prepopulated = {
#                 "user_district": QR_DISTRICT,
#                 "user_province": QR_PROVINCE
#             }

#         if prepopulated:
#             dispatcher.utter_message(response="utter_prepopulate_location_success", 
#                                       district=prepopulated.get("user_district"), 
#                                       province=prepopulated.get("user_province"))
#         else:
#             dispatcher.utter_message(response="utter_prepopulate_location_failure")

#         return [
#             SlotSet("user_district", prepopulated.get("user_district")),
#             SlotSet("user_province", prepopulated.get("user_province")),
#         ]

class ActionAskLocation(Action):
    def name(self) -> str:
        return "action_ask_location"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        dispatcher.utter_message(
            text="Do you want to provide the location details for your grievance. This is optional, your grievance can be filed without it.",
            buttons=[
                {"title": "Yes", "payload": "/start_location_process"},
                {"title": "Skip", "payload": "/ask_contact_details"},
                {"title": "Exit", "payload": "/goodbye"}
            ]
        )
        return []
    

class ValidateLocationForm(BaseFormValidationAction):
    """Form validation action for location details collection."""

    def __init__(self):
        """Initialize the form validation action."""
        print("ValidateLocationForm.__init__ called")
        super().__init__()
        print("super().__init__() completed")
        print(f"self.lang_helper exists: {hasattr(self, 'lang_helper')}")
        self.location_validator = LocationValidator()
        print("ValidateLocationForm.__init__ completed")

    def name(self) -> Text:
        return "validate_location_form"

    def _validate_municipality_input(
        self,
        input_text: Text
    ) -> Dict[Text, Any]:
        """Validate new municipality input."""
        validation_result = self.location_validator.validate_location(
            input_text.lower(), 
            qr_province=QR_PROVINCE, 
            qr_district=QR_DISTRICT
        )
        
        municipality = validation_result.get("municipality")
        
        if not municipality:
            return None
        
        municipality = municipality.title()
        print(f"✅ Municipality validated: {municipality}")
        
        return municipality

    def _validate_optional_field(
        self,
        slot_value: Text,
        min_length: int,
        field_name: str,
        dispatcher: CollectingDispatcher
    ) -> Dict[Text, Any]:
        """Validate optional fields (village/address)."""
        if slot_value == "Not provided":
            return {field_name: slot_value}
            
        if not slot_value or len(slot_value) < min_length or slot_value.startswith("/"):
            dispatcher.utter_message(
                text=f"Please provide a valid {field_name.replace('user_', '').replace('_temp', '')} (or type 'skip' to skip)."
            )
            return {field_name: None}
        
        return {field_name: slot_value}

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        print("\n=================== Location Form Required Slots ===================")
        # initialize required slots
        required_slots = ["user_municipality_temp"]
        
        #expend required slots as the slots get filled
        if tracker.get_slot("user_municipality_temp"):
            required_slots.append("user_municipality_confirmed")
        if tracker.get_slot("user_municipality_confirmed"):
            required_slots.append("provide_additional_location")
        
        #expend required slots as the slots get filled handling the optional fields
        if tracker.get_slot("provide_additional_location"):
            if tracker.get_slot("provide_additional_location") == True:
                required_slots.append("user_village")
            if tracker.get_slot("user_village"):
                required_slots.append("user_address_temp")

            if tracker.get_slot("user_address_temp"):
                required_slots.append("user_address_confirmed")
            if tracker.get_slot("user_address_confirmed"):
                required_slots.append("user_address")
                
        print(f"Required slots: {required_slots}")

        return required_slots
    

    async def extract_user_municipality_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        # Handle start location process
        if tracker.latest_message.get("text", "").strip() == "/start_location_process":
            dispatcher.utter_message(
                text=f"Please enter your municipality name in {QR_DISTRICT}, {QR_PROVINCE}"
            )
            return {}

        return await self._handle_slot_extraction(
            "user_municipality_temp",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_user_municipality_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating municipality_temp ######")
        print(f"Received value: {slot_value}")
        
        if slot_value == "slot_skipped":
            return {
                "user_municipality_temp": "slot_skipped",
                "user_municipality_confirmed": True,
                "provide_additional_location": False,
                "user_municipality": "slot_skipped"
            }
        
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            dispatcher.utter_message(
                text=f"Please enter a valid municipality name in {QR_DISTRICT}, {QR_PROVINCE} (at least 3 characters)"
            )
            return {"user_municipality_temp": None}
                
        # Validate new municipality input with the extract and rapidfuzz functions
        validated_municipality = self._validate_municipality_input(slot_value)
        print(f"Validated municipality: {validated_municipality}")
        
        if validated_municipality:
            dispatcher.utter_message(
                text=f"Is {validated_municipality} your correct municipality?",
                buttons=[
                    {"title": "Yes", "payload": "/affirm"},
                    {"title": "No", "payload": "/deny"},
                ]
            )
            return {"user_municipality_temp": validated_municipality}
        
        else:
            dispatcher.utter_message(
                text=f"Please enter your municipality name in {QR_DISTRICT}, {QR_PROVINCE}"
            )
            return {"user_municipality_temp": None,
                    "user_municipality": None,
                    "user_municipality_confirmed": None
                    }
                
    async def extract_user_municipality_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # First check if we have a municipality to confirm
        if not tracker.get_slot("user_municipality_temp"):
            return {}

        return await self._handle_boolean_slot_extraction(
            "user_municipality_confirmed",
            tracker,
            dispatcher,
            domain,
            skip_value=True  # When skipped, assume confirmed
        )
    
    async def validate_user_municipality_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating municipality confirmed slot ######")
        
        print(f"Received value for municipality confirmed: {slot_value}")
        if slot_value == True:
            print("## user_municipality_confirmed: True ######")
            print(f"Received value for municipality: {slot_value}")
#request the user if you want to provide additional location
            dispatcher.utter_message(
                text="Do you want to provide additional location details?",
                buttons=[
                    {"title": "Yes", "payload": "/affirm"},
                    {"title": "No", "payload": "/deny"},
                ]
            )
        #save the municipality to the slot
            return {"user_municipality_confirmed": True,
                    "user_municipality": tracker.get_slot("user_municipality_temp")}
            
        elif slot_value == False:
            return {"user_municipality_confirmed": None,
                    "user_municipality_temp": None,
                    "user_municipality": None
                    }
    
    async def extract_provide_additional_location(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # First check if we have a municipality
        if not tracker.get_slot("user_municipality"):
            return {}

        async def handle_affirm(dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
            dispatcher.utter_message(
                text="Please provide your village name or Skip to skip"
            )
            return {"provide_additional_location": True}

        return await self._handle_boolean_slot_extraction(
            "provide_additional_location",
            tracker,
            dispatcher,
            domain,
            skip_value=False,
            custom_affirm_action=handle_affirm
        )
    
    async def validate_provide_additional_location(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating provide_additional_location slot ######")
        return {"provide_additional_location": slot_value}

    async def extract_user_village(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "user_village",
            tracker,
            dispatcher,
            domain,
            skip_value=True  # When skipped, assume confirmed
        )
    
    async def validate_user_village(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating village ######")
        
        if slot_value == "slot_skipped":
            dispatcher.utter_message(
                text="Please provide your address or Skip to skip"
            )
            return {"user_village": "slot_skipped"}
            
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            dispatcher.utter_message(
                text="Please provide a valid village name (at least 3 characters) or type 'skip' to skip"
            )
            return {"user_village": None}
            
        dispatcher.utter_message(
            text="Please provide your address or Skip to skip"
        )
        return {"user_village": slot_value}
    
        
    
    async def extract_user_address_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "user_address_temp",
            tracker,
            dispatcher,
            domain
        )
    

    
    async def validate_user_address_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate user_address value."""
        if slot_value == "slot_skipped":
            return {"user_address_temp": "slot_skipped"}
            
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            dispatcher.utter_message(
                text="Please provide a valid address (at least 3 characters)"
            )
            return {"user_address_temp": None}
        
        #check if the address and village are correct
        confirmation_message = f"""Thank you for providing your location details:
            - Municipality: {tracker.get_slot('user_municipality')}
            - Village: {tracker.get_slot('user_village')}
            - Address: {tracker.get_slot('user_address_temp')}
            Is this correct?"""
            
        dispatcher.utter_message(
            text= confirmation_message,
            buttons=[
                {"title": "Yes", "payload": "/affirm"},
                {"title": "No", "payload": "/deny"},
            ]
        )
        return {"user_address_temp": slot_value}

    async def extract_user_address_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        # First check if we have an address to confirm
        if not tracker.get_slot("user_address_temp"):
            return {}

        return await self._handle_boolean_slot_extraction(
            "user_address_confirmed",
            tracker,
            dispatcher,
            domain,
            skip_value=True  # When skipped, assume confirmed
        )

    async def validate_user_address_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating address confirmed slot ######")
        print(f"Received value for address confirmed: {slot_value}")
        # Handle rejection of address confirmation
        if slot_value == False:
            dispatcher.utter_message(text="Please enter your correct address")
            return {
                "user_village": None,
                "user_address": None,
                "user_address_temp": None,
                "user_address_confirmed": None
            }
        
        # Check if we have a confirmation
        if slot_value == True:
            address = tracker.get_slot("user_address_temp")
            print(f"Address set to: {address}")
            return {
                "user_address": address
            }
        return {} 
    