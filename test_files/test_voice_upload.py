#!/usr/bin/env python3
import requests
import os
import time
import json
from pathlib import Path
import logging
import base64
import subprocess


# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Server URL
BASE_URL = "http://localhost:5001"  # Change this if your server is on a different port

def create_test_webm_file(path, size_kb=10):
    """Create a test webm file with valid header for testing"""
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # A minimal valid WebM file header (20 bytes)
    # This isn't a complete audio file but has the correct WebM signature
    webm_header = bytearray.fromhex(
        '1A45DFA3' +  # EBML header
        '01000000' +  # Version 1
        '00000000' +  # Reserved
        '00000000'    # Reserved
    )
    
    # Create a file with the specified size
    with open(path, 'wb') as f:
        # Write WebM header
        f.write(webm_header)
        
        # Fill the rest with random-ish data to reach the desired size
        remaining_bytes = size_kb * 1024 - len(webm_header)
        if remaining_bytes > 0:
            # Create some repeating pattern data instead of just zeros
            pattern = b'AUDIO_TEST_DATA_'
            repetitions = (remaining_bytes // len(pattern)) + 1
            f.write((pattern * repetitions)[:remaining_bytes])
    
    logger.info(f"Created test WebM file: {path} ({size_kb} KB)")
    return path

def test_grievance_creation():
    """Test creating a new grievance"""
    url = f"{BASE_URL}/create-grievance"
    
    try:
        response = requests.post(url, json={"source": "test"})
        response.raise_for_status()
        result = response.json()
        
        if result.get("status") == "SUCCESS":
            grievance_id = result.get("id")
            logger.info(f"Successfully created grievance with ID: {grievance_id}")
            return grievance_id
        else:
            logger.error(f"Failed to create grievance: {result}")
            return None
    except Exception as e:
        logger.error(f"Error creating grievance: {str(e)}")
        return None

def upload_voice_recordings(grievance_id):
    """Test uploading voice recordings with specific field names"""
    # Use the direct file upload endpoint which is more appropriate for our test
    url = f"{BASE_URL}/submit-voice-grievance"
    
    # Create test audio files
    test_files_dir = Path("./test_files")
    field_names = ["name.webm", "grievance_details.webm", "user_contact_phone.webm"]
    test_file_paths = {}
    
    for field_name in field_names:
        file_path = test_files_dir / field_name
        test_file_paths[field_name] = create_test_webm_file(file_path, 20)
    
    # Prepare multipart form data
    files = {}
    for field_name, file_path in test_file_paths.items():
        files[field_name] = (field_name, open(file_path, 'rb'), 'audio/webm')
    
    # Add form fields
    data = {
        "grievance_id": grievance_id,
        "interface_language": "en"
    }
    
    try:
        logger.info(f"Uploading files to {url} with grievance_id={grievance_id}")
        response = requests.post(url, files=files, data=data)
        
        # Log response details for debugging
        logger.info(f"Response status: {response.status_code}")
        try:
            result = response.json()
            logger.info(f"Response content: {result}")
        except ValueError:
            logger.warning(f"Response is not JSON: {response.text[:200]}")
            return None
        
        response.raise_for_status()
        
        # Close all file handles
        for field_name, file_tuple in files.items():
            file_tuple[1].close()
        
        return result
    except Exception as e:
        logger.error(f"Error uploading files: {str(e)}")
        
        # Close all file handles
        for field_name, file_tuple in files.items():
            try:
                file_tuple[1].close()
            except:
                pass
        
        return None

def check_transcriptions(grievance_id):
    """Check if transcriptions were created for the grievance"""
    # In a real test, you would query your database for transcriptions
    logger.info(f"Checking for transcriptions for grievance ID: {grievance_id}")
    
    # Wait a bit for async processing
    time.sleep(5)
    
    # Print the directory where files should be stored
    uploads_dir = Path(f"/home/ubuntu/nepal_chatbot/uploads/voice_recordings/{grievance_id}")
    if uploads_dir.exists():
        files = list(uploads_dir.glob('*'))
        logger.info(f"Found {len(files)} files in uploads directory:")
        for f in files:
            size = os.path.getsize(f)
            logger.info(f"  - {f.name} ({size} bytes)")
    else:
        logger.warning(f"Uploads directory not found: {uploads_dir}")

def check_db_records(grievance_id):
    """Check if database records were created for the uploads"""
    logger.info("Running database check...")
    
    try:
        # Use subprocess to run the Python code safely
        cmd = [
            'python3', '-c', 
            f'''
import sys
sys.path.append('.')
from accessible_server.db_manager import DatabaseManager
db = DatabaseManager()
recordings = db.execute_query('SELECT * FROM grievance_voice_recordings WHERE grievance_id = "{grievance_id}"')
print(f'Found {{len(recordings)}} voice recordings')
for rec in recordings:
    print(f'  - {{rec.get("file_path", "unknown")}} | Status: {{rec.get("processing_status", "unknown")}}')
transcriptions = db.execute_query('SELECT * FROM grievance_transcriptions WHERE grievance_id = "{grievance_id}"')
print(f'Found {{len(transcriptions)}} transcriptions')
for trans in transcriptions:
    print(f'  - Recording ID: {{trans.get("recording_id", "unknown")}} | Text: {{trans.get("automated_transcript", "unknown")[:50]}}...')
            '''
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='/home/ubuntu/nepal_chatbot')
        logger.info(f"Database query results:\n{result.stdout}")
        
        if result.stderr:
            logger.error(f"Database query errors:\n{result.stderr}")
            
    except Exception as e:
        logger.error(f"Error checking database: {e}")

def main():
    """Run the test process"""
    logger.info("Starting voice grievance test")
    
    # Create a new grievance
    grievance_id = test_grievance_creation()
    if not grievance_id:
        logger.error("Test failed: Could not create grievance")
        return
    
    # Upload voice recordings
    upload_result = upload_voice_recordings(grievance_id)
    if not upload_result or upload_result.get("status") != "success":
        logger.error("Test failed: Could not upload voice recordings")
        return
    
    # Check if files were saved correctly
    check_transcriptions(grievance_id)
    
    # Wait longer for transcription processing
    logger.info("Waiting 10 seconds for transcription processing...")
    time.sleep(10)
    
    # Check database records
    logger.info("Checking database records:")
    check_db_records(grievance_id)
    
    logger.info("Test completed!")
    logger.info(f"Grievance ID: {grievance_id}")

if __name__ == "__main__":
    main() 