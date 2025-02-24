import re
import logging
from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from .messaging import CommunicationClient, SMSClient
from .constants import EMAIL_PROVIDERS_NEPAL
from .base_form import BaseFormValidationAction
logger = logging.getLogger(__name__)


class ValidateOTPVerificationForm(FormValidationAction, OTPSMSActions):
    """Form validation action for OTP verification."""
    
    def name(self) -> Text:
        return "validate_otp_verification_form"
    
    def __init__(self):
        self.sms_client = SMSClient()

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        print("\n=================== OTP Form Required Slots ===================")
        print(f"Current slots: {tracker.slots}")
        
        # Check if we need to initiate OTP verification
        if not tracker.get_slot("otp_number"):
            print("🔄 Initiating OTP verification")
            await self._initiate_otp_verification(dispatcher, tracker)
            return ["otp_input"]
        
        # If verification is complete, no more slots needed
        if tracker.get_slot("otp_verified") in [True, False]:
            print("✅ OTP verification completed - no more slots required")
            return []
            
        print("📝 Requiring OTP input slot")
        return ["otp_input"]
    
    async def extract_otp_input(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "otp_input",
            tracker,
            dispatcher,
            domain
        )
            
    async def validate_otp_input(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("\n=================== Validating OTP Input ===================")
        print(f"Received value: {slot_value}")

        slot_value = slot_value.strip("/").lower()
        if slot_value in ["resend", "000000"]:
            print("🔄 Resend OTP requested")
            return self._handle_resend_otp(dispatcher, tracker)

        # Handle skip request
        if slot_value in ["slot_skipped", "skip", "999999"]:
            print("⏩ Skip verification requested")
            return self._handle_skip_verification(dispatcher)

        # Validate OTP format
        if not self._is_valid_otp_format(slot_value):
            print(f"❌ Invalid OTP format: {slot_value}")
            return self._handle_invalid_format(dispatcher)

        # # Handle test OTP
        # if slot_value == "000000":
        #     print("🔑 Test OTP detected")
        #     return self._handle_test_otp(dispatcher)

        # Verify OTP match
        expected_otp = tracker.get_slot("otp_number")
        if self._is_matching_otp(slot_value, expected_otp):
            print("✅ OTP matched successfully")
            return self._handle_successful_verification(dispatcher, tracker)
        
        # Handle failed verification
        print("❌ OTP verification failed")
        return self._handle_failed_verification(dispatcher, tracker, slot_value)

    def _is_valid_otp_format(self, slot_value: str) -> bool:
        """Validate OTP format (6 digits)."""
        is_valid = bool(slot_value and slot_value.isdigit() and len(slot_value) == 6)
        print(f"OTP format validation: {is_valid} for value: {slot_value}")
        return is_valid

    def _is_matching_otp(self, input_otp: str, expected_otp: str) -> bool:
        """Verify if the input OTP matches the expected OTP."""
        is_matching = bool(input_otp and expected_otp and input_otp == expected_otp)
        print(f"OTP match validation: {is_matching} (Input: {input_otp}, Expected: {expected_otp})")
        return is_matching

    def _generate_and_send_otp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        is_resend: bool = False
    ) -> Dict[Text, Any]:
        """Generate OTP and send it via SMS."""
        print("\n=================== Generating and Sending OTP ===================")
        
        # Generate OTP
        otp = ''.join([str(randint(0, 9)) for _ in range(6)])
        phone_number = tracker.get_slot("user_contact_phone")
        
        print(f"🔑 Generated OTP: {otp}")
        print(f"📱 Target phone: {phone_number}")
        
        # Prepare message
        message = (
            f"Your {'new ' if is_resend else ''}verification code is {otp}. "
            "Please enter this code to verify your phone number."
        )
        
        # Send SMS
        if self.sms_client.send_sms(phone_number, message):
            print("✅ SMS sent successfully")
            
            # Prepare success message
            if is_resend:
                dispatcher.utter_message(
                    text="✅ A new verification code has been sent to your phone number."
                )
            else:
                dispatcher.utter_message(
                    text="✅ A verification code has been sent to your phone number.\n"
                         "Please enter the 6-digit code to verify your number.\n\n"
                         "Type 'resend' or '000000' if you don't receive the code.\n\n"
                         "Type 'skip' or '999999' if you don't want to verify your phone number."
                )
            
            # Calculate resend count
            current_resend_count = tracker.get_slot("otp_resend_count") or 0
            new_resend_count = current_resend_count + 1 if is_resend else 0
            
            return {
                "otp_number": otp,
                "otp_input": None,
                "otp_resend_count": new_resend_count,
                "otp_verified": None
            }
        else:
            print("❌ Failed to send SMS")
            dispatcher.utter_message(
                text="❌ Sorry, we couldn't send the verification code. Please try again."
            )
            return {"otp_input": None}

    async def _initiate_otp_verification(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker
    ) -> None:
        """Initialize OTP verification by generating and sending OTP."""
        print("\n=================== Initiating OTP Verification ===================")
        return self._generate_and_send_otp(dispatcher, tracker, is_resend=False)

    def _handle_empty_input(self, dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
        """Handle case when no input is provided."""
        print("🔄 Handling empty input - requesting OTP again")
        dispatcher.utter_message(text="Please enter the 6-digit verification code sent to your phone.")
        return {"otp_input": None}

    def _handle_invalid_format(self, dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
        """Handle case when input format is invalid."""
        print("🔄 Handling invalid format - requesting valid OTP")
        dispatcher.utter_message(text="Please enter a valid 6-digit code.")
        return {"otp_input": None}

    def _handle_test_otp(self, dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
        """Handle test OTP case."""
        print("✅ Processing test OTP verification")
        dispatcher.utter_message(text="✅ Phone number verified successfully (Test Mode)")
        return {
            "otp_input": "000000",
            "otp_verified": False
        }

    def _handle_skip_verification(self, dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
        """Handle case when user wants to skip verification."""
        print("⏩ Processing skip verification request")
        dispatcher.utter_message(
            text="Continuing without phone verification. Your grievance details will not be sent via SMS."
        )
        return {
            "otp_input": "skipped",
            "otp_verified": False
        }

    def _handle_successful_verification(
        self, 
        dispatcher: CollectingDispatcher, 
        tracker: Tracker
    ) -> Dict[Text, Any]:
        """Handle successful OTP verification."""
        print("✅ Processing successful verification")
        phone_number = tracker.get_slot("user_contact_phone")
        print(f"Phone number being verified: {phone_number}")
        
        dispatcher.utter_message(
            text=f"✅ Phone number verified successfully!\n"
                 f"Your phone number ({phone_number}) has been verified and saved."
        )
        result = {
            "otp_input": tracker.get_slot("otp_number"),
            "otp_verified": True
        }
        print(f"Returning slots: {result}")
        return result

    def _handle_failed_verification(
        self, 
        dispatcher: CollectingDispatcher, 
        tracker: Tracker,
        slot_value: str
    ) -> Dict[Text, Any]:
        """Handle failed OTP verification."""
        print("⚠️ Processing failed verification")
        resend_count = tracker.get_slot("otp_resend_count") or 0
        print(f"Current resend count: {resend_count}")
        
        if resend_count >= 3:
            print("❌ Maximum attempts reached")
            return self._handle_max_attempts_reached(dispatcher, slot_value)
            
        dispatcher.utter_message(
            text="❌ Invalid code. Please try again or type 'resend' to get a new code."
        )
        result = {
            "otp_input": None,
            "otp_resend_count": resend_count + 1
        }
        print(f"Returning slots: {result}")
        return result

    def _handle_max_attempts_reached(
        self, 
        dispatcher: CollectingDispatcher, 
        slot_value: str
    ) -> Dict[Text, Any]:
        """Handle case when maximum attempts are reached."""
        print("❌ Processing max attempts reached")
        dispatcher.utter_message(
            text="❌ Verification failed. Maximum attempts reached.\n"
                 "You will continue without phone verification.\n"
        )
        result = {
            "otp_input": slot_value,
            "otp_verified": False
        }
        print(f"Returning slots: {result}")
        return result

    def _handle_resend_otp(
        self, 
        dispatcher: CollectingDispatcher,
        tracker: Tracker
    ) -> Dict[Text, Any]:
        """Handle OTP resend request."""
        print("\n=================== Processing OTP Resend ===================")
        
        resend_count = tracker.get_slot("otp_resend_count") or 0
        if resend_count >= 3:
            print("❌ Maximum resend attempts reached")
            dispatcher.utter_message(
                text="❌ Maximum resend attempts reached. Please try again later."
            )
            return {
                "otp_input": None,
                "otp_verified": False
            }
            
        return self._generate_and_send_otp(dispatcher, tracker, is_resend=True)

class ActionAskOTPVerificationOtpInput(Action):
    def name(self) -> Text:
        return "action_ask_otp_verification_otp_input"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Please enter the 6-digit verification code sent to your phone.\n"
                                     "Press 'resend' or '000000' if you don't receive the code.\n\n"
                                     "Press 'skip' or '999999' if you don't want to verify your phone number.",
                                buttons = [
                                    {"title": "Resend", "payload": "/resend"},
                                    {"title": "Skip", "payload": "/skip"}
                                    ]
                                )
        return []


