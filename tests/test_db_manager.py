import sys
import os

# Add the project root directory to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import pytest
from datetime import datetime
import uuid
from actions_server.db_manager import DatabaseManagers

db_manager = DatabaseManagers()

class TestDatabaseManagers:
    @pytest.fixture(autouse=True)
    def setup(self, test_db):
        """Set up test data before each test and ensure schema exists"""
        self.db_manager = test_db
        # Ensure all tables exist before running any test
        with self.db_manager.table.get_connection() as conn:
            cur = conn.cursor()
            self.db_manager.table._create_tables(cur)
            self.db_manager.table._create_indexes(cur)
            conn.commit()
        # Create test user
        self.test_user = {
            'user_unique_id': f'test_{uuid.uuid4().hex[:8]}',
            'user_full_name': 'Test User',
            'user_contact_phone': '1234567890',
            'user_contact_email': 'test@example.com',
            'user_province': 'Test Province',
            'user_district': 'Test District',
            'user_municipality': 'Test Municipality',
            'user_ward': '1',
            'user_village': 'Test Village',
            'user_address': 'Test Address'
        }
        self.user_id = self.db_manager.user.create_user(self.test_user)
        assert self.user_id is not None, "Failed to create test user"

        # Create test grievance
        self.grievance_id = self.db_manager.grievance.create_grievance()
        assert self.grievance_id is not None, "Failed to create test grievance"

        yield

        # Cleanup after each test
        if hasattr(self, 'grievance_id'):
            self.db_manager.grievance.update_grievance(self.grievance_id, {'is_temporary': True})

    def test_user_operations(self):
        """Test user-related operations"""
        # Test get_user_by_id
        user = self.db_manager.user.get_user_by_id(self.user_id)
        assert user is not None
        assert user['user_full_name'] == self.test_user['user_full_name']

        # Test update_user
        update_data = {'user_full_name': 'Updated Name'}
        success = self.db_manager.user.update_user(self.user_id, update_data)
        assert success is True

        # Verify update
        updated_user = self.db_manager.user.get_user_by_id(self.user_id)
        assert updated_user['user_full_name'] == 'Updated Name'

        # Test get_users_by_phone_number
        users = self.db_manager.user.get_users_by_phone_number(self.test_user['user_contact_phone'])
        assert len(users) > 0
        assert users[0]['user_contact_phone'] == self.test_user['user_contact_phone']

    def test_grievance_operations(self):
        """Test grievance-related operations"""
        # Test get_grievance_by_id
        grievance = self.db_manager.grievance.get_grievance_by_id(self.grievance_id)
        assert grievance is not None
        assert grievance['grievance_id'] == self.grievance_id

        # Test update_grievance
        update_data = {
            'grievance_summary': 'Test Summary',
            'grievance_details': 'Test Details',
            'user_id': self.user_id
        }
        success = self.db_manager.grievance.update_grievance(self.grievance_id, update_data)
        assert success is True

        # Verify update
        updated_grievance = self.db_manager.grievance.get_grievance_by_id(self.grievance_id)
        assert updated_grievance['grievance_summary'] == 'Test Summary'
        assert updated_grievance['grievance_details'] == 'Test Details'

        # Test status operations
        success = self.db_manager.grievance.update_grievance_status(
            self.grievance_id, 'PENDING', 'test_user'
        )
        assert success is True

        status = self.db_manager.grievance.get_grievance_status(self.grievance_id)
        assert status is not None
        assert status['status_code'] == 'PENDING'

    def test_file_operations(self):
        """Test file-related operations"""
        # Create test file data
        file_data = {
            'file_id': str(uuid.uuid4()),
            'grievance_id': self.grievance_id,
            'file_name': 'test.txt',
            'file_path': '/test/path/test.txt',
            'file_type': 'text/plain',
            'file_size': 1024
        }

        # Test store_file_attachment
        success = self.db_manager.file.store_file_attachment(file_data)
        assert success is True

        # Test get_grievance_files
        files = self.db_manager.file.get_grievance_files(self.grievance_id)
        assert len(files) > 0
        assert files[0]['file_name'] == file_data['file_name']

        # Test get_file_by_id
        file = self.db_manager.file.get_file_by_id(file_data['file_id'])
        assert file is not None
        assert file['file_name'] == file_data['file_name']

    def test_task_operations(self):
        """Test task-related operations"""
        # Create test task status
        success = self.db_manager.task.create_task_status('TEST', 'Test Status', 'Test Description')
        assert success is True

        # Get task status
        status = self.db_manager.task.get_task_status('TEST')
        assert status is not None
        assert status['status_name'] == 'Test Status'

        # Create task execution
        execution_id = self.db_manager.task.create_task_execution('TEST_TASK', self.grievance_id)
        assert execution_id is not None

        # Update task execution
        success = self.db_manager.task.update_task_execution_status(execution_id, 'SUCCESS')
        assert success is True

        # Get task execution
        execution = self.db_manager.task.get_task_execution(execution_id)
        assert execution is not None
        assert execution['status_code'] == 'SUCCESS'

    def test_invalid_operations(self):
        """Test invalid operations and error handling"""
        # Test invalid user update
        success = self.db_manager.user.update_user(999999, {'invalid_field': 'value'})
        assert success is False

        # Test invalid grievance update
        success = self.db_manager.grievance.update_grievance('INVALID_ID', {'grievance_summary': 'Test'})
        assert success is False

        # Test invalid file operations
        success = self.db_manager.file.store_file_attachment({
            'file_id': str(uuid.uuid4()),
            'grievance_id': 'INVALID_ID',
            'file_name': 'test.txt',
            'file_path': '/test/path/test.txt',
            'file_type': 'text/plain',
            'file_size': 1024
        })
        assert success is False

    def test_database_managers_initialization(self):
        """Test that all database managers are properly initialized"""
        assert isinstance(db_manager, DatabaseManagers)
        assert db_manager.file is not None
        assert db_manager.schema is not None
        assert db_manager.grievance is not None
        assert db_manager.task is not None
        assert db_manager.user is not None

    def test_generate_id(self):
        """Test ID generation for different types"""
        # Test grievance ID generation
        grievance_id = db_manager.grievance.generate_id(type='grievance_id')
        assert grievance_id.startswith('GR-')
        
        # Test user ID generation
        user_id = db_manager.user.generate_id(type='user_id')
        assert user_id.startswith('US-')
        
        # Test file ID generation
        file_id = db_manager.file.generate_id(type='file_id')
        assert file_id.startswith('FL-')

    def test_create_grievance_with_specific_data(self):
        """Test create_grievance with specific data"""
        try:
            data = {
                'grievance_id': 'GR-20250608-KO-JH-A91C-B',
                'user_id': 'US-20250608-KO-JH-6783',
                'source': 'bot'
            }
            
            # Call create_grievance
            result = db_manager.grievance.create_grievance(source='bot')
            
            # Assertions
            assert result is not None, "create_grievance should not return None"
            assert result == data['grievance_id'], f"Expected grievance_id {data['grievance_id']}, got {result}"
            
            # Verify the grievance was created in the database
            grievance = db_manager.grievance.get_grievance_by_id(data['grievance_id'])
            assert grievance is not None, "Grievance should exist in database"
            assert grievance['grievance_id'] == data['grievance_id'], "Grievance ID should match"
            assert grievance['user_id'] == data['user_id'], "User ID should match"
            assert grievance['source'] == data['source'], "Source should match"
            
            print(f"Test passed: Successfully created grievance with ID: {result}")
            
        except Exception as e:
            print(f"Test failed with error: {str(e)}")
            raise
        
    def test_create_user(self):
        """Test create_user"""
        user = db_manager.user.create_user()
        assert user is not None
        
    def test_create_grievance(self):
        """Test create_grievance"""
        grievance = db_manager.grievance.create_grievance()
        
        assert grievance is not None

if __name__ == '__main__':
    test = TestDatabaseManagers()
    test.test_create_grievance()
 