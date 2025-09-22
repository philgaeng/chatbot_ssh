from .location_validator import ContactLocationValidator
from .keyword_detector import KeywordDetector
from backend.config.constants import DEFAULT_VALUES, EMAIL_PROVIDERS_NEPAL_LIST
from rapidfuzz import process
from typing import Optional, List, Tuple
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

    def match_full_name(self, input_full_name: str, reference_full_names: list) -> list:
        """Match the input full name with the reference full names using fuzzy matching.
        First we need to parse the input and output full names to remove the title, and suffixes
        Then we need to split the input and reference full names
        Then we need to match the  each input word with each reference word using fuzzy matching
        for each input word, return the best match with its score from the list of reference words
        If the list of matched words is equal or greater than two return the matching reference full name
        return the list of matched words"""
        input_full_name = self._standardize_name(input_full_name)
        reference_full_names =  list(set([self._standardize_name(reference_full_name) for reference_full_name in reference_full_names]))
        result_list = process.extract(input_full_name, reference_full_names, score_cutoff=90)

        return result_list

    def _standardize_name(self, name: str) -> str:
        "standardize the name by removing the title, suffixes, and extra spaces"

        name = name.lower().strip()
    
        name_list = [word.strip() for word in name.split()]
        if name[0] in TITLE_LIST:
            name_list.pop(0)
        if name_list[-1] in SUFFIX_LIST:
            name_list.pop(-1)
        return (' '.join(name_list))



# Global instance for easy access
helpers_repo = HelpersRepo()