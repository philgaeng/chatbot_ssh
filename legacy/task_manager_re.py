from celery import Celery
from task_queue.logger import TaskLogger
from task_queue.registered_tasks import (
    transcribe_audio_file_task,
    classify_and_summarize_grievance_task,
    extract_contact_info_task,
    store_result_to_db_task
)
from actions_server.db_manager import db_manager
import json

class TaskManager:
    def __init__(self):
        self.logger = TaskLogger(service_name='task_manager')
        
    def complete_task(self, result, stage=None):
        """Complete a task and store its result"""
        try:
            # Prepare the result data for database storage
            result_data = self.prepare_task_result_data_to_db(result)
            
            # Store the result in the database
            if result_data:
                store_result_to_db_task.delay(result_data)
                
            return True
            
        except Exception as e:
            self.logger.log_task_event('complete_task', 'failed', {'error': str(e)})
            return False

    def prepare_task_result_data_to_db(self, input_data):
        """Prepare task result data for database storage"""
        try:
            if not isinstance(input_data, dict):
                self.logger.log_task_event('prepare_task_result_data_to_db', 'failed', 
                                         {'error': 'Input data must be a dictionary'})
                return None
                
            # Initialize the result dictionary
            result = {
                'status': input_data.get('status', 'UNKNOWN'),
                'operation': input_data.get('operation', 'unknown'),
                'field_name': input_data.get('field_name', ''),
                'value': {}
            }
            
            # Handle the value field
            value = input_data.get('value', {})
            
            # If value is a string, try to parse it as JSON
            if isinstance(value, str):
                try:
                    value = json.loads(value)
                except json.JSONDecodeError:
                    # If it's not valid JSON, keep it as is
                    pass
                    
            # If value is a dictionary, process its items
            if isinstance(value, dict):
                for field, field_value in value.items():
                    result['value'][field] = field_value
            else:
                # If value is not a dictionary, store it as is
                result['value'] = value
                
            return result
            
        except Exception as e:
            self.logger.log_task_event('prepare_task_result_data_to_db', 'failed', {'error': str(e)})
            return None 