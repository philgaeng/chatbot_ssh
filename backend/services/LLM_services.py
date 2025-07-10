import os
import json
from typing import Dict, Any, List, Tuple
from openai import OpenAI
from dotenv import load_dotenv
from logger.logger import TaskLogger
from ..config.constants import CLASSIFICATION_DATA, USER_FIELDS, DEFAULT_PROVINCE, DEFAULT_DISTRICT, TASK_STATUS, GRIEVANCE_CLASSIFICATION_STATUS
from .database_services.postgres_services.db_manager import db_manager
# Set up logging
logger = TaskLogger(service_name='llm_service')

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
    
def extract_contact_info(contact_data: Dict[str, Any], language_code: str = 'ne', complainant_district: str = DEFAULT_DISTRICT, complainant_province: str = DEFAULT_PROVINCE) -> Dict[str, Any]:
    """Extract name and phone number from contact information text"""
    try:
        # Use OpenAI to extract structured information
        if not client:
            raise ValueError("OpenAI client not available for contact info extraction")
            
        # Get the first key-value pair from contact_data
        field_name = [i for i in contact_data.keys() if i in USER_FIELDS][0]
        if not field_name:
            raise ValueError(f"Missing valid field_name in contact_data: {contact_data}")
        field_value = contact_data.get(field_name)
        if not field_value:
            raise ValueError(f"Missing {field_name} in contact_data: {contact_data}")
        
        message_input = f"""
            Extract the {field_name.replace("_", " ")} from {field_value}.
            Return the response in **strict JSON format** like this:
            {{
                "{field_name}": "value"
            }}
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"You are an assistant helping to extract contact information from a contact form containing the following fields: {USER_FIELDS}. The contact form is part of a grievance form related to road works in rural Nepal. Locations are in Nepal, precisely in the district of {complainant_district} in the province of {complainant_province}. Extract the person's contact and location information in the language which language_code is {language_code}."},
                {"role": "user", "content": message_input}
            ],
            response_format={"type": "json_object"}
        )
        
        # Get the full ChatGPT response content
        full_response = response.choices[0].message.content
        result = json.loads(full_response)
         # FIXED: Use full ChatGPT response instead of just extracted field
        
        return result  # FIXED: Return result instead of result_dict
        
    except Exception as e:
        if not response:
            logger.error(f"No response from OpenAI API")
            return {
                field_name: ""
            }
        else:
            logger.error(f"Error in extracting contact info from OpenAI API response: {str(e)}")
        return {
            field_name: ""
        }
        

def extract_all_contact_info(contact_data: Dict[str, Any], language_code: str = 'ne', complainant_district: str = DEFAULT_DISTRICT, complainant_province: str = DEFAULT_PROVINCE) -> Dict[str, Any]:
    """Extract name and phone number from contact information text"""
    try:
        # Use OpenAI to extract structured information
        if not client:
            raise ValueError("OpenAI client not available for contact info extraction")
        
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Extract the person's contact and location information in the language of the text."},
                {"role": "user", "content": f"""
                    Extract the phone number from {contact_data['complainant_phone']}. 
                    Extract the full name from {contact_data['complainant_full_name']}.
                    Extract the municipality in the district {complainant_district} of {complainant_province}, Nepal from {contact_data['contact_municipality']}.
                    Extract the village inside the municipality from {contact_data['contact_village']}.
                    Extract the address from {contact_data['contact_address']}.
                Return the response in **strict JSON format** like this:
                {{
                    "complainant_phone": "phone number",
                    "complainant_full_name": "full name",
                    "complainant_district": "district",
                    "complainant_municipality": "municipality",
                    "complainant_village": "village",
                    "complainant_address": "address"
                }}
                    """}
            ],
            response_format={"type": "json_object"}
        )
        
        result = parse_llm_response("contact_response", response.choices[0].message.content)
        return result
        
            
    except Exception as e:
        logger.error(f"Error extracting contact info")
        return {
            "complainant_phone": "",
            "complainant_full_name": "",
            "complainant_district": "",
            "complainant_municipality": "",
            "complainant_village": "",
            "complainant_address": ""
        }

def classify_and_summarize_grievance(
    grievance_text: str,
    language_code: str = 'ne',
    complainant_district: str = DEFAULT_DISTRICT,
    complainant_province: str = DEFAULT_PROVINCE,
    categories: List[str] = CLASSIFICATION_DATA
) -> Dict[str, Any]:
    """
    Classify and summarize a grievance using LLM.
    
    Args:
        grievance_text: The grievance text to process
        language_code: Language code for response (default: 'ne' for Nepali)
        categories: Optional list of categories to use (defaults to CLASSIFICATION_DATA)
    
    Returns:
        Dict containing:
        {
            "grievance_summary": str,
            "list_categories": List[str],
            "status": str,
            "error": Optional[str]
        }
    """
    try:
        if not grievance_text:
            return {
                "grievance_summary": "",
                "list_categories": [],
                "status": "error",
                "error": "No grievance text provided"
            }

        # Use provided categories or default to CLASSIFICATION_DATA
        category_list = categories or CLASSIFICATION_DATA
        category_list_str = "\n".join(f"- {c}" for c in category_list)

        # Initialize OpenAI client
        client = OpenAI(api_key=open_ai_key)
        if not client:
            raise ValueError("OpenAI client initialization failed")

        # Make API call
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"You are an assistant helping to categorize grievances for a grievance form related to road works in rural Nepal. Locations are in Nepal, precisely in the district of {complainant_district} in the province of {complainant_province}."},
                {"role": "user", "content": f"""
                    Step 1:
                    Categorize this grievance: "{grievance_text}"
                    Only choose from the following categories:
                    {category_list_str}
                    Do not create new categories.
                    Reply only with the categories, if many categories apply just list them with a format similar to a list in python:
                    [category 1, category 2, etc] - do not prompt your response yet as stricts instructions for format are providing at the end of the prompt
                    Step 2: summarize the grievance with simple and direct words so they can be understood by people with limited literacy.
                    For the summary, reply in the language of the grievance.
                    Finally,
                    Return the response in **strict JSON format** like this:
                    {{
                        "grievance_summary": "Summarized grievance text",
                        "grievance_categories": ["Category 1", "Category 2"]
                    }}
                """}
            ],
            model="gpt-4",
        )

        # Parse the response
        result = parse_llm_response("grievance_response", response.choices[0].message.content.strip(), language_code)
        return result

    except Exception as e:
        logger.error(f"Error in classify_and_summarize_grievance: {str(e)}")
        return {
            "grievance_summary": "",
            "grievance_categories": [],
            "status": "error",
            "error": str(e)
        }
        
        
def parse_llm_response(type: str, response: str, language_code: str = 'ne') -> Dict[str, Any]:
    """
    Parse the LLM response into a structured format.
    type can be "grievance_response" or "contact_response"
    
    Args:
        response: Raw LLM response string
    """
    fields = {
        "grievance_response": ["grievance_summary", "grievance_categories"],
        "contact_response": ["complainant_phone", "complainant_full_name", "complainant_district", "complainant_municipality", "complainant_village", "complainant_address"]
    }
    try:
        error_response_dict = {
            'en': "not enough information to proceed",
            'ne': "अपेक्षित जानकारी अपुरुष है",
            'hi': "पूर्ण जानकारी अपुरुष है",
            'fr': "Information insuffisante pour procéder",
        }
        error_response = error_response_dict.get(language_code, "not enough information to proceed")
        if response == "{}":
            if type == "grievance_response":
                return {
                    "grievance_summary": error_response,
                    "grievance_categories": [error_response]
                }
        result_dict = json.loads(response)
        for field in fields[type]:
            result_dict[field] = result_dict.get(field, "")
        return result_dict
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing LLM response: {str(e)}")
        return {}
    
    

def translate_grievance_to_english_LLM(input_data: Dict[str, Any]) -> str:
    """Translate a grievance to English using OpenAI API
    Args:
        grievance_data: Dict containing grievance data: {grievance_id, language_code, grievance_description, grievance_summary, grievance_categories}
    Returns:
        Dict containing translated grievance data: {grievance_id, source_language, translation_method, confidence_score, grievance_description_en, grievance_summary_en, grievance_categories_en}
    """
    if not client:
        raise RuntimeError("OpenAI client not available for translation")
    grievance_description = input_data.get('grievance_description')
    grievance_summary = input_data.get('grievance_summary')
    language_code = input_data.get('language_code')
    if not grievance_description or not language_code:
        raise ValueError("grievance_description and language_code are required")
    if not grievance_summary:
        raise Warning("grievance_summary is missing")
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"You are an assistant helping to translate grievances to English from {input_data['language_code']}. The grievance is related to road works in rural Nepal. Locations are in Nepal, precisely in the district of {input_data['complainant_district']} in the province of {input_data['complainant_province']}."},
                {"role": "user", "content": f"""
                    Translate the following grievance to English:
                    {input_data['grievance_description']}
                    and its summary:
                    {input_data['grievance_summary']}
                    
                    Make sure that the summary from the translation is not too long and is aligned with the details, if it is too long make it shorter, if it is not aligned with the details, create a new summary from the translated details.
                    Return the response in **strict JSON format** like this:
                    {{
                        "grievance_description_en": "Grievance details tranlated to English",
                        "grievance_summary_en": "Summary of the grievance tranlated to English",
                        "confidence_score": "confidence score of the translation as a number between 0 and 1"
                    }}
                """}
            ],
            model="gpt-4",
        )
        if not response:
            raise ValueError("No response from OpenAI API")
        
        if response.choices[0].message.content == "{}":
            raise ValueError("Missing information, response from OpenAI is empty or invalid, check input data: {input_data}")
        
        # Parse the response
        result = {}
        try:
            result = json.loads(response.choices[0].message.content.strip())
        except Exception as e:
            raise ValueError(f"Error parsing LLM response: {str(e)} - input_data: {input_data} - result: {result}")
        result["grievance_id"] = input_data["grievance_id"]
        result["source_language"] = input_data["language_code"]
        result["translation_method"] = "LLM"
        result["grievance_categories_en"] = input_data["grievance_categories"]
        return result
    
    except Exception as e:
        raise ValueError(f"Error translating grievance to English: {str(e)} - input_data: {input_data} - result: {result}")
        logger.error(f"Error translating grievance to English: {str(e)}")
        return None

def extract_input_data_for_translation(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the input data for translation from nested data structures
    
    This function recursively searches through nested dictionaries and lists
    to find the required fields: grievance_id, language_code, grievance_description, grievance_summary
    
    Args:
        input_data: Nested data structure (can be from group() results)
        
    Returns:
        Dict with extracted fields for translation
    """
    
    def recursive_extract(data, target_keys, found_values=None):
        """Recursively search for target keys in nested data structure"""
        if found_values is None:
            found_values = {}
            
        # If we've found all keys, return early
        if len(found_values) == len(target_keys):
            return found_values
            
        if isinstance(data, dict):
            # Check current level for target keys
            for key in target_keys:
                if key in data and key not in found_values:
                    found_values[key] = data[key]
            
            # Recursively search nested dictionaries
            for key, value in data.items():
                if len(found_values) < len(target_keys):
                    recursive_extract(value, target_keys, found_values)
                    
        elif isinstance(data, list):
            # Search through list items
            for item in data:
                if len(found_values) < len(target_keys):
                    recursive_extract(item, target_keys, found_values)
                    
        return found_values
    
    # Target keys we need for translation
    target_keys = ['grievance_id', 'language_code', 'grievance_description', 'grievance_summary']
    
    # Extract the values
    extracted = recursive_extract(input_data, target_keys)
    
    # Validate we got the required fields
    required_fields = ['grievance_id', 'language_code', 'grievance_description']
    missing_fields = [field for field in required_fields if field not in extracted]
    
    if missing_fields:
        raise ValueError(f"Missing required fields for translation: {missing_fields}. Available keys: {list(extracted.keys())}")
    
    # grievance_summary is optional, set default if missing
    if 'grievance_summary' not in extracted:
        logger.warning("grievance_summary not found, using grievance_description as summary")
        extracted['grievance_summary'] = extracted['grievance_description'][:200] + "..."  # Truncated version
    
    return extracted

