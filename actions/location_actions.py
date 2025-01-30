# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
from typing import Any, Text, Dict, List
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from twilio.rest import Client




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

class ValidateLocationForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_location_form"

    async def extract_province(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if tracker.latest_message.intent.get("name") == "skip":
            dispatcher.utter_message(response="utter_skip_province")
            return {"province": None}
        return {"province": tracker.latest_message.get("text")}

    async def extract_municipality(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if tracker.latest_message.intent.get("name") == "skip":
            dispatcher.utter_message(response="utter_skip_municipality")
            return {"municipality": None}
        return {"municipality": tracker.latest_message.get("text")}

    async def extract_ward(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if tracker.latest_message.intent.get("name") == "skip":
            dispatcher.utter_message(response="utter_skip_ward")
            return {"ward": None}
        return {"ward": tracker.latest_message.get("text")}

    async def extract_village(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if tracker.latest_message.intent.get("name") == "skip":
            dispatcher.utter_message(response="utter_skip_village")
            return {"village": None}
        return {"village": tracker.latest_message.get("text")}

    async def extract_address(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if tracker.latest_message.intent.get("name") == "skip":
            dispatcher.utter_message(response="utter_skip_address")
            return {"address": None}
        return {"address": tracker.latest_message.get("text")}

    async def validate(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        # Collect the slot values
        province = tracker.get_slot("province")
        municipality = tracker.get_slot("municipality")
        ward = tracker.get_slot("ward")
        village = tracker.get_slot("village")
        address = tracker.get_slot("address")

        # Construct the confirmation message
        confirmation_message = (
            "Thank you for providing your location details:\n"
            f"- Province: {province or 'Not provided'}\n"
            f"- Municipality: {municipality or 'Not provided'}\n"
            f"- Ward: {ward or 'Not provided'}\n"
            f"- Village: {village or 'Not provided'}\n"
            f"- Address: {address or 'Not provided'}\n\n"
            "Is this correct?"
        )

        dispatcher.utter_message(text=confirmation_message)

        return []


