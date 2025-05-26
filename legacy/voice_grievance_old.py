import os
import logging
import uuid
import json
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
from openai import OpenAI
from datetime import datetime
import traceback
from dotenv import load_dotenv
from task_queue.tasks import high_priority_task
from task_queue.monitoring import log_task_event
from task_queue.registered_tasks import (
    process_voice_grievance_task,
    transcribe_audio_file_task,
    classify_and_summarize_grievance_task,
    extract_contact_info_task
)

# Update imports to use actions_server
from actions_server.db_manager import db_manager
from actions_server.constants import GRIEVANCE_STATUS
from task_queue.registered_tasks import classify_and_summarize_grievance_task, transcribe_audio_file_task, extract_contact_info_task

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('/home/ubuntu/nepal_chatbot/.env')
open_ai_key = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client
try:
    client = OpenAI(api_key=open_ai_key)
    logger.info("OpenAI client initialized")
except Exception as e:
    logger.error(f"Error initializing OpenAI client: {str(e)}")
    client = None

# Configure upload settings
UPLOAD_FOLDER = 'uploads'
AUDIO_EXTENSIONS = {'webm', 'mp3', 'wav', 'ogg', 'm4a'}
VALID_EXTENSIONS = ['.webm', '.mp3', '.wav', '.ogg', '.m4a']
MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25MB max size for audio files

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ------- Utility Functions -------

def ensure_directory_exists(directory_path: str) -> None:
    """Ensure that a directory exists, creating it if necessary"""
    os.makedirs(directory_path, exist_ok=True)

def create_grievance_directory(grievance_id: str, dir_type: str = None) -> str:
    """Create and return a directory path for a specific grievance"""
    if dir_type:
        directory = os.path.join(UPLOAD_FOLDER, dir_type, grievance_id)
    else:
        directory = os.path.join(UPLOAD_FOLDER, grievance_id)
    
    ensure_directory_exists(directory)
    return directory

def get_recording_type_from_filename(filename: str) -> str:
    """Determine recording type based on filename"""
    filename = filename.lower()
    
    if 'grievance' in filename or 'grievance_details' in filename:
        return 'details'
    elif 'name' in filename or 'user_full_name' in filename:
        return 'contact'
    elif 'phone' in filename or 'user_contact_phone' in filename or 'contact' in filename:
        return 'contact'
    elif 'municipality' in filename or 'user_municipality' in filename:
        return 'location'
    elif 'village' in filename or 'user_village' in filename:
        return 'location'
    elif 'address' in filename or 'user_address' in filename:
        return 'location'
    
    return 'details'  # Default

def get_grievance_field_from_filename(filename: str) -> str:
    """Map filename to corresponding grievance data field"""
    filename = filename.lower()
    
    if 'grievance' in filename or 'grievance_details' in filename:
        return 'grievance_details'
    elif 'name' in filename or 'user_full_name' in filename:
        return 'user_full_name'
    elif 'phone' in filename or 'user_contact_phone' in filename:
        return 'user_contact_phone'
    elif 'municipality' in filename or 'user_municipality' in filename:
        return 'user_municipality'
    elif 'village' in filename or 'user_village' in filename:
        return 'user_village'
    elif 'address' in filename or 'user_address' in filename:
        return 'user_address'
    
    return None  # No direct mapping

def ensure_valid_filename(original_name: str, field_key: str = None) -> str:
    """Ensure the filename has a valid extension and is secure"""
    # First secure the filename
    filename = secure_filename(original_name)
    
    # If 'blob' or empty, use the field_key if available
    if not filename or filename == 'blob':
        if field_key:
            filename = secure_filename(field_key)
        else:
            filename = f"audio_{uuid.uuid4()}"
    
    # Check if the filename has a valid audio extension
    has_valid_extension = any(filename.lower().endswith(ext) for ext in VALID_EXTENSIONS)
    if not has_valid_extension:
        filename += '.webm'  # Default to webm extension
    
    return filename

