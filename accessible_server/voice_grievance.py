import os
import logging
import uuid
import json
import tempfile
from typing import Dict, Any, List, Optional
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
MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25MB max size for audio files

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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
            filename = secure_filename(audio_file.filename or f"audio_{uuid.uuid4()}.webm")
            temp_path = os.path.join(UPLOAD_FOLDER, f"temp_{filename}")
            
            # Save temp file
            audio_file.save(temp_path)
            logger.info(f"Saved temporary audio file: {temp_path}")
            
            try:
                # Transcribe with OpenAI Whisper
                with open(temp_path, "rb") as audio_data:
                    response = client.audio.transcriptions.create(
                        file=audio_data,
                        model="whisper-1",
                        language=language
                    )
                
                # Return transcription
                transcription = response.text
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
            logger.info(f"Creating grievance with source: {source}")
            
            # Create grievance using the db_manager
            logger.info("Calling db_manager.create_grievance now...")
            grievance_id = db_manager.create_grievance(source=source)
            if not grievance_id:
                logger.error("Failed to create new grievance - db_manager.create_grievance returned None")
                return jsonify({"error": "Failed to create grievance"}), 500
            
            logger.info(f"Successfully created new grievance with ID: {grievance_id}")
            
            # Return success with grievance ID
            response_data = {
                "status": "success",
                "message": "Grievance created successfully",
                "id": grievance_id
            }
            logger.info(f"Returning response with data: {response_data}")
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
            
            # Check if this is a direct file upload from the accessible interface
            files = request.files
            if files:
                logger.info(f"Received direct file upload with {len(files)} files")
                return handle_direct_file_upload(files, grievance_id)
            
            # Parse request data for API clients
            data = request.json
            if not data:
                logger.error("No JSON data in request")
                return jsonify({"error": "No data provided"}), 400
            
            # Create new grievance if not provided
            if not grievance_id:
                grievance_id = db_manager.create_grievance(source='accessibility')
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
                
            logger.info(f"Using provided grievance ID for file upload: {grievance_id}")
            
            # Check if files are provided
            if 'files[]' not in request.files:
                logger.error("No files[] in request.files")
                return jsonify({"error": "No files provided under 'files[]' key"}), 400
                
            files = request.files.getlist('files[]')
            logger.info(f"Received {len(files)} files for upload")
            
            if not files or len(files) == 0:
                logger.error("No files provided in the request")
                return jsonify({"error": "No files found in the request"}), 400
            
            # Create the upload directory
            upload_dir = os.path.join(UPLOAD_FOLDER, grievance_id)
            os.makedirs(upload_dir, exist_ok=True)
            logger.info(f"Created upload directory: {upload_dir}")
            
            # Process and save each file
            saved_files = []
            
            for file in files:
                if file and file.filename:
                    # Secure the filename
                    filename = secure_filename(file.filename)
                    
                    # Generate a unique ID for the file
                    file_id = str(uuid.uuid4())
                    
                    # Save the file
                    file_path = os.path.join(upload_dir, f"{file_id}_{filename}")
                    file.save(file_path)
                    logger.info(f"Saved file: {file_path}, size: {os.path.getsize(file_path)} bytes")
                    
                    # Determine file type from extension
                    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                    
                    # Store file metadata in database
                    file_data = {
                        'file_id': file_id,
                        'grievance_id': grievance_id,
                        'file_name': filename,
                        'file_path': file_path,
                        'file_type': file.content_type or file_ext or 'application/octet-stream',
                        'file_size': os.path.getsize(file_path)
                    }
                    
                    # Store in database
                    logger.info(f"Storing file metadata in database: {file_data}")
                    success = db_manager.store_file_attachment(file_data)
                    if success:
                        logger.info(f"Successfully stored file metadata for: {file_id}")
                        saved_files.append({
                            'file_id': file_id,
                            'filename': filename,
                            'file_size': os.path.getsize(file_path)
                        })
                    else:
                        logger.error(f"Failed to store file metadata for: {file_id}")
                        # Remove the file if db storage failed
                        try:
                            os.remove(file_path)
                            logger.info(f"Removed file after db storage failure: {file_path}")
                        except Exception as e:
                            logger.error(f"Error removing file: {str(e)}")
                else:
                    logger.warning(f"Invalid file provided")
            
            if saved_files:
                response_data = {
                    "status": "success",
                    "message": f"Successfully uploaded {len(saved_files)} files",
                    "files": saved_files,
                    "grievance_id": grievance_id
                }
                logger.info(f"File upload successful: {response_data}")
                return jsonify(response_data), 200
            else:
                logger.error("No files were saved")
                return jsonify({"error": "No files were saved"}), 400
                
        except Exception as e:
            logger.error(f"Error handling accessible file upload: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({"error": f"Error handling file upload: {str(e)}"}), 500

def handle_direct_file_upload(files, existing_grievance_id=None):
    """Handle direct voice recording uploads from the accessible interface"""
    try:
        logger.info("Processing voice recording upload")
        logger.info(f"Received files: {', '.join(files.keys())}")
        
        # Use existing grievance ID or create a new one
        grievance_id = existing_grievance_id
        if not grievance_id:
            logger.info("No existing grievance ID provided, creating new one")
            grievance_id = db_manager.create_grievance(source='accessibility')
            if not grievance_id:
                logger.error("Failed to create new grievance")
                return jsonify({"error": "Failed to create grievance"}), 500
        
        logger.info(f"Using grievance ID: {grievance_id}")
        
        # Create voice recordings directory
        # Don't use app.config as it might not be available
        upload_dir = os.path.join(UPLOAD_FOLDER, 'voice_recordings', grievance_id)
        os.makedirs(upload_dir, exist_ok=True)
        logger.info(f"Created upload directory: {upload_dir}")
        
        # Process and save each file
        saved_files = []
        file_paths = {}  # Store paths for transcription
        
        for file_key, file in files.items():
            if file and file.filename:
                # First try to use the file_key (form field name) if it's more descriptive than 'blob'
                if file.filename == 'blob' or not file.filename:
                    # Use the field name from the form instead, which is more descriptive
                    logger.info(f"Using form field name ({file_key}) instead of generic filename ({file.filename})")
                    filename = secure_filename(file_key)
                else:
                    # Use the file's own filename if it's proper
                    filename = secure_filename(file.filename)
                
                # Ensure voice recordings have .webm extension
                if not filename.endswith('.webm'):
                    filename += '.webm'
                    
                file_path = os.path.join(upload_dir, filename)
                
                # Save the file
                file.save(file_path)
                logger.info(f"Saved file: {file_path}, size: {os.path.getsize(file_path)} bytes")
                
                # Generate a file ID (UUID)
                recording_id = str(uuid.uuid4())
                
                # Determine recording type based on filename
                if 'grievance' in filename.lower() or 'grievance_details' in filename.lower():
                    recording_type = 'details'
                elif 'name' in filename.lower() or 'user_full_name' in filename.lower() or 'phone' in filename.lower() or 'user_contact_phone' in filename.lower() or 'contact' in filename.lower():
                    recording_type = 'contact'
                elif 'municipality' in filename.lower() or 'user_municipality' in filename.lower() or 'village' in filename.lower() or 'user_village' in filename.lower() or 'address' in filename.lower() or 'user_address' in filename.lower():
                    recording_type = 'location'
                else:
                    recording_type = 'details'  # Default
                
                # Store file metadata in grievance_voice_recordings table
                recording_data = {
                    'recording_id': recording_id,
                    'grievance_id': grievance_id,
                    'file_path': file_path,
                    'recording_type': recording_type,
                    'duration_seconds': None,  # We don't have this info
                    'file_size_bytes': os.path.getsize(file_path),
                    'processing_status': 'pending'
                }
                
                # Store recording metadata
                logger.info(f"Storing voice recording metadata in database: {recording_data}")
                stored_recording_id = db_manager.store_voice_recording(recording_data)
                if stored_recording_id:
                    logger.info(f"Successfully stored voice recording metadata for: {stored_recording_id}")
                    saved_files.append(stored_recording_id)
                    file_paths[stored_recording_id] = {'file_path': file_path, 'file_name': filename}
                else:
                    logger.error(f"Failed to store voice recording metadata for: {recording_id}")
            else:
                logger.warning(f"Invalid file for key: {file_key}")
        
        if not saved_files:
            logger.error("No files were saved")
            return jsonify({"error": "No valid files provided"}), 400
        
        # Process transcriptions
        logger.info(f"Processing transcriptions for {len(file_paths)} voice recordings")
        try:
            # Create a dictionary of file data for transcription
            files_data = {}
            for recording_id in file_paths:
                file_data = {
                    'recording_id': recording_id,
                    'file_path': file_paths[recording_id]['file_path'],
                    'file_name': file_paths[recording_id]['file_name'],
                    'file_type': 'audio/webm'
                }
                files_data[recording_id] = file_data
            
            # Transcribe audio files
            transcriptions = {}
            for recording_id, file_data in files_data.items():
                file_path = file_data['file_path']
                
                # Update processing status to transcribing
                db_manager.update_recording_status(recording_id, 'transcribing')
                
                # Transcribe with OpenAI Whisper
                try:
                    with open(file_path, "rb") as audio_data:
                        response = client.audio.transcriptions.create(
                            file=audio_data,
                            model="whisper-1"
                        )
                    
                    transcription = response.text
                    # Store the transcription in database
                    transcription_data = {
                        'transcription_id': str(uuid.uuid4()),
                        'recording_id': recording_id,
                        'grievance_id': grievance_id,
                        'automated_transcript': transcription,
                        'verification_status': 'pending',
                        'confidence_score': 1.0  # Default confidence
                    }
                    
                    # Log the transcription data we're about to store
                    logger.info(f"Storing transcription with data: {transcription_data}")
                    
                    # Store transcription and check result
                    transcription_id = db_manager.store_transcription(transcription_data)
                    if transcription_id:
                        logger.info(f"Successfully stored transcription with ID: {transcription_id}")
                    else:
                        logger.error(f"Failed to store transcription for recording: {recording_id}")
                    
                    # Update recording status to transcribed
                    db_manager.update_recording_status(recording_id, 'transcribed')
                    
                    # Determine the type of recording based on filename for mapping to grievance data
                    file_name = file_data['file_name'].lower()
                    if 'grievance' in file_name or 'grievance_details' in file_name:
                        transcriptions['grievance_details'] = transcription
                    elif 'name' in file_name or 'user_full_name' in file_name:
                        transcriptions['user_full_name'] = transcription
                    elif 'phone' in file_name or 'user_contact_phone' in file_name:
                        transcriptions['user_contact_phone'] = transcription
                    elif 'municipality' in file_name or 'user_municipality' in file_name:
                        transcriptions['user_municipality'] = transcription
                    elif 'village' in file_name or 'user_village' in file_name:
                        transcriptions['user_village'] = transcription
                    elif 'address' in file_name or 'user_address' in file_name:
                        transcriptions['user_address'] = transcription
                    else:
                        # Default to recording_id as key
                        transcriptions[recording_id] = transcription
                        
                    logger.info(f"Transcribed {file_data['file_name']}: {transcription[:50]}...")
                    
                except Exception as e:
                    logger.error(f"Error transcribing {file_path}: {str(e)}")
                    # Update recording status to failed
                    db_manager.update_recording_status(recording_id, 'failed')
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
        logger.info(f"Returning response with grievance ID: {response_data}")
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
                
            # Transcribe with OpenAI Whisper
            try:
                with open(file_path, "rb") as audio_data:
                    response = client.audio.transcriptions.create(
                        file=audio_data,
                        model="whisper-1"
                    )
                
                transcription = response.text
                # Determine the type of recording based on filename
                if 'grievance' in file_data['file_name'].lower():
                    transcriptions['grievance'] = transcription
                elif 'contact' in file_data['file_name'].lower():
                    transcriptions['contact'] = transcription
                elif 'address' in file_data['file_name'].lower():
                    transcriptions['address'] = transcription
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
        
        # Use OpenAI to classify and summarize grievance
        classification_result = classify_grievance(grievance_details)
        
        # Prepare grievance data
        grievance_data = {
            'grievance_id': grievance_id,
            'grievance_details': grievance_details,
            'grievance_summary': classification_result.get('summary', grievance_details[:100] + '...'),
            'grievance_categories': classification_result.get('categories', []),
            'user_full_name': user_full_name,
            'user_contact_phone': user_contact_phone,
            'user_municipality': user_municipality,
            'user_village': user_village,
            'user_address': user_address,
            'grievance_location': combined_address.strip(', ') if combined_address else user_address,
            'status': GRIEVANCE_STATUS.PENDING,
            'source': 'accessibility',
            'submission_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Update grievance in database
        success = db_manager.update_grievance(grievance_id, grievance_data)
        
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