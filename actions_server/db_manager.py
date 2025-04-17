import os
import uuid
import psycopg2
import psycopg2.extras
import logging
from datetime import datetime
import pytz
from typing import Dict, List, Optional, Any
from psycopg2.extras import DictCursor
from dotenv import load_dotenv
import json
import traceback

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """PostgreSQL database manager class"""
    def __init__(self, nepal_tz: Optional[pytz.timezone] = None, default_value: str = 'NOT_PROVIDED'):
        # Common attributes
        self.nepal_tz = nepal_tz or pytz.timezone('Asia/Kathmandu')
        self.default_value = default_value
        
        # Database connection parameters
        self.db_params = {
            'host': os.environ.get('POSTGRES_HOST'),
            'database': os.environ.get('POSTGRES_DB'),
            'user': os.environ.get('POSTGRES_USER'),
            'password': os.environ.get('POSTGRES_PASSWORD'),
            'port': os.environ.get('POSTGRES_PORT')
        }

    def get_connection(self):
        """Get PostgreSQL connection"""
        try:
            logger.info(f"Connecting to PostgreSQL database with params: host={self.db_params['host']}, database={self.db_params['database']}, port={self.db_params['port']}")
            return psycopg2.connect(
                **self.db_params,
                cursor_factory=DictCursor
            )
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def generate_grievance_id(self, source: str = 'bot') -> str:
        """Generate a unique grievance ID using Nepal time and UUID.
        
        Args:
            source (str): Source of the grievance - 'accessibility' or 'bot'
            
        Returns:
            str: A unique grievance ID in the format GR{YYYYMMDD}{UUID[:6]}_{A|B}
        """
        suffix = '_A' if source == 'accessibility' else '_B'
        return f"GR{datetime.now(self.nepal_tz).strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}{suffix}"

    def init_db(self):
        """Initialize PostgreSQL database"""
        conn = self.get_connection()
        cur = conn.cursor()
        try:
            # Set timezone
            cur.execute("SET timezone = 'Asia/Kathmandu';")
            
            # Create tables
            self._create_tables(cur)
            
            # Create indexes
            self._create_indexes(cur)
            
            conn.commit()
            logger.info("PostgreSQL database initialized successfully")
        except Exception as e:
            conn.rollback()
            logger.error(f"PostgreSQL initialization error: {e}")
        finally:
            cur.close()
            conn.close()

    def _create_tables(self, cur):
        """Create PostgreSQL tables"""
        # Status tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_statuses (
                status_code TEXT PRIMARY KEY,
                status_name_en TEXT NOT NULL,
                status_name_ne TEXT NOT NULL,
                description_en TEXT,
                description_ne TEXT,
                is_active BOOLEAN DEFAULT true,
                sort_order INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_unique_id TEXT UNIQUE,
                user_full_name TEXT,
                user_contact_phone TEXT,
                user_contact_email TEXT,
                user_province TEXT,
                user_district TEXT,
                user_municipality TEXT,
                user_ward TEXT,
                user_village TEXT,
                user_address TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Main grievances table - removed status fields
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievances (
                grievance_id TEXT PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                grievance_categories TEXT,
                grievance_summary TEXT,
                grievance_details TEXT,
                grievance_claimed_amount DECIMAL,
                grievance_location TEXT,
                grievance_creation_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                grievance_modification_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                is_temporary BOOLEAN DEFAULT TRUE,
                source TEXT DEFAULT 'bot'
            )
        """)

        # Status history table (after grievances table is created)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_status_history (
                id SERIAL PRIMARY KEY,
                grievance_id TEXT NOT NULL,
                status_code TEXT NOT NULL REFERENCES grievance_statuses(status_code),
                assigned_to TEXT,
                notes TEXT,
                created_by TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
            )
        """)

        # For backward compatibility - legacy history table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_history (
                id SERIAL PRIMARY KEY,
                grievance_id TEXT NOT NULL REFERENCES grievances(grievance_id),
                previous_status TEXT,
                new_status TEXT,
                next_step TEXT,
                notes TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # File attachments table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS file_attachments (
                id SERIAL PRIMARY KEY,
                file_id UUID NOT NULL,
                grievance_id TEXT NOT NULL REFERENCES grievances(grievance_id),
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                upload_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Voice recording tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_voice_recordings (
                recording_id UUID PRIMARY KEY,
                grievance_id TEXT REFERENCES grievances(grievance_id),
                file_path TEXT NOT NULL,
                recording_type TEXT NOT NULL CHECK (recording_type IN ('details', 'contact', 'location')),
                duration_seconds INTEGER,
                file_size_bytes INTEGER,
                processing_status TEXT DEFAULT 'pending' CHECK (processing_status IN ('pending', 'transcribing', 'transcribed', 'failed')),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_transcriptions (
                transcription_id UUID PRIMARY KEY,
                recording_id UUID REFERENCES grievance_voice_recordings(recording_id),
                grievance_id TEXT REFERENCES grievances(grievance_id),
                automated_transcript TEXT,
                verified_transcript TEXT,
                verification_status TEXT DEFAULT 'pending' CHECK (verification_status IN ('pending', 'verified', 'rejected')),
                confidence_score FLOAT,
                verification_notes TEXT,
                verified_by TEXT,
                verified_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Translations table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS grievance_translations (
                grievance_id TEXT PRIMARY KEY REFERENCES grievances(grievance_id),
                grievance_details_en TEXT,
                grievance_summary_en TEXT,
                grievance_categories_en TEXT,
                source_language TEXT NOT NULL DEFAULT 'ne',
                translation_method TEXT NOT NULL,
                confidence_scores JSONB DEFAULT '{"details": null, "summary": null, "categories": null}'::jsonb,
                verified_by TEXT,
                verified_at TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Initialize default statuses if table is empty
        cur.execute("SELECT COUNT(*) FROM grievance_statuses")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO grievance_statuses (status_code, status_name_en, status_name_ne, description_en, description_ne, sort_order) VALUES
                ('TEMP', 'Temporary', 'अस्थायी', 'Initial temporary status for new grievances', 'नयाँ गुनासोहरूको लागि प्रारम्भिक अस्थायी स्थिति', 0),
                ('PENDING', 'Pending', 'प्रतीक्षामा', 'Grievance is pending review', 'गुनासो समीक्षाको लागि प्रतीक्षामा छ', 1),
                ('IN_REVIEW', 'In Review', 'समीक्षामा', 'Grievance is being reviewed', 'गुनासो समीक्षा भइरहेको छ', 2),
                ('IN_PROGRESS', 'In Progress', 'प्रगतिमा', 'Grievance is being addressed', 'गुनासो समाधान भइरहेको छ', 3),
                ('RESOLVED', 'Resolved', 'समाधान भएको', 'Grievance has been resolved', 'गुनासो समाधान भएको छ', 4),
                ('CLOSED', 'Closed', 'बन्द भएको', 'Grievance case is closed', 'गुनासो केस बन्द भएको छ', 5),
                ('REJECTED', 'Rejected', 'अस्वीकृत', 'Grievance has been rejected', 'गुनासो अस्वीकृत भएको छ', 6)
            """)

    def _create_indexes(self, cur):
        """Create PostgreSQL indexes"""
        # Users table indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_phone ON users(user_contact_phone);
            CREATE INDEX IF NOT EXISTS idx_user_email ON users(user_contact_email);
            CREATE INDEX IF NOT EXISTS idx_user_unique_id ON users(user_unique_id);
        """)

        # Grievances table indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_grievance_user ON grievances(user_id);
            CREATE INDEX IF NOT EXISTS idx_grievance_creation_date ON grievances(grievance_creation_date);
            CREATE INDEX IF NOT EXISTS idx_grievance_modification_date ON grievances(grievance_modification_date);
            CREATE INDEX IF NOT EXISTS idx_grievance_source ON grievances(source);
            CREATE INDEX IF NOT EXISTS idx_grievance_temporary ON grievances(is_temporary);
        """)

        # Status tables indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_status_active ON grievance_statuses(is_active);
            CREATE INDEX IF NOT EXISTS idx_status_order ON grievance_statuses(sort_order);
            CREATE INDEX IF NOT EXISTS idx_status_history_grievance ON grievance_status_history(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_status_history_status ON grievance_status_history(status_code);
            CREATE INDEX IF NOT EXISTS idx_status_history_created ON grievance_status_history(created_at);
            CREATE INDEX IF NOT EXISTS idx_status_history_assigned ON grievance_status_history(assigned_to);
        """)

        # Legacy history table
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_grievance_history_id ON grievance_history(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_grievance_history_new_status ON grievance_history(new_status);
            CREATE INDEX IF NOT EXISTS idx_grievance_history_created ON grievance_history(created_at);
        """)

        # File attachments indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_attachments_grievance_id ON file_attachments(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_file_attachments_file_id ON file_attachments(file_id);
            CREATE INDEX IF NOT EXISTS idx_file_attachments_upload_timestamp ON file_attachments(upload_timestamp);
        """)

        # Voice recordings indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_grievance_id ON grievance_voice_recordings(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_status ON grievance_voice_recordings(processing_status);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_type ON grievance_voice_recordings(recording_type);
            CREATE INDEX IF NOT EXISTS idx_voice_recordings_created ON grievance_voice_recordings(created_at);
        """)

        # Transcriptions indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_transcriptions_recording_id ON grievance_transcriptions(recording_id);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_grievance_id ON grievance_transcriptions(grievance_id);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_verification_status ON grievance_transcriptions(verification_status);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_verified_by ON grievance_transcriptions(verified_by);
            CREATE INDEX IF NOT EXISTS idx_transcriptions_created ON grievance_transcriptions(created_at);
        """)

        # Translations indexes
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_translations_verified ON grievance_translations(verified_at);
            CREATE INDEX IF NOT EXISTS idx_translations_method ON grievance_translations(translation_method);
            CREATE INDEX IF NOT EXISTS idx_translations_source_language ON grievance_translations(source_language);
            CREATE INDEX IF NOT EXISTS idx_translations_created ON grievance_translations(created_at);
        """)

    def create_grievance(self, source: str = 'bot') -> Optional[str]:
        """Create a minimal grievance record with temporary status
        
        Args:
            source (str): Source of the grievance - 'accessibility' or 'bot'
            
        Returns:
            Optional[str]: The generated grievance ID or None if creation fails
        """
        logger.info(f"Creating new grievance with source: {source}")
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            logger.info("Setting timezone to Asia/Kathmandu")
            cursor.execute("SET timezone = 'Asia/Kathmandu';")
            
            # Generate grievance ID with source
            grievance_id = self.generate_grievance_id(source)
            logger.info(f"Generated grievance ID: {grievance_id}")
            
            # Create minimal user record with just an ID
            logger.info("Creating new user record")
            cursor.execute("""
                INSERT INTO users DEFAULT VALUES
                RETURNING id
            """)
            
            user_id = cursor.fetchone()[0]
            logger.info(f"Created user with ID: {user_id}")

            # Create minimal grievance record
            logger.info(f"Creating grievance record with ID: {grievance_id}")
            cursor.execute("""
                INSERT INTO grievances (
                    grievance_id, user_id, is_temporary, source
                ) VALUES (%s, %s, %s, %s)
            """, (
                str(grievance_id),
                int(user_id),
                True,
                source
            ))
            
            # Create initial status history entry
            logger.info("Creating initial status history entry")
            cursor.execute("""
                INSERT INTO grievance_status_history (
                    grievance_id, status_code, 
                    notes, created_by
                ) VALUES (%s, %s, %s, %s)
            """, (
                str(grievance_id),
                'TEMP',
                f'Grievance created with temporary status via {source} interface',
                'system'
            ))
            
            logger.info("Committing transaction")
            conn.commit()
            logger.info(f"Successfully created grievance with ID: {grievance_id}")
            return grievance_id
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Error creating temporary grievance: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
            
        finally:
            if conn:
                conn.close()

    def update_grievance_db(self, grievance_data: Dict) -> Optional[str]:
        """Update an existing grievance with complete data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            grievance_id = grievance_data.get('grievance_id')
            if not grievance_id:
                logger.error("No grievance_id provided for update")
                return None
            
            user_full_name = grievance_data.get('user_full_name', self.default_value)
            user_phone = grievance_data.get('user_contact_phone', self.default_value)
            
            # Check if user exists based on phone and name (if name is provided)
            if user_full_name != self.default_value:
                cursor.execute("""
                    SELECT id FROM users 
                    WHERE user_contact_phone = %s AND user_full_name = %s
                """, (user_phone, user_full_name))
            else:
                cursor.execute("""
                    SELECT id FROM users 
                    WHERE user_contact_phone = %s
                """, (user_phone,))
            
            user_result = cursor.fetchone()
            
            if user_result is None:
                # User doesn't exist, insert new user
                cursor.execute("""
                    INSERT INTO users (
                        user_unique_id, user_full_name, user_contact_phone,
                        user_contact_email, user_province, user_district,
                        user_municipality, user_ward, user_village, user_address
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    grievance_data.get('user_unique_id'),
                    user_full_name,
                    user_phone,
                    grievance_data.get('user_contact_email', self.default_value),
                    grievance_data.get('user_province', self.default_value),
                    grievance_data.get('user_district', self.default_value),
                    grievance_data.get('user_municipality', self.default_value),
                    grievance_data.get('user_ward', self.default_value),
                    grievance_data.get('user_village', self.default_value),
                    grievance_data.get('user_address', self.default_value)
                ))
                user_id = cursor.fetchone()[0]
            else:
                # User exists, update user
                cursor.execute("""
                    UPDATE users SET
                        user_unique_id = %s,
                        user_full_name = %s,
                        user_contact_email = %s,
                        user_province = %s,
                        user_district = %s,
                        user_municipality = %s,
                        user_ward = %s,
                        user_village = %s,
                        user_address = %s
                    WHERE id = %s
                    RETURNING id
                """, (
                    grievance_data.get('user_unique_id'),
                    user_full_name,
                    grievance_data.get('user_contact_email', self.default_value),
                    grievance_data.get('user_province', self.default_value),
                    grievance_data.get('user_district', self.default_value),
                    grievance_data.get('user_municipality', self.default_value),
                    grievance_data.get('user_ward', self.default_value),
                    grievance_data.get('user_village', self.default_value),
                    grievance_data.get('user_address', self.default_value),
                    user_result[0]
                ))
                user_id = cursor.fetchone()[0]

            # Handle grievance_claimed_amount
            claimed_amount = grievance_data.get('grievance_claimed_amount', '0')
            if claimed_amount == 'Not provided':
                claimed_amount = '0'

            # Update grievance
            cursor.execute("""
                UPDATE grievances SET
                    user_id = %s,
                    grievance_categories = %s,
                    grievance_summary = %s,
                    grievance_details = %s,
                    grievance_claimed_amount = %s,
                    grievance_location = %s,
                    is_temporary = %s,
                    grievance_modification_date = CURRENT_TIMESTAMP,
                    source = %s
                WHERE grievance_id = %s
            """, (
                user_id,
                grievance_data.get('grievance_categories', 'PENDING'),
                grievance_data.get('grievance_summary', 'PENDING'),
                grievance_data.get('grievance_details', 'PENDING'),
                claimed_amount,
                grievance_data.get('grievance_location', self.default_value),
                grievance_data.get('is_temporary', False),
                grievance_data.get('source', 'bot'),
                str(grievance_id)
            ))
            
            # Update status if provided
            status_code = grievance_data.get('grievance_status')
            if status_code:
                cursor.execute("""
                    INSERT INTO grievance_status_history (
                        grievance_id, status_code, notes, created_by
                    ) VALUES (%s, %s, %s, %s)
                """, (
                    str(grievance_id),
                    status_code,
                    'Grievance updated with complete data',
                    'system'
                ))
            
            conn.commit()
            return grievance_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating grievance: {e}")
            logger.error(f"Values being updated - grievance_id: {grievance_id}")
            logger.error(f"Grievance data values: {grievance_data}")
            return None
            
        finally:
            conn.close()

    def store_file_attachment(self, file_data: Dict) -> bool:
        """Store file attachment metadata"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO file_attachments (
                    file_id, grievance_id, file_name,
                    file_path, file_type, file_size
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                file_data['file_id'],
                file_data['grievance_id'],
                file_data['file_name'],
                file_data['file_path'],
                file_data['file_type'],
                file_data['file_size']
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing file attachment: {e}")
            return False
            
        finally:
            conn.close()

    def get_grievance_files(self, grievance_id: str) -> List[Dict]:
        """Get all files for a grievance"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT file_id, file_name, file_type, file_size, upload_timestamp
                FROM file_attachments
                WHERE grievance_id = %s
                ORDER BY upload_timestamp DESC
            """, (grievance_id,))
            
            files = cursor.fetchall()
            return [dict(file) for file in files]
            
        except Exception as e:
            logger.error(f"Error retrieving grievance files: {e}")
            return []
            
        finally:
            conn.close()

    def get_file_by_id(self, file_id: str) -> Optional[Dict]:
        """Get file metadata by ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT file_id, grievance_id, file_name, file_path, 
                       file_type, file_size, upload_timestamp
                FROM file_attachments
                WHERE file_id = %s
            """, (file_id,))
            
            file = cursor.fetchone()
            return dict(file) if file else None
            
        except Exception as e:
            logger.error(f"Error retrieving file by ID: {e}")
            return None
            
        finally:
            conn.close()

    def get_users_by_phone_number(self, phone_number: str) -> List[Dict[str, Any]]:
        """Get all users with a given phone number.
        
        Args:
            phone_number (str): The phone number to search for
            
        Returns:
            List[Dict[str, Any]]: List of user records matching the phone number
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT id, user_unique_id, user_full_name, user_contact_phone,
                       user_contact_email, user_province, user_district,
                       user_municipality, user_ward, user_village, user_address,
                       created_at
                FROM users
                WHERE user_contact_phone = %s
                ORDER BY created_at DESC
            """, (phone_number,))
            
            users = cursor.fetchall()
            return [dict(user) for user in users]
            
        except Exception as e:
            logger.error(f"Error retrieving users by phone number: {e}")
            return []
            
        finally:
            cursor.close()
            conn.close()

    def is_valid_grievance_id(self, grievance_id: str) -> bool:
        """Check if a grievance ID is valid.
        
        Args:
            grievance_id (str): The grievance ID to validate
            
        Returns:
            bool: True if the grievance ID is valid, False otherwise
        """
        if not grievance_id or not isinstance(grievance_id, str):
            return False
        
        # Check if the ID starts with GR and contains only alphanumeric characters
        if not grievance_id.startswith('GR') or not grievance_id[2:].replace('-', '').isalnum():
            return False
        
        # Check if the grievance exists in the database
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM grievances 
                WHERE grievance_id = %s
            """, (grievance_id,))
            
            count = cursor.fetchone()[0]
            return count > 0
            
        except Exception as e:
            logger.error(f"Error validating grievance ID: {e}")
            return False
            
        finally:
            conn.close()

    def get_grievance_by_id(self, grievance_id: str) -> Optional[Dict[str, Any]]:
        """Get grievance details by ID"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT g.*, u.user_full_name, u.user_contact_phone, u.user_contact_email,
                       u.user_province, u.user_district, u.user_municipality,
                       u.user_ward, u.user_village, u.user_address
                FROM grievances g
                LEFT JOIN users u ON g.user_id = u.id
                WHERE g.grievance_id = %s
            """, (grievance_id,))
            
            grievance = cursor.fetchone()
            return dict(grievance) if grievance else None
            
        except Exception as e:
            logger.error(f"Error retrieving grievance by ID: {e}")
            return None
            
        finally:
            conn.close()

    def store_voice_recording(self, recording_data: Dict) -> Optional[str]:
        """Store voice recording metadata
        
        Args:
            recording_data (Dict): Dictionary containing recording metadata:
                - grievance_id: ID of the associated grievance
                - file_path: Path to the stored audio file
                - recording_type: Type of recording ('details', 'contact', 'location')
                - duration_seconds: Duration of recording in seconds
                - file_size_bytes: Size of file in bytes
                
        Returns:
            Optional[str]: The recording ID if successful, None otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            recording_id = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO grievance_voice_recordings (
                    recording_id, grievance_id, file_path,
                    recording_type, duration_seconds, file_size_bytes
                ) VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING recording_id
            """, (
                recording_id,
                recording_data['grievance_id'],
                recording_data['file_path'],
                recording_data['recording_type'],
                recording_data.get('duration_seconds'),
                recording_data.get('file_size_bytes')
            ))
            
            conn.commit()
            return recording_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing voice recording: {e}")
            return None
            
        finally:
            conn.close()

    def store_transcription(self, transcription_data: Dict) -> Optional[str]:
        """Store transcription data
        
        Args:
            transcription_data (Dict): Dictionary containing transcription data:
                - recording_id: ID of the associated recording
                - grievance_id: ID of the associated grievance
                - automated_transcript: Text from automated transcription
                - confidence_score: Confidence score from transcription service
                
        Returns:
            Optional[str]: The transcription ID if successful, None otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            transcription_id = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO grievance_transcriptions (
                    transcription_id, recording_id, grievance_id,
                    automated_transcript, confidence_score
                ) VALUES (%s, %s, %s, %s, %s)
                RETURNING transcription_id
            """, (
                transcription_id,
                transcription_data['recording_id'],
                transcription_data['grievance_id'],
                transcription_data['automated_transcript'],
                transcription_data.get('confidence_score')
            ))
            
            conn.commit()
            return transcription_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing transcription: {e}")
            return None
            
        finally:
            conn.close()

    def verify_transcription(self, transcription_id: str, verification_data: Dict) -> bool:
        """Update transcription with verification data
        
        Args:
            transcription_id (str): ID of the transcription to verify
            verification_data (Dict): Dictionary containing verification data:
                - verified_transcript: Verified/corrected transcript text
                - verification_status: New status ('verified' or 'rejected')
                - verification_notes: Optional notes from verifier
                - verified_by: ID or name of the verifying officer
                
        Returns:
            bool: True if verification was successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE grievance_transcriptions SET
                    verified_transcript = %s,
                    verification_status = %s,
                    verification_notes = %s,
                    verified_by = %s,
                    verified_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE transcription_id = %s
            """, (
                verification_data['verified_transcript'],
                verification_data['verification_status'],
                verification_data.get('verification_notes'),
                verification_data['verified_by'],
                transcription_id
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error verifying transcription: {e}")
            return False
            
        finally:
            conn.close()

    def get_voice_recordings(self, grievance_id: str) -> List[Dict]:
        """Get all voice recordings for a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            
        Returns:
            List[Dict]: List of voice recording records
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT recording_id, file_path, recording_type,
                       duration_seconds, file_size_bytes, processing_status,
                       created_at, updated_at
                FROM grievance_voice_recordings
                WHERE grievance_id = %s
                ORDER BY created_at DESC
            """, (grievance_id,))
            
            recordings = cursor.fetchall()
            return [dict(recording) for recording in recordings]
            
        except Exception as e:
            logger.error(f"Error retrieving voice recordings: {e}")
            return []
            
        finally:
            conn.close()

    def get_transcriptions(self, grievance_id: str) -> List[Dict]:
        """Get all transcriptions for a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            
        Returns:
            List[Dict]: List of transcription records
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT t.*, r.recording_type
                FROM grievance_transcriptions t
                JOIN grievance_voice_recordings r ON t.recording_id = r.recording_id
                WHERE t.grievance_id = %s
                ORDER BY t.created_at DESC
            """, (grievance_id,))
            
            transcriptions = cursor.fetchall()
            return [dict(transcription) for transcription in transcriptions]
            
        except Exception as e:
            logger.error(f"Error retrieving transcriptions: {e}")
            return []
            
        finally:
            conn.close()

    def update_recording_status(self, recording_id: str, status: str) -> bool:
        """Update the processing status of a voice recording
        
        Args:
            recording_id (str): ID of the recording
            status (str): New status ('pending', 'transcribing', 'transcribed', 'failed')
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE grievance_voice_recordings SET
                    processing_status = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE recording_id = %s
            """, (status, recording_id))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating recording status: {e}")
            return False
            
        finally:
            conn.close()

    def store_translation(self, translation_data: Dict) -> Optional[str]:
        """Store a translation for a grievance field
        
        Args:
            translation_data (Dict): Dictionary containing translation data:
                - grievance_id: ID of the grievance
                - field_name: Field being translated ('details', 'summary', 'categories')
                - original_text: Original text in source language
                - translated_text: Translated text
                - source_language: Source language code (e.g., 'ne')
                - target_language: Target language code (e.g., 'en')
                - translation_method: Method used ('llm', 'human', 'auto')
                - confidence_score: Translation confidence score (optional)
                
        Returns:
            Optional[str]: The translation ID if successful, None otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            translation_id = str(uuid.uuid4())
            
            cursor.execute("""
                INSERT INTO grievance_translations (
                    translation_id, grievance_id, field_name,
                    original_text, translated_text,
                    source_language, target_language,
                    translation_method, confidence_score
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING translation_id
            """, (
                translation_id,
                translation_data['grievance_id'],
                translation_data['field_name'],
                translation_data['original_text'],
                translation_data['translated_text'],
                translation_data['source_language'],
                translation_data['target_language'],
                translation_data['translation_method'],
                translation_data.get('confidence_score')
            ))
            
            conn.commit()
            return translation_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing translation: {e}")
            return None
            
        finally:
            conn.close()

    def verify_translation(self, translation_id: str, verification_data: Dict) -> bool:
        """Verify a translation
        
        Args:
            translation_id (str): ID of the translation to verify
            verification_data (Dict): Dictionary containing verification data:
                - verified_by: ID or name of the verifier
                - translated_text: Updated translation text (if corrected)
                
        Returns:
            bool: True if verification was successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE grievance_translations SET
                    translated_text = %s,
                    verified_by = %s,
                    verified_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE translation_id = %s
            """, (
                verification_data.get('translated_text'),
                verification_data['verified_by'],
                translation_id
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error verifying translation: {e}")
            return False
            
        finally:
            conn.close()

    def get_translations(self, grievance_id: str, target_language: str = 'en') -> Dict[str, Dict]:
        """Get all translations for a grievance in a specific target language
        
        Args:
            grievance_id (str): ID of the grievance
            target_language (str): Target language code (default: 'en')
            
        Returns:
            Dict[str, Dict]: Dictionary of translations by field
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT field_name, translated_text, confidence_score,
                       verified_by, verified_at, translation_method
                FROM grievance_translations
                WHERE grievance_id = %s
                AND target_language = %s
                ORDER BY field_name, created_at DESC
            """, (grievance_id, target_language))
            
            translations = {}
            for row in cursor.fetchall():
                field = row['field_name']
                if field not in translations:
                    translations[field] = dict(row)
            
            return translations
            
        except Exception as e:
            logger.error(f"Error retrieving translations: {e}")
            return {}
            
        finally:
            conn.close()

    def get_untranslated_grievances(self, source_language: str = 'ne', target_language: str = 'en') -> List[Dict]:
        """Get grievances that need translation
        
        Args:
            source_language (str): Source language code (default: 'ne')
            target_language (str): Target language code (default: 'en')
            
        Returns:
            List[Dict]: List of grievances needing translation
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT g.grievance_id, g.grievance_details,
                       g.grievance_summary, g.grievance_categories
                FROM grievances g
                LEFT JOIN grievance_translations t ON g.grievance_id = t.grievance_id
                    AND t.target_language = %s
                WHERE t.translation_id IS NULL
                AND g.source = 'accessibility'
                ORDER BY g.grievance_creation_date DESC
            """, (target_language,))
            
            grievances = cursor.fetchall()
            return [dict(grievance) for grievance in grievances]
            
        except Exception as e:
            logger.error(f"Error retrieving untranslated grievances: {e}")
            return []
            
        finally:
            conn.close()

    def store_translations(self, translation_data: Dict) -> bool:
        """Store English translations for a grievance
        
        Args:
            translation_data (Dict): Dictionary containing translation data:
                - grievance_id: ID of the grievance
                - grievance_details_en: English translation of details
                - grievance_summary_en: English translation of summary
                - grievance_categories_en: English translation of categories
                - translation_method: Method used ('llm', 'human', 'auto')
                - confidence_scores: Dict with confidence scores for each field
                - source_language: Source language code (defaults to 'ne')
                
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO grievance_translations (
                    grievance_id, grievance_details_en,
                    grievance_summary_en, grievance_categories_en,
                    translation_method, confidence_scores,
                    source_language
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (grievance_id) DO UPDATE SET
                    grievance_details_en = EXCLUDED.grievance_details_en,
                    grievance_summary_en = EXCLUDED.grievance_summary_en,
                    grievance_categories_en = EXCLUDED.grievance_categories_en,
                    translation_method = EXCLUDED.translation_method,
                    confidence_scores = EXCLUDED.confidence_scores,
                    source_language = EXCLUDED.source_language,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                translation_data['grievance_id'],
                translation_data.get('grievance_details_en'),
                translation_data.get('grievance_summary_en'),
                translation_data.get('grievance_categories_en'),
                translation_data['translation_method'],
                json.dumps(translation_data.get('confidence_scores', {})),
                translation_data.get('source_language', 'ne')
            ))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error storing translations: {e}")
            return False
            
        finally:
            conn.close()

    def verify_translations(self, grievance_id: str, verification_data: Dict) -> bool:
        """Verify translations for a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            verification_data (Dict): Dictionary containing verification data:
                - verified_by: ID or name of the verifier
                - grievance_details_en: Updated English translation of details (optional)
                - grievance_summary_en: Updated English translation of summary (optional)
                - grievance_categories_en: Updated English translation of categories (optional)
                
        Returns:
            bool: True if verification was successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            update_fields = []
            update_values = []
            
            # Add any updated translations
            for field in ['details', 'summary', 'categories']:
                en_field = f'grievance_{field}_en'
                if en_field in verification_data:
                    update_fields.append(f"{en_field} = %s")
                    update_values.append(verification_data[en_field])
            
            # Add verification metadata
            update_fields.extend([
                "verified_by = %s",
                "verified_at = CURRENT_TIMESTAMP",
                "updated_at = CURRENT_TIMESTAMP"
            ])
            update_values.extend([verification_data['verified_by'], grievance_id])
            
            query = f"""
                UPDATE grievance_translations SET
                    {', '.join(update_fields)}
                WHERE grievance_id = %s
            """
            
            cursor.execute(query, update_values)
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error verifying translations: {e}")
            return False
            
        finally:
            conn.close()

    def get_translation(self, grievance_id: str) -> Optional[Dict]:
        """Get English translations for a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            
        Returns:
            Optional[Dict]: Dictionary with translations or None if not found
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT grievance_id, grievance_details_en,
                       grievance_summary_en, grievance_categories_en,
                       source_language, translation_method,
                       confidence_scores, verified_by,
                       verified_at, created_at
                FROM grievance_translations
                WHERE grievance_id = %s
            """, (grievance_id,))
            
            translation = cursor.fetchone()
            return dict(translation) if translation else None
            
        except Exception as e:
            logger.error(f"Error retrieving translation: {e}")
            return None
            
        finally:
            conn.close()

    def get_untranslated_grievances(self) -> List[Dict]:
        """Get grievances that need translation to English
        
        Returns:
            List[Dict]: List of grievances needing translation
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT g.grievance_id, g.grievance_details,
                       g.grievance_summary, g.grievance_categories
                FROM grievances g
                LEFT JOIN grievance_translations t ON g.grievance_id = t.grievance_id
                WHERE t.grievance_id IS NULL
                AND g.source = 'accessibility'
                ORDER BY g.grievance_creation_date DESC
            """)
            
            grievances = cursor.fetchall()
            return [dict(grievance) for grievance in grievances]
            
        except Exception as e:
            logger.error(f"Error retrieving untranslated grievances: {e}")
            return []
            
        finally:
            conn.close()

    def get_unverified_translations(self) -> List[Dict]:
        """Get translations that need verification
        
        Returns:
            List[Dict]: List of unverified translations
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT t.*, g.grievance_details, g.grievance_summary, g.grievance_categories
                FROM grievance_translations t
                JOIN grievances g ON t.grievance_id = g.grievance_id
                WHERE t.verified_at IS NULL
                ORDER BY t.created_at ASC
            """)
            
            translations = cursor.fetchall()
            return [dict(translation) for translation in translations]
            
        except Exception as e:
            logger.error(f"Error retrieving unverified translations: {e}")
            return []
            
        finally:
            conn.close()

    def get_grievance_status(self, grievance_id: str, language: str = 'en') -> Optional[Dict]:
        """Get current status of a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            language (str): Language code ('en' or 'ne')
            
        Returns:
            Optional[Dict]: Current status information or None if not found
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
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
            """, (grievance_id, language, language))
            
            status = cursor.fetchone()
            return dict(status) if status else None
            
        except Exception as e:
            logger.error(f"Error retrieving grievance status: {e}")
            return None
            
        finally:
            conn.close()

    def update_grievance_status(self, grievance_id: str, status_code: str, created_by: str,
                              assigned_to: Optional[str] = None, notes: Optional[str] = None) -> bool:
        """Update the status of a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            status_code (str): New status code
            created_by (str): ID/name of user making the change
            assigned_to (str, optional): ID/name of user assigned to the grievance
            notes (str, optional): Notes about the status change
            
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Verify status code exists and is active
            cursor.execute("""
                SELECT status_code FROM grievance_statuses
                WHERE status_code = %s AND is_active = true
            """, (status_code,))
            
            if not cursor.fetchone():
                logger.error(f"Invalid or inactive status code: {status_code}")
                return False
            
            # Add status history entry
            cursor.execute("""
                INSERT INTO grievance_status_history (
                    grievance_id, status_code, assigned_to,
                    notes, created_by
                ) VALUES (%s, %s, %s, %s, %s)
            """, (
                grievance_id,
                status_code,
                assigned_to,
                notes,
                created_by
            ))
            
            # Update grievance modification date
            cursor.execute("""
                UPDATE grievances SET
                    grievance_modification_date = CURRENT_TIMESTAMP
                WHERE grievance_id = %s
            """, (grievance_id,))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error updating grievance status: {e}")
            return False
            
        finally:
            conn.close()

    def get_grievance_status_history(self, grievance_id: str, language: str = 'en') -> List[Dict]:
        """Get status history of a grievance
        
        Args:
            grievance_id (str): ID of the grievance
            language (str): Language code ('en' or 'ne')
            
        Returns:
            List[Dict]: List of status changes in chronological order
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
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
            """, (language, grievance_id))
            
            history = cursor.fetchall()
            return [dict(record) for record in history]
            
        except Exception as e:
            logger.error(f"Error retrieving status history: {e}")
            return []
            
        finally:
            conn.close()

    def get_available_statuses(self, language: str = 'en') -> List[Dict]:
        """Get list of available grievance statuses
        
        Args:
            language (str): Language code ('en' or 'ne')
            
        Returns:
            List[Dict]: List of active statuses ordered by sort_order
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT 
                    status_code,
                    CASE WHEN %s = 'en' THEN status_name_en ELSE status_name_ne END as status_name,
                    CASE WHEN %s = 'en' THEN description_en ELSE description_ne END as description,
                    sort_order
                FROM grievance_statuses
                WHERE is_active = true
                ORDER BY sort_order
            """, (language, language))
            
            statuses = cursor.fetchall()
            return [dict(status) for status in statuses]
            
        except Exception as e:
            logger.error(f"Error retrieving available statuses: {e}")
            return []
            
        finally:
            conn.close()

    # Add a compatibility method to get grievance history
    def get_grievance_history(self, grievance_id: str) -> List[Dict]:
        """Get status history of a grievance from the old format
        
        Args:
            grievance_id (str): ID of the grievance
            
        Returns:
            List[Dict]: List of status changes in chronological order
        """
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=DictCursor)
        
        try:
            cursor.execute("""
                SELECT id, grievance_id, previous_status, new_status,
                       next_step, notes, created_at
                FROM grievance_history
                WHERE grievance_id = %s
                ORDER BY created_at DESC
            """, (grievance_id,))
            
            history = cursor.fetchall()
            return [dict(record) for record in history]
            
        except Exception as e:
            logger.error(f"Error retrieving grievance history: {e}")
            return []
            
        finally:
            conn.close()

# Create a singleton instance
db_manager = DatabaseManager() 