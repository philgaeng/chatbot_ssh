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


    
class ActionAskOtpVerificationOtpInput(Action):
    def __init__(self):
        self.sms_client = SMSClient()

    def name(self) -> Text:
        return "action_ask_otp_verification_form_otp_input"

    def _generate_otp(self):
        return ''.join([str(randint(0, 9)) for _ in range(6)])
    
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        logger.debug("=================== Asking for OTP Input ===================")
        otp_number = tracker.get_slot("otp_number")
        phone_number = tracker.get_slot("user_contact_phone")
        otp_status = tracker.get_slot("otp_status")
        resend_count = tracker.get_slot("otp_resend_count") or 0
        buttons_otp = [
            {"title": "Resend", "payload": "/resend"},
            {"title": "Skip", "payload": "/skip"}
        ]
        #deal with the case where the OTP needs to be generated = first send or resend
        if not otp_status or otp_status == "resend" and resend_count < 3 :
        # OTP already generated
            otp_number = self._generate_otp()
            message_sms = (
                f"Your verification code is {otp_number}. "
                "Please enter this code to verify your phone number."
            )
            message_bot = f"-------- OTP verification ongoing --------\nPlease enter the 6-digit One Time Password (OTP) sent to your phone {phone_number} to verify your number."
            if otp_status == "resend":
                message_bot = message_bot + f"This is your {resend_count + 1} attempt. You have {3 - resend_count} attempts left."
            
            try:
                self.sms_client.send_sms(phone_number, message_sms)
                logger.info("SMS sent successfully")
                dispatcher.utter_message(
                    text= message_bot,
                    buttons=buttons_otp
                )
                
            except Exception as e:
                logger.error(f"Error sending SMS: {e}")
                dispatcher.utter_message(text="Sorry, we couldn't send the verification code.")
        
        if otp_status == "resend" and resend_count >= 3:
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

        if otp_status in ["invalid_format", "invalid_otp"]:
            dispatcher.utter_message(text="❌ Invalid code. Please try again or type 'resend' to get a new code.",
                                     buttons = buttons_otp)
                
        if otp_status == "slot_skipped":
            dispatcher.utter_message(text="Continuing without phone verification. Your grievance details will not be sent via SMS.")
            

        return [SlotSet("otp_number", otp_number), SlotSet("otp_resend_count", resend_count)]
    

class ValidateOTPVerificationForm(BaseFormValidationAction):
    
    def __init__(self):
        super().__init__()

    def name(self) -> Text:
        return "validate_otp_verification_form"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        print("######################### REQUIRED SLOTS ##############")
        print(f"required_slots : {domain_slots}")
        print(f"reqested_slot : {tracker.get_slot('requested_slot')}")
        
        return ["otp_input", "otp_status"]
    
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
        if "resend" in slot_value:
            logger.info("Resend OTP requested")
            return {"otp_input": None, 
                    "otp_status": "resend",
                    "otp_resend_count": tracker.get_slot("otp_resend_count") or 0}

        # Handle skip request
        if slot_value in ["slot_skipped", "skip"]:
            logger.info("Skip verification requested")
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
            dispatcher.utter_message(text="✅ OTP verified successfully")
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
        logger.debug(f"OTP format validation: {is_valid} for value: {slot_value}")
        return is_valid

    def _is_matching_otp(self, input_otp: str, expected_otp: str) -> bool:
        """Verify if the input OTP matches the expected OTP."""
        is_matching = bool(input_otp and expected_otp and input_otp == expected_otp)
        logger.debug(f"OTP match validation: {is_matching} (Input: {input_otp}, Expected: {expected_otp})")
        return is_matching
