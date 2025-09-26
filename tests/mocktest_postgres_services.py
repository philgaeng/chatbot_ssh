import pytest
from unittest.mock import patch, MagicMock
from backend.services.database_services.postgres_services import db_manager

# --- ID GENERATION ---
def test_create_complainant_id():
    data = {'complainant_province': 'Koshi', 'complainant_district': 'Jhapa', 'complainant_office': 'Office1', 'source': 'bot'}
    result = db_manager.create_complainant_id(data)
    assert result is not None

def test_create_grievance_id():
    data = {'complainant_province': 'Koshi', 'complainant_district': 'Jhapa', 'complainant_office': 'Office1', 'source': 'bot'}
    result = db_manager.create_grievance_id(data)
    assert result is not None

# --- COMPLAINANT OPERATIONS ---
def test_update_complainant():
    with patch.object(db_manager, 'complainant') as mock_complainant:
        mock_complainant.update_complainant.return_value = True
        assert db_manager.update_complainant('test_id', {'name': 'Test'}) is True

def test_get_complainant():
    with patch.object(db_manager, 'complainant') as mock_complainant:
        mock_complainant.get_complainant_by_id.return_value = {'id': 'test_id'}
        result = db_manager.get_complainant('test_id')
        assert result['id'] == 'test_id'

def test_find_complainant_by_phone():
    with patch.object(db_manager, 'complainant') as mock_complainant:
        mock_complainant.get_complainants_by_phone_number.return_value = [{'id': 'test_id'}]
        result = db_manager.find_complainant_by_phone('1234567890')
        assert isinstance(result, list)

def test_get_complainant_from_grievance():
    with patch.object(db_manager, 'complainant') as mock_complainant:
        mock_complainant.get_complainant_from_grievance_id.return_value = {'id': 'test_id'}
        result = db_manager.get_complainant_from_grievance('grievance_id')
        assert result['id'] == 'test_id'

def test_encrypt_decrypt_complainant_data():
    with patch.object(db_manager, 'complainant') as mock_complainant:
        mock_complainant._encrypt_complainant_data.return_value = {'encrypted': True}
        mock_complainant._decrypt_complainant_data.return_value = {'decrypted': True}
        enc = db_manager._encrypt_complainant_data({'foo': 'bar'})
        dec = db_manager._decrypt_complainant_data({'foo': 'bar'})
        assert enc['encrypted'] is True
        assert dec['decrypted'] is True

# --- GRIEVANCE OPERATIONS ---
def test_submit_grievance_to_db():
    with patch.object(db_manager, 'complainant') as mock_complainant, \
         patch.object(db_manager, 'grievance') as mock_grievance, \
         patch.object(db_manager, 'logger'):
        mock_complainant.create_complainant.return_value = True
        mock_grievance.create_grievance.return_value = True
        data = {'complainant_fields': {'foo': 'bar'}, 'grievance_fields': {'baz': 'qux'}, 'grievance_id': 'gid', 'complainant_id': 'cid'}
        # Patch helper methods if needed
        db_manager.get_grievance_or_complainant_source = MagicMock(return_value='bot')
        db_manager.get_complainant_and_grievance_fields = MagicMock(return_value=data)
        assert db_manager.submit_grievance_to_db(data) is True

def test_update_grievance():
    with patch.object(db_manager, 'complainant') as mock_complainant, \
         patch.object(db_manager, 'grievance') as mock_grievance, \
         patch.object(db_manager, 'logger'):
        mock_complainant.update_complainant.return_value = True
        mock_grievance.update_grievance.return_value = True
        data = {'complainant_fields': {'foo': 'bar'}, 'grievance_fields': {'baz': 'qux'}, 'grievance_id': 'gid', 'complainant_id': 'cid'}
        db_manager.get_grievance_or_complainant_source = MagicMock(return_value='bot')
        db_manager.get_complainant_and_grievance_fields = MagicMock(return_value=data)
        assert db_manager.update_grievance('gid', data) is True

def test_get_grievance_by_id():
    with patch.object(db_manager, 'grievance') as mock_grievance:
        mock_grievance.get_grievance_by_id.return_value = {'id': 'gid'}
        result = db_manager.get_grievance_by_id('gid')
        assert result['id'] == 'gid'

