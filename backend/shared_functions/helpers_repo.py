from .location_validator import ContactLocationValidator
from .keyword_detector import KeywordDetector
from backend.config.constants import DEFAULT_VALUES, EMAIL_PROVIDERS_NEPAL_LIST
from rapidfuzz import process, fuzz
from typing import Optional, List, Tuple
from datetime import datetime, timedelta
import pandas as pd
import re

DEFAULT_PROVINCE = DEFAULT_VALUES["DEFAULT_PROVINCE"]
DEFAULT_DISTRICT = DEFAULT_VALUES["DEFAULT_DISTRICT"]
DEFAULT_LANGUAGE_CODE = DEFAULT_VALUES["DEFAULT_LANGUAGE_CODE"]

TITLE_LIST_DIC = {"en": [ 'mr', 'mrs', 'miss', 'ms','professor', 'prof', "pr", 'engineer', 'eng', "engr", 'doctor', 'dr', "honorary", "hon"],
"ne": ['श्री', 'shree', 'shri', 'श्रीमती', 'shrimati', 'कुमारी', 'kumari',
    'डाक्टर', 'डॉ',  'प्रधान', 'pradhan', 'ठेकेदार', 'thekedar']}
SUFFIX_LIST_DIC = {"en": ["Jr", "Sr", "Ph.D", "B.A", "B.S", "B.Sc", "B.Com", "MD"],
"ne": ['जी', 'ji', 'ज्यू', 'jyu',
    'दाइ', 'dai', 'दिदी', 'didi', 'भाइ', 'bhai', 'बहिनी', 'bahini',
    'बाजे', 'baje', 'बजै', 'bajai', 'सरकार', 'sarkaar', 'हजुर', 'hajur']}


TITLE_LIST = TITLE_LIST_DIC["en"] + TITLE_LIST_DIC["ne"]
TITLE_LIST = list(set([i.lower().strip() for i in TITLE_LIST]))
SUFFIX_LIST = SUFFIX_LIST_DIC["en"] + SUFFIX_LIST_DIC["ne"]
SUFFIX_LIST = list(set([i.lower().strip() for i in SUFFIX_LIST]))
SKIP_VALUE = DEFAULT_VALUES["SKIP_VALUE"]
NOT_PROVIDED = DEFAULT_VALUES["NOT_PROVIDED"]
    
