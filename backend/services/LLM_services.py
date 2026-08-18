# SPDX-License-Identifier: Apache-2.0

import json
from typing import Dict, Any, List, Tuple, Optional

from openai import OpenAI

from backend.config.llm_config import (
    get_llm_settings,
    is_too_short_to_process,
    model_for,
    response_format_kwargs,
)
from backend.services.llm_client import get_asr_client, get_llm_client
from backend.services.llm_schemas import (
    ContactExtractionAll,
    GrievanceClassification,
    GrievanceTranslation,
    SensitiveContentDetection,
    single_field_contact_schema,
)
from backend.logger.logger import TaskLogger
from ..config.constants import CLASSIFICATION_DATA, LIST_OF_CATEGORIES, USER_FIELDS, DEFAULT_VALUES
from backend.services.database_services.postgres_services import db_manager
from backend.services.db_debug_log import text_len_for_log
# Set up logging
logger = TaskLogger(service_name='llm_service').logger
DEFAULT_PROVINCE = DEFAULT_VALUES["DEFAULT_PROVINCE"]
DEFAULT_DISTRICT = DEFAULT_VALUES["DEFAULT_DISTRICT"]
DEFAULT_LANGUAGE_CODE = DEFAULT_VALUES["DEFAULT_LANGUAGE_CODE"]
# Get status codes from database constants (ensuring cohesiveness)
from backend.config.database_constants import get_task_status_codes

status_codes = get_task_status_codes()
SUCCESS = status_codes['SUCCESS']
FAILED = status_codes['FAILED']
STARTED = status_codes['STARTED']
RETRYING = status_codes['RETRYING']

# ── Clients (DPG-11) ─────────────────────────────────────────────────────────
# Built on first use by backend/services/llm_client.py from the shared registry, never at
# import. `load_dotenv('/home/ubuntu/nepal_chatbot/.env')` lived here and was deleted: an
# absolute path to a host directory that exists in no container.
#
# These two helpers return None when no client can be built — reproducing exactly the contract
# the module-level `client = None` had, so that every call site keeps its own documented
# fallback (raise / sentinel dict / fail-open). Those three idioms differ per function and are
# pinned as they are by tests/backend/test_llm_services.py; unifying them is a behaviour change
# and belongs to its own ticket, not to this migration.


def _llm_client() -> Optional[OpenAI]:
    try:
        return get_llm_client()
    except Exception as e:
        logger.error(f"Error initializing OpenAI client: {str(e)}")
        return None


def _asr_client() -> Optional[OpenAI]:
    try:
        return get_asr_client()
    except Exception as e:
        logger.error(f"Error initializing ASR client: {str(e)}")
        return None

def transcribe_audio_file(file_path: str, language_code: str = DEFAULT_LANGUAGE_CODE) -> str:
    """Transcribe an audio file using the configured ASR endpoint"""
    client = _asr_client()
    if not client:
        raise RuntimeError("OpenAI client not available for transcription")

    asr = model_for("asr")
    try:
        with open(file_path, "rb") as audio_data:
            response = client.audio.transcriptions.create(
                file=audio_data,
                model=asr.model,
                timeout=asr.timeout,
                # DPG-14.3: the SDK parameter is `language`, not `language_code`, and
                # `Transcriptions.create` declares its parameters explicitly — no **kwargs.
                # Every call on this path raised TypeError before this line was corrected.
                language=language_code
            )
        return response.text
    except Exception as e:
        logger.error(f"Error transcribing audio file {file_path}: {str(e)}")
        raise
    
