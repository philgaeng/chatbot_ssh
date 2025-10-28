from abc import abstractmethod, ABC
import re
from rasa_sdk.forms import FormValidationAction
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.events import FollowupAction, ActiveLoop
from typing import Dict, Text, Any, Tuple, List, Callable
import inspect
from .base_mixins import ActionFlowHelpersMixin, ActionMessagingHelpersMixin
from actions.utils.utterance_mapping_rasa import get_utterance_base, get_buttons_base
from backend.config.constants import DEFAULT_VALUES

DEFAULT_LANGUAGE_CODE = DEFAULT_VALUES['DEFAULT_LANGUAGE_CODE']
SKIP_VALUE = DEFAULT_VALUES['SKIP_VALUE']

    


class BaseAction( 
                ActionFlowHelpersMixin, 
                ActionMessagingHelpersMixin):


    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Standard run method with automatic logging.
        Subclasses should override execute_action() instead of run().
        """
        self._initialize_language_and_helpers(tracker)
        action_detailed_name = self.file_name + "-" + self.name()
        #I want to get the name of the file where the action is defined
        if not hasattr(self, 'session_id'):
            self.session_id = tracker.sender_id
        
        # Log action start
        self.logger.debug(f"Action started: {action_detailed_name} | Session: {self.session_id}")
        
        try:
            # Execute the actual action logic
            result = await self.execute_action(dispatcher, tracker, domain)
            
            # Log successful completion
            self.logger.debug(f"Action completed: {action_detailed_name} | Session: {self.session_id}")
            
            return result
            
        except Exception as e:
            # Log error with context
            self.logger.error(
                f"Action failed: {action_detailed_name} | Error: {str(e)}", 
                exc_info=True
            )
            raise
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Execute the actual action logic. Override this method in subclasses.
        
        Args:
            dispatcher: The dispatcher for sending messages
            tracker: The tracker for accessing conversation state
            domain: The domain configuration
            
        Returns:
            List[Dict[Text, Any]]: List of events to be applied
        """
        raise NotImplementedError("Subclasses must implement execute_action()")


