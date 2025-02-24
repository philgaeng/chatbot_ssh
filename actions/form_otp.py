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
from random import randint
logger = logging.getLogger(__name__)



class ActionAskOTPVerificationOtpInput(Action):
    def __init__(self):
        self.sms_client = SMSClient()

    def name(self) -> Text:
        return "action_ask_otp_verification_otp_input"
    
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        print("\n=================== Asking for OTP Input ===================")
        otp = tracker.get_slot("otp_number")
        phone_number = tracker.get_slot("user_contact_phone")
        otp_status = tracker.get_slot("otp_status")
        resend_count = tracker.get_slot("otp_resend_count") or 0
        buttons_otp = [
            {"title": "Resend", "payload": "/resend"},
            {"title": "Skip", "payload": "/skip"}
        ]
        
        cond_generate_otp = otp and (not otp_status or otp_status == "resend" and resend_count < 3)
        if cond_generate_otp:  # OTP already generated
            message_sms = (
                f"Your verification code is {otp}. "
                "Please enter this code to verify your phone number."
            )
            message_bot = f"Please enter the 6-digit One Time Password (OTP) sent to your phone {phone_number} to verify your number."
            if otp_status == "resend":
                message_bot = message_bot + f"This is your {resend_count + 1} attempt. You have {3 - resend_count} attempts left."
            if self.sms_client.send_sms(phone_number, message_sms):
                print("✅ SMS sent successfully")
                dispatcher.utter_message(
                    text= message_bot,
                    buttons=buttons_otp
                )
            else:
                dispatcher.utter_message(text="❌ Sorry, we couldn't send the verification code.")
        
        if otp and otp_status == "resend" and resend_count >= 3:
            dispatcher.utter_message(text="❌ Maximum resend attempts reached. Please try again later or skip verification.",
                                     buttons = buttons_otp)
            
            # TODO: Add phone number verification flow
            # 1. Show current phone number
            # 2. Add buttons/options to:
            #    - Confirm number is correct (reset OTP counter and try again)
            #    - Edit phone number (redirect to phone modification flow)
            #    - Skip verification
            # dispatcher.utter_message(
            #     text=(f"❌ Maximum resend attempts reached for {phone_number}.\n"
            #           "Would you like to verify your phone number or try a different one?"),
            #     buttons=[
            #         {"title": "Number is correct", "payload": "/affirm"},
            #         {"title": "Change number", "payload": "/modify_phone"},
            #         {"title": "Skip verification", "payload": "/skip"}
            #     ]
            # )
            # TODO: Add corresponding story paths and rules for each option

        if otp and otp_status in ["invalid_format", "invalid_otp"]:
            dispatcher.utter_message(text="❌ Invalid code. Please try again or type 'resend' to get a new code.",
                                     buttons = buttons_otp)
                
        if otp and otp_status == "slot_skipped":
            dispatcher.utter_message(text="Continuing without phone verification. Your grievance details will not be sent via SMS.")
            

        return []
    

class ValidateOTPVerificationForm(FormValidationAction):

    def name(self) -> Text:
        return "validate_otp_verification_form"
    
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
    async def validate_otp_number(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("\n=================== Generating OTP ===================")
        if tracker.get_slot("requested_slot") == "otp_number":
            otp_number = ''.join([str(randint(0, 9)) for _ in range(6)])
            print(f"Generated OTP: {otp_number}")
            return {"otp_number": otp_number}
        return {}

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
        if "resend" in slot_value:
            print("🔄 Resend OTP requested")
            return {"otp_input": None, 
                    "otp_status" : "resend",
                    "otp_resend_count" : tracker.get_slot("otp_resend_count") or 0}

        # Handle skip request
        if slot_value in ["slot_skipped", "skip"]:
            print("⏩ Skip verification requested")
            return {"otp_input": "slot_skipped", 
                    "otp_status" : "slot_skipped",
                    "otp_resend_count" : 0}

        # Validate OTP format
        if not self._is_valid_otp_format(slot_value):
            print(f"❌ Invalid OTP format: {slot_value}")
            return {"otp_input": None, 
                    "otp_status" : "invalid_format",
                    "otp_resend_count" : tracker.get_slot("otp_resend_count") or 0}
            
        # Verify OTP match
        expected_otp = tracker.get_slot("otp_number")
        
        
        if self._is_matching_otp(slot_value, expected_otp):
            print("✅ OTP matched successfully")
            return {"otp_input": slot_value,
                    "otp_status" : "verified",
                    "otp_resend_count" : 0}
        else:
            print("❌ OTP verification failed")
            return {"otp_input": None,
                    "otp_status" : "invalid_otp",
                    "otp_resend_count" : tracker.get_slot("otp_resend_count") or 0}
        return {}

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
