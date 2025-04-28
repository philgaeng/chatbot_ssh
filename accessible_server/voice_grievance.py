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

# Update imports to use actions_server
from actions_server.db_manager import db_manager
from actions_server.constants import GRIEVANCE_STATUS

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

def transcribe_audio_file(file_path: str, language: str = None) -> str:
    """Transcribe an audio file using OpenAI Whisper API"""
    if not client:
        raise RuntimeError("OpenAI client not available for transcription")
    
    try:
        with open(file_path, "rb") as audio_data:
            response = client.audio.transcriptions.create(
                file=audio_data,
                model="whisper-1",
                language=language
            )
        return response.text
    except Exception as e:
        logger.error(f"Error transcribing audio file {file_path}: {str(e)}")
        raise

def store_recording_metadata(recording_data: Dict[str, Any]) -> Optional[str]:
    """Store recording metadata in database and return recording ID"""
    logger.info(f"Storing voice recording metadata: {recording_data['recording_id']}")
    return db_manager.store_voice_recording(recording_data)

def store_transcription_data(transcription_data: Dict[str, Any]) -> Optional[str]:
    """Store transcription data in database and return transcription ID"""
    return db_manager.store_transcription(transcription_data)

def update_recording_status(recording_id: str, status: str) -> bool:
    """Update the processing status of a recording"""
    return db_manager.update_recording_status(recording_id, status)

# ------- API Registration -------