def extract_contact_info(contact_data: Dict[str, Any], language_code: str = DEFAULT_LANGUAGE_CODE, complainant_district: str = DEFAULT_DISTRICT, complainant_province: str = DEFAULT_PROVINCE) -> Dict[str, Any]:
    """Extract name and phone number from contact information text"""
    # DPG-14 / D-28: `field_name` and `response` are resolved BEFORE the try, because the
    # handler below reads both. Previously `field_name` came from a list index and `response`
    # was bound only after the API call, so every pre-call failure — no client, a provider
    # error, an empty field value — raised UnboundLocalError from inside the `except` instead
    # of the documented `{field_name: ""}`. The declared contract was unreachable.
    # The caller (registered_tasks.extract_contact_info_task) checks every returned key against
    # USER_FIELDS, so the sentinel has to carry the real field name.
    field_name = next((i for i in contact_data.keys() if i in USER_FIELDS), None)
    if not field_name:
        # No contact field to extract: a caller error, not a model failure. Raise the field
        # NAMES, never the values — this message reaches the Celery error log (T-34-b).
        raise ValueError(
            f"No valid contact field in contact_data; keys={sorted(contact_data.keys())}"
        )
    response = None
    task = model_for("extract")
    try:
        # Use the configured LLM endpoint to extract structured information
        client = _llm_client()
        if not client:
            raise ValueError("OpenAI client not available for contact info extraction")

        field_value = contact_data.get(field_name)
        if not field_value:
            raise ValueError(f"Missing value for {field_name} in contact_data")
        
        message_input = f"""
            Extract the {field_name.replace("_", " ")} from {field_value}.
            Return the response in **strict JSON format** like this:
            {{
                "{field_name}": "value"
            }}
        """
        
        response = client.chat.completions.create(
            model=task.model,
            timeout=task.timeout,
            **response_format_kwargs(
                "contact_extraction",
                single_field_contact_schema(field_name).model_json_schema(),
                task.structured_output,
            ),
            messages=[
                {"role": "system", "content": f"You are an assistant helping to extract contact information from a contact form containing the following fields: {USER_FIELDS}. The contact form is part of a grievance form related to road works in rural Nepal. Locations are in Nepal, precisely in the district of {complainant_district} in the province of {complainant_province}. Extract the person's contact and location information in the language which language_code is {language_code}."},
                {"role": "user", "content": message_input}
            ],
        )
        
        full_response = response.choices[0].message.content
        # Validated through the per-call schema: the caller checks every returned key against
        # USER_FIELDS and raises on a stray one, so dropping keys the schema does not declare is
        # the difference between a task that succeeds and a task that fails on the model's
        # enthusiasm.
        parsed = json.loads(full_response)
        return single_field_contact_schema(field_name).model_validate(parsed).model_dump()
        
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
        

