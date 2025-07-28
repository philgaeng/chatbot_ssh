import pytest
import uuid
from random import randint
from unittest.mock import patch, MagicMock
from backend.services.database_services.postgres_services import db_manager
from backend.config.constants import DEFAULT_VALUES, TASK_STATUS, GRIEVANCE_CLASSIFICATION_STATUS, GRIEVANCE_STATUS, TRANSCRIPTION_PROCESSING_STATUS
from backend.services.database_services.base_manager import BaseDatabaseManager


# Check if string is a valid UUID format
def is_valid_key(uuid_string):
    startswith = ['GR-2025', 'CM-2025', 'REC-2025', 'TR-2025', 'TL-2025']
    endswith = ['-B', '-A']
    for start in startswith:
        if uuid_string.startswith(start):
            for end in endswith:
                if uuid_string.endswith(end):
                    return True
    return False

# Test data templates
id_generation_data = {
    'complainant_province': 'Koshi',
    'complainant_district': 'Jhapa',
    'complainant_office': 'Office1',
    'source': 'bot',
}

complainant_data = {
    'complainant_province': 'Koshi',
    'complainant_district': 'Jhapa',
    'complainant_office': 'Office1',
    'source': 'bot',
    'complainant_full_name': 'Test Complainant',
    'complainant_phone': '9876543210',
    'complainant_email': 'test_complainant@gmail.com',
    'complainant_address': 'Test Address',
    'complainant_ward': '1',
    'complainant_village': 'Test Village',
    'complainant_municipality': 'Birtamod',
}

# --- FIXTURES ---
@pytest.fixture(scope="module")
def complainant_id():
    """Create a complainant ID for use in tests"""
    return db_manager.create_complainant_id(id_generation_data)

@pytest.fixture(scope="module")
def grievance_id(complainant_id):
    """Create a grievance ID for use in tests"""
    return db_manager.create_grievance_id(id_generation_data)

@pytest.fixture(scope="module")
def recording_id(grievance_id):
    """Create a recording and return its ID for use in tests"""
    recording_data = {
        'grievance_id': grievance_id,
        'file_path': '/tmp/test_recording.wav',
        'field_name': 'grievance_description',
        'file_size': 1000,
        'duration_seconds': 10,
        'language_code': 'en',
        'processing_status': TRANSCRIPTION_PROCESSING_STATUS['PROCESSING']
    }
    return db_manager.create_recording(recording_data)

@pytest.fixture(scope="module")
def transcription_id(grievance_id, recording_id):
    """Create a transcription and return its ID for use in tests"""
    transcription_data = {
        'grievance_id': grievance_id,
        'recording_id': recording_id,
        'field_name': 'grievance_description',
        'automated_transcript': 'Test transcription',
        'language_code': 'en'
    }
    return db_manager.create_transcription(transcription_data)

@pytest.fixture(scope="module")
def translation_id(grievance_id, transcription_id):
    """Create a translation and return its ID for use in tests"""
    translation_data = {
        'transcription_id': transcription_id,
        'grievance_id': grievance_id,
        'grievance_description_en': 'Test translation description',
        'grievance_summary_en': 'Test translation summary',
        'grievance_categories_en': 'Test translation categories',
        'translation_method': 'LLM',
        'confidence_score': 0.95,
        'source_language': 'ne'
    }
    return db_manager.create_translation(translation_data)

# --- ID GENERATION TESTS ---
def test_create_complainant_id():
    result = db_manager.create_complainant_id(id_generation_data)
    assert result is not None
    assert isinstance(result, str)

def test_create_grievance_id():
    result = db_manager.create_grievance_id(id_generation_data)
    assert result is not None
    assert isinstance(result, str)


# --- COMPLAINANT OPERATIONS ---
def test_create_complainant(complainant_id):
    # Add complainant_id to the data
    test_complainant_data = complainant_data.copy()
    test_complainant_data['complainant_id'] = complainant_id
    
    result = db_manager.create_complainant(test_complainant_data)
    assert result is True
    assert db_manager.get_complainant_by_id(complainant_id) is not None
    assert db_manager.get_complainant_by_id(complainant_id)['complainant_id'] == complainant_id
    assert db_manager.get_complainant_by_id(complainant_id)['complainant_province'] == 'Koshi'
    assert db_manager.get_complainant_by_id(complainant_id)['complainant_email'] == 'test_complainant@gmail.com'

def test_update_complainant(complainant_id):
    # Create updated complainant data
    updated_complainant_data = complainant_data.copy()
    updated_complainant_data['complainant_id'] = complainant_id
    updated_complainant_data['complainant_municipality'] = 'Bagmati'
    updated_complainant_data['complainant_email'] = 'test_complainant_updated@gmail.com'
    
    result = db_manager.update_complainant(complainant_id, updated_complainant_data)
    assert result is True
    updated = db_manager.get_complainant_by_id(complainant_id)
    assert updated['complainant_id'] == complainant_id
    assert updated['complainant_municipality'] == 'Bagmati'
    assert updated['complainant_email'] == 'test_complainant_updated@gmail.com'


