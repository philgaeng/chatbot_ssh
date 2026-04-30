#!/usr/bin/env python3
"""
Test script for the frontend-based classification results flow
"""

import requests
import json
import time

def test_frontend_classification_flow():
    """Test the frontend-based classification flow"""
    
    # Test data from the log
    test_data = {
        "grievance_id": "GR-20250729-KOJH-7EF0-B",
        "session_id": "test_session_123",
        "status": "SUCCESS",
        "data": {
            "grievance_summary": "धूलो सबैतिर छ। मेरा बच्चाहरू धेरै खोकी लागिरहेका छन। मलाई के गर्ने थाहा छैन। मलाई लाग्छ अस्पताल जानु पर्ला तर पैसा छैन।",
            "grievance_categories": ["Environmental - Air Pollution"],
            "grievance_description": "there is dust everywhere\nmy kids are coughing very hard \ni dont know what to do \nI think I need to go to hospital\nbut I dont have money",
            "task_name": "classify_and_summarize_grievance_task",
            "status": "SUCCESS"
        }
    }
    
    # Send to Flask API (this will trigger the frontend flow)
    flask_url = "http://localhost:5001/task-status"
    
    print("Testing frontend-based classification flow...")
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
            print("   2. Verify Rasa receives the classification message")
            print("   3. Check if grievance summary form is triggered")
        else:
            print("❌ Flask API test failed")
            
    except Exception as e:
        print(f"❌ Error testing Flask API: {e}")

def test_rasa_classification_message():
    """Test Rasa directly with the classification message format"""
    
    rasa_url = "http://localhost:5005/webhooks/rest/webhook"
    
    # Simulate the message that frontend would send
    classification_data = {
        "grievance_summary": "धूलो सबैतिर छ। मेरा बच्चाहरू धेरै खोकी लागिरहेका छन।",
        "grievance_categories": ["Environmental - Air Pollution"],
        "grievance_description": "there is dust everywhere",
        "task_name": "classify_and_summarize_grievance_task",
        "status": "SUCCESS"
    }
    
    rasa_message = {
        "sender": "test_session_123",
        "message": f"/classification_results{json.dumps(classification_data)}"
    }
    
    print(f"\nTesting Rasa with classification message: {rasa_url}")
    print(f"Message: {json.dumps(rasa_message, indent=2)}")
    
    try:
        response = requests.post(rasa_url, json=rasa_message)
        print(f"Rasa response status: {response.status_code}")
        print(f"Rasa response: {response.json()}")
        
        if response.status_code == 200:
            print("✅ Rasa classification message test passed")
        else:
            print("❌ Rasa classification message test failed")
            
    except Exception as e:
        print(f"❌ Error testing Rasa classification message: {e}")

if __name__ == "__main__":
    print("🧪 Testing Frontend-Based Classification Flow")
    print("=" * 50)
    
    test_frontend_classification_flow()
    print("\n" + "=" * 50)
    test_rasa_classification_message()
    
    print("\n📋 Manual Testing Steps:")
    print("1. Open browser console")
    print("2. Look for '🎯 Classification completed, sending results to Rasa...'")
    print("3. Look for '📤 Sending classification results to Rasa:'")
    print("4. Look for '✅ Classification results sent to Rasa successfully'")
    print("5. Check if Rasa responds with classification results")
    print("6. Verify grievance summary form is triggered") 