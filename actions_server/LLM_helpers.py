import os
import logging
import json
from typing import Dict, Any, List, Tuple
from openai import OpenAI
from dotenv import load_dotenv
from .constants import CLASSIFICATION_DATA
from .db_manager import db_manager
# Set up logging
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
    
def extract_contact_info(contact_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract name and phone number from contact information text"""
    try:
        # Use OpenAI to extract structured information
        if not client:
            raise ValueError("OpenAI client not available for contact info extraction")
            
        # Get the first key-value pair from contact_data
        field_name = contact_data.get('field_name')
        field_value = contact_data.get('value')
        language_code = contact_data.get('language_code', 'ne')
        
        message_input = f"""
            Extract the {field_name.replace("_", " ")} from {field_value}.
            Return the response in **strict JSON format** like this:
            {{
                "field_name": "{field_name}",
                "{field_name}": "value"
            }}
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": f"Extract the person's contact and location information in the language which language_code is {language_code}."},
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
                field_name: "",
                'value': ""
            }
        else:
            logger.error(f"Error in extracting contact info from OpenAI API response: {str(e)}")
        return {
            field_name: "",
            'value': ""  # Add 'value' field to error response as well
        }
        

def extract_all_contact_info(contact_data: Dict[str, Any]) -> Dict[str, Any]:
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
                    Extract the phone number from {contact_data['user_contact_phone']}. 
                    Extract the full name from {contact_data['user_full_name']}.
                    Extract the municipality in the district {contact_data['user_district']} of Nepal from {contact_data['contact_municipality']}.
                    Extract the village inside the municipality from {contact_data['contact_village']}.
                    Extract the address from {contact_data['contact_address']}.
                Return the response in **strict JSON format** like this:
                {{
                    "user_contact_phone": "phone number",
                    "user_full_name": "full name",
                    "user_district": "district",
                    "user_municipality": "municipality",
                    "user_village": "village",
                    "user_address": "address"
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
            "user_contact_phone": "",
            "user_full_name": "",
            "user_district": "",
            "user_municipality": "",
            "user_village": "",
            "user_address": ""
        }

def classify_and_summarize_grievance(
    grievance_text: str,
    language_code: str = 'ne',
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
                {"role": "system", "content": "You are an assistant helping to categorize grievances."},
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
        result = parse_llm_response("grievance_response", response.choices[0].message.content.strip())
        return result

    except Exception as e:
        logger.error(f"Error in classify_and_summarize_grievance: {str(e)}")
        return {
            "grievance_summary": "",
            "grievance_categories": [],
            "status": "error",
            "error": str(e)
        }
        
        
def parse_llm_response(type: str, response: str) -> Dict[str, Any]:
    """
    Parse the LLM response into a structured format.
    type can be "grievance_response" or "contact_response"
    
    Args:
        response: Raw LLM response string
    """
    fields = {
        "grievance_response": ["grievance_summary", "grievance_categories"],
        "contact_response": ["user_contact_phone", "user_full_name", "user_district", "user_municipality", "user_village", "user_address"]
    }
    try:
        result_dict = json.loads(response)
        for field in fields[type]:
            result_dict[field] = result_dict.get(field, "")
        return result_dict
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing LLM response: {str(e)}")
        return {}
    
    

def translate_grievance_to_english_LLM(grievance_data: Dict[str, Any]) -> str:
    """Translate a grievance to English using OpenAI API
    Args:
        grievance_data: Dict containing grievance data: {grievance_id, language_code, grievance_details, grievance_summary, grievance_categories}
    Returns:
        Dict containing translated grievance data: {grievance_id, source_language, translation_method, confidence_score, grievance_details_en, grievance_summary_en, grievance_categories_en}
    """
    if not client:
        raise RuntimeError("OpenAI client not available for translation")
    
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"You are an assistant helping to translate grievances to English from {grievance_data['language_code']}."},
                {"role": "user", "content": f"""
                    Translate the following grievance to English:
                    {grievance_data['grievance_details']}
                    and its summary:
                    {grievance_data['grievance_summary']}
                    
                    Make sure that the summary from the translation is not too long and is aligned with the details, if it is too long make it shorter, if it is not aligned with the details, create a new summary from the translated details.
                    Return the response in **strict JSON format** like this:
                    {{
                        "grievance_details_en": "Grievance details tranlated to English",
                        "grievance_summary_en": "Summary of the grievance tranlated to English",
                        "confidence_score": "confidence score of the translation as a number between 0 and 1"
                    }}
                """}
            ],
            model="gpt-4",
        )
        
        
        # Parse the response
        result = json.loads(response.choices[0].message.content.strip())
        result["grievance_id"] = grievance_data["grievance_id"]
        result["source_language"] = grievance_data["language_code"]
        result["translation_method"] = "LLM"
        result["grievance_categories_en"] = grievance_data["grievance_categories"]
        return result
    
    except Exception as e:
        logger.error(f"Error translating grievance to English: {str(e)}")
        return None
    

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
            'grievance_details': grievance_data['grievance_details'],
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
            'status': 'SUCCESS',
            'result': translation_result
        }
        
    except Exception as e:
        logger.error(f"Error in translate_grievance_to_english: {str(e)}")
        return {
            'status': 'FAILED',
            'error': str(e)
        }