class BaseFormValidationAction(FormValidationAction, BaseAction):
    """
    Base class for form validation.
    
    Forms can choose TWO patterns:
    
    PATTERN 1 (Existing - Backwards Compatible):
        Override required_slots() directly - no framework slots added.
        
        Example:
            class ValidateFormContact(BaseFormValidationAction):
                async def required_slots(self, domain_slots, dispatcher, tracker, domain):
                    return ["complainant_location_consent", "complainant_province", ...]
    
    PATTERN 2 (New - Opt-In Framework):
        Override required_slots_form() instead - automatically wraps with framework slots.
        Framework adds:
        - set_next_action (runs first - form initialization)
        - form_next_action (runs last - centralized routing via ActionAskFormNextAction)
        
        Example:
            class ValidateFormOtp(BaseFormValidationAction, BaseOtpAction):
                async def required_slots_form(self, domain_slots, dispatcher, tracker, domain):
                    # Define only OTP-specific slots
                    slots = ["complainant_phone", "otp_input", "otp_status"]
                    return slots
                    
                # Framework automatically wraps as:
                # ["set_next_action", "complainant_phone", "otp_input", "otp_status", "form_next_action"]
                # Routing logic is handled in ActionAskFormNextAction.get_next_action_for_form()
    """
    
    message_display_list_cat = False

    def __init__(self):
        """Initialize shared resources."""
        FormValidationAction.__init__(self)
        BaseAction.__init__(self)

    @abstractmethod
    def name(self) -> Text:
        """Return the form name. Must be implemented by subclasses."""
        pass
    
    def get_utterance(self, utterance_index: int=1):
        """Get utterance using calling function name"""
        function_name = inspect.currentframe().f_back.f_code.co_name
        self.logger.debug(f"get_utterance called from function: {function_name}")
        return get_utterance_base(self.file_name, function_name, utterance_index, self.language_code)
    
    def get_buttons(self, button_index: int=1) -> list:
        """Get buttons using calling function name"""
        function_name = inspect.currentframe().f_back.f_code.co_name
        return get_buttons_base(self.file_name, function_name, button_index, self.language_code)
    

    # Concrete (shared) methods that subclasses can use
    def _is_skip_requested(self, latest_message: dict) -> Tuple[bool, bool, str]:
        """Check if user wants to skip the current field."""
        if not hasattr(self, 'lang_helper'):
            return False, False, ""
        
        input_text = latest_message.get("text", "").strip()
        intent = latest_message.get("intent", {}).get("name", "")
        
        if intent == "skip":
            return True, False, "skip"
        
        if input_text:
            try:
                results = self.is_skip_instruction(input_text)
                return results
            except Exception as e:
                self.logger.error(f"Error in is_skip_requested: {e} | input_text: {input_text} | intent: {intent} | form_name: {self.name()}")
                return False, False, ""

        return False, False, ""

    def _define_skip_value(self, slot_name: Text, domain: DomainDict) -> Any:
        slot_type = domain.get("slots", {}).get(slot_name, {}).get("type")
        return False if slot_type == "bool" else self.SKIP_VALUE

    def _handle_skip_validation(
        self,
        slot_name: Text,
        tracker: Tracker,
        domain: DomainDict
    ) -> Dict[Text, Any]:
        """
        Handle skip validation response.
        
        Args:
            slot_name: Name of the slot being validated
            tracker: Conversation tracker
            domain: Domain configuration
            
        Returns:
            Dict[Text, Any]: Slot updates
        """
        latest_message = tracker.latest_message
        text = latest_message.get("text", "")
        intent = latest_message.get("intent", {}).get("name", "")
        original_text = tracker.get_slot("skipped_detected_text")
        
        if text == "/affirm_skip" or intent == "skip":
            skip_value = self._define_skip_value(slot_name, domain)
            return {
                slot_name: skip_value,
                "skip_validation_needed": None,
                "skipped_detected_text": None
            }
        else:
            return {
                slot_name: original_text,
                "skip_validation_needed": None,
                "skipped_detected_text": None
            }

    async def _handle_slot_extraction(
        self,
        slot_name: Text,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: DomainDict
    ) -> Dict[Text, Any]:
        """Helper method for slot extraction logic."""
        
        slot_type = domain.get("slots", {}).get(slot_name, {}).get("type")
        if slot_type in ["bool", "category", "categorical"]:
            return await self._handle_boolean_and_category_slot_extraction(slot_name, tracker, dispatcher, domain)

        if tracker.get_slot("requested_slot") == slot_name:
            if tracker.get_slot("skip_validation_needed") == slot_name:
                return self._handle_skip_validation(slot_name, tracker, domain)
                
            latest_message = tracker.latest_message
            message_text = latest_message.get("text", "")
            intent = latest_message.get("intent", {}).get("name", "")

            if intent == "skip":
                return {slot_name: self.SKIP_VALUE}

            if message_text.startswith("/"):
                    return {slot_name: message_text.strip("/").strip()}

            try:
                skip_result = self._is_skip_requested(tracker.latest_message)
                is_skip, needs_validation, matched_word = skip_result
            except Exception as e:
                self.logger.error(f"Error in _handle_slot_extraction: {e} | input_text: {message_text} | intent: {intent} | form_name: {self.name()}")
                is_skip, needs_validation, matched_word = False, False, ""
            
            if is_skip:
                if needs_validation:
                    dispatcher.utter_message(
                        text= self.VALIDATION_SKIP["utterance"][self.language_code].format(matched_word=matched_word),
                        buttons= self.VALIDATION_SKIP["buttons"][self.language_code]
                    )
                    return {
                        "skip_validation_needed": slot_name,
                        "skipped_detected_text": message_text
                    }
                
                slot_type = domain.get("slots", {}).get(slot_name, {}).get("type")
                self.logger.debug(f"Slot extraction: {self.name()} - {slot_name} | skip_value: {self.SKIP_VALUE}")
                return {slot_name: self.SKIP_VALUE}
            
            if message_text:
                self.logger.debug(f"Slot extraction: {self.name()} - {slot_name} | message_text: {message_text}")
                return {slot_name: message_text}
        
        return {}

    async def _handle_boolean_and_category_slot_extraction(
        self,
        slot_name: Text,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """
        Helper method for boolean slot extraction with affirm/deny handling. 
        Updated the function so it works with any category type of slot. 
        This was needed because in some cases, the slot is not a boolean slot.
        The boolean slot extraction is a particular case of the slot extraction.
        
        Args:
            slot_name: Name of the boolean slot to extract
            tracker: Conversation tracker
            dispatcher: Dispatcher for sending messages
            domain: Domain configuration
            
        Returns:
            Dict[Text, Any]: Slot updates
        """
        skip_value = self._define_skip_value(slot_name, domain)
        if tracker.get_slot("requested_slot") == slot_name:
            latest_message = tracker.latest_message
            message_text = latest_message.get("text", "")
            intent = latest_message.get("intent", {}).get("name", "")

            if intent == "skip":
                return {slot_name: skip_value}

            skip_result = self._handle_skip_case(latest_message, slot_name, dispatcher, domain)
            if skip_result:
                return skip_result

            if message_text.startswith("/affirm"):
                self.logger.debug(f"Boolean slot extraction: {self.name()} - {slot_name} | slot_value: True")
                return {slot_name: True}

            if message_text.startswith("/deny"):
                self.logger.debug(f"Boolean_slot_extraction: {self.name()} - {slot_name} | slot_value: False")
                return {slot_name: False}

            if message_text.startswith("/"): #this is for the category type of slot
                return {slot_name: message_text.strip("/").strip()}

            return {slot_name: None} #handle the case where the user enters a not expected value
        return {} #handle the case where the slot is not requested

    def _handle_skip_case(self, latest_message: Dict[Text, Any], slot_name: Text, dispatcher: CollectingDispatcher, domain: DomainDict) -> Dict[Text, Any]:
        skip_value = self._define_skip_value(slot_name, domain)
        try:
            is_skip, needs_validation, matched_word = self._is_skip_requested(latest_message)
        except Exception as e:
            is_skip, needs_validation, matched_word = False, False, ""

        if is_skip:
            if needs_validation:
                dispatcher.utter_message(
                    text= self.VALIDATION_SKIP["utterance"][self.language_code].format(matched_word=matched_word),
                    buttons= self.VALIDATION_SKIP["buttons"][self.language_code]
                )
                return {
                    "skip_validation_needed": slot_name,
                    "skipped_detected_text": matched_word
                }
            return {slot_name: skip_value}
        else:
            return {}

    def base_validate_phone(self, slot_value: Any, dispatcher: CollectingDispatcher) -> Dict[Text, Any]:
                
        self.logger.info(f"{self.name()} - Validating phone: {slot_value}")
        
        # Handle skip request
        if self.DEFAULT_VALUES['SKIP_VALUE'] in slot_value:
            self.logger.info(f"{self.name()} - Phone collection skipped")
            result = {"complainant_phone": self.DEFAULT_VALUES['SKIP_VALUE']}
            return result
        
        # Handle slash commands (invalid)
        if slot_value.startswith("/"):
            self.logger.debug(f"{self.name()} - Invalid phone (slash command)")
            result = {"complainant_phone": None}
            return result
        
        # Validate phone number format
        if not self.helpers.is_valid_phone(slot_value):
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            self.logger.info(f"{self.name()} - Invalid phone format: {slot_value}")
            result = {"complainant_phone": None,
            "complainant_phone_valid": False}
            return result
        
        # Check for Philippine phone (special case for testing)
        if self.helpers.is_philippine_phone(slot_value):
            result = {
                "complainant_phone": self.helpers.is_philippine_phone(slot_value),
                "complainant_phone_valid": True
            }
            dispatcher.utter_message(text="You entered a PH number for validation.")
            self.logger.info(f"{self.name()} - Philippine phone detected")
        else:
            # Standardize Nepal phone number
            result = {
                "complainant_phone": self.helpers.standardize_phone(self.language_code, slot_value),
                "complainant_phone_valid": True
            }
            self.logger.info(f"{self.name()} - Phone validated and standardized")

        return result

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
# ============================================
# Exports
# ============================================
__all__ = [
    'BaseAction',
    'BaseFormValidationAction'
]
