from abc import ABC, abstractmethod
from rasa_sdk.forms import FormValidationAction
from rasa_sdk import Tracker, Action
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from typing import Dict, Text, Any, Tuple, List, Callable
from rapidfuzz import fuzz
import re
import traceback
from .utterance_mapping_rasa import get_utterance_base, get_buttons_base, SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS, UTTERANCE_MAPPING
from .mapping_buttons import VALIDATION_SKIP, BUTTON_SKIP, BUTTON_AFFIRM, BUTTON_DENY
from backend.shared_functions.helpers_repo import helpers_repo
from backend.services.messaging import Messaging
from backend.config.constants import DEFAULT_VALUES, TASK_STATUS, GRIEVANCE_CLASSIFICATION_STATUS, GRIEVANCE_STATUS, LLM_CLASSIFICATION
from backend.services.database_services.postgres_services import db_manager
import inspect
import logging

DEFAULT_LANGUAGE_CODE = DEFAULT_VALUES['DEFAULT_LANGUAGE_CODE']
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
        self.SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS = SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS
        self.SKIP_VALUE = SKIP_VALUE
        self.VALIDATION_SKIP = VALIDATION_SKIP
        self.DEFAULT_LANGUAGE_CODE = DEFAULT_LANGUAGE_CODE
        self.DEFAULT_PROVINCE = DEFAULT_VALUES["DEFAULT_PROVINCE"]
        self.DEFAULT_DISTRICT = DEFAULT_VALUES["DEFAULT_DISTRICT"]
        self.DEFAULT_OFFICE = DEFAULT_VALUES["DEFAULT_OFFICE"]
        self.BUTTON_SKIP = BUTTON_SKIP
        self.BUTTON_AFFIRM = BUTTON_AFFIRM
        self.BUTTON_DENY = BUTTON_DENY
        self.DEFAULT_VALUES = DEFAULT_VALUES
        self.TASK_STATUS = TASK_STATUS
        self.GRIEVANCE_CLASSIFICATION_STATUS = GRIEVANCE_CLASSIFICATION_STATUS
        self.GRIEVANCE_STATUS = GRIEVANCE_STATUS
        self.NOT_PROVIDED = self.DEFAULT_VALUES["NOT_PROVIDED"]
        self.LLM_CLASSIFICATION = LLM_CLASSIFICATION
        
    @abstractmethod
    def name(self) -> Text:
        """Return the action name. Must be implemented by subclasses.
        
        Returns:
            Text: The name of the action
        """
        pass

    def _update_language_code_and_location_info(self, tracker: Tracker) -> None:
        """Update the language code from tracker for use in validation methods."""
        if not hasattr(self, 'language_code'):
            self.language_code = tracker.get_slot("language_code") or self.DEFAULT_LANGUAGE_CODE
        if not hasattr(self, 'province'):
            self.province = tracker.get_slot("complainant_province") or self.DEFAULT_PROVINCE
        if not hasattr(self, 'district'):
            self.district = tracker.get_slot("complainant_district") or self.DEFAULT_DISTRICT
        if not hasattr(self, 'office'):
            self.office = tracker.get_slot("complainant_office") or self.DEFAULT_OFFICE

    def _initialize_language_and_helpers(self, tracker: Tracker) -> None:
        """Initialize language code and update all helper services."""
        self._update_language_code_and_location_info(tracker)
        if not hasattr(self, 'keyword_detector'):
            self.keyword_detector = self.helpers.keyword_detector
        else:
            if not hasattr(self.keyword_detector, 'language_code'):
                self.keyword_detector._initialize_constants(self.language_code)
            if self.keyword_detector.language_code != self.language_code:
                self.keyword_detector._initialize_constants(self.language_code)

        if not hasattr(self, 'location_validator'):
            self.location_validator = self.helpers.location_validator
        else:
            if not hasattr(self.location_validator, 'language_code'):
                self.location_validator._initialize_constants(self.language_code)
            if self.location_validator.language_code != self.language_code:
                self.location_validator._initialize_constants(self.language_code)

    def detect_sensitive_content(self, dispatcher: CollectingDispatcher, slot_value: str) -> Dict[Text, Any]:
        """Check for sensitive content using keyword detection"""
        detection_result = self.helpers.detect_sensitive_content(slot_value, self.language_code)
        #handle the case where sensitive content is detected
        if detection_result.get("detected") and detection_result.get("action_required"):
            self.logger.info(f"🚨 SENSITIVE CONTENT DETECTED: {detection_result.get('category')} - {detection_result.get('level')}")
            self.logger.info(f"Confidence: {detection_result.get('confidence')}")
            self.logger.info(f"Message: {detection_result.get('message')}")
            
            return {
                "sensitive_issues_detected": True,
                "sensitive_issues_category": detection_result.get('category'),
                "sensitive_issues_level": detection_result.get('level'),
                "sensitive_issues_message": detection_result.get('message'),
                "sensitive_issues_confidence": detection_result.get('confidence')
            }
        return {}

    def dispatch_sensitive_content_utterances_and_buttons(self, dispatcher: CollectingDispatcher) -> None:
        for i in range(1, len(self.SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS['utterances']) + 1):
            dispatcher.utter_message(
                text=self.SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS['utterances'][i][self.language_code]
            )
        buttons = self.SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS['buttons'][1][self.language_code]
        dispatcher.utter_message(
            buttons=buttons
        )

    def get_utterance(self, utterance_index: int=1):
        return get_utterance_base(self.file_name, self.name(), utterance_index, self.language_code)
    
    def get_buttons(self, button_index: int=1):
        return get_buttons_base(self.file_name, self.name(), button_index, self.language_code)
            
    def is_valid_email(self, email: str) -> bool:
        """Check if the provided string is a valid email address."""
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

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


class BaseFormValidationAction(FormValidationAction, BaseAction, ABC):
    """Abstract base class for form validation with skip handling and language detection.
    
    This class defines the interface and common functionality that all form validation
    actions must implement.
    """
    message_display_list_cat = False

    def __init__(self):
        """Initialize shared resources."""
        FormValidationAction.__init__(self)
        BaseAction.__init__(self)


    @abstractmethod
    def name(self) -> Text:
        """Return the form name. Must be implemented by subclasses.
        
        Returns:
            Text: The name of the form validation action
        """
        pass

    def get_utterance(self, utterance_index: int=1):
        function_name = inspect.currentframe().f_back.f_code.co_name
        self.logger.debug(f"get_utterance called from function: {function_name}")
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

    def check_form_function_name(self, form_name: str, function_name: str) -> bool:
        try:
            UTTERANCE_MAPPING[form_name][function_name]
            self.logger.debug(f"check_form_function_name: form_name: {form_name} | function_name: {function_name}")
            self.logger.debug(f"UTTERANCE_MAPPING {form_name}: {UTTERANCE_MAPPING[form_name]}")
            self.logger.debug(f"UTTERANCE_MAPPING {form_name}[{function_name}]: {UTTERANCE_MAPPING[form_name][function_name]}")
        except Exception as e:
            self.logger.error(f"Error in check_form_function_name: {e} | form_name: {form_name} | function_name: {function_name}")

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

