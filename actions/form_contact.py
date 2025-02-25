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


class AskContactFormUserContactConsent(Action):
    def name(self) -> str:
        return "action_ask_contact_form_user_contact_consent"

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
                {"title": "Yes", "payload": "/affirm"},
                {"title": "Anonymous with phone", "payload": "/anonymous_with_phone"},
                {"title": "No contact info", "payload": "/slot_skipped"},
            ]
        )
        return []
    
class ActionAskContactFormUserFullName(Action):
    def name(self) -> Text:
        return "action_ask_contact_form_user_full_name"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Please enter your full name. You can skip this if you prefer to remain anonymous.",
                                 buttons=[
                                     {"title": "Skip", "payload": "/slot_skipped"}
                                 ]
                                 )
        return []
    
class ActionAskContactFormUserContactPhone(Action):
    def name(self) -> Text:
        return "action_ask_contact_form_user_contact_phone"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Please enter your contact phone number. Nepali phone number starts with 9 and should be 10 digits long. \nYou can skip this if you prefer to remain anonymous.",
                                 buttons=[
                                     {"title": "Skip", "payload": "/slot_skipped"}
                                 ]
                                 )
        return []
    

class ActionAskContactFormPhoneValidationRequired(Action):
    def name(self) -> Text:
        return "action_ask_contact_form_phone_validation_required"

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
                {"title": "Give Phone Number", "payload": "/affirm"},
                {"title": "File Grievance as is", "payload": "/deny"}
            ]
        )
        return []
    
class ActionAskContactFormUserContactEmailTemp(Action):
    def name(self) -> Text:
        return "action_ask_contact_form_user_contact_email_temp"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Please enter your contact email. You can skip this if you prefer to remain anonymous.",
                                 buttons=[
                                     {"title": "Skip", "payload": "/slot_skipped"}
                                 ]
                                 )
        return []
    
class ActionAskContactFormUserContactEmailConfirmed(Action):
    def name(self) -> Text:
        return "action_ask_contact_form_user_contact_email_confirmed"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        domain_name = tracker.get_slot("user_contact_email_temp").split('@')[1]
        dispatcher.utter_message(
                text=f"⚠️ The email domain '{domain_name}' is not recognized as a common Nepali email provider.\nPlease confirm if this is correct or try again with a different email.",
                buttons=[
                    {"title": "Confirm Email", "payload": f"/slot_confirmed"},
                    {"title": "Try Different Email", "payload": "/slot_edited"},
                    {"title": "Skip Email", "payload": "/slot_skipped"}
            ]
        )
        return []

    
