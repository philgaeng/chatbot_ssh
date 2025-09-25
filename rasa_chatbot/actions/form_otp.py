
from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.types import DomainDict
from rasa_chatbot.actions.utils.base_classes import BaseFormValidationAction, BaseAction
from random import randint


class ActionAskOtpConsent(BaseAction):
    def name(self) -> Text:
        return "action_ask_otp_consent"
    
    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        reset_otp_slots = self.reset_slots(tracker, "otp_submission")
        return reset_otp_slots
    
class ActionAskOtpInput(BaseAction):
    def name(self) -> Text:
        return "action_ask_otp_input"

    def _generate_otp(self):
        return ''.join([str(randint(0, 9)) for _ in range(6)])
    
    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        self.logger.debug(f"{self.name()} - Asking for OTP Input")
        otp_number = tracker.get_slot("otp_number")
        phone_number = tracker.get_slot("complainant_phone")
        otp_status = tracker.get_slot("otp_status")
        resend_count = tracker.get_slot("otp_resend_count") or 0
        buttons_otp = self.get_buttons(1)
        
        #deal with the case where the OTP needs to be generated = first send or resend
        if not otp_status or otp_status == "resend" and resend_count < 3 :
        # OTP already generated
            otp_number = self._generate_otp()
            message_sms = self.get_utterance(1)
            message_sms = message_sms.format(otp_number=otp_number)
            message_bot = self.get_utterance(2)
            message_bot = message_bot.format(phone_number=phone_number)
    
            if otp_status == "resend":
                message_bot_retry = self.get_utterance(3)
                message_bot_retry = message_bot_retry.format(
                    resend_count=resend_count + 1, max_attempts=3 - resend_count)
                message_bot = message_bot + " " + message_bot_retry
            
            try:
                self.messaging.send_sms(phone_number, message_sms)
                self.logger.info(f"{self.name()} - SMS sent successfully")
                dispatcher.utter_message(
                    text= message_bot,
                    buttons=buttons_otp
                )
                text = "TEMPORARY MESSAGE FOR TESTING " + message_sms
                dispatcher.utter_message(text=text)
                
            except Exception as e:
                self.logger.error(f"{self.name()} - Error sending SMS: {e}")
                message_error = self.get_utterance(4)
                dispatcher.utter_message(text=message_error)
        
        if otp_status == "resend" and resend_count >= 3:
            message_max_attempts = self.get_utterance(5)
            dispatcher.utter_message(text=message_max_attempts,
                                     buttons = buttons_otp)
            


        if otp_status in ["invalid_format", "invalid_otp"]:
            message_invalid_code = self.get_utterance(6)
            dispatcher.utter_message(text=message_invalid_code,
                                     buttons = buttons_otp)
                
        if otp_status == "slot_skipped":
            message_skip = self.get_utterance(7)
            dispatcher.utter_message(text=message_skip)
            

        return [SlotSet("otp_number", otp_number), SlotSet("otp_resend_count", resend_count)]
    

class ValidateFormOtp(BaseFormValidationAction):
    
    def __init__(self):
        super().__init__()

    def name(self) -> Text:
        return "validate_form_otp"

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
        self._initialize_language_and_helpers(tracker)
        self.logger.info(f"{self.name()} - reqested_slot : {tracker.get_slot('requested_slot')}")
        self.logger.info(f"{self.name()} - otp_consent : {tracker.get_slot('otp_consent')}")
        self.logger.info(f"{self.name()} - otp_status : {tracker.get_slot('otp_status')}")
        self.logger.info(f"{self.name()} - otp_input : {tracker.get_slot('otp_input')}")
        #skip the form_otp if no phone number is provided
        if not tracker.get_slot("complainant_phone") or tracker.get_slot("complainant_phone") == "slot_skipped":
            return []
        if tracker.get_slot("sensitive_issues_detected"):
            self.logger.info(f"{self.name()} - gender issues reported")
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
        return await self._handle_boolean_and_category_slot_extraction(
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
        self.logger.info(f"{self.name()} - Received value: {slot_value}")
        self.language_code = tracker.get_slot("language_code") or "en"

        slot_value = slot_value.strip("/").lower()
        if "resend" in slot_value:
            self.logger.info(f"{self.name()} - Resend OTP requested")
            return {"otp_input": None, 
                    "otp_status": "resend",
                    "otp_resend_count": tracker.get_slot("otp_resend_count") or 0}

        # Handle skip request
        if slot_value in ["slot_skipped", "skip"]:
            self.logger.info(f"{self.name()} - Skip verification requested")
            return {"otp_input": "slot_skipped", 
                    "otp_status" : "slot_skipped",
                    "otp_resend_count" : 0}

        # Validate OTP format
        if not self._is_valid_format_otp(slot_value):
            self.logger.info(f"{self.name()} - Invalid OTP format: {slot_value}")
            return {"otp_input": None, 
                    "otp_status" : "invalid_format",
                    "otp_resend_count" : tracker.get_slot("otp_resend_count") or 0}
            
        # Verify OTP match
        expected_otp = tracker.get_slot("otp_number")
        
        
        if self._is_matching_otp(slot_value, expected_otp):
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            return {"otp_input": slot_value,
                    "otp_status" : "verified",
                    "otp_verified" : True,
                    "otp_resend_count" : 0}
        else:
            self.logger.info(f"{self.name()} - OTP verification failed")
            return {"otp_input": None,
                    "otp_status" : "invalid_otp",
                    "otp_resend_count" : tracker.get_slot("otp_resend_count") or 0}
        return {}

    def _is_valid_format_otp(self, slot_value: str) -> bool:
        """Validate OTP format (6 digits)."""
        is_valid = bool(slot_value and slot_value.isdigit() and len(slot_value) == 6)
        self.logger.debug(f"{self.name()} - OTP format validation: {is_valid} for value: {slot_value}")
        return is_valid

    def _is_matching_otp(self, input_otp: str, expected_otp: str) -> bool:
        """Verify if the input OTP matches the expected OTP."""
        is_matching = bool(input_otp and expected_otp and input_otp == expected_otp)
        self.logger.debug(f"{self.name()} - OTP match validation: {is_matching} (Input: {input_otp}, Expected: {expected_otp})")
        return is_matching