def register_voice_endpoints(app: Flask):
    """Register voice-related endpoints to the Flask app"""
    
    @app.route('/transcribe-audio', methods=['POST'])
    def transcribe_audio():
        """Transcribe audio files using OpenAI Whisper API"""
        try:
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
            
            try:
                # Transcribe with OpenAI Whisper
                transcription = transcribe_audio_file(temp_path, language)
                
                # Return transcription
                logger.info(f"Transcription successful: {transcription[:50]}...")
                return jsonify({"transcription": transcription}), 200
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    logger.info(f"Removed temporary file: {temp_path}")
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}", exc_info=True)
            return jsonify({"error": f"Error transcribing audio: {str(e)}"}), 500
    
    @app.route('/create-grievance', methods=['POST'])
    def create_new_grievance():
        """Create a new grievance and return the ID"""
        try:
            logger.info("Received request to create new grievance")
            
            # Parse request data (optional source parameter)
            data = request.json or {}
            source = data.get('source', 'accessibility')
            
            # Create grievance using the db_manager
            grievance_id = db_manager.create_grievance(source=source)
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
    
    @app.route('/submit-voice-grievance', methods=['POST'])
    def submit_voice_grievance():
        """Submit a grievance with voice recordings"""
        try:
            logger.info("Received voice grievance submission")
            
            # Check if grievance_id is provided in the form data
            grievance_id = request.form.get('grievance_id')
            if grievance_id:
                logger.info(f"Using provided grievance ID: {grievance_id}")
            
            # Determine the interface language from the request
            # Default to Nepali unless explicitly from English interface
            interface_language = request.form.get('interface_language', 'ne')
            
            # Check if this is a direct file upload from the accessible interface
            files = request.files
            if files:
                return handle_direct_file_upload(files, grievance_id, interface_language)
            
            # Parse request data for API clients
            data = request.json
            if not data:
                logger.error("No JSON data in request")
                return jsonify({"error": "No data provided"}), 400
            
            # Create new grievance if not provided
            if not grievance_id:
                grievance_id = db_manager.create_grievance(source='accessibility', language_code=interface_language)
                if not grievance_id:
                    logger.error("Failed to create new grievance")
                    return jsonify({"error": "Failed to create grievance"}), 500
                logger.info(f"Created grievance with ID: {grievance_id}")
            
            # Get file references
            file_references = data.get('file_references', [])
            if not file_references:
                logger.error("No file references provided")
                return jsonify({"error": "No audio files provided"}), 400
            
            # Process audio files for transcription
            transcription_results = process_voice_grievance(grievance_id, file_references)
            if not transcription_results:
                logger.error("Failed to process voice grievance")
                return jsonify({"error": "Failed to process voice grievance"}), 500
            
            # Update grievance with transcriptions
            success = update_grievance_from_voice(grievance_id, transcription_results)
            if not success:
                logger.error(f"Failed to update grievance {grievance_id} with voice data")
                return jsonify({"error": "Failed to update grievance"}), 500
            
            # Return success response with grievance ID
            return jsonify({
                "status": "success",
                "message": "Voice grievance submitted successfully",
                "grievance_id": grievance_id
            }), 200
            
        except Exception as e:
            logger.error(f"Error submitting voice grievance: {str(e)}", exc_info=True)
            return jsonify({"error": f"Error submitting voice grievance: {str(e)}"}), 500

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
            
            for file in files:
                if not file or not file.filename:
                    logger.warning("Invalid file provided")
                    continue
                
                try:
                    # Generate a unique ID for the file
                    file_id = str(uuid.uuid4())
                    
                    # Secure and ensure valid filename
                    filename = ensure_valid_filename(file.filename)
                    unique_filename = f"{file_id}_{filename}"
                    
                    # Save the file
                    file_path, file_size = save_uploaded_file(file, upload_dir, unique_filename)
                    
                    # Determine file type from extension
                    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                    
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
                    success = db_manager.store_file_attachment(file_data)
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
                return jsonify(response_data), 200
            else:
                logger.error("No files were saved")
                return jsonify({"error": "No files were saved"}), 400
                
        except Exception as e:
            logger.error(f"Error handling accessible file upload: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({"error": f"Error handling file upload: {str(e)}"}), 500
    
    return app

def handle_direct_file_upload(files, existing_grievance_id=None, interface_language='ne'):
    """Handle direct voice recording uploads from the accessible interface"""
    try:
        logger.info("Processing voice recording upload")
        
        # Use existing grievance ID or create a new one
        grievance_id = existing_grievance_id
        if not grievance_id:
            logger.info("No existing grievance ID provided, creating new one")
            grievance_id = db_manager.create_grievance(source='accessibility', language_code=interface_language)
            if not grievance_id:
                logger.error("Failed to create new grievance")
                return jsonify({"error": "Failed to create grievance"}), 500
        
        logger.info(f"Using grievance ID: {grievance_id}")
        
        # Create voice recordings directory
        upload_dir = create_grievance_directory(grievance_id, 'voice_recordings')
        
        # Process and save each file
        saved_files = []
        file_paths = {}  # Store paths for transcription
        
        for file_key, file in files.items():
            if not file or not file.filename:
                logger.warning(f"Invalid file for key: {file_key}")
                continue
                
            try:
                # Create a proper filename based on the form field key
                filename = ensure_valid_filename(file.filename, file_key)
                
                # Save the file
                try:
                    file_path, file_size = save_uploaded_file(file, upload_dir, filename)
                    logger.info(f"Saved file: {file_path}, size: {file_size} bytes")
                except ValueError as e:
                    logger.warning(f"Skipping invalid file: {str(e)}")
                    continue
                
                # Generate a recording ID and determine recording type
                recording_id = str(uuid.uuid4())
                recording_type = get_recording_type_from_filename(filename)
                
                # Store file metadata in grievance_voice_recordings table
                recording_data = {
                    'recording_id': recording_id,
                    'grievance_id': grievance_id,
                    'file_path': file_path,
                    'recording_type': recording_type,
                    'duration_seconds': None,  # We don't have this info
                    'file_size_bytes': file_size,
                    'processing_status': 'pending',
                    'language_code': interface_language
                }
                
                # Store recording metadata
                stored_recording_id = store_recording_metadata(recording_data)
                if stored_recording_id:
                    saved_files.append(stored_recording_id)
                    file_paths[stored_recording_id] = {'file_path': file_path, 'file_name': filename}
                else:
                    logger.error(f"Failed to store voice recording metadata for: {recording_id}")
            except Exception as e:
                logger.error(f"Error processing file {file_key}: {str(e)}")
                continue
        
        if not saved_files:
            logger.error("No files were saved")
            return jsonify({"error": "No valid files provided"}), 400
        
        # Process transcriptions
        logger.info(f"Processing transcriptions for {len(file_paths)} voice recordings")
        try:
            # Transcribe audio files
            transcriptions = {}
            for recording_id, file_data in file_paths.items():
                file_path = file_data['file_path']
                
                # Update processing status to transcribing
                update_recording_status(recording_id, 'transcribing')
                
                try:
                    # Transcribe the audio file
                    transcription = transcribe_audio_file(file_path)
                    
                    # Store the transcription in database
                    transcription_data = {
                        'transcription_id': str(uuid.uuid4()),
                        'recording_id': recording_id,
                        'grievance_id': grievance_id,
                        'automated_transcript': transcription,
                        'verification_status': 'pending',
                        'confidence_score': 1.0  # Default confidence
                    }
                    
                    # Store transcription
                    transcription_id = store_transcription_data(transcription_data)
                    if transcription_id:
                        logger.info(f"Successfully stored transcription with ID: {transcription_id}")
                    else:
                        logger.error(f"Failed to store transcription for recording: {recording_id}")
                    
                    # Update recording status to transcribed
                    update_recording_status(recording_id, 'transcribed')
                    
                    # Map the transcription to the appropriate grievance field
                    field_name = get_grievance_field_from_filename(file_data['file_name'])
                    if field_name:
                        transcriptions[field_name] = transcription
                    else:
                        # Default to recording_id as key
                        transcriptions[recording_id] = transcription
                        
                    logger.info(f"Transcribed {file_data['file_name']}: {transcription[:50]}...")
                    
                except Exception as e:
                    logger.error(f"Error transcribing {file_path}: {str(e)}")
                    # Update recording status to failed
                    update_recording_status(recording_id, 'failed')
                    continue
            
            # If we have enough data, try to update the grievance details
            if transcriptions:
                update_grievance_from_voice(grievance_id, transcriptions)
        except Exception as e:
            logger.error(f"Error processing transcriptions: {str(e)}")
            # Continue with the response - we already saved the files
        
        # Return success with grievance ID - use both 'id' and 'grievance_id' for compatibility
        response_data = {
            "status": "success",
            "message": "Voice recordings received successfully",
            "id": grievance_id,
            "grievance_id": grievance_id
        }
        logger.info(f"Returning response with grievance ID: {grievance_id}")
        return jsonify(response_data), 200
            
    except Exception as e:
        logger.error(f"Error handling voice recording upload: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Error handling voice recording upload: {str(e)}"}), 500