def extract_all_contact_info(contact_data: Dict[str, Any], language_code: str = DEFAULT_LANGUAGE_CODE, complainant_district: str = DEFAULT_DISTRICT, complainant_province: str = DEFAULT_PROVINCE) -> Dict[str, Any]:
    """Extract name and phone number from contact information text"""
    task = model_for("extract")
    try:
        # Use the configured LLM endpoint to extract structured information
        client = _llm_client()
        if not client:
            raise ValueError("OpenAI client not available for contact info extraction")

        response = client.chat.completions.create(
            model=task.model,
            timeout=task.timeout,
            **response_format_kwargs(
                "contact_extraction_all",
                ContactExtractionAll.model_json_schema(),
                task.structured_output,
            ),
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
        )

        result = parse_llm_response("contact_response", response.choices[0].message.content)
        return ContactExtractionAll.model_validate(result).model_dump()
        
            
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
    language_code: str = DEFAULT_LANGUAGE_CODE,
    complainant_district: str = DEFAULT_DISTRICT,
    complainant_province: str = DEFAULT_PROVINCE,
    categories: List[str] = LIST_OF_CATEGORIES,
    categories_list: Dict[str, Any] = CLASSIFICATION_DATA
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
            "grievance_categories": List[str],
            "grievance_categories_alternative": List[str],
            "status": str,
            "error": Optional[str]
        }
    """
    try:
        if not grievance_text:
            return {
                "grievance_summary": "",
                "grievance_categories": [],
                "grievance_categories_alternative": [],
                "status": "error",
                "error": "No grievance text provided"
            }

        # DPG-19: too short to classify → do not call the model at all. This is not a failure and
        # must not be reported as one: there is nothing to summarise, and the call would cost a
        # request to be told so. `status` is deliberately absent — callers key failure on it.
        if is_too_short_to_process(grievance_text):
            logger.info(
                "classify_and_summarize_grievance: below the minimum length, skipping the model "
                "(chars=%d, minimum=%d)",
                len((grievance_text or "").strip()),
                get_llm_settings().min_classify_chars,
            )
            return {
                "grievance_summary": "",
                "grievance_categories": [],
                "grievance_categories_alternative": [],
                "follow_up_question": "",
                "skipped": "too_short",
            }

        # Use provided categories or default to CLASSIFICATION_DATA
        category_list = [f"{item.get('classification')} - {item.get('generic_grievance_name')}" for item in CLASSIFICATION_DATA.values()]
        result_dict = {}
        for key, value in CLASSIFICATION_DATA.items():
            result_dict[key] = {k:v for k,v in value.items() if "_"+language_code not in k}
        #transform the dict into a string using json.dumps
        category_list_str = json.dumps(category_list)
        result_dict_str = json.dumps(result_dict)
        
        # DPG-14.2: this used to build a SECOND client here, shadowing the module-level one,
        # with its own OPENAI_CLASSIFICATION_TIMEOUT — then guard it with `if not client`, which
        # could never fire because OpenAI(...) either returns an object or raises. One client
        # now, shared with every other call site; the classification deadline survives as a
        # per-request timeout from the registry (TIMEOUT_CLASSIFY, default 120s, with
        # OPENAI_CLASSIFICATION_TIMEOUT honoured as a deprecated alias).
        task = model_for("classify")
        client = _llm_client()
        if not client:
            raise ValueError("OpenAI client initialization failed")

        # Make API call
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": f"You are an assistant helping to categorize grievances for a grievance form related to road works in rural Nepal. Locations are in Nepal, precisely in the district of {complainant_district} in the province of {complainant_province}. You will be given a grievance text and you will need to categorize it into one or more categories as provided to you. You will also need to summarize the grievance text."},
                {"role": "user", "content": f"""
                    Step 1:
                    Categorize this grievance: "{grievance_text}"
                    Only choose from the following categories:
                    {category_list_str}. The categories response is always in English for consistency. Another process will be used to translate the categories to the language of the grievance for the bot.
                    Do not create new categories.
                    Reply only with the categories, if many categories apply just list them with a format similar to a list in python:
                    [category 1, category 2, etc] - do not prompt your response yet as stricts instructions for format are providing at the end of the prompt.
                    Provice as well a second list of categories that are alternative to the first list, these are categories that are possibly related to the grievance but that you have not picked. They will be used by the complainant to modify the categories. These categories are only coming from the following list: {category_list_str}.
                    Step 2: summarize the grievance with simple and direct words so they can be understood by people with limited literacy.
                    For the summary, reply in the language of the grievance eg if the input is in English, reply in English, if the input is in Nepali, reply in Nepali.
                    Step 3: Prepare a follow up question that the complainant can answer to provide more information about the grievance especially quantifying the impact of the grievance (health, economic, etc). Sample questions are provided in the dictionary. The follow up question is in the language of the grievance.
                    Finally,
                    Return the response in **strict JSON format** like this:
                    {{
                        "grievance_summary": "Summarized grievance text in the language of the grievance",
                        "grievance_categories": ["Category 1", "Category 2"] in English
                        "grievance_categories_alternative": ["Category 3", "Category 4", "Category 5"] in English
                        "follow_up_question": "Follow up question in the language of the grievance"
                    }}
                    Use the following dictionary to assist you in the classification and prepare the follow up question: {result_dict_str}
                """}
            ],
            model=task.model,
            timeout=task.timeout,
            **response_format_kwargs(
                "grievance_classification",
                GrievanceClassification.model_json_schema(),
                task.structured_output,
            ),
        )

        # Parse, then validate through the schema (DPG-13). Validation is what makes a
        # schema-violating reply — `grievance_categories` as a string, say — a failure the caller
        # can see, rather than a dict that looks fine until something downstream iterates it.
        raw = response.choices[0].message.content.strip()
        if raw == "{}":
            # The model looked at text long enough to summarise and said "not enough information".
            # ⚠ That is an ANSWER, not an error: `parse_llm_response` turns it into the localized
            # fallback and no `status` key is set, so `is_failed_classification()` stays False.
            # Logged with the LENGTH so DPG-23 can count how often it happens — never the narrative.
            logger.warning(
                "classify_and_summarize_grievance: the model declined to classify %d chars "
                "(above the %d-char minimum). Not a failure — the complainant sees the "
                "'not enough information' response",
                len((grievance_text or "").strip()),
                get_llm_settings().min_classify_chars,
            )
        result = parse_llm_response("grievance_response", raw, language_code)
        validated = GrievanceClassification.model_validate(result)
        _warn_about_unlisted_categories(validated.grievance_categories, category_list)
        return validated.model_dump()

    except Exception as e:
        logger.error(f"Error in classify_and_summarize_grievance: {str(e)}")
        return {
            "grievance_summary": "",
            "grievance_categories": [],
            "grievance_categories_alternative": [],
            "follow_up_question": "",
            "status": "error",
            "error": str(e)
        }
        
        
class LLMResponseParseError(ValueError):
    """
    The model's reply was not JSON.

    A distinct type because the alternative — returning `{}` — is the bug: a parse failure and a
    legitimately empty result then look identical to every caller, and this codebase was
    absorbing the difference on its primary AI path. Subclasses `ValueError` so existing
    `except ValueError` handlers keep working.
    """


def _warn_about_unlisted_categories(chosen: List[str], catalogue: List[str]) -> None:
    """
    Log — never reject — categories the model invented.

    ⚠ The catalogue is passed in, derived from `CLASSIFICATION_DATA` at call time, because it is
    **admin-configurable** and resynced into `public.grievance_classification_taxonomy`. Freezing
    today's values into a `Literal[...]` in the schema would mean a code change every time an
    administrator adds a category, and would break the resync path. And a complainant's
    classification is not worth discarding because the model named a category slightly wrong.
    """
    unlisted = [c for c in chosen if c and c not in catalogue]
    if unlisted:
        logger.warning(
            "classify_and_summarize_grievance: %d category value(s) outside the live catalogue: %s",
            len(unlisted), unlisted,
        )


def parse_llm_response(type: str, response: str, language_code: str = DEFAULT_LANGUAGE_CODE) -> Dict[str, Any]:
    """
    Parse the LLM response into a structured format.
    type can be "grievance_response" or "contact_response"
    
    Args:
        response: Raw LLM response string
    """
    fields = {
        "grievance_response": ["grievance_summary", "grievance_categories", "grievance_categories_alternative", "follow_up_question"],
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
                    "grievance_categories": [error_response],
                    "grievance_categories_alternative": [error_response],
                    "follow_up_question": error_response
                }
        result_dict = json.loads(response)
        for field in fields[type]:
            result_dict[field] = result_dict.get(field, "")
        return result_dict
    except json.JSONDecodeError as e:
        # ⚠ This used to `return {}`, which made a malformed reply **indistinguishable from a
        # successful empty classification** — the silent failure DPG-13 exists to remove. It now
        # raises, so each caller's own error contract fires and the difference is visible.
        # The log carries the response **length, not its content**: the raw body is grievance
        # narrative (T-34-c, Sprint 3).
        logger.error(
            "Error parsing LLM response (%s): %s - response length %d chars",
            type, str(e), len(response or ""),
        )
        raise LLMResponseParseError(
            f"The model's {type} reply was not valid JSON ({len(response or '')} chars)"
        ) from e
    
    

def _grievance_ref(input_data: Dict[str, Any]) -> str:
    """
    Enough to find the record in the logs, and no more.

    ⚠ The messages this feeds used to interpolate the **whole `input_data`** — the narrative, its
    summary, the district — into a `ValueError` that the Celery layer then logs. The owner's rule
    (DPG-19.3): the id plus the first three words is enough to identify a grievance, and the id is
    the half that actually identifies it.

    Three words of a grievance is still narrative text and could read *"Er. Sharma refused"*. That
    is a bounded, deliberate trade — and DPG-34's log redaction will see three words instead of a
    paragraph.
    """
    gid = input_data.get("grievance_id") or "unknown grievance"
    words = (input_data.get("grievance_description") or "").split()[:3]
    excerpt = " ".join(words)[:60]
    return f"{gid} (text starts: {excerpt!r})" if excerpt else str(gid)


def translate_grievance_to_english_LLM(input_data: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a grievance to English using OpenAI API
    Args:
        grievance_data: Dict containing grievance data: {grievance_id, language_code, grievance_description, grievance_summary, grievance_categories}
    Returns:
        Dict containing translated grievance data: {grievance_id, source_language, translation_method, confidence_score, grievance_description_en, grievance_summary_en, grievance_categories_en}
    """
    client = _llm_client()
    if not client:
        raise RuntimeError("OpenAI client not available for translation")
    task = model_for("translate")
    # DPG-19.3 / D-29: the fix is that the handlers below no longer interpolate `result` at all.
    # ⚠ A pre-binding `result = {}` was written here first and then removed: with the message
    # bounded to `_grievance_ref()`, the binding protected nothing, and its mutation check proved
    # it — deleting the binding left the test green. Dead defensive code that reads as the fix is
    # worse than no code, because the next person maintains it believing it matters.
    grievance_description = input_data.get('grievance_description')
    grievance_summary = input_data.get('grievance_summary')
    language_code = input_data.get('language_code')
    if not grievance_description or not language_code:
        raise ValueError("grievance_description and language_code are required")
    if is_too_short_to_process(grievance_description):
        # DPG-19: same rule as classification. Translating four characters costs a call and
        # returns nothing useful. (This path is parked with the voice flow — DPG-19b — but the
        # rule is uniform so it does not need rediscovering on the day it is unparked.)
        raise ValueError(
            f"Too short to translate: {_grievance_ref(input_data)} "
            f"({len(grievance_description.strip())} chars, minimum "
            f"{get_llm_settings().min_classify_chars})"
        )
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
            model=task.model,
            timeout=task.timeout,
            **response_format_kwargs(
                "grievance_translation",
                GrievanceTranslation.model_json_schema(),
                task.structured_output,
            ),
        )
        if not response:
            raise ValueError("No response from OpenAI API")
        
        if response.choices[0].message.content == "{}":
            raise ValueError("Missing information, response from OpenAI is empty or invalid, check input data: {input_data}")
        
        # Parse the response
        try:
            parsed = json.loads(response.choices[0].message.content.strip())
            result = GrievanceTranslation.model_validate(parsed).model_dump()
        except Exception as e:
            raise ValueError(
                f"Error parsing the translation reply for {_grievance_ref(input_data)}: {e}"
            )
        result["grievance_id"] = input_data["grievance_id"]
        result["source_language"] = input_data["language_code"]
        result["translation_method"] = "LLM"
        result["grievance_categories_en"] = input_data["grievance_categories"]
        return result
    
    except Exception as e:
        raise ValueError(f"Error translating grievance to English: {_grievance_ref(input_data)}: {e}")


