

from typing import Dict, List, Optional, Any, TypeVar, Generic

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
    """
    
    def __init__(self):
        # Import managers directly to avoid circular imports
        super().__init__()
        from .base_manager import TableDbManager, TaskDbManager, FileDbManager, GSheetDbManager
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


    # ===== ID GENERATION =====

    def create_complainant_id(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new complainant ID"""
        province = data.get('complainant_province', DEFAULT_PROVINCE)
        district = data.get('complainant_district', DEFAULT_DISTRICT)
        office = data.get('complainant_office', None)
        source = data.get('source', 'bot')
        return self.generate_id(type='complainant_id', province=province, district=district, office=office, suffix=source)
    
    def create_grievance_id(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new grievance ID"""
        province = data.get('complainant_province', DEFAULT_PROVINCE)
        district = data.get('complainant_district', DEFAULT_DISTRICT)
        office = data.get('complainant_office', None)
        source = data.get('source', 'bot')
        return self.generate_id(type='grievance_id', province=province, district=district, office=office, suffix=source)
    
    
    
    # ===== COMPLAINANT OPERATIONS =====

    def create_complainant(self, data: Dict[str, Any]) -> bool:
        """Create a new complainant"""
        return self.complainant.create_complainant(data)
    
    def update_complainant(self, complainant_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing complainant"""
        return self.complainant.update_complainant(complainant_id, data)
    
    def get_complainant_by_id(self, complainant_id: str) -> Optional[Dict[str, Any]]:
        """Get complainant by ID"""
        return self.complainant.get_complainant_by_id(complainant_id)
    
    def find_complainant_by_phone(self, phone_number: str) -> List[Dict[str, Any]]:
        """Find complainants by phone number"""
        return self.complainant.get_complainants_by_phone_number(phone_number)
    
    def get_complainant_from_grievance(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get complainant associated with a grievance""" 
        return self.complainant.get_complainant_from_grievance_id(grievance_id)

    def _encrypt_complainant_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt complainant data"""
        return self.complainant._encrypt_complainant_data(data)
    
    def _decrypt_complainant_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt complainant data"""
        return self.complainant._decrypt_complainant_data(data)
    
    # ===== GRIEVANCE OPERATIONS =====
    
    def submit_grievance_to_db(self, data: Dict[str, Any]) -> bool:
        """Submit a new grievance to the database"""
        try:
            grievance_id = data.get('grievance_id')
            complainant_id = data.get('complainant_id')
            source = self.get_grievance_or_complainant_source(grievance_id)
            data['source'] = source

            data = self.get_complainant_and_grievance_fields(data)
            complainant_data = data['complainant_fields']
            grievance_data = data['grievance_fields']

            if complainant_data:
                self.complainant.create_complainant(complainant_data)
                self.logger.info(f"Complainant created in db: {complainant_id}")
                if grievance_data:
                    self.grievance.create_grievance(grievance_data)
                    self.logger.info(f"Grievance created in db: {grievance_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error submitting grievance to db: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
            
    def create_grievance(self, data: Dict[str, Any]) -> bool:
        """Create a new grievance"""
        return self.grievance.create_grievance(data)
    
    def update_grievance(self, grievance_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing grievance"""
        try:
            grievance_id = data.get('grievance_id')
            complainant_id = data.get('complainant_id')
            source = self.get_grievance_or_complainant_source(grievance_id)
            data['source'] = source

            data = self.get_complainant_and_grievance_fields(data)
            complainant_data = data['complainant_fields']
            grievance_data = data['grievance_fields']

            if complainant_data:
                self.complainant.update_complainant(complainant_id, complainant_data)
                self.logger.info(f"Complainant updated in db: {complainant_id}")
                if grievance_data:
                    self.grievance.update_grievance(grievance_id, grievance_data)
                    self.logger.info(f"Grievance updated in db: {grievance_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error submitting grievance to db: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False
    
    def get_grievance_by_id(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get grievance by ID"""
        return self.grievance.get_grievance_by_id(grievance_id)
    
    def get_grievance_status(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a grievance"""
        return self.grievance.get_grievance_status(grievance_id)
    
    def update_grievance_status(self, grievance_id: str, status_code: str, created_by: Optional[str] = None, assigned_to: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Update grievance status"""
        return self.grievance.update_grievance_status(grievance_id, status_code, created_by, assigned_to, notes)
    
    def get_grievance_files(self, grievance_id: str) -> List[Dict[str, Any]]:
        """Get files attached to a grievance"""
        return self.grievance.get_grievance_files(grievance_id)
    
    # ===== RECORDING OPERATIONS =====
    
    def create_or_update_recording(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new voice recording"""
        return self.recording.create_or_update_recording(data)
    
    
    # ===== TRANSCRIPTION OPERATIONS =====
    
    def create_transcription(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new transcription"""
        return self.transcription.create_transcription(data)
    
    def update_transcription(self, transcription_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing transcription"""
        return self.transcription.update_transcription(transcription_id, data)
    
    # ===== TRANSLATION OPERATIONS =====
    
    def create_translation(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new translation"""
        return self.translation.create_translation(data)
    
    def update_translation(self, translation_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing translation"""
        return self.translation.update_translation(translation_id, data)
    
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
    
    def get_pending_tasks(self, entity_key: str = "") -> List[Dict[str, Any]]:
        """Get all pending tasks"""
        return self.task.get_pending_tasks(entity_key)
    
    # ===== FILE OPERATIONS =====
    
    def store_file(self, file_data: Dict[str, Any]) -> bool:
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


    