def process_voice_grievance(grievance_id: str, file_references: List[str]) -> Optional[Dict[str, str]]:
    """Process voice recordings for a grievance submission"""
    try:
        logger.info(f"Processing voice grievance {grievance_id} with {len(file_references)} files")
        
        # Get file data from database
        files_data = {}
        for file_id in file_references:
            file_data = db_manager.get_file_by_id(file_id)
            if file_data and os.path.exists(file_data['file_path']):
                files_data[file_id] = file_data
        
        # Check if we have all required files
        if not files_data:
            logger.error("No valid files found")
            return None
        
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
                # Transcribe the audio file
                transcription = transcribe_audio_file(file_path)
                
                # Map to appropriate field based on filename
                field_name = get_grievance_field_from_filename(file_data['file_name'])
                if field_name:
                    transcriptions[field_name] = transcription
                else:
                    # Default to file_id as key
                    transcriptions[file_id] = transcription
                    
                logger.info(f"Transcribed {file_data['file_name']}: {transcription[:50]}...")
                
            except Exception as e:
                logger.error(f"Error transcribing {file_path}: {str(e)}")
                continue
        
        return transcriptions
        
    except Exception as e:
        logger.error(f"Error processing voice grievance: {str(e)}", exc_info=True)
        return None

def update_grievance_from_voice(grievance_id: str, transcriptions: Dict[str, str]) -> bool:
    """Update grievance with data extracted from voice recordings"""
    try:
        logger.info(f"Updating grievance {grievance_id} with voice data")
        
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
            classification_result = classify_grievance(grievance_details)
        
        # Prepare grievance data
        grievance_data = {
            'grievance_id': grievance_id,
            'grievance_details': grievance_details,
            'grievance_summary': classification_result.get('summary', grievance_details[:100] + '...' if grievance_details else ''),
            'grievance_categories': classification_result.get('categories', []),
            'user_full_name': user_full_name,
            'user_contact_phone': user_contact_phone,
            'user_municipality': user_municipality,
            'user_village': user_village,
            'user_address': user_address,
            'grievance_location': combined_address.strip(', ') if combined_address else user_address,
            'status': GRIEVANCE_STATUS["SUBMITTED"],
            'source': 'accessibility',
            'submission_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Update grievance in database
        success = db_manager.update_grievance_db(grievance_data)
        
        if success:
            logger.info(f"Successfully updated grievance {grievance_id} with voice data")
            return True
        else:
            logger.error(f"Failed to update grievance {grievance_id}")
            return False
            
    except Exception as e:
        logger.error(f"Error updating grievance from voice: {str(e)}", exc_info=True)
        return False

def extract_contact_info(contact_text: str) -> tuple:
    """Extract name and phone number from contact information text"""
    try:
        # Use OpenAI to extract structured information
        if client:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Extract the person's full name and phone number from the text."},
                    {"role": "user", "content": f"Extract the full name and phone number from this text. Return JSON format with keys 'name' and 'phone': {contact_text}"}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('name', ''), result.get('phone', '')
        else:
            # Fallback: Basic extraction with simple heuristics
            words = contact_text.split()
            
            # Assume first 2-3 words might be the name
            name_candidate = ' '.join(words[:3]) if len(words) >= 3 else ' '.join(words[:2])
            
            # Look for number patterns
            phone_candidate = ''
            for word in words:
                # If word has at least 7 digits, it's likely a phone number
                if sum(c.isdigit() for c in word) >= 7:
                    phone_candidate = word
                    break
            
            return name_candidate, phone_candidate
            
    except Exception as e:
        logger.error(f"Error extracting contact info: {str(e)}")
        return '', ''

def classify_grievance(grievance_text: str) -> Dict[str, Any]:
    """Classify and summarize grievance text using OpenAI"""
    try:
        if not client:
            logger.error("OpenAI client not available for classification")
            return {'summary': '', 'categories': []}
            
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an assistant helping to categorize road-related grievances."},
                {"role": "user", "content": f"""
                    Please analyze this grievance: "{grievance_text}"
                    
                    1. Provide a concise summary of the grievance (max 100 words).
                    2. Identify the main categories this grievance belongs to from the following list:
                       - Road Construction
                       - Road Maintenance
                       - Bridge Issues
                       - Traffic Management
                       - Safety Concerns
                       - Land Acquisition
                       - Compensation
                       - Contractor Performance
                       - Project Delays
                       - Corruption Allegations
                       - Environmental Impact
                       - Other
                    
                    Return your analysis as a JSON object with two fields:
                    - 'summary': A concise summary of the grievance
                    - 'categories': An array of category names (select 1-3 most relevant categories)
                """}
            ],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        logger.info(f"Classified grievance: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error classifying grievance: {str(e)}")
        return {'summary': '', 'categories': []}

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
        return db_manager.update_recording_language(recording_id, language_code)
    except Exception as e:
        logger.error(f"Error updating recording language: {str(e)}")
        return False