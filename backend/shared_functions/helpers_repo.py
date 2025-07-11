from .location_validator import ContactLocationValidator
from .keyword_detector import KeywordDetector
from backend.config.constants import DEFAULT_PROVINCE, DEFAULT_DISTRICT, EMAIL_PROVIDERS_NEPAL_LIST
from typing import Optional
import re

class HelpersRepo:
    def __init__(self):
        self.location_validator = ContactLocationValidator()
        self.keyword_detector = KeywordDetector()

    def validate_location(self, location_string: str,
                        qr_province: str = DEFAULT_PROVINCE, 
                        qr_district: str = DEFAULT_DISTRICT) -> dict[str, str]:
        """Validate location using the location validator."""
        return self.location_validator.validate_location(location_string, qr_province, qr_district)

    def init_language(self, language_code: str):
        """Initialize the language code for the helpers."""
        self.location_validator._initialize_constants(language_code)
        self.keyword_detector.language_code = language_code
        
    def check_province(self, province: str) -> bool:
        """Check if the province is valid."""
        return self.location_validator.check_province(input_text=province)
    
    def check_district(self, district: str, province: str) -> bool:
        """Check if the district is valid."""
        return self.location_validator.check_district(input_text=district, province_name=province)
    
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


# Global instance for easy access
helpers_repo = HelpersRepo()