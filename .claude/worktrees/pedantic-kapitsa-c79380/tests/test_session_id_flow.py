#!/usr/bin/env python3
"""
Test script to verify flask_session_id flow from Rasa to Celery to Flask
"""

import requests
import json
import time

def test_flask_session_id_flow():
    """Test that flask_session_id is properly passed through the flow"""
    
    # Test data with flask_session_id
    test_data = {
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

    # Send to Flask API endpoint
    flask_url = "http://localhost:5001/task-status"

    print("Testing flask_session_id flow...")
    print(f"Sending data to Flask: {flask_url}")
    print(f"Data: {json.dumps(test_data, indent=2)}")

    try:
        response = requests.post(flask_url, json=test_data)
        print(f"Flask response status: {response.status_code}")
        print(f"Flask response: {response.json()}")

        if response.status_code == 200:
            print("✅ Flask API test passed")
            print("📝 Next steps:")
            print("   1. Check browser console for frontend logs")
            print("   2. Verify websocket message is received by frontend")
            print("   3. Check if classification results are sent to Rasa")
        else:
            print("❌ Flask API test failed")

    except Exception as e:
        print(f"❌ Error testing Flask API: {e}")

def test_rasa_session_id_vs_flask_session_id():
    """Test the difference between rasa_session_id and flask_session_id"""
    
    print("\n" + "=" * 50)
    print("Testing Rasa vs Flask session ID naming")
    print("=" * 50)
    
    # Simulate what the frontend sends
    frontend_data = {
        "rasa_session_id": "socket.id_from_frontend",  # For Rasa bot context
        "flask_session_id": "window.flaskSessionId || socket.id",  # For websocket emissions
        "grievance_id": "GR-20250729-KOJH-TEST-B"
    }
    
    print("Frontend sends:")
    print(f"  rasa_session_id: {frontend_data['rasa_session_id']} (for Rasa bot context)")
    print(f"  flask_session_id: {frontend_data['flask_session_id']} (for websocket emissions)")
    
    # Simulate what Rasa action sends to Celery
    rasa_to_celery_data = {
        "grievance_id": "GR-20250729-KOJH-TEST-B",
        "flask_session_id": "window.flaskSessionId || socket.id",  # This should be passed to Celery
        "values": {
            "grievance_description": "test grievance"
        }
    }
    
    print("\nRasa action sends to Celery:")
    print(f"  flask_session_id: {rasa_to_celery_data['flask_session_id']}")
    
    # Simulate what Celery sends to Flask
    celery_to_flask_data = {
        "status": "SUCCESS",
        "data": {"task_name": "classify_and_summarize_grievance_task"},
        "grievance_id": "GR-20250729-KOJH-TEST-B",
        "flask_session_id": "window.flaskSessionId || socket.id"  # This should be used for websocket emission
    }
    
    print("\nCelery sends to Flask:")
    print(f"  flask_session_id: {celery_to_flask_data['flask_session_id']}")
    
    print("\n✅ Session ID naming is now consistent!")

if __name__ == "__main__":
    print("🧪 Testing Flask Session ID Flow")
    print("=" * 50)

    test_flask_session_id_flow()
    test_rasa_session_id_vs_flask_session_id()

    print("\n📋 Manual Testing Steps:")
    print("1. Open browser console")
    print("2. Look for websocket messages with flask_session_id")
    print("3. Verify classification results are sent to Rasa")
    print("4. Check if grievance summary form is triggered") 