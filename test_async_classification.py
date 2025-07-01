#!/usr/bin/env python3
"""
Test script for async classification using Celery tasks
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from task_queue.registered_tasks import classify_and_summarize_grievance_task
from celery import chain
import time

def test_async_classification():
    """Test the async classification task"""
    
    # Prepare test data similar to what would come from transcription
    test_input_data = {
        'grievance_id': 'test_grievance_123',
        'user_id': 'test_user_456',
        'language_code': 'en',
        'user_province': 'Province 1',
        'user_district': 'Kathmandu',
        'values': {
            'grievance_details': 'The road in our village is very bad. It has many potholes and is difficult to drive on. We need it to be repaired soon.'
        }
    }
    
    print("Testing async classification with input data:")
    print(f"Input data: {test_input_data}")
    
    try:
        # Launch the task directly (not through chain for testing)
        task_result = classify_and_summarize_grievance_task.delay(test_input_data)
        task_id = task_result.id
        
        print(f"Task launched with ID: {task_id}")
        print("Waiting for task to complete...")
        
        # Wait for the task to complete
        result = task_result.get(timeout=60)  # 60 second timeout
        
        print(f"✅ Task completed successfully!")
        print(f"Result: {result}")
        
        if result.get('status') == SUCCESS:
            values = result.get('values', {})
            print(f"✅ Classification successful!")
            print(f"Summary: {values.get('grievance_summary', 'N/A')}")
            print(f"Categories: {values.get('grievance_categories', [])}")
        else:
            print(f"❌ Task failed with status: {result.get('status')}")
            print(f"Error: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error testing async classification: {e}")
        import traceback
        traceback.print_exc()

def test_chain_classification():
    """Test classification through a chain (like in voice orchestration)"""
    
    # Simulate the chain: transcription_result -> classification
    transcription_result = {
        'grievance_id': 'test_grievance_123',
        'user_id': 'test_user_456',
        'language_code': 'en',
        'user_province': 'Province 1',
        'user_district': 'Kathmandu',
        'values': {
            'grievance_details': 'The road in our village is very bad. It has many potholes and is difficult to drive on. We need it to be repaired soon.'
        }
    }
    
    print("\nTesting classification through chain:")
    print(f"Transcription result: {transcription_result}")
    
    try:
        # Create a chain: transcription_result -> classification
        result = chain(
            classify_and_summarize_grievance_task.s(transcription_result)
        ).delay()
        
        print(f"Chain launched with ID: {result.id}")
        print("Waiting for chain to complete...")
        
        # Wait for the chain to complete
        final_result = result.get(timeout=60)  # 60 second timeout
        
        print(f"✅ Chain completed successfully!")
        print(f"Final result: {final_result}")
        
        if final_result.get('status') == SUCCESS:
            values = final_result.get('values', {})
            print(f"✅ Classification successful!")
            print(f"Summary: {values.get('grievance_summary', 'N/A')}")
            print(f"Categories: {values.get('grievance_categories', [])}")
        else:
            print(f"❌ Chain failed with status: {final_result.get('status')}")
            print(f"Error: {final_result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"❌ Error testing chain classification: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Testing Async Classification with Celery")
    print("=" * 50)
    
    # Test direct task execution
    test_async_classification()
    
    # Test chain execution
    test_chain_classification()
    
    print("\n" + "=" * 50)
    print("Test completed!") 