class ValidateContactForm(BaseFormValidationAction):
    """Form validation action for contact details collection."""
    
    def __init__(self):
        super().__init__()

    def name(self) -> Text:
        return "validate_contact_form"

    
    async def extract_user_contact_consent(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "user_contact_consent",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_user_contact_consent(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        print("################ Validate user contact consent ###################")
        print(f"Received value: {slot_value}")
        slot_value = slot_value.strip('/')
        
        if slot_value == "slot_skipped":
            return {"user_contact_consent": "slot_skipped",
                    "user_full_name": "slot_skipped",
                    "user_contact_phone": "slot_skipped",
                    "user_contact_email_temp": "slot_skipped",
                    "user_contact_email_confirmed": "slot_skipped"
                    }
        if slot_value == "anonymous_with_phone":
            return {"user_contact_consent": "anonymous_with_phone",
                    "user_full_name": "slot_skipped",
                    "user_contact_phone": None,
                    "user_contact_email_temp": "slot_skipped",
                    "user_contact_email_confirmed": "slot_skipped"
                    }
        if slot_value == "affirm":
            return {"user_contact_consent": "affirm",
                    "user_full_name": None,
                    "user_contact_phone": None,
                    "user_contact_email_temp": None,
                    "user_contact_email_confirmed": None
                    }
        

    async def extract_user_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "user_full_name",
            tracker,
            dispatcher,
            domain
        )
    
    def validate_user_full_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        print("################ Validate user full name ###################")
        print(f"Validating value: {slot_value}")
        if "slot_skipped" in slot_value:
            print("full name skipped")
            return {"user_full_name": "slot_skipped"}
        
        if not slot_value or slot_value.startswith('/'):
            print("validation rejected")
            return {"user_full_name": None}

        if len(slot_value)<3:
            dispatcher.utter_message(text="Please enter a valid full name")
            return {"user_full_name": None}
        
        print("validated :", slot_value)
        return {"user_full_name": slot_value}
    
    # ✅ Extract user contact phone
    async def extract_user_contact_phone(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        
        return await self._handle_slot_extraction(
            "user_contact_phone",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_user_contact_phone(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate phone number and set validation requirement."""
        print("################ Validate user contact phone ###################")
        print(f"Received value: {slot_value}")

        if "slot_skipped" in slot_value:
            print("⏩ Phone number skipped")
            return {
                "user_contact_phone": "slot_skipped"
            }
        if slot_value.startswith("/"):
            print("payload in slot, reset to None")
            return {"user_contact_phone": None}  
        
        # Validate phone number format
        if not self._is_valid_phone(slot_value):
            dispatcher.utter_message(text="Please enter a valid phone number.")
            return {"user_contact_phone": None}

        print("validated :", slot_value)
        
        if re.match(r'^09\d{9}$', slot_value) or re.match(r'^639\d{8}$', slot_value):
            dispatcher.utter_message(text="You entered a PH number for validation.")
            slot_value = slot_value.replace('09', '+639') if slot_value.startswith('09') else slot_value.replace('639', '+639') if slot_value.startswith('639') else slot_value
        return {
            "user_contact_phone": slot_value,
            "phone_validation_required": True
        }

    def _is_valid_phone(self, phone: str) -> bool:
        """Check if the phone number is valid."""
        # Add your phone validation logic here
        #Nepalese logic
        # 1. Must be 10 digits and start with 9
        if re.match(r'^9\d{9}$', phone):
            return True
        #Matching PH number format for testing
        if re.match(r'^09\d{9}$', phone) or re.match(r'^639\d{8}$', phone):
            return True
        return False

    async def extract_phone_validation_required(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_slot_extraction(
            "phone_validation_required",
            tracker,
            dispatcher,
            domain
        )

    async def validate_phone_validation_required(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value and tracker.get_slot("user_contact_phone") == "slot_skipped":
            print("Reset phone number to None - expected next slot to be user_contact_phone")
            return {"phone_validation_required": None,
                    "user_contact_phone": None}
        else:
            return {"phone_validation_required": False}


    def _email_extract_from_text(self, text: str) -> Optional[str]:
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        email_match = re.search(email_pattern, text)
        return email_match.group(0) if email_match else None

    def _email_is_valid_nepal_domain(self, email: str) -> bool:
        email_domain = email.split('@')[1].lower()
        return email_domain in EMAIL_PROVIDERS_NEPAL_LIST or email_domain.endswith('.com.np')

    # ✅ Validate user contact email
    def _email_is_valid_format(self, email: Text) -> bool:
        """Check if email follows basic format requirements."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    async def extract_user_contact_email_temp(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
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
        print("################ Validate user contact email temp ###################")
        if slot_value == "slot_skipped":
            return {"user_contact_email_temp": "slot_skipped"}
        
        extracted_email = self._email_extract_from_text(slot_value)
        print(f"Extracted email: {extracted_email}")
        if not extracted_email:
            dispatcher.utter_message(
            text=(
                "⚠️ I couldn't find a valid email address in your message.\n"
                "A valid email should be in the format: **username@domain.com**."
            )
            )
            return {"user_contact_email_temp": None}
        
        # Use consistent validation methods
        if not self._email_is_valid_format(extracted_email):
            dispatcher.utter_message(text="⚠️ Please enter a valid email address.")
            return {"user_contact_email_temp": None}

        # Check for Nepali email domain using existing method
        if not self._email_is_valid_nepal_domain(extracted_email):
            print("user validation required")
            # Keep the email in slot but deactivate form while waiting for user choice
            return {"user_contact_email_temp": extracted_email,
                    "user_contact_email_confirmed": None}
            
        print("email is valid")
        # If all validations pass
        return {"user_contact_email_temp": extracted_email,
                "user_contact_email_confirmed": True,
                "user_contact_email": extracted_email}
    
    async def extract_user_contact_email_confirmed(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "user_contact_email_confirmed",
            tracker,
            dispatcher,
            domain
        )
    async def validate_user_contact_email_confirmed(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
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
        print("################ Validate user contact email confirmed ###################")
        if slot_value == "slot_skipped":
            return {"user_contact_email_confirmed": "slot_skipped"}
        if slot_value == "slot_confirmed":
            return {"user_contact_email_confirmed": True}
        if slot_value == "slot_edited":
            return {"user_contact_email_temp": None,
                    "user_contact_email_confirmed": None}


# class ActionCheckPhoneValidation(Action):
#     def name(self) -> Text:
#         return "action_check_phone_validation"

#     async def run(
#         self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
#     ) -> List[Dict[Text, Any]]:
#         phone_number = tracker.get_slot("user_contact_phone")
        
#         if phone_number and phone_number != "Skipped":
#             return [SlotSet("phone_validation_required", True)]
#         else:
#             return [SlotSet("phone_validation_required", False)]

# class ActionAskContactFormPhoneValidationRequired(Action):
#     def name(self) -> Text:
#         return "action_ask_contact_form_phone_validation_required"

#     async def run(
#         self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
#     ) -> List[Dict[Text, Any]]:
#         dispatcher.utter_message(
#             text=(
#                 "Your grievance is filed without a validated number. Providing a valid number "
#                 "will help in the follow-up of the grievance and we recommend it. However, "
#                 "you can file the grievance as is."
#             ),
#             buttons=[
#                 {"title": "Give Phone Number", "payload": "/provide_phone_number"},
#                 {"title": "File Grievance as is", "payload": "/file_without_validation"}
#             ]
#         )
#         return []

# class PhoneValidationForm(FormValidationAction):
#     def name(self) -> Text:
#         return "validate_phone_validation_form"

#     @staticmethod
#     def required_slots(tracker: Tracker) -> List[Text]:
#         return ["user_contact_phone"]

#     async def validate_user_contact_phone(
#         self,
#         slot_value: Text,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> Dict[Text, Any]:
#         if re.match(r'^\+?63\d{10}$', slot_value):
#             return {"user_contact_phone": slot_value}
#         else:
#             dispatcher.utter_message(text="Please enter a valid Philippine phone number.")
#             return {"user_contact_phone": None}

# class ActionSkipEmail(Action):
#     def name(self) -> Text:
#         return "action_skip_email"

#     async def run(
#         self, 
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any]
#     ) -> List[Dict[Text, Any]]:
#         return [SlotSet("user_contact_email", "slot_skipped")]

# class ActionConfirmEmail(Action):
#     def name(self) -> Text:
#         return "action_confirm_email"

#     async def run(
#         self, 
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any]
#     ) -> List[Dict[Text, Any]]:
#         contact_modification_mode = tracker.get_slot("contact_modification_mode")
#         if contact_modification_mode:
#             dispatcher.utter_message(text="✅ Email updated successfully!")
#             return [SlotSet("contact_modification_mode", False)]
#         return [ActiveLoop("contact_form")]

# class ActionProvideNewEmail(Action):
#     def name(self) -> Text:
#         return "action_provide_new_email"

#     async def run(
#         self, 
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any]
#     ) -> List[Dict[Text, Any]]:
#         return [
#             SlotSet("user_contact_email", None),
#             ActiveLoop("contact_form")
#         ]

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