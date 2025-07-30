#!/usr/bin/env python3
"""
Test script to verify the complete flask_session_id flow
"""

import requests
import json
import time

def test_complete_flask_session_id_flow():
    """Test the complete flow from frontend to Rasa to Celery to Flask"""
    
    print("🧪 Testing Complete Flask Session ID Flow")
    print("=" * 60)
    
    # Step 1: Simulate what the frontend sends to Rasa
    print("1. Frontend sends to Rasa:")
    frontend_message = '/introduce{"province": "Koshi", "district": "Jhapa", "flask_session_id": "test_flask_session_123"}'
    print(f"   Message: {frontend_message}")
    print(f"   This should set flask_session_id slot in Rasa")
    
    # Step 2: Simulate what Rasa action sends to Celery
    print("\n2. Rasa action sends to Celery:")
    rasa_to_celery_data = {
        'grievance_id': 'GR-20250729-KOJH-TEST-B',
        'complainant_id': 'CM-20250729-KOJH-TEST-B',
        'language_code': 'en',
        'complainant_province': 'Koshi',
        'complainant_district': 'Jhapa',
        'flask_session_id': 'test_flask_session_123',  # From slot
        'values': {
            'grievance_description': 'test grievance description'
        }
    }
    print(f"   Data: {json.dumps(rasa_to_celery_data, indent=4)}")
    
    # Step 3: Simulate what Celery sends to Flask
    print("\n3. Celery sends to Flask:")
    celery_to_flask_data = {
        "grievance_id": "GR-20250729-KOJH-TEST-B",
        "flask_session_id": "test_flask_session_123",
        "status": "SUCCESS",
        "data": {
            "grievance_summary": "धूलो सबैतिर छ। मेरा बच्चाहरू धेरै खोकी लागिरहेका छन।",
            "grievance_categories": ["Environmental - Air Pollution"],
            "grievance_description": "there is dust everywhere in my house",
            "task_name": "classify_and_summarize_grievance_task",
            "status": "SUCCESS"
        }
    }
    print(f"   Data: {json.dumps(celery_to_flask_data, indent=4)}")
    
    # Step 4: Test Flask API endpoint
    print("\n4. Testing Flask API endpoint:")
    flask_url = "http://localhost:5001/task-status"
    
    try:
        response = requests.post(flask_url, json=celery_to_flask_data)
        print(f"   Flask response status: {response.status_code}")
        print(f"   Flask response: {response.json()}")
        
        if response.status_code == 200:
            print("   ✅ Flask API test passed")
            print("   📝 Next steps:")
            print("      1. Check browser console for frontend logs")
            print("      2. Verify websocket message is received by frontend")
            print("      3. Check if classification results are sent to Rasa")
        else:
            print("   ❌ Flask API test failed")
            
    except Exception as e:
        print(f"   ❌ Error testing Flask API: {e}")
    
    print("\n" + "=" * 60)
    print("📋 Manual Testing Steps:")
    print("1. Open browser console")
    print("2. Look for '/introduce' message with flask_session_id")
    print("3. Check if flask_session_id is stored in Rasa slot")
    print("4. Verify classification results are sent to Rasa")
    print("5. Check if grievance summary form is triggered")

if __name__ == "__main__":
    test_complete_flask_session_id_flow() 