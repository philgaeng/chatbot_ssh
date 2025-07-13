from abc import ABC, abstractmethod
from rasa_sdk.forms import FormValidationAction
from rasa_sdk import Tracker, Action
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from typing import Dict, Text, Any, Tuple, List, Callable
from rapidfuzz import fuzz
import re
import traceback
from .utterance_mapping_rasa import get_utterance_base, get_buttons_base
from .mapping_buttons import VALIDATION_SKIP
from backend.shared_functions.helpers_repo import helpers_repo
from backend.services.messaging import Messaging
from backend.config.constants import DEFAULT_VALUES
from backend.services.database_services.postgres_services import db_manager
import inspect
import logging

SKIP_VALUE = DEFAULT_VALUES['SKIP_VALUE']

class LanguageHelper:
    """Helper class for language detection and skip word matching."""

    def __init__(self):
        """Initialize language patterns and skip words for different languages."""
        self.skip_words = {
            'en': {'keywords': ['skip', 'pass', 'next', 'skip it', 'pass this'],
                   'ignore_list': ['access'],
                   'fuzzy_threshold_1': 98,
                   'fuzzy_threshold_2': 75},
            
            'ne': {'keywords': [
                'छोड्नुहोस्', 'छोड', 'अर्को', 
                'छोडी दिनुस', 'छोडिदिनुस',
                'छोड्ने', 'छोड्दिनु', 
                'पछि', 'पछाडी जाऊ',
                'स्किप', 'पास', 'नेक्स्ट',
                'यसलाई छोड्नुहोस्',
                'यो चाहिएन'
            ], 'fuzzy_threshold_1': 98,
                   'fuzzy_threshold_2': 75},
            'hi': {'keywords': ['छोड़ें', 'छोड़ दो', 'अगला', 'आगे बढ़ें'],
                   'fuzzy_threshold_1': 98,
                   'fuzzy_threshold_2': 75}
        }
        
        # Compile regex patterns for each language
        self.patterns = {
            'ne': re.compile(r'[\u0900-\u097F]'),  # Devanagari Unicode range
            'en': re.compile(r'[a-zA-Z]')
        }
    
    def detect_language(self, text: str) -> str:
        """
        Detect the language of input text based on character patterns.
        
        Args:
            text: Input text to analyze
            
        Returns:
            str: Detected language code ('en', 'ne', etc.)
        """
        
        if not text:
            return 'en'
        text = text.strip()
        counts = {
            lang: len(pattern.findall(text))
            for lang, pattern in self.patterns.items()
        }
        
        if not counts or max(counts.values()) == 0:
            return 'en'
        return max(counts.items(), key=lambda x: x[1])[0]

    def _get_fuzzy_match_score(self, text: str, target_words: List[str]) -> Tuple[bool, float, str]:
        """
        Get the best fuzzy match score and matched word.
        
        Args:
            text: Input text to match
            target_words: List of words to match against
            
        Returns:
            Tuple[bool, float, str]: (needs_validation, score, matched_word)
        """
        text = text.lower().strip() if text else None
        best_score = 0
        best_match = ""
        
        for word in target_words:
            score = fuzz.ratio(text, word.lower())
            if score > best_score:
                best_score = score

        return best_score, best_match

    def is_skip_instruction(self, input_text: str) -> Tuple[bool, bool, str]:
        """Check if text is a skip instruction."""
        try:
            if input_text.startswith("/"):
                return False, False, ""
            
            input_text = input_text.lower().strip()
            # Detect language
            lang = self.detect_language(input_text)
            
            # Get skip words for detected language
            skip_words = self.skip_words.get(lang, self.skip_words['en']).get('keywords')
            fuzzy_threshold_1 = self.skip_words.get(lang, self.skip_words['en']).get('fuzzy_threshold_1')
            fuzzy_threshold_2 = self.skip_words.get(lang, self.skip_words['en']).get('fuzzy_threshold_2')
            ignore_words = self.skip_words.get(lang, self.skip_words['en']).get('ignore_list')
            
            # Get the best fuzzy match score and matched word
            best_score = 0
            best_match = ""
            for input_word in input_text.split():
                if input_word not in ignore_words:
                    score, match = self._get_fuzzy_match_score(input_word, skip_words)
                    if score > best_score:
                        best_score = score
                        best_match = input_word
            
            if best_score >= fuzzy_threshold_1:
                result = (True, False, best_match)
                return result
            
            if best_score >= fuzzy_threshold_2:
                result = (True, True, best_match)
                return result
            
            result = (False, False, "")
            return result
            
        except Exception as e:
            #print(f"Error in skip detection: {e} ---- is_skip_instruction")
            #print(f"Traceback: {traceback.format_exc()}")
            return False, False, ""
        
