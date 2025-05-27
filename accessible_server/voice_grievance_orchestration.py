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
    
    is_contact_info = 'user' in recording_data.get('file_name')
    is_grievance_details = 'grievance' in recording_data.get('file_name')

    # Initialize task chain
    task_chain = {
        'temp_path': file_path,  # Store path for cleanup
        'file_data': recording_data
    }

    # Start with transcription task
    chain_tasks = [transcribe_audio_file_task.s(recording_data)]
    
    # Build the task chain based on file type
    if is_contact_info:
        task_chain['type'] = 'contact_info'
        # After transcription, extract contact info and store in parallel
        chain_tasks.extend([
            group(
                extract_contact_info_task.s(),
                store_result_to_db_task.s()
            )
        ])
        
    elif is_grievance_details:
        task_chain['type'] = 'grievance_details'
        # After transcription, store and classify in parallel
        chain_tasks.extend([
            group(
                store_result_to_db_task.s(),
                classify_and_summarize_grievance_task.s()
            )
        ])
        
        # Add translation if needed
        if language != 'en':
            chain_tasks.extend([
                translate_grievance_to_english_task.s(),
                store_result_to_db_task.s()
            ])
    else:
        task_chain['type'] = 'transcription_only'
        # Just store the transcription
        chain_tasks.append(store_result_to_db_task.s())
    
    # Create and execute the final chain
    final_chain = chain(*chain_tasks)
    result = final_chain.delay()
    
    # Store the final task ID for tracking
    task_chain['task_id'] = result.id

    return task_chain

def orchestrate_voice_processing(audio_files: List[Any], recording_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrate parallel processing of multiple audio files.

    Args:
        audio_files: List of uploaded audio files
        language: Language code for processing
        
    Returns:
        Dict containing task IDs and status for all files
    """
    try:
        # Process each file and collect task chains
        file_tasks = {}
        temp_paths = []
        
        for audio_file in audio_files:
            if audio_file:
                # Get the original filename from the file_data if available
                filename = audio_file.get('filename', f"audio_{uuid.uuid4()}")
                file_path = audio_file.get('file_path')
                
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