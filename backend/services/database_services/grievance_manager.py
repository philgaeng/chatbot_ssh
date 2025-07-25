import uuid
import logging
from typing import Dict, List, Optional, Any
import traceback
from icecream import ic
from .base_manager import BaseDatabaseManager




class GrievanceDbManager(BaseDatabaseManager):
    """Handles grievance CRUD and business logic"""
    
    # Whitelist of fields that can be updated
    ALLOWED_UPDATE_FIELDS = {
        'complainant_id',
        'grievance_categories',
        'grievance_summary',
        'grievance_description',
        'grievance_claimed_amount',
        'grievance_location',
        'is_temporary',
        'source',
        'language_code',
        'classification_status'
    }

    def create_grievance(self, data: Dict[str, Any], source: str = 'bot') -> bool:
        """Create a new grievance record
        Args:
            data: Dictionary containing grievance data including:
                - grievance_id: ID of the grievance (required)
                - complainant_id: ID of the complainant (required)
        """
        try:
            self.logger.info(f"create_grievance: Creating grievance with data: {data}")
            grievance_id = data.get('grievance_id')
            complainant_id = data.get('complainant_id')
            if not data.get('source'):
                source = self.get_grievance_or_complainant_source(grievance_id)
                data['source'] = source
                
            self.logger.info(f"create_grievance: Creating grievance with ID: {grievance_id}")
            
            insert_query = """
                INSERT INTO grievances (
                    grievance_id, complainant_id, grievance_categories,
                    grievance_summary, grievance_description, grievance_claimed_amount,
                    grievance_location, language_code, source
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING grievance_id
            """
            self.execute_insert(insert_query, (
                grievance_id,
                complainant_id,
                data.get('grievance_categories', []),
                data.get('grievance_summary', ''),
                data.get('grievance_description', ''),
                data.get('grievance_claimed_amount', 0),
                data.get('grievance_location', ''),
                data.get('language_code', 'ne'),
                source

            ))
            self.logger.info(f"create_grievance: Successfully created grievance with ID: {grievance_id}")
            return True

        except Exception as e:
            if not complainant_id:
                self.logger.error(f"Missing complainant_id: {str(e)}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            elif not grievance_id: 
                self.logger.error(f"Missing grievance_id: {str(e)}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                self.logger.error(f"Error in create_grievance: {str(e)}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
            return False

    
    def update_grievance(self, grievance_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing grievance record"""
        try:
            self.logger.info(f"update_grievance: Updating grievance with ID: {grievance_id}")
            
            update_query = """
                    UPDATE grievances 
                    SET grievance_categories = %s,
                        grievance_summary = %s,
                        grievance_description = %s,
                        grievance_claimed_amount = %s,
                        grievance_location = %s,
                        language_code = %s,
                        grievance_modification_date = CURRENT_TIMESTAMP
                    WHERE grievance_id = %s
                    RETURNING grievance_id
                """
            result = self.execute_update(update_query, (
                    data.get('grievance_categories'),
                    data.get('grievance_summary'),
                    data.get('grievance_description'),
                    data.get('grievance_claimed_amount'),
                    data.get('grievance_location'),
                    data.get('language_code', 'ne'),
                    grievance_id
                ))
            self.logger.info(f"update_grievance: Updated grievance with ID: {grievance_id}, rows affected: {result}")
            return result > 0
            
        except Exception as e:
            self.logger.error(f"Error in update_grievance: {str(e)}")
            return False

    def get_grievance_by_id(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        query = """
                SELECT g.*, c.complainant_full_name, c.complainant_phone, c.complainant_email,
                       c.complainant_province, c.complainant_district, c.complainant_municipality,
                       c.complainant_ward, c.complainant_village, c.complainant_address
                FROM grievances g
                LEFT JOIN complainants c ON g.complainant_id = c.complainant_id
                WHERE g.grievance_id = %s
        """
        try:
            results = self.execute_query(query, (grievance_id,), "get_grievance_by_id")
            return results[0] if results else None
        except Exception as e:
            self.logger.error(f"Error retrieving grievance by ID: {str(e)}")
            return None
            
    def get_grievance_files(self, grievance_id: str) -> List[Dict]:
        query = """
            SELECT file_id, file_name, file_type, file_size, upload_timestamp
            FROM file_attachments
                WHERE grievance_id = %s
            ORDER BY upload_timestamp DESC
        """
        try:
            return self.execute_query(query, (grievance_id,), "get_grievance_files")
        except Exception as e:
            self.logger.error(f"Error retrieving grievance files: {str(e)}")
            return []

    def get_grievance_status(self, grievance_id: str, language: str = 'en') -> Optional[Dict]:
        query = """
                WITH latest_status AS (
                    SELECT status_code, assigned_to, notes, created_at
                    FROM grievance_status_history
                    WHERE grievance_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                SELECT 
                    h.status_code,
                    CASE WHEN %s = 'en' THEN s.status_name_en ELSE s.status_name_ne END as status_name,
                    CASE WHEN %s = 'en' THEN s.description_en ELSE s.description_ne END as description,
                    h.assigned_to,
                    h.notes,
                    h.created_at as status_date
                FROM latest_status h
                JOIN grievance_statuses s ON h.status_code = s.status_code
        """
        try:
            results = self.execute_query(query, (grievance_id, language, language), "get_grievance_status")
            return results[0] if results else None
        except Exception as e:
            self.logger.error(f"Error retrieving grievance status: {str(e)}")
            return None
            
    def update_grievance_status(self, grievance_id: str, status_code: str, created_by: str,
                              assigned_to: Optional[str] = None, notes: Optional[str] = None) -> bool:
        try:
            # Verify status code exists and is active
            status_check_query = """
                SELECT status_code FROM grievance_statuses
                WHERE status_code = %s AND is_active = true
            """
            status_check = self.execute_query(status_check_query, (status_code,), "check_status_code")
            if not status_check:
                self.logger.error(f"Invalid or inactive status code: {status_code}")
                return False
            # Add status history entry
            insert_query = """
                INSERT INTO grievance_status_history (
                    grievance_id, status_code, assigned_to,
                    notes, created_by
                ) VALUES (%s, %s, %s, %s, %s)
            """
            self.execute_update(insert_query, (
                grievance_id,
                status_code,
                assigned_to,
                notes,
                created_by
            ), "insert_status_history")
            # Update grievance modification date
            update_query = """
                UPDATE grievances SET
                    grievance_modification_date = CURRENT_TIMESTAMP
                WHERE grievance_id = %s
            """
            self.execute_update(update_query, (grievance_id,), "update_modification_date")
            return True
        except Exception as e:
            self.logger.error(f"Error updating grievance status: {str(e)}")
            return False
            
    def get_grievance_status_history(self, grievance_id: str, language: str = 'en') -> List[Dict]:
        query = """
                SELECT 
                    h.status_code,
                    CASE WHEN %s = 'en' THEN s.status_name_en ELSE s.status_name_ne END as status_name,
                    h.assigned_to,
                    h.notes,
                    h.created_by,
                    h.created_at
                FROM grievance_status_history h
                JOIN grievance_statuses s ON h.status_code = s.status_code
                WHERE h.grievance_id = %s
                ORDER BY h.created_at DESC
        """
        try:
            return self.execute_query(query, (language, grievance_id), "get_grievance_status_history")
        except Exception as e:
            self.logger.error(f"Error retrieving status history: {str(e)}")
            return []
            
    def get_available_statuses(self, language: str = 'en') -> List[Dict]:
        query = """
                SELECT 
                    status_code,
                    CASE WHEN %s = 'en' THEN status_name_en ELSE status_name_ne END as status_name,
                    CASE WHEN %s = 'en' THEN description_en ELSE description_ne END as description,
                    sort_order
                FROM grievance_statuses
                WHERE is_active = true
                ORDER BY sort_order
        """
        try:
            return self.execute_query(query, (language, language), "get_available_statuses")
        except Exception as e:
            self.logger.error(f"Error retrieving available statuses: {str(e)}")
            return []
            
    def get_grievance_history(self, grievance_id: str) -> List[Dict]:
        query = """
                SELECT id, grievance_id, previous_status, new_status,
                       next_step, notes, created_at
                FROM grievance_history
                WHERE grievance_id = %s
                ORDER BY created_at DESC
        """
        try:
            return self.execute_query(query, (grievance_id,), "get_grievance_history")
        except Exception as e:
            self.logger.error(f"Error retrieving grievance history: {str(e)}")
            return []

    def is_valid_grievance_id(self, grievance_id: str) -> bool:
        if not grievance_id or not isinstance(grievance_id, str):
            return False
        if not grievance_id.startswith('GR') or not grievance_id[2:].replace('-', '').isalnum():
            return False
        query = "SELECT COUNT(*) FROM grievances WHERE grievance_id = %s"
        try:
            results = self.execute_query(query, (grievance_id,), "is_valid_grievance_id")
            return results[0]['count'] > 0 if results else False
        except Exception as e:
            self.logger.error(f"Error validating grievance ID: {str(e)}")
            return False
  

class RecordingDbManager(BaseDatabaseManager):
    """Handles voice recording CRUD and lookup logic"""
    def create_recording(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new recording record - pure SQL function
        
        Args:
            data: Dictionary containing recording data including:
                - recording_id: ID of the recording (optional, will generate if not provided)
                - grievance_id: ID of the grievance (required)
                - file_path: Path to the recording file (required)
                - field_name: Name of the field being recorded (required)
                - file_size: Size of the file in bytes (optional)
                - duration_seconds: Duration of the recording in seconds (optional)
                - language_code: Language code (defaults to 'ne')
                - processing_status: Status of processing (defaults to 'pending')
                
        Returns:
            str: The recording_id if successful, None otherwise
        """
        try:
            if not data:
                data = dict()
            
            # Use provided recording_id or generate new one
            recording_id = data.get('recording_id') or str(uuid.uuid4())
            self.logger.info(f"create_recording: Creating recording with ID: {recording_id}")
            
            # Validate required fields
            required_fields = ['grievance_id', 'file_path', 'field_name']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                self.logger.error(f"Missing required fields: {missing_fields}")
                return None
            
            insert_query = """
                INSERT INTO grievance_voice_recordings (
                    recording_id, grievance_id, file_path,
                    field_name, file_size, duration_seconds,
                    processing_status, language_code
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING recording_id
            """
            result = self.execute_insert(insert_query, (
                recording_id,
                data['grievance_id'],
                data['file_path'],
                data['field_name'],
                data.get('file_size'),
                data.get('duration_seconds'),
                data.get('processing_status', 'pending'),
                data.get('language_code', 'ne')
            ))
            self.logger.info(f"create_recording: Successfully created recording with ID: {recording_id}")
            return result['recording_id'] if result else recording_id
            
        except Exception as e:
            self.logger.error(f"Error in create_recording: {str(e)}")
            return None

    def update_recording(self, recording_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing recording record - pure SQL function
        
        Args:
            recording_id: ID of the recording to update
            data: Dictionary containing fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.logger.info(f"update_recording: Updating recording with ID: {recording_id}")
            
            update_query = """
                UPDATE grievance_voice_recordings 
                SET file_path = %s,
                    field_name = %s,
                    file_size = %s,
                    duration_seconds = %s,
                    processing_status = %s,
                    language_code = %s,
                    language_code_detect = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE recording_id = %s
            """
            result = self.execute_update(update_query, (
                data.get('file_path'),
                data.get('field_name'),
                data.get('file_size'),
                data.get('duration_seconds'),
                data.get('processing_status'),
                data.get('language_code'),
                data.get('language_code_detect'),
                recording_id
            ))
            self.logger.info(f"update_recording: Updated recording with ID: {recording_id}, rows affected: {result}")
            return result > 0
            
        except Exception as e:
            self.logger.error(f"Error in update_recording: {str(e)}")
            return False

    def create_or_update_recording(self, recording_data: Dict) -> Optional[str]:
        """Create or update a voice recording record - business logic function
        
        This method:
        1. Checks if recording exists based on recording_id
        2. Calls create_recording or update_recording accordingly
        3. Validates required fields
        
        Args:
            recording_data: Dictionary containing recording data including:
                - recording_id: ID of the recording (optional for updates)
                - grievance_id: ID of the grievance (required)
                - file_path: Path to the recording file
                - field_name: Name of the field being transcribed
                - file_size: Size of the file in bytes
                - duration_seconds: Duration of the recording in seconds (optional)
                - language_code: Language code (defaults to 'ne')
                - processing_status: Status of processing (defaults to 'pending')
                
        Returns:
            str: The recording_id if successful, None otherwise
        """
        try:
            recording_id = recording_data.get('recording_id', None)
            grievance_id = recording_data.get('grievance_id', None)
            
            self.logger.info(f"create_or_update_recording: Handling recording with ID: {recording_id}")
            
            # Validate required fields
            if not grievance_id:
                self.logger.error("Missing required field: grievance_id")
                return None
                
            if not recording_data.get('file_path') or not recording_data.get('field_name'):
                self.logger.error("Missing required fields: file_path and field_name")
                return None
            
            # Check if recording actually exists in database (not just if recording_id is provided)
            existing_recording = None
            if recording_id:
                try:
                    check_query = "SELECT recording_id FROM grievance_voice_recordings WHERE recording_id = %s"
                    result = self.execute_query(check_query, (recording_id,), "check_recording_exists")
                    existing_recording = result[0] if result else None
                except Exception as e:
                    self.logger.warning(f"Could not check if recording exists: {str(e)}")
            
            if existing_recording and recording_id:
                # Recording exists, update it
                success = self.update_recording(recording_id, recording_data)
                return recording_id if success else None
            else:
                # Recording doesn't exist, create it
                # Generate new UUID if not provided or if provided UUID doesn't exist
                if not recording_id:
                    recording_data['recording_id'] = str(uuid.uuid4())
                return self.create_recording(recording_data)
            
        except Exception as e:
            self.logger.error(f"Error in create_or_update_recording: {str(e)}")
            return None

    def get_transcription_for_recording_id(self, recording_id: str) -> Dict[str, Any]:
        query = """
            SELECT grievance_id, language_code, automated_transcript, field_name
            FROM grievance_transcriptions 
            LEFT JOIN grievance_voice_recordings 
            ON grievance_transcriptions.recording_id = grievance_voice_recordings.recording_id 
            WHERE recording_id = %s
        """
        try:
            results = self.execute_query(query, (recording_id,), "get_grievance_transcription_for_recording_id")
            if results:
                return {
                    'grievance_id': results[0].get('grievance_id'),
                    'language_code': results[0].get('language_code'),
                    'automated_transcript': results[0].get('automated_transcript'),
                    'field_name': results[0].get('field_name')
                } 
            else:
                return {}
        except Exception as e:
            self.logger.error(f"Error retrieving grievance transcription for recording ID: {str(e)}")
            return {}

    def get_recording_id_for_grievance_id_and_field_name(self, grievance_id: str, field_name: str) -> Optional[str]:
        """Get recording ID for a specific grievance and field combination
        
        Args:
            grievance_id: ID of the grievance
            field_name: Name of the field being recorded
            
        Returns:
            str: The recording_id if found, None otherwise
        """
        query = """
            SELECT recording_id 
            FROM grievance_voice_recordings 
            WHERE grievance_id = %s AND field_name = %s
            ORDER BY created_at DESC 
            LIMIT 1
        """
        try:
            results = self.execute_query(query, (grievance_id, field_name), "get_recording_id_for_grievance_and_field")
            return results[0]['recording_id'] if results else None
        except Exception as e:
            self.logger.error(f"Error retrieving recording ID for grievance {grievance_id} and field {field_name}: {str(e)}")
            return None
        

        
class TranslationDbManager(BaseDatabaseManager):
    def create_translation(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new translation record - pure SQL function
        
        Args:
            data: Dictionary containing translation data including:
                - translation_id: ID of the translation (optional, will generate if not provided)
                - grievance_id: ID of the grievance (required)
                - grievance_description_en: English translation of details (optional)
                - grievance_summary_en: English translation of summary (optional)
                - grievance_categories_en: English translation of categories (optional)
                - translation_method: Method used for translation (required)
                - confidence_score: Confidence score of translation (optional)
                - source_language: Source language code (defaults to 'ne')
                
        Returns:
            str: The translation_id if successful, None otherwise
        """
        try:
            if not data:
                data = dict()
            
            # Validate required fields
            required_fields = ['grievance_id', 'translation_method']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if 'language_code' in data.keys() and 'source_language' not in data.keys():
                data['source_language'] = data['language_code']
            if missing_fields:
                self.logger.error(f"Missing required fields: {missing_fields}")
                return None
            
            insert_query = """
                INSERT INTO grievance_translations (
                    grievance_id, task_id, grievance_description_en, grievance_summary_en,
                    grievance_categories_en, source_language, translation_method,
                    confidence_score, verified_by, verified_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING translation_id
            """
            result = self.execute_insert(insert_query, (
                data['grievance_id'],
                data['task_id'],
                data.get('grievance_description_en'),
                data.get('grievance_summary_en'),
                data.get('grievance_categories_en'),
                data.get('source_language', 'ne'),
                data['translation_method'],
                data.get('confidence_score'),
                data.get('verified_by'),
                data.get('verified_at')
            ))
            self.logger.info(f"create_translation: Successfully created translation with ID: {result[0]['translation_id']}")
            return result[0]['translation_id'] if result else None
            
        except Exception as e:
            self.logger.error(f"Error in create_translation: {str(e)}")
            return None

    def update_translation(self, translation_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing translation record - pure SQL function
        
        Args:
            translation_id: ID of the translation to update
            data: Dictionary containing fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.logger.info(f"update_translation: Updating translation with ID: {translation_id}")
            
            update_query = """
                UPDATE grievance_translations 
                SET grievance_description_en = %s,
                    grievance_summary_en = %s,
                    grievance_categories_en = %s,
                    translation_method = %s,
                    confidence_score = %s,
                    source_language = %s,
                    verified_by = %s,
                    verified_at = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE translation_id = %s
            """
            result = self.execute_update(update_query, (
                data.get('grievance_description_en'),
                data.get('grievance_summary_en'),
                data.get('grievance_categories_en'),
                data.get('translation_method'),
                data.get('confidence_score'),
                data.get('source_language', 'ne'),
                data.get('verified_by'),
                data.get('verified_at'),
                translation_id
            ))
            self.logger.info(f"update_translation: Updated translation with ID: {translation_id}, rows affected: {result}")
            return result > 0
            
        except Exception as e:
            self.logger.error(f"Error in update_translation: {str(e)}")
            return False

    def create_or_update_translation(self, data: Dict[str, Any]) -> Optional[str]:
        """Create or update a translation record - business logic function
        
        This method:
        1. Checks if translation exists based on translation_id or grievance_id + translation_method
        2. Calls create_translation or update_translation accordingly
        3. Validates allowed fields
        
        Args:
            data: Dictionary containing translation data
            
        Returns:
            str: The translation_id if successful, None otherwise
        """
        try:
            if not data:
                data = dict()
            
            translation_id = data.get('translation_id')
            grievance_id = data.get('grievance_id')
            translation_method = data.get('translation_method')
            
            self.logger.info(f"create_or_update_translation: Handling translation with ID: {translation_id}")
            
            # Validate required fields
            if not grievance_id:
                self.logger.error("Missing required field: grievance_id")
                return None

            # Validate allowed fields
            allowed_fields = {
                'translation_id',
                'grievance_id',
                'grievance_description_en',
                'grievance_summary_en',
                'grievance_categories_en',
                'translation_method',
                'confidence_score',
                'source_language',
                'verified_by',
                'verified_at'
            }
            invalid_fields = set(data.keys()) - allowed_fields
            if invalid_fields:
                self.logger.error(f"Attempted to update invalid translation fields: {invalid_fields}")
                return None
            
            # Check if translation exists
            existing_translation = None
            
            if translation_id:
                # Check by translation_id first
                check_query = """
                    SELECT translation_id FROM grievance_translations 
                    WHERE translation_id = %s
                """
                result = self.execute_query(check_query, (translation_id,), "check_translation_by_id")
                existing_translation = result[0] if result else None
            
            if not existing_translation and grievance_id and translation_method:
                # Check by grievance_id and translation_method
                check_query = """
                    SELECT translation_id FROM grievance_translations 
                    WHERE grievance_id = %s AND translation_method = %s
                """
                result = self.execute_query(check_query, (grievance_id, translation_method), "check_translation_by_grievance_method")
                existing_translation = result[0] if result else None
            elif not existing_translation and grievance_id:
                # Check by grievance_id only (for backwards compatibility)
                check_query = """
                    SELECT translation_id FROM grievance_translations 
                    WHERE grievance_id = %s
                """
                result = self.execute_query(check_query, (grievance_id,), "check_translation_by_grievance")
                existing_translation = result[0] if result else None
            
            if existing_translation:
                # Translation exists, update it
                actual_translation_id = existing_translation['translation_id']
                success = self.update_translation(actual_translation_id, data)
                return actual_translation_id if success else None
            else:
                # Translation doesn't exist, create it
                return self.create_translation(data)
                
        except Exception as e:
            self.logger.error(f"Error in create_or_update_translation: {str(e)}")
            return None
    


class TranscriptionDbManager(BaseDatabaseManager):
    def create_transcription(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new transcription record - pure SQL function
        
        Args:
            data: Dictionary containing transcription data including:
                - transcription_id: ID of the transcription (optional, will generate if not provided)
                - recording_id: ID of the recording (required)
                - grievance_id: ID of the grievance (required)
                - field_name: Name of the field being transcribed (required)
                - automated_transcript: The transcription text (required)
                - language_code: Language code (defaults to 'ne')
                
        Returns:
            str: The transcription_id if successful, None otherwise
        """
        try:
            if not data:
                data = dict()
            
            # Validate required fields
            required_fields = ['recording_id', 'grievance_id', 'field_name', 'automated_transcript']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                self.logger.error(f"Missing required fields: {missing_fields}")
                return None
            
            insert_query = """
                INSERT INTO grievance_transcriptions (
                    recording_id, grievance_id, field_name, automated_transcript,
                    verified_transcript, verification_status, confidence_score,
                    verification_notes, verified_by, verified_at, language_code,
                    language_code_detect, task_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING transcription_id
            """
            result = self.execute_insert(insert_query, (
                data['recording_id'],
                data['grievance_id'],
                data['field_name'],
                data['automated_transcript'],
                data.get('verified_transcript'),
                data.get('verification_status', 'PENDING'),
                data.get('confidence_score'),
                data.get('verification_notes', 'by default, verification is pending'),
                data.get('verified_by'),
                data.get('verified_at'),
                data.get('language_code', 'ne'),
                data.get('language_code_detect'),
                data['task_id']
            ))
            self.logger.info(f"create_transcription: Successfully created transcription with ID: {result[0]['transcription_id']}")
            return result[0]['transcription_id'] if result else None
            
        except Exception as e:
            self.logger.error(f"Error in create_transcription: {str(e)}")
            return None

    def update_transcription(self, transcription_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing transcription record - pure SQL function
        
        Args:
            transcription_id: ID of the transcription to update
            data: Dictionary containing fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.logger.info(f"update_transcription: Updating transcription with ID: {transcription_id}")
            
            update_query = """
                UPDATE grievance_transcriptions 
                SET automated_transcript = %s,
                    verified_transcript = %s,
                    language_code = %s,
                    confidence_score = %s,
                    verification_notes = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE transcription_id = %s
            """
            result = self.execute_update(update_query, (
                data.get('automated_transcript'),
                data.get('verified_transcript'),
                data.get('language_code', 'ne'),
                data.get('confidence_score'),
                data.get('verification_notes'),
                transcription_id
            ))
            self.logger.info(f"update_transcription: Updated transcription with ID: {transcription_id}, rows affected: {result}")
            return result > 0
            
        except Exception as e:
            self.logger.error(f"Error in update_transcription: {str(e)}")
            return False

    def create_or_update_transcription(self, data: Dict[str, Any]) -> Optional[str]:
        """Create or update a transcription record - business logic function
        
        This method:
        1. Checks if transcription exists based on transcription_id or recording_id
        2. Calls create_transcription or update_transcription accordingly
        3. Handles lookup of recording_id if needed
        
        Args:
            data: Dictionary containing transcription data
            
        Returns:
            str: The transcription_id if successful, None otherwise
        """
        try:
            if not data:
                data = dict()
            
            transcription_id = data.get('transcription_id')
            recording_id = data.get('recording_id')
            
            self.logger.info(f"create_or_update_transcription: Handling transcription with ID: {transcription_id}")
            
            # If no recording_id provided, try to find it
            if not recording_id:
                if (data.get('grievance_id') and data.get('field_name')):
                    # Use the recording manager to get recording_id
                    recording_manager = RecordingDbManager()
                    recording_id = recording_manager.get_recording_id_for_grievance_id_and_field_name(
                        data['grievance_id'], 
                        data['field_name']
                    )
                    if recording_id:
                        data['recording_id'] = recording_id
                    else:
                        self.logger.error("Could not find recording_id for given grievance_id and field_name")
                        return None
                else:
                    self.logger.error("Missing required fields: recording_id or (grievance_id + field_name)")
                    return None
            
            # Check if transcription exists
            existing_transcription = None
            
            if transcription_id:
                # Check by transcription_id first
                check_query = """
                    SELECT transcription_id FROM grievance_transcriptions 
                    WHERE transcription_id = %s
                """
                result = self.execute_query(check_query, (transcription_id,), "check_transcription_by_id")
                existing_transcription = result[0] if result else None
            
            if not existing_transcription and recording_id:
                # Check by recording_id
                check_query = """
                    SELECT transcription_id FROM grievance_transcriptions 
                    WHERE recording_id = %s
                """
                result = self.execute_query(check_query, (recording_id,), "check_transcription_by_recording")
                existing_transcription = result[0] if result else None
            
            if existing_transcription:
                # Transcription exists, update it
                actual_transcription_id = existing_transcription['transcription_id']
                success = self.update_transcription(actual_transcription_id, data)
                return actual_transcription_id if success else None
            else:
                # Transcription doesn't exist, create it
                return self.create_transcription(data)
                
        except Exception as e:
            self.logger.error(f"Error in create_or_update_transcription: {str(e)}")
            return None