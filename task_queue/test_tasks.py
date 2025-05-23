"""
Test suite for registered tasks in the Nepal Chatbot Queue System.

This module tests the complete workflow of processing a grievance:
1. File upload and processing
2. Audio transcription and classification
3. Database storage and updates
"""

import unittest
import os
import shutil
import uuid
from typing import Dict, Any
from datetime import datetime
from celery import group

# Import test configuration
from .test_config import redis_config
from .config import celery_app

# Configure Celery to use eager mode for testing
celery_app.conf.update(
    task_always_eager=True,  # Run tasks synchronously
    task_eager_propagates=True,  # Propagate exceptions
    result_backend='cache',  # Use simple cache backend for testing
    cache_backend='memory'  # Use in-memory cache
)

# Import task modules
from .registered_tasks import (
    process_file_upload_task,
    process_batch_files_task,
    transcribe_audio_file_task,
    classify_and_summarize_grievance_task,
    extract_contact_info_task,
    translate_grievance_to_english_task,
    store_result_to_db_task
)

# Import database manager
from actions_server.db_manager import db_manager

class TestGrievanceWorkflow(unittest.TestCase):
    """Test the complete workflow of processing a grievance"""
    
    def setUp(self):
        """Set up test environment"""
        # First create the user
        self.test_user_id = db_manager.user.create_or_update_user()
        print(f"Test user ID: {self.test_user_id}")
        test_dict = {
            'user_id': self.test_user_id,
            'source': 'acc'
        }
        
        if not self.test_user_id:
            raise Exception("Failed to create test user")
        
        # Create grievance entry
        self.test_grievance_id = db_manager.grievance.create_or_update_grievance(
            test_dict
        )
        
        if not self.test_grievance_id:
            raise Exception("Failed to create test grievance")
            
        # Source directory with sample files
        source_dir = "/home/ubuntu/nepal_chatbot/uploads/GR20250519857666_A"
        
        # Destination directory using the new grievance ID
        self.sample_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                     'uploads', self.test_grievance_id)
        
        # Copy the sample directory and its contents
        if os.path.exists(source_dir):
            shutil.copytree(source_dir, self.sample_dir)
        else:
            raise Exception(f"Source directory {source_dir} does not exist")
        
        # Sample files from the grievance directory
        self.sample_files = {
            'user_address': 'user_address.webm',
            'user_village': 'user_village.webm',
            'user_municipality': 'user_municipality.webm',
            'user_contact_phone': 'user_contact_phone.webm',
            'user_full_name': 'user_full_name.webm',
            'grievance_details': 'grievance_details.webm'
        }
        
        # Create test file data for each sample
        self.test_files_data = []
        for file_type, filename in self.sample_files.items():
            file_path = os.path.join(self.sample_dir, filename)
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                self.test_files_data.append({
                    'file_id': f"{self.test_grievance_id}_{file_type}",
                    'filename': filename,
                    'file_path': file_path,
                    'file_size': file_size,
                    'file_type': 'audio',
                    'file_name': filename
                })
    
    # def test_simple_workflow(self):
    #     """Test a simplified workflow focusing on basic task execution"""
    #     # Create test data
    #     test_data = {
    #         'grievance_id': self.test_grievance_id,
    #         'user_id': self.test_user_id,
    #         'grievance_details': 'Test grievance details',
    #         'grievance_summary': 'Test summary',
    #         'grievance_categories': 'Test category',
    #         'grievance_location': 'Test location',
    #         'grievance_claimed_amount': 1000.00,
    #         'entity_key': 'grievance_id',
    #         'entity_id': self.test_grievance_id
    #     }
        
    #     # Start the workflow
    #     result = classify_and_summarize_grievance_task.delay(test_data)
        
    #     # Get the actual result value from EagerResult
    #     if hasattr(result, 'get'):
    #         result = result.get()
    #     elif hasattr(result, 'result'):
    #         result = result.result
        
    #     # Verify the result
    #     self.assertIsNotNone(result)
    #     self.assertIn('status', result)
    #     self.assertEqual(result['status'], 'SUCCESS')
    #     self.assertIn('operation', result)
    #     self.assertEqual(result['operation'], 'classification')
    #     self.assertIn('value', result)
    #     self.assertIn('entity_key', result)
    #     self.assertEqual(result['entity_key'], 'grievance_id')
    #     self.assertEqual(result['id'], test_data['grievance_id'])

    def test_complete_workflow(self):
        """Test the complete workflow of processing a grievance"""
        print("\n=== Starting Grievance Processing Workflow ===")
        
        language_code = "en"
        # Use the grievance_id that was created in setUp
        test_grievance_id = self.test_grievance_id
        print(f"Using grievance ID from setUp: {test_grievance_id}")
        
        # Test grievance details workflow
        print("\n=== Testing Grievance Details Workflow ===")
        grievance_path = os.path.join(self.sample_dir, 'grievance_details.webm')
        print(f"Processing grievance file: {grievance_path}")
        
        # Initialize task chain
        task_chain = {
            'file_data': {
                'file_name': 'grievance_details.webm',
                'file_path': grievance_path,
                'file_type': 'webm',
                'file_size': os.path.getsize(grievance_path),
                'upload_date': datetime.now().isoformat(),
                'language_code': language_code,
                'grievance_id': test_grievance_id
            }
        }
        
        # Test parallel processing workflow
        print("\n1. Starting transcription...")
        transcription_result = transcribe_audio_file_task.delay(
            file_path=grievance_path,
            language=language_code,
            grievance_id=test_grievance_id,
            service='llm_queue'
        )
        
        # Handle EagerResult
        if hasattr(transcription_result, 'get'):
            transcription_result = transcription_result.get()
        elif hasattr(transcription_result, 'result'):
            transcription_result = transcription_result.result
            
        self.assertIsNotNone(transcription_result)
        self.assertEqual(transcription_result['status'], 'SUCCESS')
        self.assertEqual(transcription_result['operation'], 'transcription')
        print(f"Transcription: {transcription_result['value']}")
        print(f"\n\n Transcription result: {transcription_result}")
        
        # Test parallel classification and storage
        print("\n2. Starting parallel classification and storage...")
        classification_group = group(
            classify_and_summarize_grievance_task.s(transcription_result, emit_websocket=False),  # Disable websocket
            store_result_to_db_task.s('transcription', transcription_result)
        )
        classification_group_results = classification_group.apply()
        
        # Handle group results
        results = []
        for result in classification_group_results:
            if hasattr(result, 'get'):
                results.append(result.get())
            elif hasattr(result, 'result'):
                results.append(result.result)
            else:
                results.append(result)
                
        print(f"Classification group results: {results}")
        # Verify classification results
        for result in results:
            self.assertIsNotNone(result)
            self.assertIn('status', result)
            if result['operation'] == 'classification':
                self.assertIn('value', result)
                print(f"Classification: {result['value']}")
                classification_result = result
                print(f"Classification result: {classification_result}")
            elif result['operation'] == 'transcription':
                self.assertEqual(result['status'], 'success')
                print("Transcription stored successfully")
        
        # Test contact info workflow
        print("\n=== Testing Contact Info Workflow ===")
        contact_path = os.path.join(self.sample_dir, 'user_contact.webm')
        print(f"Processing contact file: {contact_path}")
        
        # Update task chain for contact info
        task_chain['file_data'].update({
            'file_name': 'user_contact.webm',
            'file_path': contact_path,
            'file_size': os.path.getsize(contact_path)
        })
        
        # Test contact info workflow
        print("\n1. Starting contact info transcription...")
        contact_transcription = transcribe_audio_file_task.delay(
            file_path=contact_path,
            language=language_code,
            grievance_id=test_grievance_id,
            service='llm_queue'
        )
        self.assertIsNotNone(contact_transcription)
        self.assertEqual(contact_transcription['status'], 'SUCCESS')
        self.assertEqual(contact_transcription['operation'], 'transcription')
        print(f"Contact Transcription: {contact_transcription['value']}")
        
        # Test parallel contact info processing
        print("\n2. Starting parallel contact info processing...")
        contact_group = group(
            extract_contact_info_task.s(),  # Will receive contact_transcription as transcription_data
            store_result_to_db_task.s('transcription')  # Will receive contact_transcription as input_data
        )
        contact_results = contact_group.apply()
        
        # Verify contact info results
        for result in contact_results:
            self.assertIsNotNone(result)
            self.assertIn('status', result)
            if result['operation'] == 'contact_extraction':
                self.assertIn('value', result)
                print(f"Contact Info: {result['value']}")
            elif result['operation'] == 'transcription':
                self.assertEqual(result['status'], 'success')
                print("Contact transcription stored successfully")
        
        print("\n=== Grievance Processing Workflow Completed ===")

if __name__ == '__main__':
    unittest.main() 