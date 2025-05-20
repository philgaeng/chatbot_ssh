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

# Import test configuration
from .test_config import redis_config

# Import task modules
from .registered_tasks import (
    process_file_upload_task,
    process_batch_files_task,
    transcribe_audio_file_task,
    classify_and_summarize_grievance_task,
    extract_contact_info_task,
    translate_grievance_to_english_task,
    store_user_info_task,
    store_grievance_task,
    store_transcription_task,
    update_task_execution_task
)

# Import database manager
from actions_server.db_manager import db_manager

class TestGrievanceWorkflow(unittest.TestCase):
    """Test the complete workflow of processing a grievance"""
    
    def setUp(self):
        """Set up test environment"""
        # First create the user
        self.test_user_id = db_manager.user.create_user()
        
        if not self.test_user_id:
            raise Exception("Failed to create test user")
        
        # Create grievance entry
        self.test_grievance_id = db_manager.grievance.create_grievance(
            self.test_user_id, 
            source='acc'
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
    
    def test_complete_workflow(self):
        """Test the complete workflow of processing a grievance"""
        print("\n=== Starting Grievance Processing Workflow ===")
        
        # Generate a test task ID
        test_task_id = f"test_task_{uuid.uuid4().hex[:8]}"
        
        language_code = "en"
        # Step 2: Transcribe grievance details
        print("\n2. Transcribing Grievance...")
        grievance_file = os.path.join(self.sample_dir, 'grievance_details.webm')
        transcription_result = transcribe_audio_file_task(
            grievance_file,
            language_code,  
            self.test_grievance_id,
            service='llm_queue',
            task_id=test_task_id  # Pass the test task ID
        )
        self.assertIsNotNone(transcription_result)
        self.assertIn('status', transcription_result)
        self.assertIn('transcription', transcription_result)
        print("\nTranscription Details:")
        print(f"Status: {transcription_result['status']}")
        print(f"Transcription: {transcription_result['transcription']}")
        if 'confidence' in transcription_result:
            print(f"Confidence: {transcription_result['confidence']}")
        if 'language' in transcription_result:
            print(f"Language: {transcription_result['language']}")
        
        # Step 3: Classify and summarize grievance
        print("\n3. Classifying Grievance...")
        classification_result = classify_and_summarize_grievance_task(
            self.test_grievance_id,
            task_id=test_task_id  # Pass the test task ID
        )
        self.assertIsNotNone(classification_result)
        self.assertIn('status', classification_result)
        self.assertIn('summary', classification_result)
        self.assertIn('categories', classification_result)
        print("\nClassification Details:")
        print(f"Status: {classification_result['status']}")
        print(f"Summary: {classification_result['summary']}")
        print("\nCategories:")
        for category in classification_result['categories']:
            print(f"- {category}")
        if 'priority' in classification_result:
            print(f"Priority: {classification_result['priority']}")
        if 'sentiment' in classification_result:
            print(f"Sentiment: {classification_result['sentiment']}")
        
        # Step 4: Store user information
        print("\n4. Storing User Information...")
        user_info = {
            'name': 'Test User',
            'phone': '+1234567890',
            'address': 'Test Address',
            'village': 'Test Village',
            'municipality': 'Test Municipality'
        }
        user_result = store_user_info_task(
            user_info,
            {'grievance_id': self.test_grievance_id, 'task_id': test_task_id}
        )
        self.assertIsNotNone(user_result)
        self.assertIn('status', user_result)
        print(f"User Info Storage Result: {user_result}")
        
        # Step 5: Store grievance information
        print("\n5. Storing Grievance Information...")
        grievance_result = store_grievance_task(
            user_info,
            {'grievance_id': self.test_grievance_id, 'task_id': test_task_id}
        )
        self.assertIsNotNone(grievance_result)
        self.assertIn('status', grievance_result)
        print(f"Grievance Storage Result: {grievance_result}")
        
        # Step 6: Update task execution status
        print("\n6. Updating Task Status...")
        update_result = update_task_execution_task(
            test_task_id,  # Use the test task ID
            {'status': 'completed'}
        )
        self.assertIsNotNone(update_result)
        self.assertIn('status', update_result)
        print(f"Task Update Result: {update_result}")
        
        print("\n=== Grievance Processing Workflow Completed ===")

if __name__ == '__main__':
    unittest.main() 