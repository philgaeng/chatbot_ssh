
from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.types import DomainDict
from rasa_chatbot.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction
from random import randint

class BaseOtpAction(BaseAction):
    def __init__(self):
        super().__init__()
        
    def get_otp_phone_number(self, tracker: Tracker) -> str:
        """
        Get the phone number from the tracker, according to the current flow, language code, standardize it and return it.
        """
        flow = tracker.get_slot("story_main")
        if flow == "grievance_submission":
            phone_number = tracker.get_slot("complainant_phone")
        elif flow == "status_check":
            phone_number = tracker.get_slot("complainant_phone")
        else:
            phone_number = None
        if phone_number:
            phone_number = self.helpers.standardize_phone(language_code=self.language_code, phone=phone_number)
        return phone_number



class ActionAskOtpConsent(BaseOtpAction):
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
        reset_otp_slots = self.reset_slots(tracker, flow = "otp_submission", output = "slot_list")
        return reset_otp_slots
    
class ActionAskOtpInput(BaseOtpAction):
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
        phone_number = self.get_otp_phone_number(tracker)
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
    

class ValidateFormOtp(BaseFormValidationAction, BaseOtpAction):
    
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
        Dynamically determine required slots based on phone collection and OTP verification needs.
        1. Collect phone if not already provided
        2. Deal with the case where a gender issue is reported (OTP is optional)
        3. Set up the required slots to generate and validate the OTP
        """
        self._initialize_language_and_helpers(tracker)
        self.logger.debug(f"{self.name()} - requested_slot : {tracker.get_slot('requested_slot')}")
        self.logger.debug(f"{self.name()} - complainant_phone : {tracker.get_slot('complainant_phone')}")
        self.logger.debug(f"{self.name()} - otp_consent : {tracker.get_slot('otp_consent')}")
        self.logger.debug(f"{self.name()} - otp_status : {tracker.get_slot('otp_status')}")
        self.logger.debug(f"{self.name()} - otp_input : {tracker.get_slot('otp_input')}")
        
        required_slots = ["complainant_phone", "otp_consent", "otp_input", "otp_status"]
        
        # # 1. Collect phone if not already provided
        # phone = tracker.get_slot("complainant_phone")
        # if not phone or phone == self.DEFAULT_VALUES['SKIP_VALUE']:
        #     required_slots.append("complainant_phone")
        #     # If we need to collect phone, don't ask for OTP yet
        #     return required_slots
        
        # # 2. Phone exists, proceed with OTP verification
        # if tracker.get_slot("grievance_sensitive_issue"):
        #     self.logger.debug(f"{self.name()} - sensitive issue reported - OTP is optional")
        #     if tracker.get_slot("otp_consent") == False:
        #         required_slots = ["otp_consent"]
        #     else:
        #         required_slots = ["otp_consent", "otp_input", "otp_status"]
        # else:
        #     required_slots = ["otp_input", "otp_status"]
        
        # required_slots.append("form_otp_next_action")
        
        return required_slots
    
    async def extract_complainant_phone(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Extract phone number from user input."""
        return await self._handle_slot_extraction(
            "complainant_phone",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_complainant_phone(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """Validate phone number format and standardize it."""
        return self.base_validate_phone(slot_value, dispatcher)
    
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

        slot_value = slot_value.strip("/").lower()
        
        # Handle change phone request
        if "modify_phone" in slot_value:
            self.logger.info(f"{self.name()} - Change phone requested")
            return {
                "otp_input": None,
                "otp_status": None,
                "otp_number": None,
                "otp_resend_count": 0,
                "complainant_phone": None  # Reset phone to trigger re-collection
            }
        
        # Handle resend request
        if "resend" in slot_value:
            self.logger.info(f"{self.name()} - Resend OTP requested")
            return {"otp_input": None, 
                    "otp_status": "resend",
                    "otp_resend_count": tracker.get_slot("otp_resend_count") + 1 if tracker.get_slot("otp_resend_count") else 1}

        # Handle skip request
        if slot_value in [self.DEFAULT_VALUES['SKIP_VALUE'], "skip"]:
            self.logger.info(f"{self.name()} - Skip verification requested")
            return {"otp_input": self.DEFAULT_VALUES['SKIP_VALUE'], 
                    "otp_status" : self.DEFAULT_VALUES['SKIP_VALUE'],
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



