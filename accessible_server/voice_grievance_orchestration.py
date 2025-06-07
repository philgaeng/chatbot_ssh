from typing import Dict, Any, List, Optional, Tuple
import os
import uuid
from celery import chain, group
from .voice_grievance_helpers import *
from task_queue.registered_tasks import (
    transcribe_audio_file_task,
    extract_contact_info_task,
    classify_and_summarize_grievance_task,
    translate_grievance_to_english_task,
    store_result_to_db_task
)
from actions_server.db_manager import db_manager
from logger.logger import TaskLogger

task_logger = TaskLogger(service_name='voice_grievance')

def process_single_audio_file(recording_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process a single audio file and return its task chain.

    Args:
        recording_data: Dictionary containing recording data passed from the submit_grievance endpoint
        
    Returns:
        Dict containing task chain information
    """
    file_path = recording_data.get('file_path')
    language = recording_data.get('language_code')
    task_logger.log_task_event('process_single_audio_file', 'file_saved', {'file_path': file_path})
    
    # Use field_name instead of file_name, and add null safety
    field_name = recording_data.get('field_name', '')
    is_contact_info = 'user' in field_name if field_name else False
    is_grievance_details = 'grievance' in field_name if field_name else False

    # Initialize task chain
    task_chain = {
        'temp_path': file_path,  # Store path for cleanup
        'file_data': recording_data
    }

    # Build the task chain based on file type
    if is_contact_info:
        task_chain['type'] = 'contact_info'
        # Simple sequential chain: transcription → contact extraction
        result = chain(
            transcribe_audio_file_task.s(recording_data),
            extract_contact_info_task.s(),
        ).delay()
        
    elif is_grievance_details:
        task_chain['type'] = 'grievance_details'
        # Simple sequential chain: transcription → classification [→ translation]
        if language != 'en':
            result = chain(
                transcribe_audio_file_task.s(recording_data),
                classify_and_summarize_grievance_task.s(),
                translate_grievance_to_english_task.s(),
            ).delay()
        else:
            result = chain(
                transcribe_audio_file_task.s(recording_data),
                classify_and_summarize_grievance_task.s(),
            ).delay()
        
    else:
        task_chain['type'] = 'transcription_only'
        # Simple transcription only
        result = transcribe_audio_file_task.s(recording_data).delay()
    
    # Store the final task ID for tracking
    task_chain['task_id'] = result.id

    return task_chain

def orchestrate_voice_processing(audio_files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Orchestrate parallel processing of multiple audio files.

    Args:
        audio_files: List of uploaded audio files in format:
            [{'field_name': str, 'file_path': str, 'file_data': dict}, ...]
        
    Returns:
        Dict containing task IDs and status for all files
    """
    try:
        # Process each file and collect task chains
        file_tasks = {}
        temp_paths = []
        
        for recording_data in audio_files:
             
            # Use field_name as the filename for task tracking
            filename = recording_data.get('field_name', f"audio_{uuid.uuid4()}")
            file_path = recording_data.get('file_path')
            
            if not file_path:
                continue
                
            task_chain = process_single_audio_file(recording_data)
            file_tasks[filename] = {
                'task_id': task_chain['task_id'],
                'type': task_chain['type'],
                'status': 'pending'
            }
            temp_paths.append(task_chain['temp_path'])
        
        if not file_tasks:
            raise ValueError("No valid audio files provided")
        
        return {
            'status': 'SUCCESS',
            'files': file_tasks
        }
            
    except Exception as e:
        task_logger.log_task_event('orchestrate_voice_processing', 'failed', {'error': str(e)})
        # Clean up any temp files that were created
        for temp_path in temp_paths:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as cleanup_error:
                task_logger.log_task_event('orchestrate_voice_processing', 'failed', {'error': str(cleanup_error)})
        raise