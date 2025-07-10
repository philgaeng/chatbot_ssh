"""
Backend Repository for Rasa Actions

This file serves as a single interface for all backend services used by Rasa actions.
It provides a clean facade pattern that abstracts the complexity of multiple backend services
and makes it easy to switch implementations (e.g., from direct imports to REST API calls).

Usage:
    from .backend_repository import BackendRepository
    
    repo = BackendRepository()
    grievance_id = repo.create_grievance(complainant_data)
    repo.send_sms(phone, message)
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

# Import enhanced logging
from .enhanced_logging import log_backend_operation, log_error_with_context, log_action_execution

# Import all backend services
from backend.config.constants import (
    GRIEVANCE_STATUS, GRIEVANCE_CLASSIFICATION_STATUS, EMAIL_TEMPLATES, DIC_SMS_TEMPLATES, DEFAULT_VALUES, 
    ADMIN_EMAILS, CLASSIFICATION_DATA, LIST_OF_CATEGORIES, USER_FIELDS,
    GRIEVANCE_FIELDS, DEFAULT_PROVINCE, DEFAULT_DISTRICT, TASK_STATUS,
    MAX_FILE_SIZE
)
from backend.services.database_services.postgres_services import db_manager
from backend.services.messaging import SMSClient, EmailClient, CommunicationClient
from backend.services.LLM_services import classify_and_summarize_grievance
from backend.shared_functions.helpers import ContactLocationValidator



class BackendRepository:
    """
    Repository pattern implementation for backend services used by Rasa actions.
    
    This class provides a clean interface to all backend services, making it easy to:
    - Switch implementations (e.g., from direct imports to REST API calls)
    - Centralize error handling
    - Add logging and monitoring
    - Maintain clean separation of concerns
    """
    
    def __init__(self):
        """Initialize the repository with all necessary services."""
        self.db = db_manager
        self.sms_client = SMSClient()
        self.email_client = EmailClient()
        self.communication_client = CommunicationClient()
        
    # ============================================================================
    # DATABASE OPERATIONS
    # ============================================================================
    
    def submit_grievance_to_db(self, data: Dict[str, Any]) -> bool:
        """Create a new complainant and return success status."""
        try:
            # Use the complainant manager directly
            success = self.db.submit_grievance_to_db(data)
            log_backend_operation("submit_grievance_to_db", success, data)
            return success
        except Exception as e:
            log_error_with_context(e, "submit_grievance_to_db", data)
            return False

    def update_grievance_in_db(self, data: Dict[str, Any]) -> bool:
        """Update a grievance in the database."""
        try:
            success = self.db.update_grievance(data)
            log_backend_operation("update_grievance_in_db", success, data)
            return success
        except Exception as e:
            log_error_with_context(e, "update_grievance_in_db", data)
            return False


    def get_grievance_by_id(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get grievance details by ID."""
        try:
            grievance = self.db.get_grievance_by_id(grievance_id)
            success = grievance not in [False, None]
            log_backend_operation("get_grievance_by_id", success, {"grievance_id": grievance_id})
            return grievance
        except Exception as e:
            log_error_with_context(e, "get_grievance_by_id", {"grievance_id": grievance_id})
            return None
    
    
    def update_complainant(self, complainant_id: str, update_data: Dict[str, Any]) -> bool:
        """Update complainant information."""
        try:
            success = self.db.update_complainant(complainant_id, update_data)
            log_backend_operation("update_complainant", success, {"complainant_id": complainant_id, "update_data": update_data})
            return success
        except Exception as e:
            log_error_with_context(e, "update_complainant", {"complainant_id": complainant_id, "update_data": update_data})
            return False
    
    
    def get_grievance_status(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a grievance."""
        try:
            status = self.db.get_grievance_status(grievance_id)
            success = status is not None
            log_backend_operation("get_grievance_status", success, {"grievance_id": grievance_id})
            return status
        except Exception as e:
            log_error_with_context(e, "get_grievance_status", {"grievance_id": grievance_id})
            return None
    
    # ============================================================================
    # MESSAGING OPERATIONS
    # ============================================================================
    
    def send_sms(self, phone_number: str, message: str) -> bool:
        """Send SMS message."""
        try:
            success = self.sms_client.send_sms(phone_number, message)
            log_backend_operation("send_sms", success, {"phone_number": phone_number, "message_length": len(message)})
            return success
        except Exception as e:
            log_error_with_context(e, "send_sms", {"phone_number": phone_number, "message_length": len(message)})
            return False
    
    def send_email(self, email: str, subject: str, message: str) -> bool:
        """Send email message."""
        try:
            success = self.email_client.send_email([email], subject, message)
            log_backend_operation("send_email", success, {"email": email, "subject": subject, "message_length": len(message)})
            return success
        except Exception as e:
            log_error_with_context(e, "send_email", {"email": email, "subject": subject, "message_length": len(message)})
            return False
    
    def send_otp(self, phone_number: str, otp: str) -> bool:
        """Send OTP via SMS."""
        try:
            # Since CommunicationClient doesn't have send_otp method, use SMS client
            message = f"Your OTP is: {otp}"
            success = self.sms_client.send_sms(phone_number, message)
            log_backend_operation("send_otp", success, {"phone_number": phone_number})
            return success
        except Exception as e:
            log_error_with_context(e, "send_otp", {"phone_number": phone_number})
            return False
    
    def verify_otp(self, phone_number: str, otp: str) -> bool:
        """Verify OTP."""
        try:
            # Since CommunicationClient doesn't have verify_otp method, implement basic verification
            # In a real implementation, you would verify against stored OTP
            log_backend_operation("verify_otp", True, {"phone_number": phone_number})
            return True  # Placeholder implementation
        except Exception as e:
            log_error_with_context(e, "verify_otp", {"phone_number": phone_number})
            return False
    
    # ============================================================================
    # LLM SERVICES
    # ============================================================================
    
    def classify_and_summarize_grievance(self, grievance_text: str) -> Dict[str, Any]:
        """Classify and summarize grievance using LLM services."""
        try:
            result = classify_and_summarize_grievance(grievance_text)
            log_backend_operation("classify_and_summarize_grievance", True, {"text_length": len(grievance_text)})
            return result
        except Exception as e:
            log_error_with_context(e, "classify_and_summarize_grievance", {"text_length": len(grievance_text)})
            return {
                'category': 'general',
                'summary': grievance_text,
                'confidence': 0.0
            }
    
    # ============================================================================
    # LOCATION VALIDATION
    # ============================================================================
    
    def create_location_validator(self, tracker=None) -> Optional[ContactLocationValidator]:
        """Create a location validator instance."""
        try:
            validator = ContactLocationValidator(tracker=tracker)
            log_backend_operation("create_location_validator", True)
            return validator
        except Exception as e:
            log_error_with_context(e, "create_location_validator", {"tracker": str(tracker) if tracker else None})
            return None
    
    
    def validate_location(self, location_string: str, qr_province: Optional[str] = None, 
                        qr_district: Optional[str] = None, tracker=None) -> Dict[str, Any]:
        """Validate location using the location validator."""
        try:
            validator = self.create_location_validator(tracker)
            if validator:
                result = validator._validate_location(location_string, qr_province, qr_district)
                log_backend_operation("validate_location", True, {"location_string": location_string, "qr_province": qr_province, "qr_district": qr_district})
                return result
            log_backend_operation("validate_location", False, {"location_string": location_string, "qr_province": qr_province, "qr_district": qr_district})
            return {'province': None, 'district': None, 'municipality': None}
        except Exception as e:
            log_error_with_context(e, "validate_location", {"location_string": location_string, "qr_province": qr_province, "qr_district": qr_district})
            return {'province': None, 'district': None, 'municipality': None}
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    def get_constant(self, constant_name: str) -> Any:
        """Get a constant value by name."""
        constants_map = {
            'GRIEVANCE_STATUS': GRIEVANCE_STATUS,
            'EMAIL_TEMPLATES': EMAIL_TEMPLATES,
            'DIC_SMS_TEMPLATES': DIC_SMS_TEMPLATES,
            'DEFAULT_VALUES': DEFAULT_VALUES,
            'ADMIN_EMAILS': ADMIN_EMAILS,
            'CLASSIFICATION_DATA': CLASSIFICATION_DATA,
            'LIST_OF_CATEGORIES': LIST_OF_CATEGORIES,
            'USER_FIELDS': USER_FIELDS,
            'GRIEVANCE_FIELDS': GRIEVANCE_FIELDS,
            'DEFAULT_PROVINCE': DEFAULT_PROVINCE,
            'DEFAULT_DISTRICT': DEFAULT_DISTRICT,
            'TASK_STATUS': TASK_STATUS,
            'MAX_FILE_SIZE': MAX_FILE_SIZE
        }
        return constants_map.get(constant_name)


    def log_action(self, action_name: str, data: Optional[Dict[str, Any]] = None):
        """Log action execution for monitoring."""
        log_action_execution(action_name , data)
    


# Global instance for easy access
backend_repo = BackendRepository() 