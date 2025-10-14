

from typing import Dict, List, Optional, Any, TypeVar, Generic
import traceback

# Import database configuration from constants.py (single source of truth)
from backend.config.constants import DB_CONFIG, DEFAULT_VALUES

DEFAULT_PROVINCE = DEFAULT_VALUES["DEFAULT_PROVINCE"]
DEFAULT_DISTRICT = DEFAULT_VALUES["DEFAULT_DISTRICT"]
DEFAULT_LANGUAGE_CODE = DEFAULT_VALUES["DEFAULT_LANGUAGE_CODE"]

# Import base manager for inheritance
from .base_manager import BaseDatabaseManager
from backend.logger import logger


class DatabaseManager(BaseDatabaseManager):
    """
    High-level API interface for all database operations.
    This provides a clean, consistent interface for the rest of the application.
    Implements singleton pattern to prevent multiple initializations.
    """
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not DatabaseManager._initialized:
            # Import managers directly to avoid circular imports
            super().__init__()
            from .base_manager import TableDbManager, TaskDbManager, FileDbManager
            from .gsheet_query_manager import GSheetDbManager
            from .complainant_manager import ComplainantDbManager
            from .grievance_manager import GrievanceDbManager, RecordingDbManager, TranscriptionDbManager, TranslationDbManager
            
            # Direct attribute assignment - much cleaner!
            self.table = TableDbManager()
            self.task = TaskDbManager()
            self.file = FileDbManager()
            self.gsheet = GSheetDbManager()
            self.complainant = ComplainantDbManager()
            self.grievance = GrievanceDbManager()
            self.recording = RecordingDbManager()
            self.transcription = TranscriptionDbManager()
            self.translation = TranslationDbManager()
            DatabaseManager._initialized = True


    # ===== ID GENERATION =====

    def generate_complainant_id(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new complainant ID"""
        province = data.get('complainant_province', DEFAULT_PROVINCE)
        district = data.get('complainant_district', DEFAULT_DISTRICT)
        office = data.get('complainant_office', None)
        source = data.get('source', 'bot')
        return self.generate_id(type='complainant_id', province=province, district=district, office=office, suffix=source)
    
    def generate_grievance_id(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new grievance ID"""
        province = data.get('complainant_province', DEFAULT_PROVINCE)
        district = data.get('complainant_district', DEFAULT_DISTRICT)
        office = data.get('complainant_office', None)
        source = data.get('source', 'bot')
        return self.generate_id(type='grievance_id', province=province, district=district, office=office, suffix=source)
    
    
    
    # ===== COMPLAINANT OPERATIONS =====

    def create_complainant(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new complainant"""
        complainant_id = data.get('complainant_id')
        if not complainant_id:
            complainant_id = self.generate_complainant_id(data)
            data['complainant_id'] = complainant_id
        self.complainant.create_complainant(data)
        return complainant_id
    
    def update_complainant(self, complainant_id: str, data: Dict[str, Any]):
        """Update an existing complainant"""
        self.complainant.update_complainant(complainant_id, data)

    def create_or_update_complainant(self, data: Dict[str, Any]):
        """Create or update a complainant"""
        try:
            complainant_id = data.get('complainant_id')
            if self.complainant.get_complainant_by_id(complainant_id):
                self.update_complainant(complainant_id, data)
            else:
                self.create_complainant(data)
        except Exception as e:
            self.logger.error(f"Error creating or updating complainant: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    
    def get_complainant_by_id(self, complainant_id: str) -> Optional[Dict[str, Any]]:
        """Get complainant by ID"""
        return self.complainant.get_complainant_by_id(complainant_id)
    
    def get_complainants_by_phone(self, phone_number: str) -> List[Dict[str, Any]]:
        """Find complainants by phone number"""
        return self.complainant.get_complainants_by_phone(phone_number)
    
    def get_complainant_from_grievance(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get complainant associated with a grievance""" 
        return self.complainant.get_complainant_from_grievance_id(grievance_id)

    def _encrypt_complainant_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt complainant data"""
        return self.complainant._encrypt_sensitive_data(data)
    
    def _decrypt_complainant_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt complainant data"""
        return self.complainant._decrypt_sensitive_data(data)

    def get_all_complainant_full_names(self) -> List[str]:
        """Get all complainant full names"""
        return self.complainant.get_all_complainant_full_names()
    
    # ===== GRIEVANCE OPERATIONS =====

    async def create_complainant_and_grievance(self, data: Dict[str, Any]) -> None:
        """Create a new complainant and grievance"""
        try:
            complainant_id = data.get('complainant_id')
            if not complainant_id:
                complainant_id = self.generate_complainant_id(data)
                data['complainant_id'] = complainant_id
            self.complainant.create_complainant(data)
        except Exception as e:
            self.logger.error(f"Error creating complainant: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        try:
            grievance_id = data.get('grievance_id')
            if not grievance_id:
                grievance_id = self.generate_grievance_id(data)
                data['grievance_id'] = grievance_id
            self.grievance.create_grievance(data)
        except Exception as e:
            self.logger.error(f"Error creating grievance: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
        
    
    def submit_grievance_to_db(self, data: Dict[str, Any]) -> bool:
        """Submit a new grievance to the database"""
        try:
            grievance_id = data.get('grievance_id')
            complainant_id = data.get('complainant_id')
            if not (grievance_id and complainant_id):
                self.logger.error(f"Error - submitting_grievance_to_db: grievance_id or complainant_id is missing in input_data: {data}")
                return False
            
            source = self.get_grievance_or_complainant_source(grievance_id)
            data['source'] = source

            #validate that the complainant and grievance ids are already in the database
            complainant = self.get_complainant_by_id(complainant_id)
            if not complainant:
                self.logger.error(f"Error - submitting_grievance_to_db: complainant_id not found in db: {complainant_id}")
                return False
            grievance = self.get_grievance_by_id(grievance_id)
            if not grievance:
                self.logger.error(f"Error - submitting_grievance_to_db: grievance_id not found in db: {grievance_id}")
                return False

            data = self.get_complainant_and_grievance_fields(data)
            complainant_data = data['complainant_fields']
            grievance_data = data['grievance_fields']

            if complainant_data:
                self.complainant.update_complainant(complainant_id, complainant_data)
                self.logger.info(f"Complainant updated in db: {complainant_id}")
            if grievance_data:
                self.grievance.update_grievance(grievance_id, grievance_data)
                self.logger.info(f"Grievance updated in db: {grievance_id}")

            if grievance_data or complainant_data:
                # Add initial creation entry for SUBMITTED status
                status_update_success = self.grievance.log_grievance_change(
                    grievance_id=grievance_id,
                    change_type='creation',
                    created_by=self.DEFAULT_USER,
                    status_code='SUBMITTED',
                    assigned_to=None,
                    notes='Initial grievance creation (first submission)',
                    source='user_input'
                )
                if status_update_success:
                    self.logger.info(f"Status history updated for grievance: {grievance_id}")
                else:
                    self.logger.warning(f"Failed to update status history for grievance: {grievance_id}")
            
            return True
        except Exception as e:
            self.logger.error(f"Error submitting grievance to db: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
            
    def create_grievance(self, data: Dict[str, Any]) -> str:
        """Create a new grievance"""
        grievance_id = data.get('grievance_id')
        if not grievance_id:
            grievance_id = self.generate_grievance_id(data)
            data['grievance_id'] = grievance_id
        self.grievance.create_grievance(data)
        return grievance_id
    
    def update_grievance(self, grievance_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing grievance"""
        try:
            
            source = self.get_grievance_or_complainant_source(grievance_id)
            data['source'] = source

            data = self.get_complainant_and_grievance_fields(data)
            complainant_data = data['complainant_fields']
            grievance_data = data['grievance_fields']
            #deal with the complainant data
            if complainant_data:
                complainant_id = self.complainant.get_complainant_id_from_grievance_id(grievance_id)
                self.complainant.update_complainant(complainant_id, complainant_data)
                self.logger.info(f"Complainant updated in db: {grievance_id}")
            if grievance_data:
                self.grievance.update_grievance(grievance_id, grievance_data)
                self.logger.info(f"Grievance updated in db: {grievance_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error submitting grievance to db: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    def create_or_update_grievance(self, data: Dict[str, Any]):
        """Create or update a grievance"""
        try:
            grievance_id = data.get('grievance_id')
            self.logger.debug(f"create_or_update_grievance: for grievance_id: {grievance_id}")
            if self.grievance.get_grievance_by_id(grievance_id):
                self.update_grievance(grievance_id, data)
            else:
                self.create_grievance(data)
        except Exception as e:
            self.logger.error(f"Error creating or updating grievance: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            
    
    def get_grievance_by_id(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get grievance by ID"""
        return self.grievance.get_grievance_by_id(grievance_id)
    
    def is_valid_grievance_id(self, grievance_id: str) -> bool:
        """Check if a grievance ID exists in the database"""
        return self.grievance.is_valid_grievance_id(grievance_id)
    
    def get_grievance_status(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a grievance"""
        return self.grievance.get_grievance_status(grievance_id)
    
    def update_grievance_status(self, grievance_id: str, status_code: str, created_by: Optional[str] = None, assigned_to: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Update grievance status"""
        return self.grievance.update_grievance_status(grievance_id, status_code, created_by, assigned_to, notes)
    
    def get_grievance_files(self, grievance_id: str) -> List[Dict[str, Any]]:
        """Get files attached to a grievance"""
        return self.grievance.get_grievance_files(grievance_id)

    def get_grievance_by_complainant_phone(self, phone_number: str) -> List[Dict[str, Any]]:
        """Get grievance by complainant phone number"""
        return self.grievance.get_grievance_by_complainant_phone(phone_number)
    
    # ===== RECORDING OPERATIONS =====
    
    def create_recording(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new voice recording"""
        return self.recording.create_recording(data)

    def update_recording(self, recording_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing voice recording"""
        return self.recording.update_recording(recording_id, data)

    def get_recording_by_id(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """Get recording by ID"""
        return self.recording.get_recording_by_id(recording_id)
    
    def create_or_update_recording(self, data: Dict[str, Any]):
        """Create or update a recording"""
        try:
            recording_id = data.get('recording_id')
            if self.recording.get_recording_by_id(recording_id):
                self.update_recording(recording_id, data)
            else:
                self.create_recording(data)
        except Exception as e:
            self.logger.error(f"Error creating or updating recording: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    
    # ===== TRANSCRIPTION OPERATIONS =====
    
    def create_transcription(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new transcription"""
        return self.transcription.create_transcription(data)
    
    def update_transcription(self, transcription_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing transcription"""
        return self.transcription.update_transcription(transcription_id, data)

    def get_transcription_by_id(self, transcription_id: str) -> Optional[Dict[str, Any]]:
        """Get transcription by ID"""
        return self.transcription.get_transcription_by_id(transcription_id)

    def create_or_update_transcription(self, data: Dict[str, Any]):
        """Create or update a transcription"""
        try:
            transcription_id = data.get('transcription_id')
            if self.transcription.get_transcription_by_id(transcription_id):
                self.update_transcription(transcription_id, data)
            else:
                self.create_transcription(data)
        except Exception as e:
            self.logger.error(f"Error creating or updating transcription: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    
    # ===== TRANSLATION OPERATIONS =====

    def get_translation_by_id(self, translation_id: str) -> Optional[Dict[str, Any]]:
        """Get translation by ID"""
        return self.translation.get_translation_by_id(translation_id)
    
    def create_translation(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new translation"""
        return self.translation.create_translation(data)
    
    def update_translation(self, translation_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing translation"""
        return self.translation.update_translation(translation_id, data)

    def create_or_update_translation(self, data: Dict[str, Any]):
        """Create or update a translation"""
        try:
            translation_id = data.get('translation_id')
            if self.translation.get_translation_by_id(translation_id):
                self.update_translation(translation_id, data)
            else:
                self.create_translation(data)
        except Exception as e:
            self.logger.error(f"Error creating or updating translation: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")


    # ===== RECORDING OPERATIONS =====

    def create_recording(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new recording"""
        return self.recording.create_recording(data)
    
    def update_recording(self, recording_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing recording"""
        return self.recording.update_recording(recording_id, data)
    
    def get_recording_by_id(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """Get recording by ID"""
        return self.recording.get_recording_by_id(recording_id)
    
    def create_or_update_recording(self, data: Dict[str, Any]):
        """Create or update a recording"""
        try:
            recording_id = data.get('recording_id')
            if self.recording.get_recording_by_id(recording_id):
                self.update_recording(recording_id, data)
            else:
                self.create_recording(data)
        except Exception as e:
            self.logger.error(f"Error creating or updating recording: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    # ===== TASK OPERATIONS =====
    
    def create_task(self, task_id: str, task_name: str, entity_key: str, entity_id: str) -> Optional[str]:
        """Create a new task"""
        return self.task.create_task(task_id, task_name, entity_key, entity_id)
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID"""
        return self.task.get_task(task_id)
    
    def update_task(self, task_id: str, update_data: Dict[str, Any]) -> bool:
        """Update task status and details"""
        return self.task.update_task(task_id, update_data)
    
    
    # ===== FILE OPERATIONS =====
    
    def store_file_attachment(self, file_data: Dict[str, Any]) -> bool:
        """Store file attachment"""
        return self.file.store_file_attachment(file_data)
    
    def get_grievance_file_attachments(self, grievance_id: str) -> List[Dict[str, Any]]:
        """Get files for a grievance"""
        return self.file.get_grievance_files(grievance_id)
    
    # ===== SCHEMA OPERATIONS =====
    
    def init_database(self) -> bool:
        """Initialize database schema"""
        return self.table.init_db()
    
    def recreate_database(self) -> bool:
        """Recreate all tables"""
        return self.table.recreate_all_tables()
    
    def get_available_statuses(self, language: str = 'en') -> List[Dict[str, Any]]:
        """Get available grievance statuses"""
        return self.grievance.get_available_statuses(language)
    


# Create a single instance for the application
db_manager = DatabaseManager()


    