import os
import sqlite3
import psycopg2
from typing import Dict, List, Optional
from datetime import datetime
from psycopg2.extras import DictCursor
import uuid
import pytz

class GrievanceDB:
    def __init__(self):
        self.db_type = self._determine_db_type()
        self.nepal_tz = pytz.timezone('Asia/Kathmandu')
        self.init_db()

    def _determine_db_type(self) -> str:
        """Check if PostgreSQL credentials exist in environment variables"""
        postgres_vars = {
            'POSTGRES_DB': os.getenv('POSTGRES_DB'),
            'POSTGRES_USER': os.getenv('POSTGRES_USER'),
            'POSTGRES_PASSWORD': os.getenv('POSTGRES_PASSWORD'),
            'POSTGRES_HOST': os.getenv('POSTGRES_HOST', 'localhost'),
            'POSTGRES_PORT': os.getenv('POSTGRES_PORT', '5432')
        }

        if all(postgres_vars.values()):
            try:
                # Test PostgreSQL connection
                conn = psycopg2.connect(
                    dbname=postgres_vars['POSTGRES_DB'],
                    user=postgres_vars['POSTGRES_USER'],
                    password=postgres_vars['POSTGRES_PASSWORD'],
                    host=postgres_vars['POSTGRES_HOST'],
                    port=postgres_vars['POSTGRES_PORT']
                )
                conn.close()
                print("Successfully connected to PostgreSQL")
                return "postgres"
            except psycopg2.Error as e:
                print(f"PostgreSQL connection failed: {e}")
                print("Falling back to SQLite")
                return "sqlite"
        else:
            print("PostgreSQL environment variables not found. Using SQLite")
            return "sqlite"

    def get_connection(self):
        """Get database connection based on available database type"""
        if self.db_type == "postgres":
            return psycopg2.connect(
                dbname=os.getenv('POSTGRES_DB'),
                user=os.getenv('POSTGRES_USER'),
                password=os.getenv('POSTGRES_PASSWORD'),
                host=os.getenv('POSTGRES_HOST', 'localhost'),
                port=os.getenv('POSTGRES_PORT', '5432'),
                cursor_factory=DictCursor
            )
        else:
            return sqlite3.connect("grievances.db")

    def get_nepal_time(self) -> datetime:
        """Get current time in Nepal timezone"""
        return datetime.now(self.nepal_tz)

    def init_db(self):
        """Initialize the database with required tables"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if self.db_type == "postgres":
            # First set the timezone for the database session
            cursor.execute("SET timezone = 'Asia/Kathmandu';")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    user_full_name TEXT NOT NULL,
                    user_contact_phone TEXT NOT NULL UNIQUE,
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

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grievances (
                    grievance_id TEXT PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    grievance_category TEXT,
                    grievance_summary TEXT NOT NULL,
                    grievance_details TEXT,
                    grievance_claimed_amount DECIMAL,
                    grievance_location TEXT,
                    grievance_creation_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    grievance_modification_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    grievance_status TEXT DEFAULT 'Submitted',
                    grievance_status_update_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grievance_history (
                    id SERIAL PRIMARY KEY,
                    grievance_id TEXT REFERENCES grievances(grievance_id),
                    previous_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    next_step TEXT,
                    expected_resolution_date TIMESTAMP WITH TIME ZONE,
                    update_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_by TEXT,
                    notes TEXT
                )
            """)

        else:
            # SQLite-specific CREATE TABLE statements
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_full_name TEXT NOT NULL,
                    user_contact_phone TEXT NOT NULL UNIQUE,
                    user_contact_email TEXT,
                    user_province TEXT,
                    user_district TEXT,
                    user_municipality TEXT,
                    user_ward TEXT,
                    user_village TEXT,
                    user_address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grievances (
                    grievance_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    grievance_category TEXT,
                    grievance_summary TEXT NOT NULL,
                    grievance_details TEXT,
                    grievance_claimed_amount DECIMAL,
                    grievance_location TEXT,
                    grievance_creation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    grievance_modification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    grievance_status TEXT DEFAULT 'Submitted',
                    grievance_status_update_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS grievance_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    grievance_id TEXT,
                    previous_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    next_step TEXT,
                    expected_resolution_date TIMESTAMP,
                    update_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_by TEXT,
                    notes TEXT,
                    FOREIGN KEY (grievance_id) REFERENCES grievances(grievance_id)
                )
            """)

        # Add indexes for better performance
        if self.db_type == "postgres":
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_phone ON users(user_contact_phone);
                CREATE INDEX IF NOT EXISTS idx_grievance_user ON grievances(user_id);
                CREATE INDEX IF NOT EXISTS idx_grievance_status ON grievances(grievance_status);
                CREATE INDEX IF NOT EXISTS idx_grievance_history ON grievance_history(grievance_id, update_date);
            """)
        else:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_phone ON users(user_contact_phone)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_grievance_user ON grievances(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_grievance_status ON grievances(grievance_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_grievance_history ON grievance_history(grievance_id, update_date)")

        conn.commit()
        conn.close()

    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a query and return results as a list of dictionaries"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(query, params or ())
        
        if self.db_type == "postgres":
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in results]
        else:
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return results

    def get_grievance_by_id(self, grievance_id: str) -> Optional[Dict]:
        """Retrieve complete grievance details by ID with user information"""
        if self.db_type == "postgres":
            query = """
                SELECT 
                    g.grievance_id,
                    g.grievance_category,
                    g.grievance_summary,
                    g.grievance_details,
                    g.grievance_date,
                    g.grievance_claimed_amount,
                    g.grievance_location,
                    g.grievance_creation_date,
                    g.grievance_status,
                    g.grievance_status_update_date,
                    u.user_full_name,
                    u.user_contact_phone,
                    u.user_address,
                    h.next_step,
                    h.expected_resolution_date
                FROM grievances g
                JOIN users u ON g.user_id = u.id
                LEFT JOIN (
                    SELECT DISTINCT ON (grievance_id)
                        grievance_id, next_step, expected_resolution_date
                    FROM grievance_history
                    ORDER BY grievance_id, update_date DESC
                ) h ON g.grievance_id = h.grievance_id
                WHERE g.grievance_id = %s
            """
        else:  # SQLite
            query = """
                SELECT 
                    g.grievance_id,
                    g.grievance_category,
                    g.grievance_summary,
                    g.grievance_details,
                    g.grievance_date,
                    g.grievance_claimed_amount,
                    g.grievance_location,
                    g.grievance_creation_date,
                    g.grievance_status,
                    g.grievance_status_update_date,
                    u.user_full_name,
                    u.user_contact_phone,
                    u.user_address,
                    h.next_step,
                    h.expected_resolution_date
                FROM grievances g
                JOIN users u ON g.user_id = u.id
                LEFT JOIN (
                    SELECT grievance_id, next_step, expected_resolution_date
                    FROM grievance_history h1
                    WHERE update_date = (
                        SELECT MAX(update_date)
                        FROM grievance_history h2
                        WHERE h2.grievance_id = h1.grievance_id
                    )
                ) h ON g.grievance_id = h.grievance_id
                WHERE g.grievance_id = ?
            """
        
        results = self.execute_query(query, (grievance_id,))
        return results[0] if results else None

    def get_grievances_by_phone(self, phone_number: str) -> List[Dict]:
        """Retrieve all grievances for a phone number with latest status"""
        if self.db_type == "postgres":
            query = """
                SELECT 
                    g.grievance_id,
                    g.grievance_category,
                    g.grievance_summary,
                    g.grievance_date,
                    g.grievance_creation_date,
                    g.grievance_status,
                    g.grievance_status_update_date,
                    h.next_step
                FROM grievances g
                JOIN users u ON g.user_id = u.id
                LEFT JOIN (
                    SELECT DISTINCT ON (grievance_id)
                        grievance_id, next_step
                    FROM grievance_history
                    ORDER BY grievance_id, update_date DESC
                ) h ON g.grievance_id = h.grievance_id
                WHERE u.user_contact_phone = %s
                ORDER BY g.grievance_creation_date DESC
            """
        else:  # SQLite
            query = """
                SELECT 
                    g.grievance_id,
                    g.grievance_category,
                    g.grievance_summary,
                    g.grievance_date,
                    g.grievance_creation_date,
                    g.grievance_status,
                    g.grievance_status_update_date,
                    h.next_step
                FROM grievances g
                JOIN users u ON g.user_id = u.id
                LEFT JOIN (
                    SELECT grievance_id, next_step
                    FROM grievance_history h1
                    WHERE update_date = (
                        SELECT MAX(update_date)
                        FROM grievance_history h2
                        WHERE h2.grievance_id = h1.grievance_id
                    )
                ) h ON g.grievance_id = h.grievance_id
                WHERE u.user_contact_phone = ?
                ORDER BY g.grievance_creation_date DESC
            """
        
        return self.execute_query(query, (phone_number,))

    def create_grievance(self, user_data: Dict, grievance_data: Dict) -> Optional[str]:
        """Create a new grievance with user information"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Set timezone only for PostgreSQL
            if self.db_type == "postgres":
                cursor.execute("SET timezone = 'Asia/Kathmandu';")
                
            # Generate grievance ID with Nepal time
            nepal_time = self.get_nepal_time()
            grievance_id = f"GR{nepal_time.strftime('%Y%m%d')}{uuid.uuid4().hex[:6].upper()}"
            
            # Convert category list to string if it's a list
            category = grievance_data.get('grievance_category', '')
            if isinstance(category, list):
                category = '; '.join(category)

            # First, get or create user
            if self.db_type == "postgres":
                cursor.execute("""
                    INSERT INTO users (
                        user_full_name, user_contact_phone, user_contact_email,
                        user_province, user_district, user_municipality,
                        user_ward, user_village, user_address
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_contact_phone) 
                    DO UPDATE SET 
                        user_full_name = EXCLUDED.user_full_name,
                        user_contact_email = EXCLUDED.user_contact_email
                    RETURNING id
                """, (
                    user_data.get('user_full_name'),
                    user_data.get('user_contact_phone'),
                    user_data.get('user_contact_email'),
                    user_data.get('user_province'),
                    user_data.get('user_district'),
                    user_data.get('user_municipality'),
                    user_data.get('user_ward'),
                    user_data.get('user_village'),
                    user_data.get('user_address')
                ))
            else:
                # SQLite version
                cursor.execute("""
                    INSERT OR REPLACE INTO users (
                        user_full_name, user_contact_phone, user_contact_email,
                        user_province, user_district, user_municipality,
                        user_ward, user_village, user_address
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(user_data.get('user_full_name', '')),
                    str(user_data.get('user_contact_phone', '')),
                    str(user_data.get('user_contact_email', '')),
                    str(user_data.get('user_province', '')),
                    str(user_data.get('user_district', '')),
                    str(user_data.get('user_municipality', '')),
                    str(user_data.get('user_ward', '')),
                    str(user_data.get('user_village', '')),
                    str(user_data.get('user_address', ''))
                ))
                cursor.execute("SELECT last_insert_rowid()")
            
            user_id = cursor.fetchone()[0]

            # Create grievance with appropriate placeholders
            placeholder = "%s" if self.db_type == "postgres" else "?"
            cursor.execute(f"""
                INSERT INTO grievances (
                    grievance_id, user_id, grievance_category,
                    grievance_summary, grievance_details,
                    grievance_claimed_amount, grievance_location
                ) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """, (
                str(grievance_id),
                int(user_id),
                str(category),
                str(grievance_data.get('grievance_summary', '')),
                str(grievance_data.get('grievance_details', '')),
                str(grievance_data.get('grievance_claimed_amount', '0')),
                str(grievance_data.get('grievance_location', ''))
            ))
            
            # Create initial history entry
            cursor.execute(f"""
                INSERT INTO grievance_history (
                    grievance_id, previous_status, new_status,
                    next_step, notes
                ) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})
            """, (
                str(grievance_id),
                '',  # Empty string instead of None for previous_status
                'Submitted',
                'Under Review',
                'Grievance submitted successfully'
            ))
            
            conn.commit()
            return grievance_id
            
        except Exception as e:
            conn.rollback()
            print(f"Error creating grievance: {e}")
            print(f"Values being inserted - user_id: {user_id}, grievance_id: {grievance_id}")
            print(f"Grievance data values:", {
                'category': category,
                'grievance_summary': grievance_data.get('grievance_summary'),
                'grievance_details': grievance_data.get('grievance_details'),
                'grievance_claimed_amount': grievance_data.get('grievance_claimed_amount'),
                'grievance_location': grievance_data.get('grievance_location')
            })
            return None
            
        finally:
            conn.close()

    def get_grievance_history(self, grievance_id: str) -> List[Dict]:
        """Retrieve complete history of a grievance"""
        query = """
            SELECT 
                previous_status,
                new_status,
                next_step,
                expected_resolution_date,
                update_date,
                updated_by,
                notes
            FROM grievance_history
            WHERE grievance_id = %s
            ORDER BY update_date DESC
        """
        return self.execute_query(query, (grievance_id,))

    def create_status_update(self, grievance_id: str, status: str, next_step: str = None, notes: str = None) -> bool:
        """Create a new status update entry"""
        try:
            query = """
                INSERT INTO status_updates (
                    grievance_id, status, next_step, notes
                ) VALUES (
                    %s, %s, %s, %s
                )
            """
            
            self.execute_query(query, (grievance_id, status, next_step, notes))
            
            # Update the current status in grievances table
            self.execute_query(
                "UPDATE grievances SET current_status = %s, last_updated = CURRENT_TIMESTAMP WHERE id = %s",
                (status, grievance_id)
            )
            
            return True
            
        except Exception as e:
            print(f"Error creating status update: {e}")
            return False
