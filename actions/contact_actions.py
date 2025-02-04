# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
import re
from typing import Any, Text, Dict, List
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from twilio.rest import Client


class AskContactConsent(Action):
    def name(self) -> str:
        return "action_ask_contact_consent"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = (
            "Would you like to provide your contact information? Here are your options:\n\n"
            "1️⃣ **Yes**: Share your contact details for follow-up and updates about your grievance.\n"
            "2️⃣ **Anonymous with phone number**: Stay anonymous but provide a phone number to receive your grievance ID.\n"
            "3️⃣ **No contact information**: File your grievance without providing contact details. "
            "Note that we won't be able to follow up or share your grievance ID."
        )
        dispatcher.utter_message(
            text=message,
            buttons=[
                {"title": "Yes", "payload": "/provide_contact_yes"},
                {"title": "Anonymous with phone", "payload": "/anonymous_with_phone"},
                {"title": "No contact info", "payload": "/no_contact_provided"},
            ]
        )
        return []


# Action to send OTP
class ActionSendOtp(Action):
    def name(self) -> Text:
        return "action_send_otp"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        phone_number = tracker.get_slot("user_contact_phone")
        otp = randint(100000, 999999)

        # Save OTP for verification
        dispatcher.utter_message(response="utter_send_otp", phone_number=phone_number)

        # Send OTP via SMS (Twilio Example)
        try:
            client = Client("account_sid", "auth_token")
            client.messages.create(
                body=f"Your OTP is {otp}",
                from_="your_twilio_number",
                to=phone_number,
            )
        except Exception as e:
            dispatcher.utter_message(response="utter_send_otp_failure", error=str(e))

        return [SlotSet("otp", otp)]


class ActionVerifyOtp(Action):
    def name(self) -> Text:
        return "action_verify_otp"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        user_otp = tracker.latest_message.get("text")
        expected_otp = tracker.get_slot("otp")

        if user_otp == str(expected_otp):
            dispatcher.utter_message(response="utter_otp_verified_success")
            return [SlotSet("otp_verified", True)]
        else:
            dispatcher.utter_message(response="utter_otp_verified_failure")
            return [SlotSet("otp_verified", False)]
        

class ValidateContactForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_contact_form"

    async def validate_user_full_name(
        self, slot_name: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        intent = tracker.latest_message.get("intent", {}).get("name")
        value = tracker.latest_message.get("text")
        
        # ✅ Ignore payloads from buttons (they start with "/")
        if value and value.startswith("/"):  
            dispatcher.utter_message(response="utter_ask_contact_form_user_full_name")
            return {slot_name: None}  # Ask again


        if intent == "skip":
            dispatcher.utter_message(response="utter_skip_full_name")
            return {slot_name: None}
        
        if len(value.strip()) < 2:  # Ensure it's at least "First Last"
            dispatcher.utter_message(response="utter_ask_contact_form_user_full_name")
            return {slot_name: None}  # Ask again
        
        if value and value.strip():
                    # Example of enforcing a basic rule (modify as needed)
            return {slot_name: value.strip()}
        
        # If user does not respond, schedule a follow-up action
        return [FollowupAction("action_remind_user_full_name")]


    
    async def validate_user_contact_phone(
        self, slot_name: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        phone_number = tracker.latest_message.get("text")
        intent = tracker.latest_message.get("intent", {}).get("name")
        
        # ✅ Ignore payloads from buttons (they start with "/")
        if phone_number and phone_number.startswith("/"):  
            dispatcher.utter_message(response="utter_ask_contact_form_user_contact_phone")
            return {slot_name: None}  # Ask again

        if intent in ['skip', 'skip_contact_phone']:
            dispatcher.utter_message(response="utter_skip_phone_number")
            return {slot_name: None}

        # Remove all non-numeric characters
        cleaned_number = re.sub(r"\D", "", phone_number)  # Removes anything that is not a digit

        # Validate Nepal phone number format (must start with 97 or 98 and be exactly 10 digits)
        if not re.match(r"^(98|97)\d{8}$", cleaned_number):
            dispatcher.utter_message(
                text=(
                    "The phone number you provided is invalid. "
                    "Nepal mobile numbers must start with 98 or 97 and be exactly 10 digits long. "
                    "Please provide a valid number."
                ), 
                buttons = [  # Add buttons for better user interaction
                {"title": "Retry", "payload": "/provide_contact_phone"},
                {"title": "Skip", "payload": "/skip_contact_phone"}
            ]
        )
            return {slot_name: None} # Forces the bot to re-ask for input

        return {slot_name: cleaned_number}


    async def validate_user_contact_email(
        self, slot_name: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> Dict[Text, Any]:
        email = tracker.latest_message.get("text")
        intent = tracker.latest_message.get("intent", {}).get("name")

        # ✅ Ignore payloads from buttons (they start with "/")
        if email and email.startswith("/"):  
            dispatcher.utter_message(response="utter_ask_contact_form_user_contact_email")
            return {slot_name: None}  # Ask again

        # Handle user skipping email input
        if intent in ['skip', 'skip_contact_email']:
            dispatcher.utter_message(text="✅ No problem! You can proceed without an email.")
            return {slot_name: None}

        # Clean email input
        email = email.strip().lower()

        # Email validation pattern
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        # Check if email is valid
        if not re.match(email_pattern, email):
            dispatcher.utter_message(
                text=(
                    "⚠️ The email address you provided is invalid.\n"
                    "A valid email should be in the format: **username@domain.com**.\n"
                    "Please provide a valid email address or skip this step."
                ),
                buttons=[
                    {"title": "Retry", "payload": "/provide_contact_email"},
                    {"title": "Skip Email", "payload": "/skip_contact_email"},
                ]
            )
            return {slot_name: None}  # Forces bot to re-ask

        return {slot_name: email}


    # async def validate(
    #     self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    # ) -> List[Dict[Text, Any]]:
    #     try:
    #         # Collect the slot values
    #         user_full_name = tracker.get_slot("user_full_name")
    #         user_contact_phone = tracker.get_slot("user_contact_phone")
    #         user_contact_email = tracker.get_slot("user_contact_email")
    #         user_honorific_prefix = tracker.get_slot("user_honorific_prefix")
            
    #         if user_contact_phone:

    #             # Construct the confirmation message
    #             confirmation_message = (
    #                 "Thank you for providing your contact details:\n"
    #                 f"- Full Name: {user_full_name or 'Not provided'}\n"
    #                 f"- Honorific Prefix: {user_honorific_prefix or 'Not provided'}\n"
    #                 f"- Phone Number: {user_contact_phone or 'Not provided'}\n"
    #                 f"- Email Address: {user_contact_email or 'Not provided'}\n\n"
    #                 "Is this correct?"
    #             )

    #             dispatcher.utter_message(text=confirmation_message)
    #             return []
            
    #         else:
    #             dispatcher.utter_message(text="An error occurred while processing your contact details. You need to provide your contact phone",
    #                                      buttons=[
    #                                         {"title": "Modify contact phone", "payload": "/anonymous_with_phone"},
    #                                         {"title": "No contact info", "payload": "/no_contact_provided"},
    #                                     ]
    #                                 )
    #             return []
        
    #     except Exception as e:
    #         dispatcher.utter_message(text="An error occurred while processing your contact details. You need to provide your contact phone")
    #         print(f"Error in validate_contact_form: {e}")
    #         return []







