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
            "QR001": {"district": "Kathmandu", "municipality": "KMC"},
            "QR002": {"district": "Bhaktapur", "municipality": "Bhaktapur"},
        }
        prepopulated = location_mapping.get(qr_code, {})

        if prepopulated:
            dispatcher.utter_message(response="utter_prepopulate_location_success", 
                                      district=prepopulated.get("district"), 
                                      municipality=prepopulated.get("municipality"))
        else:
            dispatcher.utter_message(response="utter_prepopulate_location_failure")

        return [
            SlotSet("district", prepopulated.get("district")),
            SlotSet("municipality", prepopulated.get("municipality")),
        ]



# class ValidateLocationForm(FormValidationAction):
#     def name(self) -> Text:
#         return "validate_location_form"

#     async def extract_slot(self, slot_name: str, dispatcher: CollectingDispatcher, tracker: Tracker) -> Dict[Text, Any]:
        
#         """Handles slot extraction, skipping when intent is 'skip', and ensures the correct question is always asked."""
#         intent_name = tracker.latest_message.get("intent", {}).get("name")
#         user_response = tracker.latest_message.get("text", "").strip().lower()

#         # If the user wants to skip, acknowledge and move to the next slot
#         if intent_name == "skip":
#             dispatcher.utter_message(text=f"Skipping {slot_name}.")
#             return {slot_name: None}  # Move to the next question

#         # # Always ask the corresponding question before processing input
#         # dispatcher.utter_message(response=f"utter_ask_{slot_name}")

#         # If the response is "yes" or "no", repeat the question
#         if user_response in ["yes", "no"]:
#             dispatcher.utter_message(text=f"I need more details for {slot_name}. Please provide a valid answer.")
#             return {slot_name: None}  # Keep asking until a valid answer is given

#         return {slot_name: user_response}  # Store the valid response

#     async def extract_province(self, dispatcher, tracker, domain) -> Dict[Text, Any]:
#         return await self.extract_slot("province", dispatcher, tracker)

#     async def extract_municipality(self, dispatcher, tracker, domain) -> Dict[Text, Any]:
#         return await self.extract_slot("municipality", dispatcher, tracker)

#     async def extract_ward(self, dispatcher, tracker, domain) -> Dict[Text, Any]:
#         return await self.extract_slot("ward", dispatcher, tracker)

#     async def extract_village(self, dispatcher, tracker, domain) -> Dict[Text, Any]:
#         return await self.extract_slot("village", dispatcher, tracker)

#     async def extract_address(self, dispatcher, tracker, domain) -> Dict[Text, Any]:
#         return await self.extract_slot("address", dispatcher, tracker)

    # async def validate(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
    #     # Collect the slot values
    #     province = tracker.get_slot("province")
    #     municipality = tracker.get_slot("municipality")
    #     ward = tracker.get_slot("ward")
    #     village = tracker.get_slot("village")
    #     address = tracker.get_slot("address")

    #     # Construct the confirmation message
    #     confirmation_message = (
    #         "Thank you for providing your location details:\n"
    #         f"- Province: {province or 'Not provided'}\n"
    #         f"- Municipality: {municipality or 'Not provided'}\n"
    #         f"- Ward: {ward or 'Not provided'}\n"
    #         f"- Village: {village or 'Not provided'}\n"
    #         f"- Address: {address or 'Not provided'}\n\n"
    #         "Is this correct?"
    #     )
    #     logger.debug(f"Validating location form: province={province}, district={district}, municipality={municipality}, ward={ward}, village={village}, address={address}")

    #     dispatcher.utter_message(text=confirmation_message)

    #     return [
    #         SlotSet("province", province),
    #         SlotSet("municipality", municipality),
    #         SlotSet("ward", ward),
    #         SlotSet("village", village),
    #         SlotSet("address", address),
    #     ]
class ActionConfirmLocation(Action):
    def name(self) -> str:
        return "action_confirm_location"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        province = tracker.get_slot("province")
        district = tracker.get_slot("district")
        municipality = tracker.get_slot("municipality")
        ward = tracker.get_slot("ward")
        village = tracker.get_slot("village")
        address = tracker.get_slot("address")

        confirmation_message = (
            f"Thank you for providing your location details:\n"
            f"- Province: {province or 'Skipped'}\n"
            f"- District: {district or 'Skipped'}\n"
            f"- Municipality: {municipality or 'Skipped'}\n"
            f"- Ward: {ward or 'Skipped'}\n"
            f"- Village: {village or 'Skipped'}\n"
            f"- Address: {address or 'Skipped'}\n\n"
            "Is this correct?"
        )
        
        dispatcher.utter_message(text=confirmation_message)
        
        return []

class ActionResetLocationSlots(Action):
    def name(self) -> str:
        return "action_reset_location_slots"

    def run(self, dispatcher, tracker, domain):
        """Resets all location-related slots before the form starts."""
        return [
            SlotSet("province", None),
            SlotSet("district", None),
            SlotSet("municipality", None),
            SlotSet("ward", None),
            SlotSet("village", None),
            SlotSet("address", None),
        ]
        
class ValidateLocationForm(FormValidationAction):
    def name(self) -> str:
        return "validate_location_form"

    async def validate(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain) -> dict:
        """Handles slot validation, allowing skipping and ensuring valid input."""
        requested_slot = tracker.get_slot("requested_slot")  # Get the slot currently being requested

        if not requested_slot:
            return {}

        user_response = tracker.latest_message.get("text", "").strip().lower()
        intent_name = tracker.latest_message.get("intent", {}).get("name")

        # If the user wants to skip, acknowledge and move to the next slot
        if intent_name == "skip":
            dispatcher.utter_message(text=f"Skipping {requested_slot}.")
            return {requested_slot: None}

        # If the response is "yes" or "no", repeat only the current question
        if user_response in ["yes", "no"]:
            dispatcher.utter_message(text=f"I need more details for {requested_slot}. Please provide a valid answer.")
            return {requested_slot: None}

        return {requested_slot: user_response}  # Store the valid response