class HelpersRepo:
    def __init__(self):
        self.location_validator = ContactLocationValidator()
        self.keyword_detector = KeywordDetector()

    def validate_municipality_input(self, location_string: str,
                        qr_province: str = DEFAULT_PROVINCE, 
                        qr_district: str = DEFAULT_DISTRICT) -> dict[str, str]:
        """Validate location using the location validator."""
        return self.location_validator.validate_municipality_input(location_string, qr_province, qr_district)

    def init_language(self, language_code: str = DEFAULT_LANGUAGE_CODE):
        """Initialize the language code for the helpers."""
        self.location_validator._initialize_constants(language_code)
        self.keyword_detector.language_code = language_code
        
    def check_province(self, province: str) -> bool:
        """Check if the province is valid."""
        return self.location_validator.check_province(input_text=province)
    
    def check_district(self, district: str, province: str) -> bool:
        """Check if the district is valid."""
        return self.location_validator.check_district(input_text=district, province_name=province)

    def validate_village_input(self, location_string: str,
                        qr_municipality: str) -> dict[str, str]:
        """Validate location using the location validator."""
        return self.location_validator.validate_village_input(location_string, qr_municipality)
    
    def detect_sensitive_content(self, text: str, language_code: str = "en") -> dict:
        """
        Detect sensitive content in text using keyword detector.
        
        Args:
            text: Text to analyze for sensitive content
            language_code: Language code for detection (default: "en")
            
        Returns:
            Dict containing detection results with keys:
            - detected: bool - Whether sensitive content was detected
            - level: str - Level of sensitivity (low, medium, high)
            - category: str - Category of sensitive content
            - message: str - Description of detected content
            - action_required: str - Recommended action
        """
        try:
            # Update language if needed
            if language_code != self.keyword_detector.language_code:
                self.keyword_detector = KeywordDetector(language_code=language_code)
            
            # Detect sensitive content
            result = self.keyword_detector.detect_sensitive_content(text)
            
            # Return structured result
            return {
                'detected': result.detected,
                'level': result.level,
                'category': result.category,
                'message': result.message,
                'action_required': result.action_required
            }
        except Exception as e:
            # Return safe default on error
            return {
                'detected': False,
                'level': 'low',
                'category': 'unknown',
                'message': f'Error in detection: {str(e)}',
                'action_required': 'none'
            }

    def validate_string_length(self, text: str, min_length: int = 2) -> bool:
        """Validate if the string meets minimum length requirement."""
        return bool(text and len(text.strip()) >= min_length)
    
    def is_valid_phone(self, phone: str) -> bool:
        """Check if the phone number is valid."""
        # Add your phone validation logic here
        #Nepalese logic
        # 1. Must be 10 digits and start with 9
        if re.match(r'^9\d{9}$', phone):
            return True
        #Matching PH number format for testing
        if re.match(r'^09\d{9}$', phone) or re.match(r'^639\d{8}$', phone):
            return True
        return False

    def standardize_phone(self, language_code: str, phone: str) -> str:
        if language_code == 'ne':
            phone = phone.replace('9', '+9779') if phone.startswith('9') else phone.replace('+9779', '+9779') if phone.startswith('+9779') else phone
            return phone
        return phone

    def is_philippine_phone(self, phone: str) -> bool:
        if re.match(r'^09\d{9}$', phone) or re.match(r'^639\d{8}$', phone):
            phone = phone.replace('09', '+639') if phone.startswith('09') else phone.replace('639', '+639') if phone.startswith('639') else phone
            return phone
        return None
    
    def email_extract_from_text(self, text: str) -> Optional[str]:
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        email_match = re.search(email_pattern, text)
        return email_match.group(0) if email_match else None

    def email_is_valid_nepal_domain(self, email: str) -> bool:
        email_domain = email.split('@')[1].lower()
        return email_domain in EMAIL_PROVIDERS_NEPAL_LIST or email_domain.endswith('.com.np')

    # ✅ Validate user contact email
    def email_is_valid_format(self, email: str) -> bool:
        """Check if email follows basic format requirements."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def match_full_name_word(self, input_full_name: str, reference_full_name: str) -> list:
        """Match the input full name with the reference full name using fuzzy matching.
        Uses partial_ratio for optimal partial name matching (first name or last name only).
        """
        input_full_name = self._standardize_name(input_full_name)
        reference_full_name = self._standardize_name(reference_full_name)
        
        # Use partial_ratio for optimal partial matching (first name or last name only)
        result = process.extractOne(
            input_full_name, 
            [reference_full_name], 
            scorer=fuzz.partial_ratio, 
            score_cutoff=60
        )
        print(f"match_full_name_word: result: {result}")
        return [(result[0], result[1])] if result else []

    def match_full_name_list(self, input_full_name: str, reference_full_names: list) -> list:
        """Match the input full name with the reference full names using fuzzy matching.
        
        This function normalizes both the input name and all reference names by removing
        titles, suffixes, and extra spaces before performing fuzzy matching. This makes it
        very forgiving with different spellings and non-normalized database entries (especially
        useful for legacy data or external databases).
        
        Args:
            input_full_name: The name to match against the reference list
            reference_full_names: List of reference names to match against
            
        Returns:
            List of original (non-standardized) reference names that match the input
            above the cutoff threshold (70%). Results are sorted by similarity score.
            
        Example:
            Input: "राम", References: ["राम शर्मा", "श्याम शर्मा", "राम शाह"]
            Returns: ["राम शर्मा", "राम शाह"]  # Original names, not standardized
        """
        input_full_name = self._standardize_name(input_full_name)
        reference_standardized_dic = {reference_full_name :self._standardize_name(reference_full_name) for reference_full_name in reference_full_names}
        reference_full_names_standardized = list(set(list(reference_standardized_dic.values())))     
        standardized_matches = process.extract(input_full_name, reference_full_names_standardized, score_cutoff=60)
        # process.extract returns list of tuples: (matched_string, score, index)
        matched_standardized_values = {m[0] for m in standardized_matches}
        result_list = [original for original, std in reference_standardized_dic.items() if std in matched_standardized_values]

        return result_list

    def _standardize_name(self, name: str) -> str:
        "standardize the name by removing the title, suffixes, and extra spaces"

        # Handle empty names
        if not name:
            return ""
        if name.lower() == SKIP_VALUE.lower():
            return ""
        if name.lower() == NOT_PROVIDED.lower():
            return ""
        name = name.lower().strip()
        

        name_list = [word.strip() for word in name.split()]
        if name_list and name_list[0] in TITLE_LIST:
            name_list.pop(0)
        if name_list and name_list[-1] in SUFFIX_LIST:
            name_list.pop(-1)
        return (' '.join(name_list))

    def get_office_in_charge_info(self, municipality, district = None, province = None):
        """Get the office in charge info from the municipality data."""
        return self.location_validator.get_office_in_charge_info(municipality, district, province)

    def get_current_datetime(self) -> str:
        """Get current date and time in YYYY-MM-DD HH:MM format."""
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    def get_timeline_by_status_code(self, status_update_code: str, grievance_high_priority: bool = False, 
                                  sensitive_issues_detected: bool = False) -> str:
        """
        Get the status update timeline from the database constants.
        
        Args:
            status_update_code: The status code to get timeline for
            grievance_high_priority: Whether the grievance is high priority
            sensitive_issues_detected: Whether sensitive issues are detected
            
        Returns:
            Timeline in days
        """
        try:
            # Import here to avoid circular imports
            from backend.config.database_constants import get_timedelta_for_status
            
            # Use the pre-loaded constants (super fast!)
            timeline_days = get_timedelta_for_status(
                status_code=status_update_code,
                grievance_high_priority=grievance_high_priority,
                sensitive_issues_detected=sensitive_issues_detected
            )
            current_date = datetime.now()
            timeline_date = current_date + timedelta(days=timeline_days)
            return timeline_date.strftime("%Y-%m-%d")
            
        except Exception as e:
            # Fallback to default timeline if database is unavailable
            return None

# Global instance for easy access
helpers_repo = HelpersRepo()