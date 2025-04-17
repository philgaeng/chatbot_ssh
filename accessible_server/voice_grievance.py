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

    def handle_direct_file_upload(files, existing_grievance_id=None):
        """Handle direct file uploads from the accessible interface"""
        try:
            logger.info("Processing direct file upload")
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
            
            # Create uploads directory if it doesn't exist
            upload_dir = os.path.join(app.config.get('UPLOAD_FOLDER', 'uploads'), 'voice_recordings', grievance_id)
            os.makedirs(upload_dir, exist_ok=True)
            logger.info(f"Created upload directory: {upload_dir}")
            
            # Process and save each file
            saved_files = []
            for file_key, file in files.items():
                if file and file.filename:
                    # Secure the filename
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(upload_dir, filename)
                    
                    # Save the file
                    file.save(file_path)
                    logger.info(f"Saved file: {file_path}, size: {os.path.getsize(file_path)} bytes")
                    
                    # Generate a file ID
                    file_id = str(uuid.uuid4())
                    
                    # Store file metadata in database
                    file_data = {
                        'file_id': file_id,
                        'grievance_id': grievance_id,
                        'file_name': filename,
                        'file_path': file_path,
                        'file_type': file.content_type or 'audio/webm',
                        'file_size': os.path.getsize(file_path)
                    }
                    
                    # Store file metadata
                    logger.info(f"Storing file metadata in database: {file_data}")
                    success = db_manager.store_file_attachment(file_data)
                    if success:
                        logger.info(f"Successfully stored file metadata for: {file_id}")
                        saved_files.append(file_id)
                    else:
                        logger.error(f"Failed to store file metadata for: {file_id}")
                else:
                    logger.warning(f"Invalid file for key: {file_key}")
            
            if not saved_files:
                logger.error("No files were saved")
                return jsonify({"error": "No valid files provided"}), 400
            
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
            logger.error(f"Error handling direct file upload: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({"error": f"Error handling file upload: {str(e)}"}), 500

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
        grievance_text = transcriptions.get('grievance', '')
        
        # Extract contact information
        contact_text = transcriptions.get('contact', '')
        name, phone = extract_contact_info(contact_text)
        
        # Extract address
        address = transcriptions.get('address', '')
        
        # Use OpenAI to classify and summarize grievance
        classification_result = classify_grievance(grievance_text)
        
        # Prepare grievance data
        grievance_data = {
            'grievance_id': grievance_id,
            'grievance_details': grievance_text,
            'grievance_summary': classification_result.get('summary', grievance_text[:100] + '...'),
            'grievance_categories': classification_result.get('categories', []),
            'user_name': name,
            'contact_number': phone,
            'address': address,
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