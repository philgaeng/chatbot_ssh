import uuid
import logging
from typing import Dict, List, Optional, Any
import traceback
from .base_manager import BaseDatabaseManager
from backend.config.constants import TRANSCRIPTION_PROCESSING_STATUS


# Whitelist of fields that can be updated
ALLOWED_UPDATE_FIELDS = [
        'complainant_id',
        'grievance_categories',
        'grievance_categories_alternative',
        'follow_up_question',
        'grievance_summary',
        'grievance_sensitive_issue',
        'grievance_high_priority',
        'grievance_description',
        'grievance_claimed_amount',
        'grievance_location',
        'is_temporary',
        'source',
        'language_code',
        'grievance_classification_status'
    ]

class GrievanceDbManager(BaseDatabaseManager):
    """Handles grievance CRUD and business logic"""
    

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def create_grievance(self, data: Dict[str, Any], source: str = 'bot') -> None:
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
            allowed_fields = ['grievance_id'] + ALLOWED_UPDATE_FIELDS
           
            self.logger.info(f"create_grievance: Creating grievance with allowed fields: {allowed_fields}")
            self.execute_insert(table_name='grievances', input_data=data, allowed_fields=allowed_fields, returning = 'grievance_id')

            self.logger.info(f"create_grievance: Successfully created grievance with ID: {grievance_id}")

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

    
    def update_grievance(self, grievance_id: str, data: Dict[str, Any]) -> int:
        """Update an existing grievance record"""
        try:
            self.logger.info(f"update_grievance: Updating grievance with ID: {grievance_id}")
            expected_fields = ['grievance_categories', 'grievance_categories_alternative', 'grievance_summary', 'grievance_description', 'grievance_claimed_amount', 'grievance_location', 'language_code', 'follow_up_question', 'grievance_sensitive_issue', 'grievance_high_priority']
            update_fields, update_values = self.generate_update_query(data, expected_fields)

            if update_fields and update_values:
            
                # Always update the modification date
                update_fields.append("grievance_modification_date = CURRENT_TIMESTAMP")
                
                # Build the complete query
                update_query = f"""
                    UPDATE grievances 
                    SET {', '.join(update_fields)}
                    WHERE grievance_id = %s
                    RETURNING grievance_id
                """
                
                # Add grievance_id to the values tuple
                update_values.append(grievance_id)
                
                affected_rows = self.execute_update(update_query, tuple(update_values))
                self.logger.info(f"update_grievance: Updated grievance with ID: {grievance_id}, rows affected: {affected_rows}")
                return affected_rows
            else:
                self.logger.warning(f"update_grievance: No fields to update for this query: {data} with expected fields: {expected_fields} for grievance_id: {grievance_id}")
                return False
            
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
            if results:
                # Parse the result to convert JSON fields back to Python objects
                parsed_result = self._parse_database_result(results[0])
                self.logger.debug(f"get_grievance_by_id: grievance_id: {parsed_result}, results: {results}")
                return parsed_result
            return None
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


    def get_grievance_status(self, grievance_id: str) -> Optional[Dict]:
        query = """
                WITH latest_status AS (
                    SELECT status_code, assigned_to, notes, created_at, grievance_id
                    FROM grievance_status_history
                    WHERE grievance_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                SELECT 
                    h.status_code,
                    CASE WHEN %s = 'en' THEN s.status_name_en ELSE s.status_name_ne END as status_name,
                    h.assigned_to,
                    h.notes,
                    h.created_at as status_date
                FROM latest_status h
                JOIN grievance_statuses s ON h.status_code = s.status_code
        """
        try:
            self.logger.debug(f"get_grievance_status: grievance_id: {grievance_id}, language: {self.DEFAULT_LANGUAGE_CODE}")
            results = self.execute_query(query, (grievance_id, self.DEFAULT_LANGUAGE_CODE), "get_grievance_status")
            return results[0] if results else None
        except Exception as e:
            self.logger.error(f"Error retrieving grievance status: {str(e)}")
            return None
            
    def update_grievance_status(self, grievance_id: str, status_code: str, 
                                created_by: Optional[str] = None,
                              assigned_to: Optional[str] = None, notes: Optional[str] = None) -> bool:
        try:
            if created_by is None:
                created_by = self.DEFAULT_USER
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
            self.execute_insert(table_name='grievance_status_history', input_data={
                'grievance_id': grievance_id,
                'status_code': status_code,
                'assigned_to': assigned_to,
                'notes': notes,
                'created_by': created_by
            })
            # Update grievance modification date
            update_query = """
                UPDATE grievances SET
                    grievance_modification_date = CURRENT_TIMESTAMP
                WHERE grievance_id = %s
            """
            self.execute_update(update_query, (grievance_id,))
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

    def get_grievance_by_complainant_phone(self, phone_number: str) -> List[Dict[str, Any]]:
        # Encrypt the phone number for search if encryption is enabled
        self.logger.debug(f"original phone number: {phone_number}")
        standardized_phone = self._standardize_phone_number(phone_number)
        search_phone = self._hash_value(standardized_phone) if self.encryption_key else standardized_phone
        self.logger.debug(f"hashed phone number: {search_phone}")
        
        # Add debug logging to track the hash
        self.logger.debug(f"Phone number '{standardized_phone}' hashed to '{search_phone}' in search")
        
        query = """
            WITH latest_status AS (
                SELECT DISTINCT ON (grievance_id) 
                    grievance_id,
                    status_code as grievance_status,
                    created_at as grievance_status_update_date
                FROM grievance_status_history
                ORDER BY grievance_id, created_at DESC
            )
            SELECT 
                g.grievance_id,
                g.grievance_creation_date,
                g.grievance_timeline,
                g.grievance_categories,
                c.complainant_full_name,
                c.complainant_phone,
                ls.grievance_status,
                ls.grievance_status_update_date
            FROM complainants c
            INNER JOIN grievances g ON c.complainant_id = g.complainant_id
            LEFT JOIN latest_status ls ON g.grievance_id = ls.grievance_id
            WHERE c.complainant_phone_hash = %s
            ORDER BY g.grievance_creation_date DESC, ls.grievance_status_update_date DESC
        """
        try:
            self.logger.debug(f"search_phone at query time: {search_phone}")
            results = self.execute_query(query, (search_phone,), "get_complainants_by_phone_number")
            # Decrypt sensitive fields in results
            decrypted_results = []
            self.logger.debug(f"{len(results)} complainants found")
            self.logger.debug(f"results: {results}")
            for complainant in results:
                decrypted_results.append(self._decrypt_sensitive_data(complainant))
            self.logger.debug(f"{len(decrypted_results)} complainants successfully decrypted")
            self.logger.debug(f"decrypted results: {decrypted_results}")
            return decrypted_results
        except Exception as e:
            self.logger.error(f"Error retrieving complainants by phone number: {str(e)}")
            return []
  

