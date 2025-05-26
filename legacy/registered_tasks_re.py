from celery import shared_task
from task_queue.logger import TaskLogger
from task_queue.task_manager_re import TaskManager
from actions_server.db_manager import db_manager
import json

# Initialize TaskManager
task_mgr = TaskManager()

@shared_task
def transcribe_audio_file_task(file_path, language='en', emit_websocket=True):
    """Transcribe an audio file to text"""
    try:
        # Your transcription logic here
        result = {
            'status': 'SUCCESS',
            'operation': 'transcription',
            'field_name': 'transcription',
            'value': 'Sample transcription text'  # Replace with actual transcription
        }
        
        if emit_websocket:
            task_mgr.complete_task(result)
            
        return result
        
    except Exception as e:
        return {
            'status': 'ERROR',
            'operation': 'transcription',
            'field_name': 'transcription',
            'value': str(e)
        }

@shared_task
def classify_and_summarize_grievance_task(transcription_result, emit_websocket=True):
    """Classify and summarize a grievance from its transcription"""
    try:
        # Your classification and summarization logic here
        temp_result = {
            'grievance_categories': ['category1', 'category2'],
            'grievance_summary': 'Sample summary'
        }
        
        result = {
            'status': 'SUCCESS',
            'operation': 'classification',
            'field_name': 'grievance_categories, grievance_summary',
            'value': temp_result  # Keep as Python dict
        }
        
        if emit_websocket:
            task_mgr.complete_task(result, stage='classification')
            
        return result
        
    except Exception as e:
        return {
            'status': 'ERROR',
            'operation': 'classification',
            'field_name': 'grievance_categories, grievance_summary',
            'value': str(e)
        }

@shared_task
def extract_contact_info_task(transcription_result, emit_websocket=True):
    """Extract contact information from transcription"""
    try:
        # Your contact info extraction logic here
        result = {
            'status': 'SUCCESS',
            'operation': 'contact_extraction',
            'field_name': 'contact_info',
            'value': {
                'name': 'Sample Name',
                'phone': '1234567890'
            }
        }
        
        if emit_websocket:
            task_mgr.complete_task(result)
            
        return result
        
    except Exception as e:
        return {
            'status': 'ERROR',
            'operation': 'contact_extraction',
            'field_name': 'contact_info',
            'value': str(e)
        }

@shared_task
def store_result_to_db_task(result_data):
    """Store task result in the database"""
    try:
        if not isinstance(result_data, dict):
            raise ValueError("Result data must be a dictionary")
            
        # Store the result in the database
        success = db_manager.store_task_result(result_data)
        
        return {
            'status': 'SUCCESS' if success else 'ERROR',
            'operation': 'store_result',
            'field_name': result_data.get('field_name', ''),
            'value': result_data.get('value', {})
        }
        
    except Exception as e:
        return {
            'status': 'ERROR',
            'operation': 'store_result',
            'field_name': result_data.get('field_name', '') if isinstance(result_data, dict) else '',
            'value': str(e)
        } 