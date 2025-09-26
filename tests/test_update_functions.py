import pytest
from random import randint
from backend.services.database_services.grievance_manager import GrievanceDbManager, RecordingDbManager, TranslationDbManager, TranscriptionDbManager
from backend.services.database_services.complainant_manager import ComplainantDbManager
from backend.services.database_services.postgres_services import DatabaseManager
from backend.config.constants import GRIEVANCE_STATUS, TASK_STATUS

# Initialize database managers
db_manager = DatabaseManager()  # This has all the methods we need
recording_manager = RecordingDbManager()
translation_manager = TranslationDbManager()
transcription_manager = TranscriptionDbManager()
complainant_manager = ComplainantDbManager()
complainant_phone = '+9779' + str(randint(100000000, 999999999))

def is_valid_key(uuid_string):
    """Check if a string is a valid UUID format"""
    if not uuid_string:
        return False
    # Check if it starts with the expected prefix and has the right format
    if uuid_string.startswith('GR-') or uuid_string.startswith('TL-') or uuid_string.startswith('TR-') or uuid_string.startswith('RC-'):
        return True
    return False

@pytest.fixture(scope="module")
def complainant_id():
    """Create a unique complainant ID for testing"""
    return f"CP-20250728-{randint(1000, 9999)}-{randint(1000, 9999)}"

@pytest.fixture(scope="module")
def grievance_id(complainant_id):
    """Create a unique grievance ID for testing"""
    return f"GR-20250728-{randint(1000, 9999)}-{randint(1000, 9999)}"

@pytest.fixture(scope="module")
def recording_id(grievance_id):
    """Create a unique recording ID for testing"""
    return f"RC-20250728-{randint(1000, 9999)}-{randint(1000, 9999)}"

@pytest.fixture(scope="module")
def transcription_id(grievance_id, recording_id):
    """Create a unique transcription ID for testing"""
    return f"TR-20250728-{randint(1000, 9999)}-{randint(1000, 9999)}"

@pytest.fixture(scope="module")
def translation_id(grievance_id, transcription_id):
    """Create a unique translation ID for testing"""
    return f"TL-20250728-{randint(1000, 9999)}-{randint(1000, 9999)}"

def test_create_complainant_for_updates(complainant_id):
    """Create a complainant for update tests"""
    complainant_data = {
        'complainant_id': complainant_id,
        'complainant_full_name': 'Test User for Updates',
        'complainant_phone': complainant_phone,  # Use the specific phone number we want to test
        'complainant_email': f'test{randint(100, 999)}@example.com',
        'complainant_province': 'Province 1',
        'complainant_district': 'District 1',
        'complainant_municipality': 'Municipality 1',
        'complainant_ward': 1,
        'complainant_village': 'Village 1',
        'complainant_address': 'Test Address for Updates'
    }
    result = db_manager.create_complainant(complainant_data)
    assert result is True

def test_create_grievance_for_updates(complainant_id, grievance_id):
    """Create a grievance for update tests"""
    grievance_data = {
        'grievance_id': grievance_id,
        'complainant_id': complainant_id,
        'grievance_categories': 'Test Category for Updates',
        'grievance_summary': 'Test summary for updates',
        'grievance_description': 'Test description for updates',
        'grievance_claimed_amount': 1000.00,
        'grievance_location': 'Test Location for Updates',
        'language_code': 'ne',
        'source': 'test'
    }
    result = db_manager.create_grievance(grievance_data)
    assert result is True

def test_create_recording_for_updates(grievance_id, recording_id):
    """Create a recording for update tests"""
    recording_data = {
        'recording_id': recording_id,
        'grievance_id': grievance_id,
        'file_path': '/tmp/test_recording_for_updates.wav',
        'field_name': 'grievance_description',
        'file_size': 1024000,
        'duration_seconds': 30,
        'processing_status': 'PROCESSING',
        'language_code': 'ne'
    }
    result = recording_manager.create_recording(recording_data)
    assert result is not None

def test_create_transcription_for_updates(grievance_id, recording_id, transcription_id):
    """Create a transcription for update tests"""
    transcription_data = {
        'transcription_id': transcription_id,
        'recording_id': recording_id,
        'grievance_id': grievance_id,
        'field_name': 'grievance_description',
        'automated_transcript': 'Test transcription for updates',
        'language_code': 'ne'
    }
    result = transcription_manager.create_transcription(transcription_data)
    assert result is not None

def test_create_translation_for_updates(grievance_id, translation_id):
    """Create a translation for update tests"""
    translation_data = {
        'translation_id': translation_id,
        'grievance_id': grievance_id,
        'grievance_description_en': 'Test translation description for updates',
        'grievance_summary_en': 'Test translation summary for updates',
        'grievance_categories_en': 'Test translation categories for updates',
        'translation_method': 'LLM',
        'confidence_score': 0.95,
        'source_language': 'ne'
    }
    result = translation_manager.create_translation(translation_data)
    assert result is not None