class BaseAction(Action, ABC):
    """Abstract base class for all actions.
    
    This class provides common functionality for all actions, including language detection
    and standard logging patterns.
    """
    def __init__(self):
        super().__init__()
        self.lang_helper = LanguageHelper()
        self.logger = logging.getLogger(__name__)
        self.file_name = self.__class__.__module__.split(".")[-1]
        self.helpers = helpers_repo
        self.messaging = Messaging()
        self.db_manager = db_manager
        # Remove this line: self.language_code = self.get_language_code(tracker)
        # The language code should be retrieved from the tracker within methods where the tracker is available,
        # not in __init__, since tracker is not available at initialization.
        
    @abstractmethod
    def name(self) -> Text:
        """Return the action name. Must be implemented by subclasses.
        
        Returns:
            Text: The name of the action
        """
        pass

    def _update_language_code(self, tracker: Tracker) -> None:
        """Update the language code from tracker for use in validation methods."""
        if not hasattr(self, 'language_code'):
            self.language_code = self.get_language_code(tracker)

    def _initialize_language_and_helpers(self, tracker: Tracker) -> None:
        """Initialize language code and update all helper services."""
        self._update_language_code(tracker)
        if self.helpers.keyword_detector.language_code != self.language_code:
            self.helpers.init_language(self.language_code)
        if self.helpers.location_validator.language_code != self.language_code:
            self.helpers.init_language(self.language_code)

    def get_utterance(self, utterance_index: int) -> str:
        
        return get_utterance_base(self.file_name, self.name(), utterance_index, self.language_code)
    
    def get_buttons(self, button_index: int) -> list:
        return get_buttons_base(self.file_name, self.name(), button_index, self.language_code)
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Standard run method with automatic logging.
        Subclasses should override execute_action() instead of run().
        """
        self._initialize_language_and_helpers(tracker)
        action_detailed_name = self.file_name + "-" + self.name()
        #I want to get the name of the file where the action is defined
        
        self.session_id = tracker.session_id
        
        # Log action start
        self.logger.debug(f"Action started: {action_detailed_name} | Session: {self.session_id}")
        
        try:
            # Execute the actual action logic
            result = self.execute_action(dispatcher, tracker, domain)
            
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


class BaseFormValidationAction(FormValidationAction, ABC):
    """Abstract base class for form validation with skip handling and language detection.
    
    This class defines the interface and common functionality that all form validation
    actions must implement.
    """
    message_display_list_cat = False

    def __init__(self):
        """Initialize shared resources."""
        super().__init__()  # Call parent's __init__
        self.lang_helper = LanguageHelper()
        self.helpers = helpers_repo

    @abstractmethod
    def name(self) -> Text:
        """Return the form name. Must be implemented by subclasses.
        
        Returns:
            Text: The name of the form validation action
        """
        pass

    def _update_language_code(self, tracker: Tracker) -> None:
        """Update the language code from tracker for use in validation methods."""
        if not hasattr(self, 'language_code'):
            self.language_code = self.get_language_code(tracker)

    def get_utterance(self, utterance_index: int=1) -> str:
        function_name = inspect.currentframe().f_back.f_code.co_name
        return get_utterance_base(self.file_name, function_name, utterance_index, self.language_code)
    
    def get_buttons(self, button_index: int=1) -> list:
        function_name = inspect.currentframe().f_back.f_code.co_name
        return get_buttons_base(self.file_name, function_name, button_index, self.language_code)

    # Concrete (shared) methods that subclasses can use
    def _is_skip_requested(self, latest_message: dict) -> Tuple[bool, bool, str]:
        """Check if user wants to skip the current field."""
        if not hasattr(self, 'lang_helper'):
            #print("ERROR: lang_helper not initialized!")
            return False, False, ""
        
        input_text = latest_message.get("text", "").strip()
        intent = latest_message.get("intent", {}).get("name", "")
        
        if intent == "skip":
            #print("Skip detected through intent")
            return True, False, "skip"
        
        if input_text:
            try:
                results = self.lang_helper.is_skip_instruction(input_text)
                return results
            except Exception as e:
                self.logger.error(f"Error in is_skip_requested: {e} | input_text: {input_text} | intent: {intent} | form_name: {self.name()}")
                return False, False, ""

        return False, False, ""

    # Protected methods that subclasses might want to override
    def _validate_string_length(self, text: str, min_length: int = 2) -> bool:
        """Validate string length. Can be overridden by subclasses if needed.
        
        Args:
            text: The text to validate
            min_length: Minimum required length
            
        Returns:
            bool: True if length is valid, False otherwise
        """
        if not text or not isinstance(text, str):
            return False
        return len(text.strip()) > min_length

    def _handle_skip_validation(
        self,
        slot_name: Text,
        tracker: Tracker,
        domain: DomainDict,
        skip_value: Any = SKIP_VALUE
    ) -> Dict[Text, Any]:
        """
        Handle skip validation response.
        
        Args:
            slot_name: Name of the slot being validated
            tracker: Conversation tracker
            domain: Domain configuration
            skip_value: Value to use when skipping
            
        Returns:
            Dict[Text, Any]: Slot updates
        """
        latest_message = tracker.latest_message
        text = latest_message.get("text", "")
        intent = latest_message.get("intent", {}).get("name", "")
        original_text = tracker.get_slot("skipped_detected_text")
        
        # Determine if user confirmed skip
        if text == "/affirm_skip" or intent == "skip":
            # User confirmed skip - use provided or default skip value
            if skip_value is None:
                slot_type = domain.get("slots", {}).get(slot_name, {}).get("type")
                skip_value = False if slot_type == "bool" else SKIP_VALUE
            
            return {
                slot_name: skip_value,
                "skip_validation_needed": None,
                "skipped_detected_text": None
            }
        else:
            # User denied skip - use original text
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
        domain: DomainDict,
        skip_value: Any = None,
        custom_action: Callable = None
    ) -> Dict[Text, Any]:
        """Helper method for slot extraction logic."""
        
        
        if tracker.get_slot("requested_slot") == slot_name:
            # Check if we're in skip validation mode
            if tracker.get_slot("skip_validation_needed") == slot_name:
                return self._handle_skip_validation(slot_name, tracker, domain, skip_value)
                
            latest_message = tracker.latest_message
            message_text = latest_message.get("text", "")
            intent = latest_message.get("intent", {}).get("name", "")

            if intent == "skip":
                return {slot_name: SKIP_VALUE}
            
            # Execute custom action if provided
            if custom_action:
                await custom_action(dispatcher, tracker, domain)

            try:
                skip_result = self._is_skip_requested(tracker.latest_message)
                is_skip, needs_validation, matched_word = skip_result
            except Exception as e:
                self.logger.error(f"Error in _handle_slot_extraction: {e} | input_text: {message_text} | intent: {intent} | form_name: {self.name()}")
                is_skip, needs_validation, matched_word = False, False, ""
            
            if is_skip:
                #print(f"---------- SLOT EXTRACTION END ----------")
                if needs_validation:
                    # Store original text and request validation
                    dispatcher.utter_message(
                        text= VALIDATION_SKIP["utterance"][self.language_code].format(matched_word=matched_word),
                        buttons= VALIDATION_SKIP["buttons"][self.language_code]
                    )
                    return {
                        "skip_validation_needed": slot_name,
                        "skipped_detected_text": message_text
                    }
                
                # Direct skip (high confidence match)
                slot_type = domain.get("slots", {}).get(slot_name, {}).get("type")
                skip_value = False if slot_type == "bool" else SKIP_VALUE
                return {slot_name: skip_value}
            self.logger.debug(f"Slot extraction: {self.name()} - {slot_name} | skip_value: {skip_value}")
            if message_text:
                self.logger.debug(f"Slot extraction: {self.name()} - {slot_name} | message_text: {message_text}")
                return {slot_name: message_text}
        
        return {}

    async def _handle_boolean_slot_extraction(
        self,
        slot_name: Text,
        tracker: Tracker,
        dispatcher: CollectingDispatcher,
        domain: DomainDict,
        skip_value: bool = False,
        custom_affirm_action: Callable = None
    ) -> Dict[Text, Any]:
        """
        Helper method for boolean slot extraction with affirm/deny handling.
        
        Args:
            slot_name: Name of the boolean slot to extract
            tracker: Conversation tracker
            dispatcher: Dispatcher for sending messages
            domain: Domain configuration
            skip_value: Value to use when skipping (default: False)
            custom_affirm_action: Optional callback for custom affirm handling
            
        Returns:
            Dict[Text, Any]: Slot updates
        """
        if tracker.get_slot("requested_slot") == slot_name:
            latest_message = tracker.latest_message
            message_text = latest_message.get("text", "")
            intent = latest_message.get("intent", {}).get("name", "")

            if intent == "skip":
                return {slot_name: SKIP_VALUE}

            # Check if we're in skip validation mode
            if tracker.get_slot("skip_validation_needed") == slot_name:
                return self._handle_skip_validation(slot_name, tracker, domain, skip_value)

            # Check for skip using the updated method
            try:
                is_skip, needs_validation, matched_word = self._is_skip_requested(latest_message)

            except Exception as e:

                is_skip, needs_validation, matched_word = False, False, ""
            if is_skip:
                if needs_validation:
                    dispatcher.utter_message(
                        text= VALIDATION_SKIP["utterance"][self.language_code].format(matched_word=matched_word),
                        buttons= VALIDATION_SKIP["buttons"][self.language_code]
                    )
                    return {
                        "skip_validation_needed": slot_name,
                        "skipped_detected_text": message_text
                    }
                return {slot_name: skip_value}

            # Handle affirmative responses
            if message_text.startswith("/affirm") or intent == "affirm":
                if custom_affirm_action:
                    return await custom_affirm_action(dispatcher)
                self.logger.debug(f"Boolean slot extraction: {self.name()} - {slot_name} | slot_value: True")
                return {slot_name: True}

            # Handle negative responses
            if message_text.startswith("/deny") or intent == "deny":
                self.logger.debug(f"Boolean_slot_extraction: {self.name()} - {slot_name} | slot_value: False")
                return {slot_name: False}

        return {}

