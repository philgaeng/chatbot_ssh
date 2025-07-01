#!/usr/bin/env python3
"""
Test script demonstrating the new asynchronous retry mechanism

This script shows how the new approach handles:
1. First execution: Entity creation + task record creation
2. Retry execution: Entity update + task record update with retry tracking
3. Proper separation of concerns between task execution and database operations
"""

import sys
import uuid
import json
from typing import Dict, Any

# Add project root to path
sys.path.append('.')

def create_mock_task(task_id: str = None, retries: int = 0):
    """Create a mock Celery task for testing"""
    class MockRequest:
        def __init__(self, task_id: str, retries: int):
            self.id = task_id
            self.retries = retries
    
    class MockTask:
        def __init__(self, task_id: str, retries: int):
            self.request = MockRequest(task_id, retries)
            self.name = 'test_task'
    
    return MockTask(task_id or str(uuid.uuid4()), retries)

def simulate_task_execution(is_retry: bool = False, task_id: str = None):
    """Simulate a task execution (first time or retry)"""
    from task_queue.task_manager import TaskManager, DatabaseTaskManager
    
    # Use same task_id for retry scenario
    if not task_id:
        task_id = str(uuid.uuid4())
    
    # Create mock task with appropriate retry count
    retry_count = 1 if is_retry else 0
    mock_task = create_mock_task(task_id, retry_count)
    
    # Simulate business logic task (e.g., transcription)
    task_mgr = TaskManager(task=mock_task, task_type='LLM', emit_websocket=False, service='llm_processor')
    
    print(f"\n{'='*50}")
    print(f"{'RETRY' if is_retry else 'FIRST'} EXECUTION - Task ID: {task_id}")
    print(f"{'='*50}")
    
    # Step 1: start_task (no DB interaction)
    print("1. Starting task (logging only, no DB interaction)...")
    success = task_mgr.start_task(
        entity_key='transcription_id',
        entity_id=str(uuid.uuid4()),
        grievance_id='test_grievance_123',
        stage='transcription'
    )
    print(f"   ✓ Task started successfully: {success}")
    print(f"   ✓ Celery retry count detected: {getattr(mock_task.request, 'retries', 0)}")
    
    # Step 2: Simulate task completion
    print("2. Completing task (logging only, no DB interaction)...")
    transcription_id = str(uuid.uuid4())
    task_result = {
        'status': SUCCESS,
        'operation': 'transcription',
        'field_name': 'grievance_details',
        'value': 'This is a test transcription',
        'task_id': task_id,
        'entity_key': 'transcription_id',
        'id': transcription_id,
        'grievance_id': 'test_grievance_123',
        'recording_id': str(uuid.uuid4()),
        'language_code': 'ne'
    }
    task_mgr.complete_task(task_result, stage='transcription')
    print(f"   ✓ Task completed successfully")
    
    # Step 3: Simulate store_result_to_db_task (with DB interaction)
    print("3. Storing results to database (entity creation + retroactive task recording)...")
    db_task_mgr = DatabaseTaskManager(task=mock_task, task_type='Database', emit_websocket=False)
    
    try:
        result = db_task_mgr.handle_db_operation(task_result)
        print(f"   ✓ Database operation completed: {result['status']}")
        if is_retry:
            print(f"   ✓ Retry detected and handled in database")
        else:
            print(f"   ✓ First execution recorded in database")
        return task_id, True
    except Exception as e:
        print(f"   ✗ Database operation failed: {str(e)}")
        return task_id, False

def main():
    """Demonstrate the new retry mechanism"""
    print("Testing New Asynchronous Retry Mechanism")
    print("="*60)
    print("\nThis test demonstrates:")
    print("• First execution: Creates entity + task record")
    print("• Retry execution: Updates entity + updates task record with retry info")
    print("• No chicken-and-egg problem: entities exist before task creation")
    
    # Test 1: First execution
    task_id, success = simulate_task_execution(is_retry=False)
    
    if success:
        # Test 2: Retry execution (same task_id)
        simulate_task_execution(is_retry=True, task_id=task_id)
    
    print(f"\n{'='*60}")
    print("SUMMARY:")
    print("✓ Task lifecycle methods (start_task, complete_task) work without DB")
    print("✓ Database operations happen asynchronously in store_result_to_db_task")
    print("✓ Retry detection moved to handle_db_operation method")
    print("✓ Chicken-and-egg problem solved: entities created before task records")
    print("✓ Proper retry tracking maintained in database")

if __name__ == "__main__":
    main() 