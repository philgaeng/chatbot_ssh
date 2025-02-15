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
from actions.helpers import LocationValidator  # Add this import
from .constants import QR_PROVINCE, QR_DISTRICT, DISTRICT_LIST, USE_QR_CODE  # Import the constants


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
    

class ValidateLocationForm(FormValidationAction):
    """Form validation action for location details collection."""

    def __init__(self):
        self.location_validator = LocationValidator()

    def name(self) -> Text:
        return "validate_location_form"

    def _is_skip_requested(self,latest_message: dict) -> bool:
        """Check if user wants to skip the current field."""
        """Create this function to enable calling for translation in the future"""
        text = latest_message.get("text", "").strip()
        intent = latest_message.get("intent", {}).get("name", "")
        return text.lower().strip() in ['skip', 'pass', 'next'] or intent == "skip"

        

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
    
    # Add skip request handling
    async def extract_validation(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating ######")
        print(f"########### Slot value: {slot_value} ###########")
        if self._is_skip_requested(tracker.latest_message):
            requested_slot = tracker.get_slot("requested_slot")
            print (f"######## SKIP --- {requested_slot}")
            if tracker.get_slot("requested_slot").type() ==  "bool":
                if requested_slot in ["user_municipality_confirmed", "user_address_confirmed"]:
                    return {requested_slot: True}
                return {requested_slot: False}
            
            return {requested_slot: "Skipped"}
        
        validated_slot = await super().validate(slot_value, dispatcher, tracker, domain)
        
        print("Validation Result:", validated_slot)
        print("=============================================================\n")
        
        
        return validated_slot
        

            

    async def extract_user_municipality_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        #dispactch the start location process message
        latest_message = tracker.latest_message
        
        extracted_text = tracker.latest_message.get("text", "").strip()
        print(f"Received value: {extracted_text}")
        if extracted_text == "/start_location_process":
            dispatcher.utter_message(
                text=f"Please enter your municipality name in {QR_DISTRICT}, {QR_PROVINCE}"
            )
            return {}
        #check that the active slot is user_municipality_temp
        if tracker.get_slot("requested_slot") == "user_municipality_temp":

            print("######## FORM: Extracting municipality temp ######")
                # Just return the extracted value, validation will handle slot setting
            return {"user_municipality_temp": extracted_text}
        return {}
    
    async def validate_user_municipality_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating municipality_temp ######")
        print(f"Received value: {slot_value}")
        #check that the active slot is user_municipality_temp

        # ask user to confirm the municipality after extracting the municipality

        
        if slot_value == "Skipped":
            #update the slots value to reflect the user's choice and terminate the form
            return {"user_municipality_temp": "Skipped",
                    "user_municipality_confirmed": True,
                    "provide_additional_location": False,
                    "user_municipality": "Skipped"
                    }
                
        # Validate new municipality input with the extract and rapidfuzz functions
        validated_municipality = self._validate_municipality_input(slot_value)
        print(f"Validated municipality: {validated_municipality}")
        try:
            print(f"validated_municipality: {validated_municipality['municipality']}")
        except:
            print("No more dic in results")
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

        
        if tracker.get_slot("requested_slot") == "user_municipality_confirmed":
            print("######## FORM: Extracting municipality confirmed slot ######")
            
            latest_message = tracker.latest_message
            
                    # Handle skip request
            if self._is_skip_requested(latest_message):
                return {"user_municipality_confirmed": True}
            
            #check if the user has provided a municipality
            extracted_text = latest_message.get("text")
            if tracker.get_slot("user_municipality_temp"):
                if extracted_text == "/affirm":
                    print("## user_municipality_confirmed: True ######")
                    return {"user_municipality_confirmed": True}
                elif extracted_text == "/deny":
                    print("## user_municipality_confirmed: False ######")
                    return {"user_municipality_confirmed": False}
                else:
                    print("## user_municipality_confirmed: None ######")
                    return {"user_municipality_confirmed": None}
        return {}
    
    async def validate_user_municipality_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating municipality confirmed slot ######")
        # Handle skip request
        if self._is_skip_requested(tracker.latest_message):
            return {"user_municipality_confirmed": True,
                    "user_municipality": "Skipped"}
        
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

        
        if tracker.get_slot("requested_slot") == "provide_additional_location":
            
            latest_message = tracker.latest_message
            # Handle skip request
            if self._is_skip_requested(latest_message):
                return {"provide_additional_location": False}
            
            
            print("######## FORM: Extracting provide_additional_location slot######")
            extracted_text = latest_message.get("text")
            
            if tracker.get_slot("user_municipality"):
                if extracted_text == "/affirm":
                    dispatcher.utter_message(
                        text="Please provide your village name or Skip to skip"
                    )
                    return {"provide_additional_location": True}
                elif extracted_text == "/deny":
                    return {"provide_additional_location": False}
            return {}
        return {}
    
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

        
        if tracker.get_slot("requested_slot") == "user_village":
            latest_message = tracker.latest_message
                        # Handle skip request
            if self._is_skip_requested(latest_message):
                return {"user_village": "Skipped"}
            
            print("######## FORM: Extracting village ######")
            extracted_text = latest_message.get("text")
            print(f"Received value for village: {extracted_text}")
            return {"user_village": extracted_text}
        return {}
    
    async def validate_user_village(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating village ######")
        dispatcher.utter_message(
            text="Please provide your address or Skip to skip"
        )
        return self._validate_optional_field(slot_value, 2, "user_village", dispatcher)
    
        
    
    async def extract_user_address_temp( 
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:


        
        if tracker.get_slot("requested_slot") == "user_address_temp":
            latest_message = tracker.latest_message
                    # Handle skip request   
            # if self._is_skip_requested(tracker.latest_message):
            #     return {"user_address_temp": "Skipped"}
            extracted_text = latest_message.get("text")
            # Get the latest user message text
            print("######## FORM: Extracting address temp ######")
            print(f"Received value for address: {extracted_text}")
            return {"user_address_temp": extracted_text}
        return {}
    

    
    async def validate_user_address_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        print("######## FORM: Validating address temp ######")
            
        result = self._validate_optional_field(slot_value, 2, "user_address_temp", dispatcher)
        # If we have a temp value, we're in confirmation mode
        
        if result.get("user_address_temp") is not None:
            confirmation_message = (
                f"Thank you for providing your location details:\n"
                f"- Municipality: {tracker.get_slot('user_municipality')}\n"
                f"- Village: {tracker.get_slot('user_village')}\n"
                f"- Address: {tracker.get_slot('user_address_temp')}\n\n"
                "Is this correct?"
            )
        
            dispatcher.utter_message(
                text=confirmation_message,
                buttons=[
                    {"title": "Yes", "payload": "/affirm_location_address"},
                    {"title": "No, modify", "payload": "/deny"},
                ]
            )
            return result
        
    async def extract_user_address_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if tracker.get_slot("requested_slot") == "user_address_confirmed":
            print("######## FORM: Extracting address confirmed slot ######")
            latest_message = tracker.latest_message.get("text")
            if tracker.get_slot("user_address_temp"):
                if latest_message == "/affirm_location_address":
                    return {"user_address_confirmed": True}
                elif latest_message == "/deny":
                    return {"user_address_confirmed": False}
        return {}

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
    