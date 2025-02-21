import re
import logging
from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from .constants import EMAIL_PROVIDERS_NEPAL
from .base_form import BaseFormValidationAction
logger = logging.getLogger(__name__)

EMAIL_PROVIDERS_NEPAL_LIST = [domain for provider in EMAIL_PROVIDERS_NEPAL.values() for domain in provider]


class AskContactFormContactConsent(Action):
    def name(self) -> str:
        return "action_ask_contact_form_contact_consent"

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

        
    
class ValidateContactForm(BaseFormValidationAction):
    """Form validation action for contact details collection."""

    def name(self) -> Text:
        return "validate_contact_form"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        print("\n=================== Contact Form Required Slots ===================")
        # if not domain_slots:
        # required_slots = ["user_contact_consent"]

        # if tracker.get_slot("user_contact_consent"):
        #     required_slots = ["user_full_name", "user_contact_phone", "user_contact_email_temp"]
        
        # if tracker.get_slot("email_validation_required"):
        #     required = ["user_full_name", "user_contact_phone", "user_contact_email_temp", "user_contact_email_confirmed"]
        
        # if tracker.get_slot("user_contact_email_confirmed") == False:
        #     required = ["user_full_name", "user_contact_phone", "user_contact_email_temp"]
        required_slots = ["user_contact_consent", "user_full_name", "user_contact_phone", "user_contact_email_temp", "user_contact_email_confirmed"]
        print(f"Required slots: {required_slots}")
        return required_slots
    
    async def extract_user_contact_consent(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_slot_extraction(
            "user_contact_consent",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_user_contact_consent(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return {"user_contact_consent": slot_value}

    async def extract_user_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        if tracker.get_slot("requested_slot") == "user_full_name":
            user_response = tracker.latest_message.get("text", "").strip()
            intent_name = tracker.latest_message.get("intent", {}).get("name")
            
            print("############# Extract user full name ##########")
            print("Requested Slot:", tracker.get_slot("requested_slot"))
            print("User Response:", user_response)

            if intent_name in ["skip", "skip_user_full_name"]:
                print("skipping - slot set to slot_kipped")
                return {"user_full_name": "slot_skipped"}  # Explicitly marking skipped slots
            
            # ✅ Ignore button payloads (they start with "/")
            if user_response.startswith("/"):
                # dispatcher.utter_message(response="utter_ask_contact_form_user_full_name")
                print("payload in slot, reset to None")
                return {"user_full_name": None}  
            
            if tracker.get_slot("requested_slot") != "user_full_name":
                return {}

            return {"user_full_name": user_response if user_response else None}
        return {}
    
    def _validate_user_full_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        print("################ Validate user full name ###################")

        if not slot_value:
            return {"user_full_name": None}
        if len(slot_value)<3:
            dispatcher.utter_message(text="Please enter a valid full name")
            return {"user_full_name": None}
        print("validated", slot_value)
        return {"user_full_name": slot_value}
    
    # ✅ Extract user contact phone
    async def extract_user_contact_phone(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        
        if tracker.get_slot("requested_slot") == "user_contact_phone":
            user_response = tracker.latest_message.get("text", "").strip()
            intent_name = tracker.latest_message.get("intent", {}).get("name")
            
            print("############# Extract user contact phone ##########")
            print("Requested Slot:", tracker.get_slot("requested_slot"))
            print("User Response:", user_response)

            
            if intent_name in ['skip', 'skip_contact_phone']:
                dispatcher.utter_message(response="utter_skip_phone_number")
                print("skipping - slot set to slot_kipped")
                return {"user_contact_phone": 'slot_skipped'}
            
            # ✅ Ignore button payloads (they start with "/")
            if user_response.startswith("/"):
                # dispatcher.utter_message(response="utter_ask_contact_form_user_contact_phone")
                print("payload in slot, reset to None")
                return {"user_contact_phone": None}  

            if tracker.get_slot("requested_slot") != "user_contact_phone":
                return {}

            return {"user_contact_phone": user_response}
        
        return {}
    
    
    async def validate_user_contact_phone(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate phone number and set validation requirement."""
        print("\n✨ FORM: Validating phone number")
        print(f"Received value: {slot_value}")

        if not slot_value:
            return {"user_contact_phone": None}

        if slot_value.lower() in ['skip', 'pass']:
            print("⏩ Phone number skipped")
            return {
                "user_contact_phone": "Skipped",
                "phone_validation_required": False
            }

        # Validate phone number format
        if not self._is_valid_phone(slot_value):
            dispatcher.utter_message(text="Please enter a valid phone number.")
            return {"user_contact_phone": None}

        print("✅ Valid phone number format")
        dispatcher.utter_message(text="Do you want to provide your email address?",
                                 buttons=[
                                     {"title": "Yes", "payload": "/provide_contact_email"},
                                     {"title": "No", "payload": "/skip_contact_email"}
                                 ]
                                 )
        return {
            "user_contact_phone": slot_value,
            "phone_validation_required": True
        }

    def _is_valid_phone(self, phone: str) -> bool:
        """Check if the phone number is valid."""
        # Add your phone validation logic here
        # For example: must be 10 digits, start with valid prefix, etc.
        return bool(re.match(r'^\d{10}$', phone))

    # def extact_user_required_email(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
    #     if tracker.get_slot("requested_slot") == "user_required_email":
    #         user_response = tracker.latest_message.get("text", "").strip()
    #         intent_name = tracker.latest_message.get("intent", {}).get("name")

    #         print("############# Extract user required email ##########")
    #         print("Requested Slot:", tracker.get_slot("requested_slot"))
    #         print("User Response:", user_response)

    #         if intent_name in ['skip', 'skip_contact_email']:
    #             return {"user_required_email": False}
            
    #         if intent_name == "deny":
    #             return {"user_required_email": False}
            
    #         if intent_name == "agree":
    #             return {"user_required_email": True}
        
    #     return {}
    
    # def _validate_user_required_email(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
    #     return {"user_required_email": slot_value}
        


    # # ✅ Extract user contact email
    # async def extract_user_contact_email(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
    #     user_response = tracker.latest_message.get("text", "").strip()
    #     intent_name = tracker.latest_message.get("intent", {}).get("name")

    #     print("############# Extract user contact email ##########")
    #     print("Requested Slot:", tracker.get_slot("requested_slot"))
    #     print("User Response:", user_response)

    #     # Extract and validate email
    #     extracted_email = self._email_extract_from_text(user_response)
    #     if not extracted_email:
    #         return self._email_handle_invalid_format(dispatcher)
        
    #     # Validate domain
    #     if not self._email_is_valid_nepal_domain(extracted_email):
    #         return self._email_handle_unknown_domain(dispatcher, extracted_email)
        
    #     return {"user_contact_email": extracted_email}


    def _email_extract_from_text(self, text: str) -> Optional[str]:
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        email_match = re.search(email_pattern, text)
        return email_match.group(0) if email_match else None

    def _email_is_valid_nepal_domain(self, email: str) -> bool:
        email_domain = email.split('@')[1].lower()
        return email_domain in EMAIL_PROVIDERS_NEPAL_LIST or email_domain.endswith('.com.np')

    def _email_handle_invalid_format(self, dispatcher: CollectingDispatcher) -> Dict[str, Any]:
        dispatcher.utter_message(
            text=(
                "⚠️ I couldn't find a valid email address in your message.\n"
                "A valid email should be in the format: **username@domain.com**."
            ),
            buttons=[
                {"title": "Retry", "payload": "/provide_contact_email"},
                {"title": "Skip Email", "payload": "/skip_contact_email"},
            ]
        )
        return {"user_contact_email_temp": None}

    def _email_handle_unknown_domain(self, dispatcher: CollectingDispatcher, email: str) -> Dict[str, Any]:
        email_domain = email.split('@')[1].lower()
        dispatcher.utter_message(
            text=(
                f"⚠️ The email domain '{email_domain}' is not recognized as a common Nepali email provider.\n"
                "Please confirm if this is correct or try again with a different email."
            ),
            buttons=[
                {"title": "Confirm Email", "payload": f"/confirm_email{{{email}}}"},
                {"title": "Try Different Email", "payload": "/provide_contact_email"},
                {"title": "Skip Email", "payload": "/skip_contact_email"},
            ]
        )
        return {"user_contact_email_temp": None}


    
    
    # ✅ Validate user contact email
    def _email_is_valid_format(self, email: Text) -> bool:
        """Check if email follows basic format requirements."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    async def extract_user_contact_email_temp(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_slot_extraction(
            "user_contact_email_temp",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_user_contact_email_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if not slot_value:
            return {"user_contact_email_temp": None}
                # Extract and validate email
        extracted_email = self._email_extract_from_text(slot_value)
        if not extracted_email:
            dispatcher.utter_message(
            text=(
                "⚠️ I couldn't find a valid email address in your message.\n"
                "A valid email should be in the format: **username@domain.com**."
            ),
            buttons=[
                {"title": "Retry", "payload": "/provide_contact_email"},
                {"title": "Skip Email", "payload": "/skip_contact_email"},
            ]
            )
            return {"user_contact_email_temp": None}
        
        # Use consistent validation methods
        if not self._email_is_valid_format(extracted_email):
            dispatcher.utter_message(text="⚠️ Please enter a valid email address.")
            return {"user_contact_email_temp": None}

        # Check for Nepali email domain using existing method
        if not self._email_is_valid_nepal_domain(extracted_email):
            domain = slot_value.split('@')[1]
            dispatcher.utter_message(
                text=f"⚠️ The email domain '{domain}' is not recognized as a common Nepali email provider.\nPlease confirm if this is correct or try again with a different email.",
                buttons=[
                    {"title": "Confirm Email", "payload": f"/slot_confirmed"},
                    {"title": "Try Different Email", "payload": "/slot_edited"},
                    {"title": "Skip Email", "payload": "/slot_skipped"}
                ]
            )
            # Keep the email in slot but deactivate form while waiting for user choice
            return {"user_contact_email_temp": extracted_email,
                    "email_validation_required": True}

        # If all validations pass
        return {"user_contact_email_temp": extracted_email}
    
    async def extract_user_contact_email_confirmed(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_boolean_slot_extraction(
            "user_contact_email_confirmed",
            tracker,
            dispatcher,
            domain
        )
    async def validate_user_contact_email_confirmed(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value == "true":
            return {"user_contact_email": tracker.get_slot("user_contact_email_temp"),
                    "user_contact_email_confirmed": True}
        else:
            #reset the slots to restart the loop
            return {
                    "user_contact_email_temp" : None,
                    "user_contact_email_confirmed" : None
                    }


class ActionCheckPhoneValidation(Action):
    def name(self) -> Text:
        return "action_check_phone_validation"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        phone_number = tracker.get_slot("user_contact_phone")
        
        if phone_number and phone_number != "Skipped":
            return [SlotSet("phone_validation_required", True)]
        else:
            return [SlotSet("phone_validation_required", False)]

class ActionRecommendPhoneValidation(Action):
    def name(self) -> Text:
        return "action_recommend_phone_validation"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text=(
                "Your grievance is filed without a validated number. Providing a valid number "
                "will help in the follow-up of the grievance and we recommend it. However, "
                "you can file the grievance as is."
            ),
            buttons=[
                {"title": "Give Phone Number", "payload": "/provide_phone_number"},
                {"title": "File Grievance as is", "payload": "/file_without_validation"}
            ]
        )
        return []

class PhoneValidationForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_phone_validation_form"

    @staticmethod
    def required_slots(tracker: Tracker) -> List[Text]:
        return ["user_contact_phone"]

    async def validate_user_contact_phone(
        self,
        slot_value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if re.match(r'^\+?63\d{10}$', slot_value):
            return {"user_contact_phone": slot_value}
        else:
            dispatcher.utter_message(text="Please enter a valid Philippine phone number.")
            return {"user_contact_phone": None}

class ActionSkipEmail(Action):
    def name(self) -> Text:
        return "action_skip_email"

    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        return [SlotSet("user_contact_email", "slot_skipped")]

class ActionConfirmEmail(Action):
    def name(self) -> Text:
        return "action_confirm_email"

    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        contact_modification_mode = tracker.get_slot("contact_modification_mode")
        if contact_modification_mode:
            dispatcher.utter_message(text="✅ Email updated successfully!")
            return [SlotSet("contact_modification_mode", False)]
        return [ActiveLoop("contact_form")]

class ActionProvideNewEmail(Action):
    def name(self) -> Text:
        return "action_provide_new_email"

    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        return [
            SlotSet("user_contact_email", None),
            ActiveLoop("contact_form")
        ]

class ActionModifyContactInfo(Action):
    def name(self) -> Text:
        return "action_modify_contact_info"

    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        current_email = tracker.get_slot("user_contact_email")
        current_phone = tracker.get_slot("user_contact_phone")
        
        buttons = []
        if current_email and current_email != "slot_skipped":
            buttons.append({"title": f"📧 Change Email ({current_email})", "payload": "/modify_email"})
        elif current_email == "slot_skipped":
            buttons.append({"title": "📧 Add Email", "payload": "/modify_email"})
            
        if current_phone and current_phone != "slot_skipped":
            buttons.append({"title": f"📱 Change Phone ({current_phone})", "payload": "/modify_phone"})
        elif current_phone == "slot_skipped":
            buttons.append({"title": "📱 Add Phone", "payload": "/modify_phone"})
            
        buttons.append({"title": "❌ Cancel", "payload": "/cancel_modification_contact"})
            
        dispatcher.utter_message(
            text="Which contact information would you like to modify?",
            buttons=buttons
        )
        return []

class ActionModifyEmail(Action):
    def name(self) -> Text:
        return "action_modify_email"

    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        return [
            SlotSet("user_contact_email", None),
            SlotSet("contact_modification_mode", True),
            ActiveLoop("contact_form")
        ]

class ActionCancelModification(Action):
    def name(self) -> Text:
        return "action_cancel_modification_contact"

    async def run(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="✅ Modification cancelled. Your contact information remains unchanged.")
        return [SlotSet("contact_modification_mode", False)]