def save_uploaded_file(file_obj, directory: str, filename: str) -> Tuple[str, int]:
    """Save an uploaded file and return the path and size"""
    if not file_obj:
        raise ValueError("No file provided")
    
    file_path = os.path.join(directory, filename)
    file_obj.save(file_path)
    file_size = os.path.getsize(file_path)
    
    # If file is empty, remove it and raise error
    if file_size == 0:
        try:
            os.remove(file_path)
        except Exception:
            pass
        raise ValueError("File is empty")
    
    return file_path, file_size

def store_recording_metadata(recording_data: Dict[str, Any]) -> Optional[str]:
    """Store recording metadata in database and return recording ID"""
    logger.info(f"Storing voice recording metadata: {recording_data['recording_id']}")
    return db_manager.file.store_voice_recording(recording_data)

def store_transcription_data(transcription_data: Dict[str, Any]) -> Optional[str]:
    """Store transcription data in database and return transcription ID"""
    return db_manager.file.store_transcription(transcription_data)

def update_recording_status(recording_id: str, status: str) -> bool:
    """Update the processing status of a recording"""
    return db_manager.file.update_recording_status(recording_id, status)

# ------- API Registration -------

def register_voice_endpoints(app: Flask):
    """Register voice-related endpoints to the Flask app"""
    
    @app.route('/transcribe-audio', methods=['POST'])
    def transcribe_audio():
        """Transcribe audio files using OpenAI Whisper API"""
        language = 'en'  # Default language
        logger.info("Received audio transcription request")

        # Check if audio file is provided
        if 'audio' not in request.files:
            logger.error("No audio file in request")
            return jsonify({"error": "No audio file provided"}), 400

        audio_file = request.files['audio']
        if not audio_file:
            logger.error("Empty audio file")
            return jsonify({"error": "Empty audio file"}), 400

        # Check file size
        audio_file.seek(0, 2)  # Seek to end of file
        file_size = audio_file.tell()  # Get current position (file size)
        audio_file.seek(0)  # Reset file pointer to beginning

        if file_size > MAX_AUDIO_SIZE:
            logger.error(f"Audio file too large: {file_size} bytes")
            return jsonify({"error": "Audio file too large"}), 413

        # Get language if provided
        language = request.form.get('language', language)

        # Check if OpenAI client is available
        if not client:
            logger.error("OpenAI client not available")
            return jsonify({"error": "Transcription service unavailable"}), 503

        # Create temp file name
        filename = ensure_valid_filename(audio_file.filename)
        temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{filename}")

        # Save temp file
        audio_file.save(temp_path)
        logger.info(f"Saved temporary audio file: {temp_path}")

        response = None
        try:
            # Queue transcription task
            task = transcribe_audio_file_task.delay(temp_path, language)
            logger.info(f"Queued transcription task: {task.id}")
            response = jsonify({
                "status": "success",
                "message": "Transcription task queued",
                "task_id": task.id
            }), 202
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                logger.info(f"Removed temporary file: {temp_path}")
        return response

    @app.route('/create-grievance', methods=['POST'])
    def create_new_grievance():
        """Create a new grievance and return the ID"""
        try:
            logger.info("Received request to create new grievance")
            
            # Parse request data (optional source parameter)
            data = request.json or {}
            source = data.get('source', 'accessibility')
            
            # Create grievance using the db_manager
            grievance_id = db_manager.grievance.create_grievance(source=source)
            if not grievance_id:
                logger.error("Failed to create new grievance")
                return jsonify({"error": "Failed to create grievance"}), 500
            
            logger.info(f"Successfully created new grievance with ID: {grievance_id}")
            
            # Return success with grievance ID
            response_data = {
                "status": "success",
                "message": "Grievance created successfully",
                "id": grievance_id
            }
            return jsonify(response_data), 200
                
        except Exception as e:
            logger.error(f"Error creating grievance: {str(e)}", exc_info=True)
            return jsonify({"error": f"Error creating grievance: {str(e)}"}), 500

    @app.route('/accessible-file-upload', methods=['POST'])
    def accessible_file_upload():
        """Handle file uploads from the accessible interface directly"""
        try:
            logger.info("Received file upload from accessible interface")
            
            # Check if grievance_id is provided
            grievance_id = request.form.get('grievance_id')
            if not grievance_id:
                logger.error("No grievance_id provided for file upload")
                return jsonify({"error": "Grievance ID is required for file upload"}), 400
            
            # Determine the interface language from the request
            interface_language = request.form.get('interface_language', 'ne')
            
            # Check if files are provided
            if 'files[]' not in request.files:
                logger.error("No files[] in request.files")
                return jsonify({"error": "No files provided under 'files[]' key"}), 400
                
            files = request.files.getlist('files[]')
            if not files or len(files) == 0:
                logger.error("No files provided in the request")
                return jsonify({"error": "No files found in the request"}), 400
            
            # Create the upload directory for this grievance
            upload_dir = create_grievance_directory(grievance_id)
            
            # Process and save each file
            saved_files = []
            has_voice_recording = False
            
            for file in files:
                if not file or not file.filename:
                    logger.warning("Invalid file provided")
                    continue
                
                try:
                    # Check if file is a voice recording
                    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
                    if file_ext in AUDIO_EXTENSIONS:
                        has_voice_recording = True
                    
                    # Generate a unique ID for the file
                    file_id = str(uuid.uuid4())
                    
                    # Secure and ensure valid filename
                    filename = ensure_valid_filename(file.filename)
                    unique_filename = f"{file_id}_{filename}"
                    
                    # Save the file
                    file_path, file_size = save_uploaded_file(file, upload_dir, unique_filename)
                    
                    # Store file metadata in database
                    file_data = {
                        'file_id': file_id,
                        'grievance_id': grievance_id,
                        'file_name': filename,
                        'file_path': file_path,
                        'file_type': file.content_type or file_ext or 'application/octet-stream',
                        'file_size': file_size
                    }
                    
                    # Store in database
                    success = db_manager.file.store_file_attachment(file_data)
                    if success:
                        logger.info(f"Successfully stored file metadata for: {file_id}")
                        saved_files.append({
                            'file_id': file_id,
                            'filename': filename,
                            'file_size': file_size
                        })
                    else:
                        logger.error(f"Failed to store file metadata for: {file_id}")
                        # Remove the file if db storage failed
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            logger.error(f"Error removing file: {str(e)}")
                except Exception as e:
                    logger.error(f"Error processing file {file.filename if file else 'unknown'}: {str(e)}")
                    continue
            
            if saved_files:
                response_data = {
                    "status": "success",
                    "message": f"Successfully uploaded {len(saved_files)} files",
                    "files": saved_files,
                    "grievance_id": grievance_id
                }
                
                # Add warning if voice recordings were uploaded
                if has_voice_recording:
                    response_data["warning"] = (
                        "Voice recordings were detected. For better processing of voice recordings, "
                        "please use the voice grievance collection process instead of direct file upload."
                    )
                
                return jsonify(response_data), 200
            else:
                logger.error("No files were saved")
                return jsonify({"error": "No files were saved"}), 400
                
        except Exception as e:
            logger.error(f"Error handling accessible file upload: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({"error": f"Error handling file upload: {str(e)}"}), 500
    
    @app.route('/submit-voice-grievance', methods=['POST'])
    def submit_voice_grievance():
        """Submit voice recordings for a grievance"""
    try:
            # Get form data
            form_data = request.form
            files = request.files
            
            # Validate required fields
            if not files:
                return jsonify({
                    'status': 'error',
                    'message': 'No files provided'
                }), 400
            
            # Create grievance record
            grievance_id = db_manager.grievance.create_grievance({
                'status': 'pending',
                'interface_language': form_data.get('interface_language', 'ne')
            })
            
            if not grievance_id:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to create grievance record'
                }), 500
            
            # Save files and collect references
            file_references = []
            for field_name, file in files.items():
                if file and file.filename:
                    # Save file
                    file_path = save_uploaded_file(
                        file,
                        create_grievance_directory(grievance_id),
                        ensure_valid_filename(file.filename, field_name)
                    )
                    
                    # Store file metadata
                    file_id = db_manager.file.store_file_metadata({
                        'grievance_id': grievance_id,
                        'file_path': file_path,
                        'file_type': get_file_type(file.filename),
                        'field_name': field_name
                    })
                    
                    if file_id:
                        file_references.append(file_id)
            
            if not file_references:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to save files'
                }), 500
            
            # Queue processing task
            task = process_voice_grievance_task.delay(
                grievance_id,
                file_references,
                form_data.get('interface_language', 'ne')
            )
            
            return jsonify({
                'status': 'success',
                'grievance_id': grievance_id,
                'task_id': task.id,
                'message': 'Voice grievance submitted successfully'
            })
            
        except Exception as e:
            logger.error(f"Error submitting voice grievance: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    @app.route('/grievance-status/<grievance_id>', methods=['GET'])
    def get_grievance_status(grievance_id):
        """Get the current status of a grievance and its tasks"""
        try:
            # Get grievance data
            grievance = db_manager.grievance.get_grievance_by_id(grievance_id)
            if not grievance:
                return jsonify({
                    'status': 'error',
                    'message': 'Grievance not found'
                }), 404
            
            # Get transcription task statuses
            transcription_tasks = grievance.get('transcription_tasks', {})
            transcription_status = {}
            for file_id, task_id in transcription_tasks.items():
                task_result = AsyncResult(task_id)
                transcription_status[file_id] = {
                    'status': task_result.status,
                    'result': task_result.result if task_result.ready() else None
                }
            
            # Get classification task status
            classification_task_id = grievance.get('classification_task_id')
            classification_status = None
            if classification_task_id:
                task_result = AsyncResult(classification_task_id)
                classification_status = {
                    'status': task_result.status,
                    'result': task_result.result if task_result.ready() else None
                }
            
            return jsonify({
                'status': 'success',
                'grievance_id': grievance_id,
                'grievance_status': grievance['status'],
                'transcription_status': transcription_status,
                'classification_status': classification_status
            })
            
    except Exception as e:
            logger.error(f"Error getting grievance status: {str(e)}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500

    return app

def process_voice_grievance(grievance_id: str, file_references: List[str], language_code: str = 'None') -> Dict[str, Any]:
    """Process voice recordings for a grievance
    
    Args:
        grievance_id: ID of the grievance
        file_references: List of file references to process
        
    Returns:
        Dict containing processing results and transcriptions
    """
    log_task_event('process_voice_grievance', 'started', {
        'grievance_id': grievance_id,
        'files': file_references
    })
    
    try:
        logger.info(f"Processing voice grievance {grievance_id} with {len(file_references)} files")
        
        # Get file data from database
        files_data = {}
        for file_id in file_references:
            file_data = db_manager.file.get_file_by_id(file_id)
            if file_data and os.path.exists(file_data['file_path']):
                files_data[file_id] = file_data
        
        # Check if we have all required files
        if not files_data:
            logger.error("No valid files found")
            raise Exception("No valid files found for processing")
        
        # Transcribe each audio file
        transcriptions = {}
        for file_id, file_data in files_data.items():
            file_path = file_data['file_path']
            
            # Skip non-audio files
            file_ext = file_data['file_type'].lower()
            if file_ext not in AUDIO_EXTENSIONS:
                logger.warning(f"Skipping non-audio file: {file_path}")
                continue
            
            try:
                # Queue transcription task
                task = transcribe_audio_file_task.delay(file_path, language_code)
                
                # Map to appropriate field based on filename
                field_name = get_grievance_field_from_filename(file_data['file_name'])
                if field_name:
                    transcriptions[field_name] = task.id  # Store task ID for tracking
                else:
                    # Default to file_id as key
                    transcriptions[file_id] = task.id  # Store task ID for tracking
                    
                logger.info(f"Queued transcription task for {file_data['file_name']}: {task.id}")
                
            except Exception as e:
                logger.error(f"Error queuing transcription for {file_path}: {str(e)}")
                continue
        
        if not transcriptions:
            raise Exception("Failed to process any voice recordings")
        
        # Update grievance with transcription task IDs
        success = update_grievance_from_voice(grievance_id, transcriptions)
        if not success:
            raise Exception(f"Failed to update grievance {grievance_id} with voice data")
        
        log_task_event('process_voice_grievance', 'completed', {
            'grievance_id': grievance_id,
            'status': 'success'
        })
        
        return {
            'status': 'success',
            'grievance_id': grievance_id,
            'transcription_tasks': transcriptions  # Return task IDs instead of results
        }
        
    except Exception as e:
        log_task_event('process_voice_grievance', 'failed', {
            'grievance_id': grievance_id,
            'error': str(e)
        })
        raise

def update_grievance_from_voice(grievance_id: str, transcriptions: Dict[str, str]) -> bool:
    """Update grievance with data extracted from voice recordings"""
    try:
        logger.info(f"Updating grievance {grievance_id} with voice data")
        
        # extract language from transcriptions
        language_code = transcriptions.get('language', 'ne')
        
        # Extract grievance details
        grievance_details = transcriptions.get('grievance_details', '')
        
        # Extract contact information
        user_full_name = transcriptions.get('user_full_name', '')
        user_contact_phone = transcriptions.get('user_contact_phone', '')
        
        # Extract address information
        user_municipality = transcriptions.get('user_municipality', '')
        user_village = transcriptions.get('user_village', '')
        user_address = transcriptions.get('user_address', '')
        
        # Combine address fields if needed
        combined_address = ''
        if user_municipality:
            combined_address += user_municipality + ', '
        if user_village:
            combined_address += user_village + ', '
        if user_address:
            combined_address += user_address
        
        # Use OpenAI to classify and summarize grievance if we have grievance details
        classification_result = {'summary': '', 'categories': []}
        if grievance_details:
            # Queue classification task
            task = classify_and_summarize_grievance_task.delay(grievance_details, language_code)
            classification_result = {
                'task_id': task.id,
                'status': 'pending'
            }
        
        # Prepare grievance data
        grievance_data = {
            'grievance_id': grievance_id,
            'grievance_details': grievance_details,
            'grievance_summary': '',  # Will be updated when classification task completes
            'grievance_categories': [],  # Will be updated when classification task completes
            'user_full_name': user_full_name,
            'user_contact_phone': user_contact_phone,
            'user_municipality': user_municipality,
            'user_village': user_village,
            'user_address': user_address,
            'grievance_location': combined_address.strip(', ') if combined_address else user_address,
            'status': GRIEVANCE_STATUS["SUBMITTED"],
            'source': 'accessibility',
            'submission_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'language_code': language_code,
            'classification_status': 'pending',
            'classification_task_id': classification_result.get('task_id')
        }
        
        # Update grievance in database
        success = db_manager.grievance.update_grievance_db(grievance_data)
        
        if success:
            logger.info(f"Successfully updated grievance {grievance_id} with voice data")
            return True
        else:
            logger.error(f"Failed to update grievance {grievance_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating grievance from voice: {str(e)}", exc_info=True)
        return False

def update_recording_language(recording_id: str, language_code: str) -> bool:
    """Update the detected language for a voice recording
    
    Args:
        recording_id: The ID of the recording to update
        language_code: The detected language code
        
    Returns:
        bool: True if the update was successful, False otherwise
    """
    try:
        logger.info(f"Updating language for recording {recording_id} to {language_code}")
        return db_manager.file.update_recording_language(recording_id, language_code)
    except Exception as e:
        logger.error(f"Error updating recording language: {str(e)}")
        return False