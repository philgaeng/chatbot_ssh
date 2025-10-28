from abc import ABC, abstractmethod
from rasa_sdk.forms import FormValidationAction
from rasa_sdk import Tracker, Action
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from typing import Dict, Text, Any, Tuple, List, Callable
from rapidfuzz import fuzz
import re
import traceback
import json
import inspect
import logging
from actions.utils.utterance_mapping_rasa import get_utterance_base, get_buttons_base, SENSITIVE_ISSUES_UTTERANCES_AND_BUTTONS, UTTERANCE_MAPPING
from actions.utils.mapping_buttons import VALIDATION_SKIP, BUTTON_SKIP, BUTTON_AFFIRM, BUTTON_DENY
from backend.shared_functions.helpers_repo import helpers_repo
from backend.services.messaging import Messaging
from backend.config.constants import DEFAULT_VALUES, LLM_CLASSIFICATION, USER_FIELDS, GRIEVANCE_FIELDS, CLASSIFICATION_DATA, EMAIL_TEMPLATES, DIC_SMS_TEMPLATES, ADMIN_EMAILS
from backend.config.database_constants import TASK_STATUS, GRIEVANCE_CLASSIFICATION_STATUS, GRIEVANCE_STATUS, GRIEVANCE_STATUS_DICT
from backend.services.database_services.postgres_services import db_manager

DEFAULT_LANGUAGE_CODE = DEFAULT_VALUES['DEFAULT_LANGUAGE_CODE']
SKIP_VALUE = DEFAULT_VALUES['SKIP_VALUE']

    
class ActionCommonMixin(Action, ABC):
    """Abstract base class for all actions.
    
    This class provides common functionality for all actions, including language detection
    and standard logging patterns.
    """
    def __init__(self):
        super().__init__()
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
        self.helpers_repo = helpers_repo  # Add helpers_repo as instance attribute
        self.NOT_PROVIDED = self.DEFAULT_VALUES["NOT_PROVIDED"]
        self.LLM_CLASSIFICATION = LLM_CLASSIFICATION
        
    @abstractmethod
    def name(self) -> Text:
        """Return the action name. Must be implemented by subclasses.
        
        Returns:
            Text: The name of the action
        """
        pass

