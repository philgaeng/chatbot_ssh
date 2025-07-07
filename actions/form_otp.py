import re
import logging
from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from backend.services.messaging import CommunicationClient, SMSClient
from .base_classes import BaseFormValidationAction, BaseAction
from .utterance_mapping_rasa import get_utterance, get_buttons
from random import randint
logger = logging.getLogger(__name__)
from icecream import ic

class ActionAskOtpVerificationFormOtpConsent(BaseAction):
    def name(self) -> Text:
        return "action_ask_otp_verification_form_otp_consent"
    
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        message = get_utterance("otp_verification_form", self.name(), 1, language_code)
        buttons = get_buttons("otp_verification_form", self.name(), 1, language_code)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskOtpVerificationFormOtpInput(BaseAction):
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
        self.sms_client = SMSClient()
        logger.debug("=================== Asking for OTP Input ===================")
        language_code = tracker.get_slot("language_code") or "en"
        otp_number = tracker.get_slot("otp_number")
        phone_number = tracker.get_slot("user_contact_phone")
        otp_status = tracker.get_slot("otp_status")
        resend_count = tracker.get_slot("otp_resend_count") or 0
        buttons_otp = get_buttons("otp_verification_form", self.name(), 1, language_code)
        
        #deal with the case where the OTP needs to be generated = first send or resend
        if not otp_status or otp_status == "resend" and resend_count < 3 :
        # OTP already generated
            otp_number = self._generate_otp()
            message_sms = get_utterance("otp_verification_form", self.name(), 1, language_code).format(otp_number=otp_number)
            message_bot = get_utterance("otp_verification_form", self.name(), 2, language_code).format(phone_number=phone_number)
    
            if otp_status == "resend":
                message_bot_retry = get_utterance("otp_verification_form", self.name(), 3, language_code).format(
                    resend_count=resend_count + 1, max_attempts=3 - resend_count)
                message_bot = message_bot + " " + message_bot_retry
            
            try:
                self.sms_client.send_sms(phone_number, message_sms)
                logger.info("SMS sent successfully")
                dispatcher.utter_message(
                    text= message_bot,
                    buttons=buttons_otp
                )
                text = "TEMPORARY MESSAGE FOR TESTING " + message_sms
                dispatcher.utter_message(text=text)
                
            except Exception as e:
                logger.error(f"Error sending SMS: {e}")
                message_error = get_utterance("otp_verification_form", self.name(), 4, language_code)
                dispatcher.utter_message(text=message_error)
        
        if otp_status == "resend" and resend_count >= 3:
            message_max_attempts = get_utterance("otp_verification_form", self.name(), 5, language_code)
            dispatcher.utter_message(text=message_max_attempts,
                                     buttons = buttons_otp)
            


        if otp_status in ["invalid_format", "invalid_otp"]:
            message_invalid_code = get_utterance("otp_verification_form", self.name(), 6, language_code)
            dispatcher.utter_message(text=message_invalid_code,
                                     buttons = buttons_otp)
                
        if otp_status == "slot_skipped":
            message_skip = get_utterance("otp_verification_form", self.name(), 7, language_code)
            dispatcher.utter_message(text=message_skip)
            

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
        """
        Deal with the case where a gender issues is reported, 
        which means that the OTP verification is optional
        If not set up the required slots to generate and validate the OTP
        """
        print("######################### REQUIRED SLOTS ##############")

        print(f"reqested_slot : {tracker.get_slot('requested_slot')}")
        ic(tracker.get_slot("otp_consent"))
        ic(tracker.get_slot("otp_status"))
        ic(tracker.get_slot("otp_input"))
        #skip the otp_verification_form if no phone number is provided
        if not tracker.get_slot("user_contact_phone") or tracker.get_slot("user_contact_phone") == "slot_skipped":
            return []
        if tracker.get_slot("gender_issues_reported"):
            ic("gender issues reported")
            if tracker.get_slot("otp_consent") == False:
                required_slots =  ["otp_consent"]
            else:
                required_slots = ["otp_consent", "otp_input", "otp_status"]
        else:
            required_slots = ["otp_input", "otp_status"]
        return required_slots
    
    async def extract_otp_consent(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_boolean_slot_extraction(
            "otp_consent",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_otp_consent(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        ######## validate the otp consent #########
        ic(slot_value)
        return {"otp_consent": slot_value}
    
    
    async def extract_otp_input(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction("otp_input", 
                                                       tracker, 
                                                       dispatcher, 
                                                       domain)
    
    async def validate_otp_input(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("\n=================== Validating OTP Input ===================")
        print(f"Received value: {slot_value}")
        self.language_code = tracker.get_slot("language_code") or "en"

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
        if not self._is_valid_otp_verification_format(slot_value):
            print(f"❌ Invalid OTP format: {slot_value}")
            return {"otp_input": None, 
                    "otp_status" : "invalid_format",
                    "otp_resend_count" : tracker.get_slot("otp_resend_count") or 0}
            
        # Verify OTP match
        expected_otp = tracker.get_slot("otp_number")
        
        
        if self._is_matching_otp(slot_value, expected_otp):
            print("✅ OTP matched successfully")
            message = get_utterance("otp_verification_form", "otp_verified_successfully", 1, self.language_code)
            dispatcher.utter_message(text=message)
            return {"otp_input": slot_value,
                    "otp_status" : "verified",
                    "otp_verified" : True,
                    "otp_resend_count" : 0}
        else:
            print("❌ OTP verification failed")
            return {"otp_input": None,
                    "otp_status" : "invalid_otp",
                    "otp_resend_count" : tracker.get_slot("otp_resend_count") or 0}
        return {}

    def _is_valid_otp_verification_format(self, slot_value: str) -> bool:
        """Validate OTP format (6 digits)."""
        is_valid = bool(slot_value and slot_value.isdigit() and len(slot_value) == 6)
        logger.debug(f"OTP format validation: {is_valid} for value: {slot_value}")
        return is_valid

    def _is_matching_otp(self, input_otp: str, expected_otp: str) -> bool:
        """Verify if the input OTP matches the expected OTP."""
        is_matching = bool(input_otp and expected_otp and input_otp == expected_otp)
        logger.debug(f"OTP match validation: {is_matching} (Input: {input_otp}, Expected: {expected_otp})")
        return is_matching