class RecordingDbManager(BaseDatabaseManager):
    """Handles voice recording CRUD and lookup logic"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_recording_by_id(self, recording_id: str) -> Optional[Dict[str, Any]]:
        """Get recording by ID"""
        query = "SELECT * FROM grievance_voice_recordings WHERE recording_id = %s"
        try:
            results = self.execute_query(query, (recording_id,), "get_recording_by_id")
            return results[0] if results else None
        except Exception as e:
            self.logger.error(f"Error retrieving recording by ID: {str(e)}")
            return None
        
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
            recording_id = data.get('recording_id')
            if not recording_id:
                recording_id = self.generate_id('recording_id')
                data['recording_id'] = recording_id
                self.logger.info(f"create_recording: Generated recording ID: {recording_id}")
            self.logger.info(f"create_recording: Creating recording with ID: {recording_id}")
            
            # Validate required fields
            required_fields = ['grievance_id', 'file_path', 'field_name']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                self.logger.error(f"Missing required fields: {missing_fields}")
                return None
            allowed_fields = ['recording_id', 'grievance_id', 'file_path', 'field_name', 'file_size', 'duration_seconds', 'processing_status', 'language_code']

            #execute the upsert query
            result = self.execute_insert(table_name='grievance_voice_recordings', input_data=data, allowed_fields=allowed_fields, returning = None)

            self.logger.info(f"create_recording: Successfully created recording with ID: {recording_id}")
            return recording_id if result else None
            
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def get_translation_by_id(self, translation_id: str) -> Optional[Dict[str, Any]]:
        """Get translation by ID"""
        query = "SELECT * FROM grievance_translations WHERE translation_id = %s"
        try:
            results = self.execute_query(query, (translation_id,), "get_translation_by_id")
            return results[0] if results else None
        except Exception as e:
            self.logger.error(f"Error retrieving translation by ID: {str(e)}")
            return None
        
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
            translation_id = data.get('translation_id') if data.get('translation_id') else self.generate_id('translation_id')
            if not data.get('translation_id'):
                data['translation_id'] = translation_id
                self.logger.info(f"create_translation: Generated translation ID: {translation_id}")
               
            
            # Validate required fields
            required_fields = ['grievance_id', 'translation_method']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if 'language_code' in data.keys() and 'source_language' not in data.keys():
                data['source_language'] = data['language_code']
            if missing_fields:
                self.logger.error(f"Missing required fields: {missing_fields}")
                return None
            allowed_fields = ['translation_id', 'grievance_id', 'task_id', 'grievance_description_en', 'grievance_summary_en', 'grievance_categories_en', 'source_language', 'translation_method', 'confidence_score', 'verified_by', 'verified_at']
            query_data = self.select_query_data(data, allowed_fields)
            values = self.generate_values_tuple(query_data)
            conflict_fields = ['grievance_summary_en', 'grievance_description_en', 'grievance_categories_en']
            query_values = f"INSERT INTO grievance_translations ({', '.join(query_data.keys())}) VALUES ({', '.join(['%s'] * len(values))})"
            self.logger.debug(f"create_translation: Query values: {query_values}")
            query_conflict = f" ON CONFLICT (translation_id) DO UPDATE SET {', '.join([f'{key} = EXCLUDED.{key}' for key in conflict_fields if key in query_data.keys()])} RETURNING translation_id"
            self.logger.debug(f"create_translation: Query conflict: {query_conflict}")
            query = query_values + query_conflict
            self.logger.debug(f"create_translation: Query: {query}")
            result = self.execute_query(query, values, "create_translation")
            if result:
                self.logger.info(f"create_translation: Successfully created translation with ID: {result[0]['translation_id']}")
                return result[0]['translation_id']
            else:   
                self.logger.error(f"Error in create_translation: No result returned")
                return None
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



class TranscriptionDbManager(BaseDatabaseManager):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.transcription_processing_status = TRANSCRIPTION_PROCESSING_STATUS

    def get_transcription_by_id(self, transcription_id: str) -> Optional[Dict[str, Any]]:
        """Get transcription by ID"""
        query = "SELECT * FROM grievance_transcriptions WHERE transcription_id = %s"
        try:
            results = self.execute_query(query, (transcription_id,), "get_transcription_by_id")
            return results[0] if results else None
        except Exception as e:
            self.logger.error(f"Error retrieving transcription by ID: {str(e)}")
            return None
        
    def create_transcription(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new transcription record - pure SQL function
        
        Args:
            data: Dictionary containing transcription data including:
                - transcription_id: ID of the transcription (optional, will generate if not provided)
                - recording_id: ID of the recording (required)
                - grievance_id: ID of the grievance (required)
                - field_name: Name of the field being transcribed (required)
                - automated_transcript: The transcription text (required)
                - language_code: Language code (defaults to 'ne'),
                - verification_status: Status of verification (defaults to DEFAULT_VERIFICATION_STATUS['FOR_VERIFICATION'])
                
        Returns:
            str: The transcription_id if successful, None otherwise
        """
        try:
            if not data.get('transcription_id'):
                data['transcription_id'] = self.generate_id('transcription_id')
            transcription_id = data.get('transcription_id')
            #update the verification status if not provided
            if not data.get('verification_status'):
                data['verification_status'] = self.transcription_processing_status['FOR_VERIFICATION']
            # Validate required fields
            required_fields = ['transcription_id', 'recording_id', 'grievance_id', 'field_name', 'automated_transcript']
            allowed_fields = ['transcription_id', 'recording_id', 'grievance_id', 'field_name', 'automated_transcript', 'verified_transcript', 'verification_status', 'confidence_score', 'verification_notes', 'verified_by', 'verified_at', 'language_code', 'language_code_detect', 'task_id']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                self.logger.error(f"Missing required fields: {missing_fields}")
                return None
            #execute the upsert query
            self.execute_insert(table_name='grievance_transcriptions', input_data=data, allowed_fields=allowed_fields)

            self.logger.info(f"create_transcription: Successfully created transcription with ID: {transcription_id}")
            return  transcription_id
            
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

    def get_office_emails_for_grievance(self, grievance_id: str) -> List[str]:
        """
        Get email addresses of offices responsible for a grievance
        Args:
            grievance_id: The ID of the grievance
        Returns:
            List of email addresses
        """
        try:
            # Get the grievance's municipality to find responsible office
            grievance_query = """
                SELECT c.complainant_municipality
                FROM grievances g
                JOIN complainants c ON g.complainant_id = c.complainant_id
                WHERE g.grievance_id = %s
            """
            grievance_result = self.execute_query(grievance_query, (grievance_id,), "get_grievance_municipality")
            
            if not grievance_result:
                return []
            
            municipality = grievance_result[0]['complainant_municipality']
            
            # Get emails for:
            # 1. PD Office (always included)
            # 2. Office responsible for the municipality
            email_query = """
                SELECT DISTINCT ou.email
                FROM office_user ou
                JOIN office_management om ON ou.office_id = om.office_id
                WHERE om.office_id = 'pd_office' 
                   OR om.office_id IN (
                       SELECT DISTINCT omw.office_id 
                       FROM office_municipality_ward omw 
                       WHERE LOWER(omw.municipality) LIKE LOWER(%s)
                   )
                AND ou.email IS NOT NULL
                AND ou.email != ''
            """
            
            # Use ILIKE with wildcards for municipality matching
            municipality_pattern = f"%{municipality}%"
            email_results = self.execute_query(email_query, (municipality_pattern,), "get_office_emails")
            
            return [result['email'] for result in email_results if result['email']]
            
        except Exception as e:
            self.logger.error(f"Error getting office emails for grievance {grievance_id}: {str(e)}")
            return []
