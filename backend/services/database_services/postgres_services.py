

from typing import Dict, List, Optional, Any, TypeVar, Generic
import traceback
import json
from datetime import datetime
import uuid

# Import database configuration from constants.py (single source of truth)
from backend.config.constants import DB_CONFIG, DEFAULT_VALUES

DEFAULT_PROVINCE = DEFAULT_VALUES["DEFAULT_PROVINCE"]
DEFAULT_DISTRICT = DEFAULT_VALUES["DEFAULT_DISTRICT"]
DEFAULT_LANGUAGE_CODE = DEFAULT_VALUES["DEFAULT_LANGUAGE_CODE"]

# Import base manager for inheritance
from .base_manager import BaseDatabaseManager
from backend.logger import logger


def seah_party_role_from_victim_survivor_role(
    seah_victim_survivor_role: Optional[str],
) -> Optional[str]:
    """
    Map slot seah_victim_survivor_role to grievance_parties.party_role.
    """
    if not seah_victim_survivor_role:
        return "victim_survivor"
    r = str(seah_victim_survivor_role).strip()
    if r == "victim_survivor":
        return "victim_survivor"
    if r == "not_victim_survivor":
        return "relative_or_representative"
    if r == "focal_point":
        return "seah_focal_point"
    return "victim_survivor"


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
        return self.generate_id(type='complainant_id', province=province, district=district, office=office, source=source)
    
    def generate_grievance_id(self, data: Dict[str, Any]) -> Optional[str]:
        """Create a new grievance ID"""
        province = data.get('complainant_province', DEFAULT_PROVINCE)
        district = data.get('complainant_district', DEFAULT_DISTRICT)
        office = data.get('complainant_office', None)
        source = data.get('source', 'bot')
        return self.generate_id(type='grievance_id', province=province, district=district, office=office, source=source)
    
    
    
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

    def get_complainant_data_by_grievance_id(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get complainant data by grievance id"""
        complainant_id = self.complainant.get_complainant_id_from_grievance_id(grievance_id)
        if complainant_id:
            return self.complainant.get_complainant_by_id(complainant_id)
        else:
            return None
        
    
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

            # Ensure canonical party linkage exists for standard submissions.
            self.execute_update(
                """
                INSERT INTO grievance_parties (
                    party_id,
                    grievance_id,
                    complainant_id,
                    party_role,
                    is_primary_reporter,
                    contact_allowed,
                    notes_safe
                )
                SELECT %s, %s, %s, 'victim_survivor', TRUE, TRUE, 'default party from standard submit'
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM grievance_parties gp
                    WHERE gp.grievance_id = %s
                      AND gp.is_primary_reporter = TRUE
                )
                """,
                (f"party-{uuid.uuid4()}", grievance_id, complainant_id, grievance_id),
            )

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

    def _ensure_seah_contact_points_table(self) -> None:
        """Reference rows for SEAH center / referral text (spec 08)."""
        ddl = """
            CREATE TABLE IF NOT EXISTS seah_contact_points (
                seah_contact_point_id TEXT PRIMARY KEY,
                province TEXT,
                district TEXT,
                municipality TEXT,
                ward TEXT,
                project_uuid TEXT,
                seah_center_name TEXT NOT NULL,
                address TEXT,
                phone TEXT,
                opening_days TEXT,
                opening_hours TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                sort_order INTEGER DEFAULT 0
            );
        """
        self.execute_update(ddl, ())
        seed = """
            INSERT INTO seah_contact_points (
                seah_contact_point_id, province, district, municipality, ward, project_uuid,
                seah_center_name, address, phone, opening_days, opening_hours, is_active, sort_order
            ) VALUES (
                'default-national-seah',
                NULL, NULL, NULL, NULL, NULL,
                'SEAH Information Desk',
                'Contact your nearest ADB SEAH focal point or national support line.',
                '',
                'Monday to Friday',
                '09:00–17:00 (placeholder)',
                TRUE,
                0
            ) ON CONFLICT (seah_contact_point_id) DO NOTHING;
        """
        try:
            self.execute_update(seed, ())
        except Exception as e:
            self.logger.warning(f"seah_contact_points seed skipped: {e}")

    def find_seah_contact_point(
        self,
        province: Optional[str],
        district: Optional[str] = None,
        municipality: Optional[str] = None,
        ward: Optional[str] = None,
        project_uuid: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Best-effort lookup for outro referral block (spec 08)."""
        self._ensure_seah_contact_points_table()
        p = (province or "").strip().lower()
        rows: List[Dict[str, Any]] = []
        try:
            if p:
                rows = self.execute_query(
                    """
                    SELECT * FROM seah_contact_points
                    WHERE is_active = TRUE
                      AND (
                        province IS NULL
                        OR LOWER(TRIM(province)) = %s
                      )
                    ORDER BY CASE WHEN province IS NULL THEN 1 ELSE 0 END,
                             sort_order NULLS LAST, seah_contact_point_id
                    """,
                    (p,),
                )
            else:
                rows = self.execute_query(
                    """
                    SELECT * FROM seah_contact_points
                    WHERE is_active = TRUE AND province IS NULL
                    ORDER BY sort_order NULLS LAST, seah_contact_point_id
                    """,
                    (),
                )
        except Exception as e:
            self.logger.error(f"find_seah_contact_point: {e}")
            return None

        if not rows and p:
            try:
                rows = self.execute_query(
                    """
                    SELECT * FROM seah_contact_points
                    WHERE is_active = TRUE AND province IS NULL
                    ORDER BY sort_order NULLS LAST, seah_contact_point_id
                    """,
                    (),
                )
            except Exception:
                return None

        if not rows:
            return None

        def score(r: Dict[str, Any]) -> int:
            s = 0
            if project_uuid and r.get("project_uuid") and str(r["project_uuid"]).strip() == str(project_uuid).strip():
                s += 100
            if ward and r.get("ward") and str(r["ward"]).strip() == str(ward).strip():
                s += 40
            if municipality and r.get("municipality") and str(r["municipality"]).lower() == str(municipality).lower():
                s += 30
            if district and r.get("district") and str(r["district"]).lower() == str(district).lower():
                s += 20
            if p and r.get("province") and str(r["province"]).lower() == p:
                s += 10
            if r.get("province") is None:
                s += 1
            return s

        best = max(rows, key=lambda r: (score(r), -(r.get("sort_order") or 0)))
        return best

    def submit_seah_to_db(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Persist SEAH intake in canonical public tables only."""
        try:
            not_provided = DEFAULT_VALUES.get("NOT_PROVIDED", "Not provided")
            grievance_id = data.get("grievance_id")
            if grievance_id in (None, "", not_provided):
                grievance_id = self.generate_grievance_id(data)

            anonymous_route = bool(data.get("seah_anonymous_route"))
            complainant_id = data.get("complainant_id")
            has_identity = any(
                data.get(k) not in (None, "", not_provided)
                for k in ("complainant_full_name", "complainant_phone", "complainant_email")
            )
            if complainant_id in (None, "", not_provided):
                complainant_id = None if anonymous_route and not has_identity else self.generate_complainant_id(data)

            if complainant_id:
                complainant_payload = {
                    "complainant_id": complainant_id,
                    "complainant_full_name": data.get("complainant_full_name"),
                    "complainant_phone": data.get("complainant_phone"),
                    "complainant_email": data.get("complainant_email"),
                    "complainant_province": data.get("complainant_province"),
                    "complainant_district": data.get("complainant_district"),
                    "complainant_municipality": data.get("complainant_municipality"),
                    "complainant_ward": data.get("complainant_ward"),
                    "complainant_village": data.get("complainant_village"),
                    "complainant_address": data.get("complainant_address"),
                    "contact_id": data.get("contact_id"),
                    "country_code": data.get("country_code"),
                    "location_code": data.get("location_code"),
                    "location_resolution_status": data.get("location_resolution_status"),
                    "level_1_name": data.get("level_1_name"),
                    "level_2_name": data.get("level_2_name"),
                    "level_3_name": data.get("level_3_name"),
                    "level_4_name": data.get("level_4_name"),
                    "level_5_name": data.get("level_5_name"),
                    "level_6_name": data.get("level_6_name"),
                    "level_1_code": data.get("level_1_code"),
                    "level_2_code": data.get("level_2_code"),
                    "level_3_code": data.get("level_3_code"),
                    "level_4_code": data.get("level_4_code"),
                    "level_5_code": data.get("level_5_code"),
                    "level_6_code": data.get("level_6_code"),
                }
                if self.complainant.get_complainant_by_id(complainant_id):
                    self.complainant.update_complainant(complainant_id, complainant_payload)
                else:
                    self.complainant.create_complainant(complainant_payload)

            grievance_payload = {
                "grievance_id": grievance_id,
                "complainant_id": complainant_id,
                "grievance_summary": data.get("grievance_summary"),
                "grievance_categories": data.get("grievance_categories"),
                "grievance_sensitive_issue": True,
                "grievance_description": None,
                "grievance_location": data.get("grievance_location"),
                "grievance_timeline": str(data.get("grievance_timeline") or ""),
                "grievance_classification_status": data.get("grievance_status"),
                "source": "seah_intake",
                "language_code": data.get("language_code", "en"),
                "case_sensitivity": "seah",
            }
            if self.grievance.get_grievance_by_id(grievance_id):
                self.grievance.update_grievance(grievance_id, grievance_payload)
            else:
                self.grievance.create_grievance(grievance_payload)

            party_role = seah_party_role_from_victim_survivor_role(data.get("seah_victim_survivor_role"))
            party_id = f"party-{uuid.uuid4()}"
            self.execute_update(
                """
                DELETE FROM grievance_parties
                WHERE grievance_id = %s
                  AND is_primary_reporter = TRUE
                """,
                (grievance_id,),
            )
            self.execute_update(
                """
                INSERT INTO grievance_parties (
                    party_id,
                    grievance_id,
                    complainant_id,
                    party_role,
                    is_primary_reporter,
                    contact_allowed,
                    contact_channel,
                    consent_scope,
                    notes_safe
                )
                VALUES (%s, %s, %s, %s, TRUE, %s, %s::jsonb, %s::jsonb, %s)
                """,
                (
                    party_id,
                    grievance_id,
                    complainant_id,
                    party_role,
                    False if anonymous_route else True,
                    json.dumps({"channel": data.get("seah_contact_consent_channel")}),
                    json.dumps({"complainant_consent": data.get("complainant_consent")}),
                    "primary reporter from seah submit path",
                ),
            )

            grievance_description = data.get("grievance_description")
            if grievance_description not in (None, "", not_provided):
                vault_payload_id = f"vault-{uuid.uuid4()}"
                self.execute_update(
                    """
                    INSERT INTO grievance_vault_payloads (
                        vault_payload_id,
                        grievance_id,
                        case_sensitivity,
                        payload_type,
                        content_ciphertext,
                        source_channel,
                        source_language_code,
                        created_by
                    )
                    VALUES (%s, %s, 'seah', 'original_grievance', %s, 'chatbot', %s, %s)
                    """,
                    (vault_payload_id, grievance_id, grievance_description, data.get("language_code", "en"), self.DEFAULT_USER),
                )
                self.grievance.update_grievance(
                    grievance_id,
                    {
                        "vault_payload_ref": vault_payload_id,
                        "vault_last_updated_at": datetime.now(),
                        "case_sensitivity": "seah",
                    },
                )

            return {
                "ok": True,
                "complainant_id": complainant_id,
                "grievance_id": grievance_id,
            }
        except Exception as e:
            self.logger.error(f"Error submitting SEAH grievance to db: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return {"ok": False, "error": str(e)}
            
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
                grievance_id = self.create_grievance(data)
            return grievance_id
        except Exception as e:
            self.logger.error(f"Error creating or updating grievance: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
            
    
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

    def get_grievance_id_by_last_6_characters(self, text_standardized: str) -> str:
        """Get grievance ID by last 6 characters"""
        return self.grievance.get_grievance_id_by_last_6_characters(text_standardized)
    
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


    