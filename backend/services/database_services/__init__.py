# Import all managers from their respective files
from .base_manager import (
    BaseDatabaseManager,
    TableDbManager,
    TaskDbManager,
    FileDbManager,
    GSheetDbManager
)

from .complainant_manager import ComplainantDbManager
from .grievance_manager import (
    GrievanceDbManager,
    RecordingDbManager,
    TranscriptionDbManager,
    TranslationDbManager
)

class DatabaseManagers:
    """Unified access point for all database managers with lazy loading"""
    def __init__(self):
        self._managers = {}
    
    def _get_manager(self, name, manager_class):
        """Lazy load a manager instance"""
        if name not in self._managers:
            self._managers[name] = manager_class()
        return self._managers[name]
    
    @property
    def table(self):
        return self._get_manager('table', TableDbManager)
    
    @property
    def grievance(self):
        return self._get_manager('grievance', GrievanceDbManager)
    
    @property
    def task(self):
        return self._get_manager('task', TaskDbManager)
    
    @property
    def user(self):
        return self._get_manager('user', ComplainantDbManager)
    
    @property
    def file(self):
        return self._get_manager('file', FileDbManager)
    
    @property
    def recording(self):
        return self._get_manager('recording', RecordingDbManager)
    
    @property
    def transcription(self):
        return self._get_manager('transcription', TranscriptionDbManager)
    
    @property
    def translation(self):
        return self._get_manager('translation', TranslationDbManager)
    
    @property
    def base(self):
        return self._get_manager('base', BaseDatabaseManager)
    
    @property
    def gsheet(self):
        return self._get_manager('gsheet', GSheetDbManager)

# Create a single instance of the unified manager
db_manager = DatabaseManagers()

# Export all managers for direct import
__all__ = [
    'BaseDatabaseManager',
    'TableDbManager',
    'TaskDbManager',
    'FileDbManager',
    'GSheetDbManager',
    'ComplainantDbManager',
    'GrievanceDbManager',
    'RecordingDbManager',
    'TranscriptionDbManager',
    'TranslationDbManager',
    'DatabaseManagers',
    'db_manager'
] 