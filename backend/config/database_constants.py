"""
Database constants loaded from database at startup.

These constants are automatically loaded from the database when the module is first imported.
They behave like regular Python constants but are sourced from the database.
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Default timeline
DEFAULT_TIMELINE_DAYS = 15

############################
# GLOBAL CONSTANTS (LOADED FROM DATABASE)
############################

# These will be populated from the database on first import
GRIEVANCE_STATUSES = {}
TASK_STATUSES = {}
PROCESSING_STATUSES = {}
GRIEVANCE_CLASSIFICATION_STATUSES = {}
FIELD_NAMES = {}
TIMELINE_CACHE = {}

# Status code mappings (derived from database)
GRIEVANCE_STATUS_CODES = {}
TASK_STATUS_CODES = {}
PROCESSING_STATUS_CODES = {}

# Initialization flag
_LOADED = False

############################
# INITIALIZATION FUNCTIONS
############################

def _initialize_constants():
    """Initialize constants from database - called automatically on first import"""
    global GRIEVANCE_STATUSES, TASK_STATUSES, PROCESSING_STATUSES, GRIEVANCE_CLASSIFICATION_STATUSES, FIELD_NAMES, TIMELINE_CACHE
    global GRIEVANCE_STATUS_CODES, TASK_STATUS_CODES, PROCESSING_STATUS_CODES, _LOADED
    
    if _LOADED:
        return  # Already loaded
    
    try:
        # Import here to avoid circular imports
        from backend.services.database_services.postgres_services import DatabaseManager
        
        db_manager = DatabaseManager()
        
        # Load grievance statuses
        grievance_statuses = db_manager.execute_query(
            "SELECT * FROM grievance_statuses ORDER BY sort_order, status_code"
        )
        GRIEVANCE_STATUSES = {row['status_code']: row for row in grievance_statuses}
        GRIEVANCE_STATUS_CODES = {row['status_code']: row['status_code'] for row in grievance_statuses}
        
        # Load task statuses
        task_statuses = db_manager.execute_query(
            "SELECT * FROM task_statuses ORDER BY task_status_code"
        )
        TASK_STATUSES = {row['task_status_code']: row for row in task_statuses}
        TASK_STATUS_CODES = {row['task_status_code']: row['task_status_code'] for row in task_statuses}
        
        # Load processing statuses
        processing_statuses = db_manager.execute_query(
            "SELECT * FROM processing_statuses ORDER BY status_code"
        )
        PROCESSING_STATUSES = {row['status_code']: row for row in processing_statuses}
        PROCESSING_STATUS_CODES = {row['status_code']: row['status_code'] for row in processing_statuses}
        
        # Load grievance classification statuses
        classification_statuses = db_manager.execute_query(
            "SELECT * FROM grievance_classification_statuses ORDER BY code"
        )
        GRIEVANCE_CLASSIFICATION_STATUSES = {row['code']: row for row in classification_statuses}
        
        # Load field names
        field_names = db_manager.execute_query(
            "SELECT * FROM field_names ORDER BY field_name"
        )
        FIELD_NAMES = {row['field_name']: row for row in field_names}
        
        # Load timeline cache
        timeline_data = db_manager.execute_query(
            "SELECT status_update_code, grievance_high_priority, sensitive_issues_detected, timeline FROM status_update_timeline"
        )
        TIMELINE_CACHE = {}
        for row in timeline_data:
            key = (row['status_update_code'], row['grievance_high_priority'], row['sensitive_issues_detected'])
            TIMELINE_CACHE[key] = row['timeline']
        
        _LOADED = True
        logger.info(f"Database constants loaded successfully:")
        logger.info(f"  - Grievance statuses: {len(GRIEVANCE_STATUSES)}")
        logger.info(f"  - Task statuses: {len(TASK_STATUSES)}")
        logger.info(f"  - Processing statuses: {len(PROCESSING_STATUSES)}")
        logger.info(f"  - Grievance classification statuses: {len(GRIEVANCE_CLASSIFICATION_STATUSES)}")
        logger.info(f"  - Field names: {len(FIELD_NAMES)}")
        logger.info(f"  - Timeline entries: {len(TIMELINE_CACHE)}")
        
    except Exception as e:
        logger.error(f"Failed to load database constants: {str(e)}")
        # Set fallback values
        _set_fallback_values()
        _LOADED = True

def _set_fallback_values():
    """Set fallback values when database is unavailable"""
    global GRIEVANCE_STATUSES, TASK_STATUSES, PROCESSING_STATUSES, GRIEVANCE_CLASSIFICATION_STATUSES, FIELD_NAMES, TIMELINE_CACHE
    global GRIEVANCE_STATUS_CODES, TASK_STATUS_CODES, PROCESSING_STATUS_CODES
    
    logger.warning("Using fallback values for database constants")
    
    # Fallback grievance statuses
    GRIEVANCE_STATUSES = {
        "SUBMITTED": {"status_code": "SUBMITTED", "status_name_en": "Submitted", "status_name_ne": "जमा भएको"},
        "UNDER_EVALUATION": {"status_code": "UNDER_EVALUATION", "status_name_en": "Under Evaluation", "status_name_ne": "समीक्षा भइरहेको"},
        "ESCALATED": {"status_code": "ESCALATED", "status_name_en": "Escalated", "status_name_ne": "विस्तारित भएको"},
        "RESOLVED": {"status_code": "RESOLVED", "status_name_en": "Resolved", "status_name_ne": "समाधान भएको"},
        "DENIED": {"status_code": "DENIED", "status_name_en": "Denied", "status_name_ne": "अस्वीकृत"},
        "DISPUTED": {"status_code": "DISPUTED", "status_name_en": "Disputed", "status_name_ne": "विरोध भएको"},
        "CLOSED": {"status_code": "CLOSED", "status_name_en": "Closed", "status_name_ne": "बन्द भएको"}
    }
    GRIEVANCE_STATUS_CODES = {k: k for k in GRIEVANCE_STATUSES.keys()}
    
    # Fallback task statuses
    TASK_STATUSES = {
        "started": {"task_status_code": "started", "task_status_name": "Started"},
        "SUCCESS": {"task_status_code": "SUCCESS", "task_status_name": "Success"},
        "failed": {"task_status_code": "failed", "task_status_name": "Failed"},
        "retrying": {"task_status_code": "retrying", "task_status_name": "Retrying"}
    }
    TASK_STATUS_CODES = {k: k for k in TASK_STATUSES.keys()}
    
    # Fallback processing statuses
    PROCESSING_STATUSES = {
        "PROCESSING": {"status_code": "PROCESSING", "status_name": "Processing"},
        "COMPLETED": {"status_code": "COMPLETED", "status_name": "Completed"},
        "FAILED": {"status_code": "FAILED", "status_name": "Failed"},
        "FOR_VERIFICATION": {"status_code": "FOR_VERIFICATION", "status_name": "For Verification"},
        "VERIFICATION_IN_PROGRESS": {"status_code": "VERIFICATION_IN_PROGRESS", "status_name": "Verification In Progress"},
        "VERIFIED": {"status_code": "VERIFIED", "status_name": "Verified"},
        "VERIFIED_AND_AMENDED": {"status_code": "VERIFIED_AND_AMENDED", "status_name": "Verified and Amended"}
    }
    PROCESSING_STATUS_CODES = {k: k for k in PROCESSING_STATUSES.keys()}
    
    # Fallback grievance classification statuses
    from backend.config.database_tables import GRIEVANCE_CLASSIFICATION_STATUS_SEED_DATA
    GRIEVANCE_CLASSIFICATION_STATUSES = {row['code']: row for row in GRIEVANCE_CLASSIFICATION_STATUS_SEED_DATA}
    
    # Fallback field names
    FIELD_NAMES = {
        "grievance_description": {"field_name": "grievance_description", "description": "Grievance details"},
        "complainant_full_name": {"field_name": "complainant_full_name", "description": "User full name"},
        "complainant_phone": {"field_name": "complainant_phone", "description": "User phone number"},
        "complainant_email": {"field_name": "complainant_email", "description": "User email address"},
        "complainant_province": {"field_name": "complainant_province", "description": "User province"},
        "complainant_district": {"field_name": "complainant_district", "description": "User district"},
        "complainant_municipality": {"field_name": "complainant_municipality", "description": "User municipality"},
        "complainant_ward": {"field_name": "complainant_ward", "description": "User ward number"},
        "complainant_village": {"field_name": "complainant_village", "description": "User village"},
        "complainant_address": {"field_name": "complainant_address", "description": "User address"},
        "grievance_categories": {"field_name": "grievance_categories", "description": "Grievance categories"},
        "grievance_summary": {"field_name": "grievance_summary", "description": "Grievance summary"},
        "grievance_description_en": {"field_name": "grievance_description_en", "description": "Grievance description in English"}
    }
    
    # Fallback timeline cache
    TIMELINE_CACHE = {
        ("SUBMITTED", False, False): 15,
        ("SUBMITTED", True, True): 15,
        ("UNDER_REVIEW", False, False): 15,
        ("UNDER_REVIEW", True, True): 15,
        ("IN_PROGRESS", False, False): 15,
        ("IN_PROGRESS", True, True): 15,
        ("NEEDS_INFO", False, False): 15,
        ("NEEDS_INFO", True, True): 15,
        ("ESCALATED", False, False): 15,
        ("ESCALATED", True, True): 15,
        ("RESOLVED", False, False): 15,
        ("RESOLVED", True, True): 15,
        ("REJECTED", False, False): 15,
        ("REJECTED", True, True): 15,
        ("CLOSED", False, False): 15,
        ("CLOSED", True, True): 15
    }

############################
# ACCESS FUNCTIONS
############################

def get_timedelta_for_status(status_code: str, grievance_high_priority: bool = False, 
                           sensitive_issues_detected: bool = False) -> int:
    """Get timeline in days for a specific status update configuration."""
    key = (status_code, grievance_high_priority, sensitive_issues_detected)
    
    if key in TIMELINE_CACHE:
        return TIMELINE_CACHE[key]
    
    # Fallback to default timeline
    logger.warning(f"Timeline not found for {key}, using default {DEFAULT_TIMELINE_DAYS} days")
    return DEFAULT_TIMELINE_DAYS

def get_grievance_status(status_code: str) -> Optional[Dict[str, Any]]:
    """Get a specific grievance status by code."""
    return GRIEVANCE_STATUSES.get(status_code)

def get_task_status(status_code: str) -> Optional[Dict[str, Any]]:
    """Get a specific task status by code."""
    return TASK_STATUSES.get(status_code)

def get_task_status_codes():
    """Get commonly used task status codes from database."""
    return {
        'STARTED': TASK_STATUSES.get("started", {}).get("task_status_code", "started"),
        'SUCCESS': TASK_STATUSES.get("SUCCESS", {}).get("task_status_code", "SUCCESS"),
        'FAILED': TASK_STATUSES.get("failed", {}).get("task_status_code", "failed"),
        'RETRYING': TASK_STATUSES.get("retrying", {}).get("task_status_code", "retrying")
    }

def get_processing_status(status_code: str) -> Optional[Dict[str, Any]]:
    """Get a specific processing status by code."""
    return PROCESSING_STATUSES.get(status_code)

def get_field_name(field_name: str) -> Optional[Dict[str, Any]]:
    """Get a specific field name by field name."""
    return FIELD_NAMES.get(field_name)

def refresh_constants():
    """Refresh all constants from the database."""
    global _LOADED
    _LOADED = False
    _initialize_constants()

# Auto-initialize on import
_initialize_constants()

############################
# BACKWARDS COMPATIBILITY EXPORTS
############################

# Export old names for backwards compatibility with existing code
# These map to the new database-loaded constants

# Create a backwards-compatible GRIEVANCE_STATUS_DICT
# Maps status_code to dict with keys like "name_en", "name_ne", "description_en", "description_ne"
GRIEVANCE_STATUS_DICT = {
    status_code: {
        "name_en": data.get("status_name_en", ""),
        "name_ne": data.get("status_name_ne", ""),
        "description_en": data.get("description_en", ""),
        "description_ne": data.get("description_ne", "")
    }
    for status_code, data in GRIEVANCE_STATUSES.items()
}

# Legacy exports - these now point to database-loaded values
TASK_STATUS = get_task_status_codes()  # Returns {'STARTED': 'started', 'SUCCESS': 'SUCCESS', etc.}
GRIEVANCE_STATUS = GRIEVANCE_STATUS_CODES  # Maps status codes to themselves
GRIEVANCE_CLASSIFICATION_STATUS = {row['code']: row['code'] for row in GRIEVANCE_CLASSIFICATION_STATUSES.values()}
TRANSCRIPTION_PROCESSING_STATUS = PROCESSING_STATUS_CODES