def translate_grievance_to_english(grievance_id: str) -> Dict[str, Any]:
    """Translate a grievance to English and save it to the database
    Args:
        grievance_id: The ID of the grievance to translate
    Returns:
        Dict containing status and result of the translation
    """
    try:
        # Initialize database manager
        db = db_manager()
        
        # Get grievance data from database
        grievance_data = db.grievance.get_grievance_by_id(grievance_id)
        if not grievance_data:
            return {
                'status': 'FAILED',
                'error': f'Grievance {grievance_id} not found'
            }
            
        # Select the keys in grievance_data necessary for LLM translation
        translation_input = {
            'grievance_id': grievance_data['grievance_id'],
            'language_code': grievance_data['language_code'],
            'grievance_description': grievance_data['grievance_description'],
            'grievance_summary': grievance_data['grievance_summary']
        }
        
        # Get translation from LLM
        translation_result = translate_grievance_to_english_LLM(translation_input)
        if not translation_result:
            return {
                'status': 'FAILED',
                'error': 'Translation failed'
            }
        
        # Update database
        success = db.grievance.update_translation(grievance_id, translation_result)
        if not success:
            return {
                'status': 'FAILED',
                'error': 'Failed to update translation in database'
            }
        
        return {
            'status': SUCCESS,
            'result': translation_result
        }
        
    except Exception as e:
        logger.error(f"Error in translate_grievance_to_english: {str(e)}")
        return {
            'status': 'FAILED',
            'error': str(e)
        }