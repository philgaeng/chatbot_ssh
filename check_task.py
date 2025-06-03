#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from actions_server.db_manager import db_manager
    import json
    
    # Check the specific task status
    task_id = 'fb770fde-01c2-4158-963a-54a40292f138'
    print(f'=== Checking Task {task_id} ===')

    # Get task details
    task_info = db_manager.task.get_task(task_id)
    if task_info:
        print('Task found in database:')
        for key, value in task_info.items():
            if key == 'entities' and value:
                print(f'  {key}: {json.dumps(value, indent=2)}')
            else:
                print(f'  {key}: {value}')
    else:
        print('Task NOT found in database')

    print('\n=== Checking Task Status ===')
    task_status = db_manager.task.get_task_status(task_id)
    if task_status:
        print('Task status:')
        for key, value in task_status.items():
            print(f'  {key}: {value}')
    else:
        print('No task status found')

    # Also check for related tasks with same entity
    print('\n=== Checking Related Tasks for User US-20250603-KO-JH-0E37 ===')
    related_tasks = db_manager.task.get_tasks_by_entity_key('user_id', 'US-20250603-KO-JH-0E37')
    if related_tasks:
        print(f'Found {len(related_tasks)} related tasks:')
        for task in related_tasks:
            print(f'  Task {task["task_id"]}: {task["status_code"]} - {task["task_name"]}')
    else:
        print('No related tasks found')
        
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc() 