def detect_sensitive_content_llm(text: str, language_code: str = DEFAULT_LANGUAGE_CODE) -> Dict[str, Any]:
    """
    Lightweight LLM call to detect if text describes sexual or gender harassment only.
    Does not flag land issues or violence (those are high_priority, not sensitive_content).

    Returns:
        Dict with: detected (bool), level ("high"|"medium"|"low"), message (str excerpt or "").
        On parse/LLM failure returns detected=False, level="low", message="".
    """
    client = _llm_client()
    if not client:
        logger.warning("detect_sensitive_content_llm: OpenAI client not available")
        return {"detected": False, "level": "low", "message": ""}
    if not text or not text.strip():
        logger.debug("detect_sensitive_content_llm: empty text, skipping detection")
        return {"detected": False, "level": "low", "message": ""}
    detect = model_for("detect")
    try:
        lang_label = "Nepali" if language_code == "ne" else "English"
        logger.debug(
            "detect_sensitive_content_llm: calling LLM | language_code=%s, %s",
            language_code,
            text_len_for_log("input", text),
        )
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant that detects if a user is reporting sexual or gender harassment in the cultural context of provincial Nepal - be extra sensitive as awareness around the issue is low and people may be reluctant to report and evasive when reporting, so anything that may imply sexual or gender harassment should be flagged, even things like being looked at or smiled at or followed or touched. Do NOT flag land issues, property disputes, or physical violence—only sexual assault or gender/sexual harassment. Respond with a JSON object only, no other text.",
                },
                {
                    "role": "user",
                    "content": f"""Does this text in {lang_label} contain any content related to the user reporting sexual or gender harassment in the cultural context of provincial Nepal? Do not flag land issues or violence.

Text: "{text[:2000]}"

Respond with a JSON object only: {{"detected": true or false, "level": "high" or "medium" or "low", "message": "short excerpt of the relevant part of the text, or empty string if not detected"}}""",
                },
            ],
            model=detect.model,
            timeout=detect.timeout,
            **response_format_kwargs(
                "sensitive_content_detection",
                SensitiveContentDetection.model_json_schema(),
                detect.structured_output,
            ),
        )
        raw = response.choices[0].message.content.strip()
        out = json.loads(raw)
        detected = bool(out.get("detected", False))
        level = out.get("level", "low")
        if level not in ("high", "medium", "low"):
            level = "low"
        message = out.get("message") or ""
        if not isinstance(message, str):
            message = str(message)[:200]
        # Clamp first, validate second. The clamp stays even though the schema makes `level`
        # structural, because the schema is only enforced on the rungs where the provider honours
        # it — and this is the SEAH path, which does not get to depend on a provider's goodwill.
        validated = SensitiveContentDetection(detected=detected, level=level, message=message)
        detected, level, message = validated.detected, validated.level, validated.message
        logger.info(
            "detect_sensitive_content_llm: result | detected=%s, level=%s, %s",
            detected,
            level,
            text_len_for_log("message", message),
        )
        return {"detected": detected, "level": level, "message": message}
    except Exception as e:
        logger.warning(f"detect_sensitive_content_llm failed: {e}")
        return {"detected": False, "level": "low", "message": ""}


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
        
        # Get grievance data from database
        grievance_data = db_manager.get_grievance_by_id(grievance_id)
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
        success = db_manager.update_translation(grievance_id, translation_result)
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