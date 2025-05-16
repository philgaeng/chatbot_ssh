"""
Tests for the voice processing system.

This module contains tests for the voice processing functionality,
including file handling, transcription, and task management.
"""

import os
import unittest
import tempfile
import shutil
from typing import Dict, Any
from datetime import datetime

from actions_server.voice_processor import voice_processor
from actions_server.db_manager import db_manager
from actions_server.constants import AUDIO_EXTENSIONS

class TestVoiceProcessor(unittest.TestCase):
    """Test cases for the voice processor."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Create test grievance
        self.grievance_id = str(uuid.uuid4())
        self.grievance_dir = os.path.join(self.test_dir, self.grievance_id)
        os.makedirs(self.grievance_dir)
        
        # Create test audio files
        self.test_files = self._create_test_files()
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def _create_test_files(self) -> Dict[str, str]:
        """Create test audio files."""
        files = {}
        for ext in AUDIO_EXTENSIONS:
            filename = f"test_{ext}.{ext}"
            filepath = os.path.join(self.grievance_dir, filename)
            with open(filepath, 'w') as f:
                f.write(f"Test content for {filename}")
            files[filename] = filepath
        return files
    
    def test_process_voice_grievance(self):
        """Test processing voice grievance."""
        # Store file metadata
        file_references = []
        for filename, filepath in self.test_files.items():
            file_data = {
                'file_id': str(uuid.uuid4()),
                'grievance_id': self.grievance_id,
                'file_name': filename,
                'file_path': filepath,
                'file_type': filename.rsplit('.', 1)[1],
                'file_size': os.path.getsize(filepath),
                'upload_date': datetime.now().isoformat(),
                'language_code': 'ne'
            }
            file_id = db_manager.store_file_metadata(file_data)
            if file_id:
                file_references.append(file_id)
        
        # Process voice grievance
        result = voice_processor.process_voice_grievance(
            self.grievance_id,
            file_references
        )
        
        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['grievance_id'], self.grievance_id)
        self.assertIn('transcription_tasks', result)
        
        # Verify task records
        tasks = db_manager.get_grievance_tasks(self.grievance_id)
        self.assertTrue(len(tasks) > 0)
        
        # Verify file records
        files = db_manager.get_grievance_files(self.grievance_id)
        self.assertEqual(len(files), len(file_references))
    
    def test_invalid_file_references(self):
        """Test processing with invalid file references."""
        result = voice_processor.process_voice_grievance(
            self.grievance_id,
            ['invalid_file_id']
        )
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('error', result)
    
    def test_empty_file_references(self):
        """Test processing with empty file references."""
        result = voice_processor.process_voice_grievance(
            self.grievance_id,
            []
        )
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('error', result)
    
    def test_non_audio_files(self):
        """Test processing with non-audio files."""
        # Create a non-audio file
        non_audio_file = os.path.join(self.grievance_dir, 'test.txt')
        with open(non_audio_file, 'w') as f:
            f.write('Test content')
        
        # Store file metadata
        file_data = {
            'file_id': str(uuid.uuid4()),
            'grievance_id': self.grievance_id,
            'file_name': 'test.txt',
            'file_path': non_audio_file,
            'file_type': 'txt',
            'file_size': os.path.getsize(non_audio_file),
            'upload_date': datetime.now().isoformat(),
            'language_code': 'ne'
        }
        file_id = db_manager.store_file_metadata(file_data)
        
        # Process voice grievance
        result = voice_processor.process_voice_grievance(
            self.grievance_id,
            [file_id]
        )
        
        # Verify result
        self.assertEqual(result['status'], 'error')
        self.assertIn('error', result)
    
    def test_task_recording(self):
        """Test task recording functionality."""
        # Create a test task
        task_id = str(uuid.uuid4())
        task_name = 'test_task'
        task_type = 'test'
        
        # Record task start
        success = db_manager.record_task_start(
            task_id,
            self.grievance_id,
            task_name,
            task_type
        )
        self.assertTrue(success)
        
        # Record task completion
        success = db_manager.record_task_completion(
            task_id,
            'COMPLETED',
            execution_time_ms=100,
            result_text='Test result'
        )
        self.assertTrue(success)
        
        # Verify task record
        tasks = db_manager.get_grievance_tasks(self.grievance_id)
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task['task_id'], task_id)
        self.assertEqual(task['task_name'], task_name)
        self.assertEqual(task['task_type'], task_type)
        self.assertEqual(task['status'], 'COMPLETED')
        self.assertEqual(task['result_text'], 'Test result')
        self.assertEqual(task['execution_time_ms'], 100)

if __name__ == '__main__':
    unittest.main() 