class LanguageHelpersMixin(ActionCommonMixin):
    def __init__(self):
        super().__init__()
        """Initialize language patterns and skip words for different languages."""
    SKIP_WORDS_DIC = {
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
    PATTERNS = {
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
            for lang, pattern in self.PATTERNS.items()
        }
        
        if not counts or max(counts.values()) == 0:
            return 'en'
        return max(counts.items(), key=lambda x: x[1])[0]

    def _get_fuzzy_match_score(self, text: str, target_words: List[str]) -> Tuple[float, str]:
        """
        Get the best fuzzy match score and matched word.
        
        Args:
            text: Input text to match
            target_words: List of words to match against
            
        Returns:
            Tuple[float, str]: (score, matched_word)
        """
        text = text.lower().strip() if text else ""
        best_score = 0.0
        best_match = ""
        
        for word in target_words:
            score = fuzz.ratio(text, word.lower())
            if score > best_score:
                best_score = score
                best_match = word

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
            skip_words = self.SKIP_WORDS_DIC.get(lang, self.SKIP_WORDS_DIC['en']).get('keywords')
            fuzzy_threshold_1 = self.SKIP_WORDS_DIC.get(lang, self.SKIP_WORDS_DIC['en']).get('fuzzy_threshold_1')
            fuzzy_threshold_2 = self.SKIP_WORDS_DIC.get(lang, self.SKIP_WORDS_DIC['en']).get('fuzzy_threshold_2')
            ignore_words = self.SKIP_WORDS_DIC.get(lang, self.SKIP_WORDS_DIC['en']).get('ignore_list', [])
            
            # Get the best fuzzy match score and matched word
            best_score = 0
            best_match = ""
            for input_word in input_text.split():
                if not ignore_words or input_word not in ignore_words:
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
    
    def _get_categories_in_local_language(self, categories: List[str]) -> List[str]:
        """Get the categories in the local language."""
        if self.language_code == "en":
            return categories
        categories_local = []
        key_local_1 = f"generic_grievance_name_{self.language_code}"
        key_local_2 = f"classification_{self.language_code}"
        for category in categories:
            category = category.split(" - ")[1].strip()
            category_data = CLASSIFICATION_DATA.get(category, {})
            category_name_local_1 = category_data.get(key_local_1, category)
            category_name_local_2 = category_data.get(key_local_2, category)
            category_name_local = f"{category_name_local_2} - {category_name_local_1}"
            categories_local.append(category_name_local)
        return categories_local

    def _get_categories_in_english(self, categories: List[str]) -> List[str]:
        """Get the categories in the English language."""
        if self.language_code == "en":
            return categories
        
        key_local_1 = f"classification_{self.language_code}"
        key_local_2 = f"generic_grievance_name_{self.language_code}"
    
        categories_en = []
        for category in categories:
            # Find the matching item in CLASSIFICATION_DATA
            for item in CLASSIFICATION_DATA.values():
                local_classification = item.get(key_local_1, "")
                local_grievance_name = item.get(key_local_2, "")
                local_category = f"{local_classification} - {local_grievance_name}"
                
                if category == local_category:
                    # Found match, get the English version
                    english_classification = item.get('classification', "")
                    english_grievance_name = item.get('generic_grievance_name', "")
                    english_category = f"{english_classification} - {english_grievance_name}"
                    categories_en.append(english_category)
                    break
        
        return categories_en

    def is_valid_email(self, email: str) -> bool:
        """Check if the provided string is a valid email address."""
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def get_status_and_description_str_in_language(self, status: str) -> str:
        """Get the status and description string in the language."""
        return GRIEVANCE_STATUS_DICT[status]["name_" + self.language_code] + " - " + GRIEVANCE_STATUS_DICT[status]["description_" + self.language_code]


class SensitiveContentHelpersMixin(ActionCommonMixin):
    def __init__(self):
        super().__init__()

    def detect_sensitive_content(self, dispatcher: CollectingDispatcher, slot_value: str) -> Dict[Text, Any]:
        """Check for sensitive content using keyword detection"""
        detection_result = self.helpers.detect_sensitive_content(slot_value, self.language_code)
        #handle the case where sensitive content is detected
        if detection_result.get("detected") and detection_result.get("action_required"):
            self.logger.info(f"🚨 SENSITIVE CONTENT DETECTED: {detection_result.get('category')} - {detection_result.get('level')}")
            self.logger.info(f"Confidence: {detection_result.get('confidence')}")
            self.logger.info(f"Message: {detection_result.get('message')}")
            
            return {
                "grievance_sensitive_issue": True,
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

class ActionHelpersMixin(
                        LanguageHelpersMixin,
                        SensitiveContentHelpersMixin):
    def __init__(self):
        super().__init__()
        
    def get_utterance(self, utterance_index: int=1):
        return get_utterance_base(self.file_name, self.name(), utterance_index, self.language_code)
    
    def get_buttons(self, button_index: int=1):
        return get_buttons_base(self.file_name, self.name(), button_index, self.language_code)
        
    
    def check_form_function_name(self, form_name: str, function_name: str) -> bool:
        """Check if the function name is valid for the form. this function is used for debugging only.
        Args:
            form_name: The name of the form
            function_name: The name of the function
        Returns:
            bool: True if the function name is valid, False otherwise
        """
        try:
            UTTERANCE_MAPPING[form_name][function_name]
            self.logger.debug(f"check_form_function_name: form_name: {form_name} | function_name: {function_name}")
            self.logger.debug(f"UTTERANCE_MAPPING {form_name}: {UTTERANCE_MAPPING[form_name]}")
            self.logger.debug(f"UTTERANCE_MAPPING {form_name}[{function_name}]: {UTTERANCE_MAPPING[form_name][function_name]}")
            return True
        except Exception as e:
            self.logger.error(f"Error in check_form_function_name: {e} | form_name: {form_name} | function_name: {function_name}")
            return False
    

    
    def validate_full_name_to_list(self, full_name: str) -> list:
        """Check if the provided string is a valid full name."""
        #we want to fuzzy match the full name with the full name in the database
        full_name = full_name.lower().strip()
        all_full_names = self.db_manager.get_all_complainant_full_names()
        results = self.helpers.match_full_name_list(full_name, all_full_names)
        return results

class ActionFlowHelpersMixin(ActionHelpersMixin):
    def __init__(self):
        super().__init__()
        

    def reset_slots(self, tracker: Tracker, flow: str, output:str = "dict") -> Dict[Text, Any]:
        if flow not in ["status_check", "new_grievance", "otp_submission"]:
            self.logger.error(f"ActionStartStatusCheck - reset_slots - flow: {flow} is not valid")
            raise ValueError(f"ActionStartStatusCheck - reset_slots - flow: {flow} is not valid")
        self.logger.info(f"ActionStartStatusCheck - reset_slots - tracker: {tracker} - flow: {flow}")

        dic_flow_prefix = {
            "status_check": {"prefix" :["status_check"], "avoid_slots": []},
            "new_grievance": {"prefix" :["grievance"], "avoid_slots": ["grievance_id", "complainant_id"]},
            "otp_submission": {"prefix" :["otp"], "avoid_slots": []}
        }
        prefix = dic_flow_prefix["otp_submission"]["prefix"]
        avoid_slots = dic_flow_prefix["otp_submission"]["avoid_slots"]
        if flow != "otp_submission":
            prefix = dic_flow_prefix[flow]["prefix"] + prefix
            avoid_slots = dic_flow_prefix[flow]["avoid_slots"] + avoid_slots
        #select the slots to reset
        slots_to_reset = [slot for slot in tracker.slots if any(prefix in slot for prefix in prefix) and slot not in avoid_slots]
        self.logger.info(f"ActionStartStatusCheck - reset_slots - slots_to_reset: {slots_to_reset}")
        if output == "dict":
            return {slot : None for slot in slots_to_reset}
        elif output == "slot_list":
            return [SlotSet(slot, None) for slot in slots_to_reset]


    def prepare_grievance_text_for_display(self, grievance: Dict, display_only_short: bool = True) -> str:
        key_mapping_language= {
            "grievance_id": {"en": "grievance_id", "ne": "गुनासो ID"},
            "grievance_categories": {"en": "Grievance categories", "ne": "गुनासो श्रेणी"},
            "grievance_status": {"en": "Grievance status", "ne": "गुनासो स्थिति"},
            "grievance_timeline": {"en": "Grievance timeline", "ne": "गुनासो टाइमलाइन"},
        }

        key_mapping_language_long = {
            "grievance_description": {"en": "Grievance description", "ne": "गुनासो विवरण"},
            "grievance_summary": {"en": "Grievance summary", "ne": "गुनासो सारांश"}, 
            "grievance_status_update_date": {"en": "Grievance status update date", "ne": "गुनासो स्थिति अपडेट गरिएको"},"grievance_creation_date": {"en": "Grievance creation date", "ne": "गुनासो सिर्जना गरिएको"},
        }

        if not display_only_short:
            key_mapping_language.update(key_mapping_language_long)
        
        utterance = []
        self.logger.debug(f"prepare_grievance_text_for_display: {grievance}")
        for k in key_mapping_language.keys():
            if k in grievance:
                v = grievance[k]
                denomination = key_mapping_language[k][self.language_code]
                if k == "grievance_status":
                    v = self.get_status_and_description_str_in_language(v)
                if v:
                    utterance.append(f"{denomination}: {v}")
        self.logger.debug(f"prepare_grievance_text_for_display: utterance_list: {utterance}")
        utterance = "\n".join(utterance)
        return utterance

    def collect_grievance_data_from_id(self, grievance_id: str, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        grievances = tracker.get_slot("list_grievance_id")
        if grievances: #access directly from the tracker to avoid extra call to db
            grievance = [g for g in grievances if g.get("grievance_id") == grievance_id]
            self.logger.debug(f"action_ask_status_check_grievance_selected_action: grievance_id: {grievance_id}, grievance: {grievance}")
            grievance = grievance[0] if grievance else None
        else:
            grievance = self.db_manager.get_grievance_by_id(grievance_id) #default case if the slot is not set - call to db
        return grievance if grievance else None

    def validate_grievance_id_format(self, text: Any) -> bool:
        """Validate if the text has a valid grievance ID format (last 6 characters: 2 letters + 4 digits)"""
        if not text:
            return False
        #deal with legacy grievance id format ending by -B or -A
        if text.endswith("-B") or text.endswith("-A"):
            text = text[:-2]
        # Extract only alphanumeric characters
        text = re.sub(r'[^a-zA-Z0-9]', '', text).strip().upper()
        if len(text) < 6:
            return False
        # Check the last 6 characters
        text = text[-6:]
        # Should be 2 letters followed by 4 digits
        if re.match(r'^[A-Z]{2}[A-Z0-9]{4}$', text):
            return True
        return False
    
    def standardize_grievance_id_response(self, text: Any) -> str:
        """Extract and format the last 6 characters as grievance ID format (XX-XXXX)"""
                #deal with legacy grievance id format ending by -B or -A
        self.logger.debug(f"standardize_grievance_id_response: text before standardization: {text}")
        if text.endswith("-B") or text.endswith("-A"):
            text = text[:-2]
        self.logger.debug(f"standardize_grievance_id_response: text after legacy grievance id format handling: {text}")
        text = re.sub(r'[^a-zA-Z0-9]', '', text).strip().upper()
        self.logger.debug(f"standardize_grievance_id_response: text after alphanumeric characters handling: {text}")
        text = text[-6:]  # Keep only the last 6 characters
        return text[:2] + "-" + text[2:]
        
    def fetch_grievance_id_from_slot(self, text: Any) -> str:
        """Fetch full grievance ID from database using last 6 characters"""
        if self.validate_grievance_id_format(text):
            standardized = self.standardize_grievance_id_response(text)
            self.logger.debug(f"fetch_grievance_id_from_slot: standardized: {standardized}")
            return self.db_manager.get_grievance_id_by_last_6_characters(standardized)
        self.logger.debug(f"fetch_grievance_id_from_slot: no grievance id found")
        return False

    def select_grievances_from_full_name_list(self, full_name_matches: List[Tuple[str, float, int]], list_grievances_by_phone: list, dispatcher: CollectingDispatcher) -> List[str]:
        matching_grievance_list = []
        self.logger.debug(f"select_grievances_from_full_name_list: full_name: {full_name_matches}")
        self.logger.debug(f"select_grievances_from_full_name_list: list_grievances_by_phone: {list_grievances_by_phone}")
        matching_grievance_list = [grievance for grievance in list_grievances_by_phone if grievance["complainant_full_name"] in full_name_matches]
        # for grievance in list_grievances_by_phone:
        #     for full_name in full_name_matches:
        #         if self.helpers.match_full_name_word(grievance["complainant_full_name"], full_name[0]):
        #             matching_grievance_list.append(grievance)
        # self.logger.debug(f"select_grievances_from_full_name_list: matching_grievance_list: {matching_grievance_list}")
        if len(matching_grievance_list) == 0:
           return []
        #sort the matching grievances by status and status date
        #first we sort by status, where all the closed cases are at the en d and the rest are at the beginning
        #amongst the rest we sort by status date
        matching_grievance_not_closed = [grievance for grievance in matching_grievance_list if grievance.get("grievance_status") and grievance.get("grievance_status") not in ["CLOSED"]]
        matching_grievance_not_closed.sort(key=lambda x: x["grievance_creation_date"], reverse=True)
        matching_grievance_closed = [grievance for grievance in matching_grievance_list if grievance["grievance_status"] in ["CLOSED"]]
        matching_grievance_closed.sort(key=lambda x: x["grievance_creation_date"], reverse=True)
        return matching_grievance_not_closed + matching_grievance_closed
        
    def match_similar_full_names_in_list(self, list_full_names: list) -> list:
        unique_full_names = []
        remaining_names = list_full_names.copy()
        
        for full_name in list_full_names:
            if full_name not in unique_full_names:
                # Remove current name from remaining names for comparison
                remaining_names = [name for name in remaining_names if name != full_name]
                # Check if the full name is similar to any of the remaining full names
                if len(self.helpers.match_full_name_list(full_name, remaining_names)) == 0:
                    unique_full_names.append(full_name)
        return unique_full_names

    def convert_grievance_datetime_to_string(self, list_grievances: List[Dict[Text, Any]]) -> List[Dict[Text, Any]]:
        # Convert datetime objects to strings for JSON serialization
        serializable_grievances = []
        for grievance in list_grievances:
            serializable_grievance = {}
            for key, value in grievance.items():
                if hasattr(value, 'isoformat'):  # datetime object
                    serializable_grievance[key] = value.isoformat()
                else:
                    serializable_grievance[key] = value
            serializable_grievances.append(serializable_grievance)
        return serializable_grievances

    def extract_unique_full_names_from_list(self, list_grievances: List[Dict[Text, Any]]) -> List[str]:
        result = list(set([grievance["complainant_full_name"] for grievance in list_grievances if grievance["complainant_full_name"] != self.DEFAULT_VALUES["NOT_PROVIDED"]]))
        result.sort(key=lambda x: len(x), reverse=True)
        return result

    def get_next_action_for_form(self, tracker: Tracker) -> str:
        """
        Centralized routing logic for ALL forms.
        Single source of truth - all form transitions defined here.
        
        Dictionary structure:
            story_main -> form -> story_route -> story_step -> action_name
        
        Returns:
            str: Name of next action/form to execute, or "action_listen" if no routing found
        """
        # Get routing context from tracker
        active_loop = tracker.active_loop
        form_name = active_loop.get("name") if active_loop else None
        
        # If no active loop, get the last completed form from latest action
        if not form_name:
            latest_action_name = tracker.latest_action_name
            if latest_action_name and latest_action_name.startswith("form_"):
                form_name = latest_action_name
                self.logger.debug(f"get_next_action_for_form - Using completed form: {form_name}")
        
        story_main = tracker.get_slot("story_main")
        story_route = tracker.get_slot("story_route")  # e.g., "grievance_id" or "complainant_phone"
        story_step = tracker.get_slot("story_step")    # e.g., "request_follow_up"
        
        self.logger.debug(f"get_next_action_for_form - story: {story_main}, form: {form_name}, route: {story_route}, step: {story_step}")
        
        #nested dictionary for the status check next action as it is used in multiple places
        dic_status_check_next_action = {    
            self.SKIP_VALUE: "action_skip_status_check_outro",
            "status_check_modify": "form_status_check_modify",
            "status_check_follow_up": "action_status_check_follow_up"
        }
        # Nested dictionary-based routing (organized by main story first)
        routing_map = {
            "new_grievance": {
                "form_grievance": "form_contact",
                "form_contact": "form_otp",
                "form_otp": "action_submit_grievance"
            },
            "status_check": {
                "form_status_check_1": {
                    "route_status_check_grievance_id": "form_story_step",
                    "route_status_check_phone": "form_otp",
                    self.SKIP_VALUE: "form_status_check_skip"
                },
                "form_status_check_2": "form_story_step",
                "form_otp": {
                    "route_status_check_phone": "form_status_check_2",
                    self.SKIP_VALUE: "form_status_check_skip",
                    "route_status_check_grievance_id": dic_status_check_next_action
                },
                "form_story_step": {
                    self.SKIP_VALUE: "form_status_check_skip",
                    "route_status_check_grievance_id": "form_otp",
                    "route_status_check_phone": dic_status_check_next_action
                },
                "form_status_check_skip": "action_skip_status_check_outro",
                "form_story_step": {"route_status_check_grievance_id": {
                    "status_check_request_follow_up": "action_status_check_request_follow_up",
                    "status_check_modify": "form_status_check_modify"},
                    "route_status_check_phone": {
                    "status_check_request_follow_up": "action_status_check_request_follow_up",
                    "status_check_modify": "form_status_check_modify"}
                }
            }
        }
        
        # Navigate through the nested dictionary: story_main -> form -> story_route -> story_step
        if story_main not in routing_map:
            error_msg = f"No routing found for story_main: '{story_main}'. Available stories: {list(routing_map.keys())}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        next_action = routing_map[story_main]
        
        # Level 2: form_name
        if isinstance(next_action, dict):
            if form_name not in next_action:
                error_msg = f"No routing found for form: '{form_name}' in story: '{story_main}'. Available forms: {list(next_action.keys())}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
            next_action = next_action[form_name]
        
        # Level 3: story_route
        if isinstance(next_action, dict):
            if story_route and story_route in next_action:
                next_action = next_action[story_route]
            elif "default" in next_action:
                self.logger.debug(f"Using default route for story_route: {story_route}")
                next_action = next_action["default"]
            else:
                error_msg = f"No routing found for story_route: '{story_route}' in form: '{form_name}', story: '{story_main}'. Available routes: {list(next_action.keys())}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
        
        # Level 4: story_step
        if isinstance(next_action, dict):
            if story_step and story_step in next_action:
                next_action = next_action[story_step]
            elif "default" in next_action:
                self.logger.debug(f"Using default route for story_step: {story_step}")
                next_action = next_action["default"]
            else:
                error_msg = f"No routing found for story_step: '{story_step}' in route: '{story_route}', form: '{form_name}', story: '{story_main}'. Available steps: {list(next_action.keys())}"
                self.logger.error(error_msg)
                raise ValueError(error_msg)
        
        # Final validation
        if not next_action or not isinstance(next_action, str):
            error_msg = f"Invalid routing result: {next_action} for form: '{form_name}', story: '{story_main}', route: '{story_route}', step: '{story_step}'"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        self.logger.debug(f"get_next_action_for_form - resolved next_action: {next_action}")
        return next_action 

    def _retrieve_and_set_grievances_by_phone(self, tracker: Tracker) -> Dict[Text, Any]:
        """
        Helper function to retrieve grievances by phone and return slot updates.
        This keeps the validation logic clean and readable.
        """
        complainant_phone = tracker.get_slot("complainant_phone")
        
        self.logger.debug(f"{self.name()}: Retrieving grievances for phone: {complainant_phone}")
        
        # Check if phone is skipped or not provided
        if not complainant_phone or complainant_phone == self.DEFAULT_VALUES['SKIP_VALUE']:
            self.logger.debug(f"{self.name()}: Phone skipped or not provided")
            return {
                "status_check_retrieve_grievances": self.SKIP_VALUE,
                "story_route": self.SKIP_VALUE
            }
        
        # Retrieve grievances by phone
        list_grievances_by_phone = self.db_manager.get_grievance_by_complainant_phone(complainant_phone)
        
        self.logger.debug(f"{self.name()}: Found {len(list_grievances_by_phone)} grievances")
        
        if len(list_grievances_by_phone) == 0:
            self.logger.debug(f"{self.name()}: No grievances found for phone")
            return {
                "status_check_retrieve_grievances": True,
                "status_check_complainant_phone_valid": "no_phone_found",
                "list_grievances_by_phone": [],
                "story_route": self.SKIP_VALUE
            }
        
        # Convert datetime to string for all grievances
        list_grievances_by_phone = self.convert_grievance_datetime_to_string(list_grievances_by_phone)
        
        slots_to_set = {
            "status_check_retrieve_grievances": True,
            "list_grievances_by_phone": list_grievances_by_phone,
            "status_check_complainant_phone_valid": True
        }
        
        # If only one grievance, select it directly
        if len(list_grievances_by_phone) == 1:
            grievance_id_selected = list_grievances_by_phone[0]["grievance_id"]
            self.logger.debug(f"{self.name()}: Single grievance found: {grievance_id_selected}")
            slots_to_set["status_check_grievance_id_selected"] = grievance_id_selected
            return slots_to_set
        
        # Multiple grievances - need to check full names
        list_complainant_full_names = self.extract_unique_full_names_from_list(list_grievances_by_phone)
        
        if len(list_complainant_full_names) == 0:
            # All grievances have "Not provided" as name
            self.logger.debug(f"{self.name()}: Multiple grievances, all without names")
            slots_to_set.update({
                "status_check_complainant_full_name": self.DEFAULT_VALUES["NOT_PROVIDED"],
                "list_grievance_id": list_grievances_by_phone
            })
        elif len(list_complainant_full_names) == 1:
            # All grievances have the same name
            self.logger.debug(f"{self.name()}: Multiple grievances, same name: {list_complainant_full_names[0]}")
            slots_to_set.update({
                "status_check_complainant_full_name": list_complainant_full_names[0],
                "list_grievance_id": list_grievances_by_phone
            })
        else:
            # Multiple different names - need to ask user to choose
            self.logger.debug(f"{self.name()}: Multiple grievances, different names: {list_complainant_full_names}")
            slots_to_set["complainant_list_full_names"] = list_complainant_full_names
        
        return slots_to_set



class ActionMessagingHelpersMixin(ActionHelpersMixin):
    def __init__(self):
        super().__init__()
        
    def prepare_recap_email(self, 
                                          to_emails: List[str],
                                          email_data: Dict[str, Any],
                                          body_name: str) -> Tuple[str, str]:
        """Send a recap email to the user."""
        try:
            self.logger.debug(f"_prepare_recap_email called with body_name: {body_name}")
            self.logger.debug(f"_prepare_recap_email email_data keys: {list(email_data.keys())}")
            self.logger.debug(f"_prepare_recap_email email_data: {email_data}")
            
            json_data = json.dumps(email_data, indent=2, ensure_ascii=False)
            
            if email_data.get('grievance_categories') and email_data.get('grievance_categories') != self.NOT_PROVIDED:
                categories_html = ''.join(f'<li>{category}</li>' for category in (email_data['grievance_categories'] or []))
            else:
                self.logger.debug(f"_prepare_recap_email no grievance_categories or it's NOT_PROVIDED")
                categories_html = ""
            # Create email body using template
            self.logger.debug(f"_prepare_recap_email checking EMAIL_TEMPLATES for body_name: {body_name}")
            self.logger.debug(f"_prepare_recap_email available EMAIL_TEMPLATES keys: {list(EMAIL_TEMPLATES.keys())}")
        

            if body_name in EMAIL_TEMPLATES:
                subject = EMAIL_TEMPLATES[body_name][self.language_code]
                body = EMAIL_TEMPLATES[body_name][self.language_code]
            else:
                self.logger.error(f"Unknown body_name: {body_name}")
                return "", ""

            self.logger.debug(f"_prepare_recap_email formatting subject and body")
            #format subject and body
            subject = subject.format(
                grievance_id=email_data.get('grievance_id', '')
            )
            body = body.format(
            complainant_name=email_data.get('complainant_full_name', self.NOT_PROVIDED),
            grievance_description=email_data.get('grievance_description', self.NOT_PROVIDED),
            project=email_data.get('complainant_project', self.NOT_PROVIDED),
            complainant_municipality=email_data.get('complainant_municipality', self.NOT_PROVIDED),
            complainant_village=email_data.get('complainant_village', self.NOT_PROVIDED),
            complainant_address=email_data.get('complainant_address', self.NOT_PROVIDED),
            complainant_phone=email_data.get('complainant_phone', self.NOT_PROVIDED),
            grievance_id=email_data.get('grievance_id', ''),
            complainant_email=email_data.get('complainant_email', self.NOT_PROVIDED),
            grievance_timeline=email_data.get('grievance_timeline', self.NOT_PROVIDED),
            grievance_timestamp=email_data.get('grievance_timestamp', self.NOT_PROVIDED),
            categories_html=categories_html,
            grievance_summary=email_data.get('grievance_summary', self.NOT_PROVIDED)
            )
            
            self.logger.debug(f"_prepare_recap_email successfully prepared email")
            return (body, subject)

            
        except Exception as e:
            self.logger.error(f"Failed to prepare recap email: {e}")
            return "", ""
        
    
    async def send_recap_email(self, to_emails: List[str],
                                                         grievance_data: Dict[str, Any],
                                                         body_name: str
                                                         ) -> None:
        """Prepare and send a recap email according to the body name."""
        #send email to user
        try:    
            body, subject = self.prepare_recap_email(to_emails, 
                                                    grievance_data, 
                                                    body_name)
            
            self.messaging.send_email(to_emails,
                                            subject = subject,
                                            body=body
                                            )       
        except Exception as e:
            self.logger.error(f"Failed to send system notification email: {e}"
            )
            
    async def send_recap_email_to_admin(self, 
                                                   grievance_data: Dict[str, Any],
                                                   body_name: str,
                                                   dispatcher: CollectingDispatcher) -> None:
        """Send a recap email to the admin."""
        try:
            self.logger.debug(f"_send_recap_email_to_admin called with grievance_data keys: {list(grievance_data.keys())}")
            await self.send_recap_email(ADMIN_EMAILS, 
                                                grievance_data, 
                                                body_name = body_name
                                                )
        except Exception as e:
            self.logger.error(f"Failed to send recap email to admin: {e}")
            self.logger.error(f"Admin email error details: {traceback.format_exc()}")


    async def send_recap_email_to_complainant(self, 
                                                         complainant_email: str,
                                                         body_name: str,
                                                         grievance_data: Dict[str, Any],
                                                         dispatcher: CollectingDispatcher) -> None:
        """Send a recap email to the complainant."""
        try:
            self.logger.debug(f"_send_grievance_recap_email_to_complainant called with email: {complainant_email}")
            self.logger.debug(f"_send_grievance_recap_email_to_complainant grievance_data keys: {list(grievance_data.keys())}")
            await self.send_recap_email([complainant_email], 
                                                grievance_data, 
                                                body_name = body_name
                                                )
            message = self.get_utterance(3)
            utterance = message.format(complainant_email=complainant_email)
            dispatcher.utter_message(text=utterance)
        except Exception as e:
            self.logger.error(f"Failed to send recap email to complainant {complainant_email}: {e}")
            self.logger.error(f"Complainant email error details: {traceback.format_exc()}")


    def send_sms(self, sms_data: Dict[str, Any], body_name: str) -> None:
        """Send a SMS to the user."""
        try:
            complainant_phone = sms_data["complainant_phone"]
            sms_body = DIC_SMS_TEMPLATES[body_name][self.language_code]
            sms_body = sms_body.format(**sms_data)
            self.messaging.send_sms(complainant_phone, sms_body)
        except Exception as e:
            self.logger.error(f"Failed to send SMS: {e}")
            self.logger.error(f"SMS error details: {traceback.format_exc()}")

    def _get_attached_files_info(self, grievance_id: str) -> Dict[str, Any]:
        """Get information about files attached to a grievance.
        
        Args:
            grievance_id (str): The ID of the grievance to check for files
            
        Returns:
            str: A formatted string containing file information, or empty string if no files
        """
        try:
            files = self.db_manager.get_grievance_files(grievance_id)
            if not files:
                return {"has_files": False,
                        "files_info": ""}
            else:
                files_info = "\nAttached files:\n" + "\n".join([
                f"- {file['file_name']} ({file['file_size']} bytes)"
                for file in files
            ])
                return {"has_files": True,
                        "files_info": files_info}

        except Exception as e:
            self.logger.error(f"❌ Error getting attached files info: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to get attached files info: {str(e)}")

    def collect_grievance_data_from_tracker(self, tracker: Tracker = None) -> Dict[str, Any]:
        """Collect grievance data from the tracker."""
        grievance_data = {k: tracker.get_slot(k) for k in tracker.slots if k in USER_FIELDS + GRIEVANCE_FIELDS}
        return grievance_data