import pytest
from unittest.mock import patch, MagicMock
from backend.services.database_services.postgres_services import db_manager

id_generation_data = {
    'complainant_province': 'Koshi',
    'complainant_district': 'Jhapa',
    'complainant_office': 'Office1',
    'source': 'bot',
}

complainant_id = db_manager.create_complainant_id(id_generation_data)
grievance_id = db_manager.create_grievance_id(id_generation_data)

complainant_data = {
    'complainant_id': complainant_id,
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



grievance_data = {
    'grievance_id': grievance_id,
    'complainant_id': complainant_id,
    'grievance_description': 'Test grievance',
    'grievance_status': 'pending',

}
# --- ID GENERATION ---
def test_create_complainant_id():
    result = db_manager.create_complainant_id(id_generation_data)
    assert result is not None
    assert isinstance(result, str)

def test_create_grievance_id():
    result = db_manager.create_grievance_id(id_generation_data)
    assert result is not None
    assert isinstance(result, str)


# --- COMPLAINANT OPERATIONS ---
def test_create_complainant():
    result = db_manager.create_complainant(complainant_data)
    assert result is True
    assert db_manager.get_complainant_by_id(complainant_id) is not None
    assert db_manager.get_complainant_by_id(complainant_id)['complainant_id'] == complainant_id
    assert db_manager.get_complainant_by_id(complainant_id)['complainant_province'] == 'Koshi'
    assert db_manager.get_complainant_by_id(complainant_id)['complainant_email'] == 'test_complainant@gmail.com'

#update complainant data
updated_complainant_data = complainant_data.copy()
updated_complainant_data['complainant_municipality'] = 'Bagmati'
updated_complainant_data['complainant_email'] = 'test_complainant_updated@gmail.com'

def test_update_complainant():
    # Create first
    result = db_manager.update_complainant(complainant_id, updated_complainant_data)
    assert result is True
    updated = db_manager.get_complainant_by_id(complainant_id)
    assert updated['complainant_id'] == complainant_id
    assert updated['complainant_municipality'] == 'Bagmati'
    assert updated['complainant_email'] == 'test_complainant_updated@gmail.com'


def test_find_complainant_by_phone():
    # Insert a complainant with a known phone number
    phone = complainant_data['complainant_phone']
    result = db_manager.find_complainant_by_phone(phone)
    assert len(result)
    assert any(c['complainant_id'] == complainant_id for c in result)

# --- Add similar tests for all other methods, using real data ---

# Example for grievance:
def test_create_grievance():
    # Create complainant first
    db_manager.create_grievance(grievance_data)
    result = db_manager.get_grievance_by_id(grievance_id)
    assert result is not None
    assert result['grievance_id'] == grievance_id

# ...repeat for update_grievance, get_grievance_status, etc.