def test_get_grievance_status():
    with patch.object(db_manager, 'grievance') as mock_grievance:
        mock_grievance.get_grievance_status.return_value = {'status': 'open'}
        result = db_manager.get_grievance_status('gid')
        assert result['status'] == 'open'

def test_update_grievance_status():
    with patch.object(db_manager, 'grievance') as mock_grievance:
        mock_grievance.update_grievance_status.return_value = True
        assert db_manager.update_grievance_status('gid', 'status', 'creator') is True

def test_get_grievance_files():
    with patch.object(db_manager, 'grievance') as mock_grievance:
        mock_grievance.get_grievance_files.return_value = [{'file': 'f1'}]
        result = db_manager.get_grievance_files('gid')
        assert isinstance(result, list)

# --- RECORDING OPERATIONS ---
def test_create_or_update_recording():
    with patch.object(db_manager, 'recording') as mock_recording:
        mock_recording.create_or_update_recording.return_value = 'rec_id'
        result = db_manager.create_or_update_recording({'foo': 'bar'})
        assert result == 'rec_id'

# --- TRANSCRIPTION OPERATIONS ---
def test_create_transcription():
    with patch.object(db_manager, 'transcription') as mock_transcription:
        mock_transcription.create_transcription.return_value = 'trans_id'
        result = db_manager.create_transcription({'foo': 'bar'})
        assert result == 'trans_id'

def test_update_transcription():
    with patch.object(db_manager, 'transcription') as mock_transcription:
        mock_transcription.update_transcription.return_value = True
        assert db_manager.update_transcription('tid', {'foo': 'bar'}) is True

# --- TRANSLATION OPERATIONS ---
def test_create_translation():
    with patch.object(db_manager, 'translation') as mock_translation:
        mock_translation.create_translation.return_value = 'trans_id'
        result = db_manager.create_translation({'foo': 'bar'})
        assert result == 'trans_id'

def test_update_translation():
    with patch.object(db_manager, 'translation') as mock_translation:
        mock_translation.update_translation.return_value = True
        assert db_manager.update_translation('tid', {'foo': 'bar'}) is True

# --- TASK OPERATIONS ---
def test_create_task():
    with patch.object(db_manager.task, 'create_task', return_value='task_id'):
        result = db_manager.create_task('task_id', 'task_name', 'entity_key', 'entity_id')
        assert result == 'task_id'

def test_get_task():
    with patch.object(db_manager, 'task') as mock_task:
        mock_task.get_task.return_value = {'id': 'task_id'}
        result = db_manager.get_task('task_id')
        assert result['id'] == 'task_id'

def test_update_task():
    with patch.object(db_manager, 'task') as mock_task:
        mock_task.update_task.return_value = True
        assert db_manager.update_task('task_id', {'foo': 'bar'}) is True

def test_get_pending_tasks():
    with patch.object(db_manager, 'task') as mock_task:
        mock_task.get_pending_tasks.return_value = [{'id': 'task_id'}]
        result = db_manager.get_pending_tasks()
        assert isinstance(result, list)

# --- FILE OPERATIONS ---
def test_store_file():
    with patch.object(db_manager, 'file') as mock_file:
        mock_file.store_file_attachment.return_value = True
        assert db_manager.store_file({'foo': 'bar'}) is True

def test_get_grievance_file_attachments():
    with patch.object(db_manager, 'file') as mock_file:
        mock_file.get_grievance_files.return_value = [{'file': 'f1'}]
        result = db_manager.get_grievance_file_attachments('gid')
        assert isinstance(result, list)

# --- SCHEMA OPERATIONS ---
def test_init_database():
    with patch.object(db_manager, 'table') as mock_table:
        mock_table.init_db.return_value = True
        assert db_manager.init_database() is True

def test_recreate_database():
    with patch.object(db_manager, 'table') as mock_table:
        mock_table.recreate_all_tables.return_value = True
        assert db_manager.recreate_database() is True

def test_get_available_statuses():
    with patch.object(db_manager, 'grievance') as mock_grievance:
        mock_grievance.get_available_statuses.return_value = [{'status': 'open'}]
        result = db_manager.get_available_statuses()
        assert isinstance(result, list)