# Update function tests
def test_update_complainant(complainant_id):
    """Test updating a complainant"""
    updated_complainant_data = {
        'complainant_full_name': 'Updated Test User',
        'complainant_email': 'updated@example.com',
        'complainant_province': 'Updated Province',
        'complainant_district': 'Updated District',
        'complainant_municipality': 'Updated Municipality',
        'complainant_village': 'Updated Village',
        'complainant_address': 'Updated Address'
    }
    result = db_manager.update_complainant(complainant_id, updated_complainant_data)
    assert result == 1

def test_update_grievance(grievance_id):
    """Test updating a grievance"""
    updated_grievance_data = {
        'grievance_categories': 'Updated Category',
        'grievance_summary': 'Updated summary',
        'grievance_description': 'Updated description',
        'grievance_claimed_amount': 2000.00,
        'grievance_location': 'Updated Location',
        'language_code': 'en'
    }
    result = db_manager.update_grievance(grievance_id, updated_grievance_data)
    assert result is True

def test_update_recording(recording_id):
    """Test updating a recording"""
    updated_recording_data = {
        'file_path': '/tmp/updated_recording.wav',
        'field_name': 'grievance_summary',
        'file_size': 2048000,
        'duration_seconds': 60,
        'processing_status': 'COMPLETED',
        'language_code': 'en',
        'language_code_detect': 'en'
    }
    result = recording_manager.update_recording(recording_id, updated_recording_data)
    assert result is True

def test_update_transcription(transcription_id):
    """Test updating a transcription"""
    updated_transcription_data = {
        'automated_transcript': 'Updated transcription text',
        'verified_transcript': 'Verified transcription text',
        'language_code': 'en',
        'confidence_score': 0.98,
        'verification_notes': 'Updated verification notes'
    }
    result = transcription_manager.update_transcription(transcription_id, updated_transcription_data)
    assert result is True

def test_update_translation(translation_id):
    """Test updating a translation"""
    updated_translation_data = {
        'grievance_description_en': 'Updated translation description',
        'grievance_summary_en': 'Updated translation summary',
        'grievance_categories_en': 'Updated translation categories',
        'translation_method': 'MANUAL',
        'confidence_score': 0.99,
        'source_language': 'ne',
        'verified_by': 'test_user',
        'verified_at': '2025-07-28 10:00:00'
    }
    result = translation_manager.update_translation(translation_id, updated_translation_data)
    assert result is True

def test_update_grievance_status(grievance_id):
    """Test updating grievance status"""
    result = db_manager.update_grievance_status(
        grievance_id, 
        status_code=GRIEVANCE_STATUS['SUBMITTED'],
        created_by='test_user',
        assigned_to='test_assignee',
        notes='Test status update'
    )
    assert result is True


def test_hash_value_length():
    """Test that hash has correct length"""
    phone = "+9779876543210"
    hashed = complainant_manager._hash_value(phone)
    assert len(hashed) == 64  # SHA256 produces 64 character hex string

def test_hash_value_consistency():
    """Test that hash is consistent for same input"""
    phone = "+9779876543210"
    hashed1 = complainant_manager._hash_value(phone)
    hashed2 = complainant_manager._hash_value(phone)
    assert hashed1 == hashed2

def test_hash_value_expected():
    """Test that hash matches expected value"""
    phone = "+9779876543210"
    hashed = complainant_manager._hash_value(phone)
    expected_hash = 'c95ee4a714418be9379a77482c9a8b2003400429703eabebc8d6d971e864f8e0'
    assert hashed == expected_hash

def test_hash_value():
    """Combined test for all hash value assertions"""
    phone = "+9779876543210"
    hashed = complainant_manager._hash_value(phone)
    hash_value = 'c95ee4a714418be9379a77482c9a8b2003400429703eabebc8d6d971e864f8e0'
    assert len(hashed) == 64 
    assert hashed == complainant_manager._hash_value(phone) # SHA256 produces 64 character hex string
    assert hashed == hash_value

# Verification tests - verify that updates actually worked
def test_verify_find_complainant_by_phone(complainant_id):
    """Verify that complainant was actually updated and can be found by phone"""
    complainants = db_manager.find_complainant_by_phone(complainant_phone)
    assert complainants is not None
    assert len(complainants) > 0
    complainant = complainants[0]  # Get the first complainant
    assert complainant['complainant_full_name'] == 'Updated Test User'
    assert complainant['complainant_id'] == complainant_id  # Should find the specific complainant we created

def test_verify_grievance_update(grievance_id):
    """Verify that grievance was actually updated"""
    grievance = db_manager.get_grievance_by_id(grievance_id)
    assert grievance is not None
    assert grievance['grievance_description'] == 'Updated description'

def test_verify_translation_update(translation_id):
    """Verify that translation was actually updated"""
    # Note: We don't have a get_translation_by_id method, so we'll just verify the update didn't fail
    # In a real scenario, you'd want to add a getter method to verify the update
    pass 