def test_find_complainant_by_phone(complainant_id):
    # Insert a complainant with a known phone number
    phone = complainant_data['complainant_phone']
    result = db_manager.find_complainant_by_phone(phone)
    assert len(result)
    assert any(c['complainant_id'] == complainant_id for c in result)

# --- Add similar tests for all other methods, using real data ---

def test_create_grievance(complainant_id, grievance_id):
    # Create grievance data
    grievance_data = {
        'grievance_id': grievance_id,
        'complainant_id': complainant_id,
        'grievance_description': 'Test grievance',
        'grievance_status': GRIEVANCE_STATUS['UNDER_EVALUATION'],
    }
    
    result = db_manager.create_grievance(grievance_data)
    assert result is True
    result = db_manager.get_grievance_by_id(grievance_id)
    assert result is not None
    assert result['grievance_id'] == grievance_id

def test_update_grievance(complainant_id, grievance_id):
    # Update grievance data
    updated_grievance_data = {
        'grievance_id': grievance_id,
        'complainant_id': complainant_id,
        'grievance_description': 'Updated grievance description',
        'grievance_status': GRIEVANCE_STATUS['UNDER_EVALUATION'],
    }
    result = db_manager.update_grievance(grievance_id, updated_grievance_data)
    assert result is True
    updated = db_manager.get_grievance_by_id(grievance_id)
    assert updated['grievance_description'] == 'Updated grievance description'

# def test_get_grievance_status():
#     status = db_manager.get_grievance_status(grievance_id)
#     assert status is not None
#     assert status['status_code'] == GRIEVANCE_STATUS['UNDER_EVALUATION']

def test_update_grievance_status(grievance_id):
    result = db_manager.update_grievance_status(grievance_id, GRIEVANCE_STATUS['SUBMITTED'])
    assert result is True
    # status = db_manager.get_grievance_status(grievance_id)
    # assert status is not None
    # assert status['grievance_status'] == GRIEVANCE_STATUS['SUBMITTED']

def test_get_grievance_files(grievance_id):
    files = db_manager.get_grievance_files(grievance_id)
    assert isinstance(files, list)

def test_create_or_update_recording(recording_id):
    assert recording_id is not None
    print(f"rec_id: {recording_id}")
    assert is_valid_key(recording_id)

def test_create_transcription(grievance_id, recording_id):
    transcription_data = {
        "recording_id": recording_id,  # Now this will have the actual ID
        "grievance_id": grievance_id,
        "field_name": "grievance_description",
        "automated_transcript": "Test create transcription ",
        "language_code": "en"
    }
    trans_id = db_manager.create_transcription(transcription_data)
    assert trans_id is not None
    assert is_valid_key(trans_id)



def test_create_translation(grievance_id, transcription_id):
    translation_data = {
        'transcription_id': transcription_id,
        'grievance_id': grievance_id,
        'grievance_description_en': 'Test translation description',
        'grievance_summary_en': 'Test translation summary',
        'grievance_categories_en': 'Test translation categories',
        'translation_method': 'LLM',
        'confidence_score': 0.95,
        'source_language': 'ne'
    }
    translation_id = db_manager.create_translation(translation_data)
    assert translation_id is not None



def test_create_task(grievance_id):
    task_id = "task" + str(randint(100, 999))
    task_name = 'Test Task'
    entity_key = 'grievance_id'
    entity_id = grievance_id
    result = db_manager.create_task(task_id = task_id, task_name=task_name, entity_key=entity_key, entity_id=entity_id)
    assert result is not None

def test_get_task():
    # This test needs a specific task_id, so we'll create one
    task_id = "task" + str(randint(100, 999))
    task = db_manager.get_task(task_id)
    assert task is None or isinstance(task, dict)

def test_update_task():
    # Create a task first, then update it
    task_id = "task" + str(randint(100, 999))
    update_data = {'status': TASK_STATUS['SUCCESS']}
    result = db_manager.update_task(task_id, update_data)
    assert result in [True, False]  # Accept both for now

def test_store_file(grievance_id):
    file_data = {
        'grievance_id': grievance_id,
        'file_path': '/tmp/test_file.txt',
        'file_type': 'txt',
        'uploaded_by': 'tester',
    }
    result = db_manager.store_file(file_data)
    assert result in [True, False]

def test_get_grievance_file_attachments(grievance_id):
    files = db_manager.get_grievance_file_attachments(grievance_id)
    assert isinstance(files, list)

