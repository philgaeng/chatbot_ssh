import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_manager import DBManager

def test_create_grievance_with_specific_data():
    """Test create_grievance with specific data"""
    try:
        data = {
            'grievance_id': 'GR-20250608-KO-JH-A91C-B',
            'user_id': 'US-20250608-KO-JH-6783',
            'source': 'bot'
        }
        
        # Create instance of DBManager
        db_manager = DBManager()
        
        # Call create_grievance
        result = db_manager.grievance.create_grievance(data=data)
        
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

if __name__ == '__main__':
    test_create_grievance_with_specific_data() 