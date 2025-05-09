"""
Example tasks for the queue system.

This module contains example tasks that demonstrate:
1. Different priority levels (high, medium, low)
2. Task retries and error handling
3. Task monitoring and metrics
4. Different types of processing tasks
"""

import time
import random
from typing import Dict, Any
from .tasks import (
    high_priority_task,
    medium_priority_task,
    low_priority_task,
    task_with_retry
)
from .monitoring import log_task_event, metrics_collector

@high_priority_task
def process_voice_recording(audio_file: str) -> Dict[str, Any]:
    """Process a voice recording (high priority)"""
    log_task_event('process_voice_recording', 'started', {'file': audio_file})
    
    # Simulate processing
    time.sleep(random.uniform(0.5, 1.5))
    
    # Simulate occasional failure
    if random.random() < 0.2:
        raise Exception("Failed to process voice recording")
    
    result = {
        'status': 'success',
        'duration': random.uniform(10, 30),
        'text': 'Sample transcribed text'
    }
    
    log_task_event('process_voice_recording', 'completed', result)
    return result

@medium_priority_task
def extract_contact_info(text: str) -> Dict[str, Any]:
    """Extract contact information from text (medium priority)"""
    log_task_event('extract_contact_info', 'started', {'text_length': len(text)})
    
    # Simulate processing
    time.sleep(random.uniform(1, 2))
    
    result = {
        'status': 'success',
        'contacts': [
            {'name': 'John Doe', 'phone': '+1234567890'},
            {'name': 'Jane Smith', 'email': 'jane@example.com'}
        ]
    }
    
    log_task_event('extract_contact_info', 'completed', result)
    return result

@low_priority_task
def process_file_upload(file_path: str) -> Dict[str, Any]:
    """Process an uploaded file (low priority)"""
    log_task_event('process_file_upload', 'started', {'file': file_path})
    
    # Simulate processing
    time.sleep(random.uniform(2, 3))
    
    result = {
        'status': 'success',
        'file_size': random.randint(1000, 10000),
        'file_type': 'document'
    }
    
    log_task_event('process_file_upload', 'completed', result)
    return result

@medium_priority_task
@task_with_retry(max_retries=3)
def generate_file_metadata(file_path: str) -> Dict[str, Any]:
    """Generate metadata for a file with retry logic"""
    log_task_event('generate_file_metadata', 'started', {'file': file_path})
    
    # Simulate processing
    time.sleep(random.uniform(0.5, 1))
    
    # Simulate occasional failure
    if random.random() < 0.3:
        raise Exception("Failed to generate metadata")
    
    result = {
        'status': 'success',
        'metadata': {
            'created': '2024-01-01T00:00:00Z',
            'modified': '2024-01-02T00:00:00Z',
            'size': random.randint(1000, 10000),
            'type': 'document'
        }
    }
    
    log_task_event('generate_file_metadata', 'completed', result)
    return result

@low_priority_task
def cleanup_old_files(days: int = 30) -> Dict[str, Any]:
    """Clean up old files (low priority)"""
    log_task_event('cleanup_old_files', 'started', {'days': days})
    
    # Simulate processing
    time.sleep(random.uniform(1, 2))
    
    result = {
        'status': 'success',
        'files_removed': random.randint(5, 20),
        'space_freed': random.randint(1000, 5000)
    }
    
    log_task_event('cleanup_old_files', 'completed', result)
    return result

@medium_priority_task
def generate_usage_report(start_date: str, end_date: str) -> Dict[str, Any]:
    """Generate usage report (medium priority)"""
    log_task_event('generate_usage_report', 'started', {
        'start_date': start_date,
        'end_date': end_date
    })
    
    # Simulate processing
    time.sleep(random.uniform(1.5, 2.5))
    
    result = {
        'status': 'success',
        'report': {
            'total_tasks': random.randint(100, 1000),
            'success_rate': random.uniform(0.95, 0.99),
            'average_duration': random.uniform(1, 5)
        }
    }
    
    log_task_event('generate_usage_report', 'completed', result)
    return result

def run_example_tasks() -> None:
    """Run all example tasks"""
    print("\nRunning example tasks...")
    
    # Run high priority tasks
    process_voice_recording.delay('audio.mp3')
    process_voice_recording.delay('voice_note.wav')
    
    # Run medium priority tasks
    extract_contact_info.delay('Contact John at +1234567890 or email jane@example.com')
    generate_usage_report.delay('2024-01-01', '2024-01-31')
    
    # Run low priority tasks
    process_file_upload.delay('document.pdf')
    cleanup_old_files.delay(30)
    
    # Run task with retry
    generate_file_metadata.delay('image.jpg')
    
    print("All example tasks have been queued") 