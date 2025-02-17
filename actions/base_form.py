from rasa_sdk.forms import FormValidationAction
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from typing import Dict, Text, Any, Tuple, List, Callable
from rapidfuzz import fuzz
import re

class LanguageHelper:
    """Helper class for language detection and skip word matching."""

    def __init__(self):
        """Initialize language patterns and skip words for different languages."""
        self.skip_words = {
            'en': ['skip', 'pass', 'next', 'skip it', 'pass this'],
            'ne': [
                'छोड्नुहोस्', 'छोड', 'अर्को', 
                'छोडी दिनुस', 'छोडिदिनुस',
                'छोड्ने', 'छोड्दिनु', 
                'पछि', 'पछाडी जाऊ',
                'स्किप', 'पास', 'नेक्स्ट',
                'यसलाई छोड्नुहोस्',
                'यो चाहिएन'
            ],
            'hi': ['छोड़ें', 'छोड़ दो', 'अगला', 'आगे बढ़ें']
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
        """
        Check if text is a skip instruction.
        
        Args:
            text: Input text to analyze
            
        Returns:
            Tuple[bool, bool]: (is_skip, needs_validation, matched_word)
        """
        try:
            # Detect language
            lang = self.detect_language(input_text)
            
            # Get skip words for detected language
            skip_words = self.skip_words.get(lang, self.skip_words['en'])
            
            # Get fuzzy match results
            score, best_match = self._get_fuzzy_match_score(input_text, skip_words)
            if score >= 98:
                return True, False, best_match
            
            if score >= 60:
                return True, True, best_match
            return False, False, ""
            
        except Exception as e:
            print(f"Error in skip detection: {e}")
            return False, False, ""

class BaseFormValidationAction(FormValidationAction):
    """Base class for form validation with skip handling and language detection."""

    def __init__(self):
        """Initialize the base form validation action with language helper."""
        self.lang_helper = LanguageHelper()

    def _is_skip_requested(self, latest_message: dict) -> Tuple[bool, bool, str]:
        """
        Check if user wants to skip the current field.
        
        Args:
            latest_message: Latest message from the tracker
            
        Returns:
            Tuple[bool, bool, str]: (is_skip, needs_validation, matched_word)
        """
        
        text = latest_message.get("text", "")
        text = text.strip() if text else None  
        intent = latest_message.get("intent", {}).get("name", "")
        if intent == "skip":
            return True, False, ""
        return self.lang_helper.is_skip_instruction(text)

    def _handle_skip_validation(
        self,
        slot_name: Text,
        tracker: Tracker,
        domain: DomainDict,
        skip_value: Any = None
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
                skip_value = False if slot_type == "bool" else "slot_skipped"
            
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
        skip_value: Any = None
    ) -> Dict[Text, Any]:
        """
        Helper method for slot extraction logic.
        
        Args:
            slot_name: Name of the slot to extract
            tracker: Conversation tracker
            dispatcher: Dispatcher for sending messages
            domain: Domain configuration
            skip_value: Value to use when skipping
            
        Returns:
            Dict[Text, Any]: Slot updates
        """
        if tracker.get_slot("requested_slot") == slot_name:
            # Check if we're in skip validation mode
            if tracker.get_slot("skip_validation_needed") == slot_name:
                return self._handle_skip_validation(slot_name, tracker, domain, skip_value)

            # Normal slot extraction
            latest_message = tracker.latest_message
            text = latest_message.get("text", "")
            
            is_skip, needs_validation, matched_word = self._is_skip_requested(latest_message)
            
            if is_skip:
                if needs_validation:
                    # Store original text and request validation
                    dispatcher.utter_message(
                        text=f"Did you want to skip this field? I matched '{matched_word}'",
                        buttons=[
                            {"title": "Yes, skip it", "payload": "/affirm_skip"},
                            {"title": "No, let me enter a value", "payload": "/deny_skip"}
                        ]
                    )
                    return {
                        "skip_validation_needed": slot_name,
                        "skipped_detected_text": text
                    }
                
                # Direct skip (high confidence match)
                if skip_value is None:
                    slot_type = domain.get("slots", {}).get(slot_name, {}).get("type")
                    skip_value = False if slot_type == "bool" else "slot_skipped"
                return {slot_name: skip_value}
                
            return {slot_name: text}
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
            text = latest_message.get("text", "")
            intent = latest_message.get("intent", {}).get("name", "")

            # Check if we're in skip validation mode
            if tracker.get_slot("skip_validation_needed") == slot_name:
                return self._handle_skip_validation(slot_name, tracker, domain, skip_value)

            # Check for skip using the updated method
            is_skip, needs_validation, matched_word = self._is_skip_requested(latest_message)
            if is_skip:
                if needs_validation:
                    dispatcher.utter_message(
                        text=f"Did you want to skip this field? I matched '{matched_word}'",
                        buttons=[
                            {"title": "Yes, skip it", "payload": "/affirm_skip"},
                            {"title": "No, let me enter a value", "payload": "/deny_skip"}
                        ]
                    )
                    return {
                        "skip_validation_needed": slot_name,
                        "skipped_detected_text": text
                    }
                return {slot_name: skip_value}

            # Handle affirmative responses
            if text.startswith("/affirm") or intent == "affirm":
                if custom_affirm_action:
                    return await custom_affirm_action(dispatcher)
                return {slot_name: True}

            # Handle negative responses
            # Handle negative responses
            if text.startswith("/deny") or intent == "deny":
                return {slot_name: False}

        return {}

    def _validate_string_length(self, text: str, min_length: int = 2) -> bool:
        """
        Validate string length is above minimum requirement.
        
        Args:
            text: String to validate
            min_length: Minimum required length (default: 2)
            
        Returns:
            bool: True if string length is valid, False otherwise
        """
        if not text or not isinstance(text, str):
            return False
        
        # Remove whitespace and check length
        cleaned_text = text.strip()
        return len(cleaned_text) > min_length
