import re
import logging
import os
import json
from random import randint

from dotenv import load_dotenv
from openai import OpenAI
from typing import Any, Text, Dict, List, Tuple, Union, Optional

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Restarted, FollowupAction, ActiveLoop
from rasa_sdk.types import DomainDict
from .base_classes import BaseFormValidationAction, BaseAction
from backend.config.constants import GRIEVANCE_STATUS, EMAIL_TEMPLATES, DIC_SMS_TEMPLATES, DEFAULT_VALUES, ADMIN_EMAILS, CLASSIFICATION_DATA, LIST_OF_CATEGORIES, DEFAULT_PROVINCE, DEFAULT_DISTRICT, TASK_STATUS, GRIEVANCE_CLASSIFICATION_STATUS
from backend.services.database_services.postgres_services import db_manager
from backend.services.messaging import SMSClient, EmailClient
from .utterance_mapping_rasa import get_utterance, get_buttons, BUTTON_SKIP, BUTTON_AFFIRM, BUTTON_DENY
from .keyword_detector import KeywordDetector, DetectionResult
from datetime import datetime, timedelta
from rapidfuzz import process
import traceback

from icecream import ic

SKIP_VALUE = DEFAULT_VALUES["SKIP_VALUE"]
SUCCESS = TASK_STATUS["SUCCESS"]
ERROR = TASK_STATUS["ERROR"]
IN_PROGRESS = TASK_STATUS["IN_PROGRESS"]


#define and load variables

load_dotenv('/home/ubuntu/nepal_chatbot/.env')
open_ai_key = os.getenv("OPENAI_API_KEY")

# Categories are already stripped in constants.py
logger = logging.getLogger(__name__)


# Initialize keyword detector
keyword_detector = None

def get_keyword_detector(language_code: str = "en") -> KeywordDetector:
    """Get or create keyword detector instance"""
    global keyword_detector
    if keyword_detector is None or keyword_detector.language_code != language_code:
        keyword_detector = KeywordDetector(language_code=language_code)
    return keyword_detector

############################ STEP 0 - GENERIC ACTIONS ############################

class ActionSubmitGrievanceAsIs(BaseAction):
    def name(self) -> Text:
        return "action_submit_grievance_as_is"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        grievance_description = tracker.get_slot("grievance_description")
        if grievance_description:
            dispatcher.utter_message(response="utter_grievance_submitted_as_is", grievance_description=grievance_description)
        else:
            dispatcher.utter_message(response="utter_grievance_submitted_no_details_as_is")
            
        # Trigger the submit grievance action
        return [FollowupAction("action_submit_grievance")]
    
class ActionStartGrievanceProcess(BaseAction):

    def name(self) -> Text:
        return "action_start_grievance_process"

    async def run(self, dispatcher, tracker, domain):
        # reset the form parameters
        BaseFormValidationAction.message_display_list_cat = True
        set_id_data = {
            'complainant_province': tracker.get_slot("complainant_province") or DEFAULT_PROVINCE,
            'complainant_district': tracker.get_slot("complainant_district") or DEFAULT_DISTRICT,
            'complainant_office': tracker.get_slot("complainant_office") or None,
            'source': 'bot'
        }
        # Create the grievance with temporary status and specify source as 'bot'
        complainant_id = db_manager.create_complainant_id(set_id_data)
        ic(f"Created user with ID: {complainant_id}")
        grievance_id = db_manager.create_grievance_id(set_id_data)
        ic(f"Created temporary grievance with ID: {grievance_id}")
        
        # Get language code from tracker
        language_code = tracker.get_slot("language_code") or "en"
        
        # Get utterance and buttons from mapping
        utterance = get_utterance("grievance_form", "action_start_grievance_process", 1, language_code)
        
        # Send utterance with grievance ID in the text
        dispatcher.utter_message(
            text=utterance,
        )
        
        # Emit custom event with grievance ID for frontend
        dispatcher.utter_message(
            json_message={
                "data": {
                    "grievance_id": grievance_id,
                    "event_type": "grievance_id_set"
                }
            }
        )
        
        # Also set it as a slot for session persistence
        return [
                SlotSet("grievance_id", grievance_id),
                SlotSet("complainant_id", complainant_id),
                SlotSet("grievance_new_detail", None),
                SlotSet("grievance_description", None),
                SlotSet("grievance_summary", None),
                SlotSet("grievance_categories", None),
                SlotSet("grievance_summary_status", None),
                SlotSet("grievance_categories_status", None),
                SlotSet("main_story", "new_grievance"),
                SlotSet("gender_issues_reported", False),
                SlotSet("grievance_description_status", None)]


############################ STEP 1 - GRIEVANCE FORM DETAILS ############################

class ValidateGrievanceDetailsForm(BaseFormValidationAction):# Use the singleton instance directly
        
    def name(self) -> Text:
        return "validate_grievance_description_form"
    
    async def _trigger_async_classification(self, tracker: Tracker, dispatcher: CollectingDispatcher) -> Dict[str, Any]:
        """
        Trigger async classification when grievance details form is completed.
        
        Returns:
            Dict with slots to set for async classification tracking
        """
        grievance_id = tracker.get_slot("grievance_id")
        grievance_description = tracker.get_slot("grievance_description")
        language_code = tracker.get_slot("language_code") or "en"
        
        # If no grievance details or ID, skip classification
        if not grievance_description or not grievance_id:
            return {
                "classification_status": SKIP_VALUE,
                "grievance_summary": "",
                "grievance_categories": [],
                "grievance_summary_status": SKIP_VALUE,
                "grievance_categories_status": SKIP_VALUE
            }
            
        try:
            # Import the Celery task
            from task_queue.registered_tasks import classify_and_summarize_grievance_task
            
            # Prepare input data for Celery task
            input_data = {
                'grievance_id': grievance_id,
                'complainant_id': tracker.get_slot("complainant_id"),
                'language_code': language_code,
                'complainant_province': tracker.get_slot("complainant_province") or DEFAULT_PROVINCE,
                'complainant_district': tracker.get_slot("complainant_district") or DEFAULT_DISTRICT,
                'values': {
                    'grievance_description': grievance_description
                }
            }
            
            # Launch Celery task asynchronously
            task_result = classify_and_summarize_grievance_task.delay(input_data)
            task_id = task_result.id
            
            print(f"Async classification triggered for grievance {grievance_id} with task ID: {task_id}")
            
            # Return slots to indicate async processing
            return {
                "classification_task_id": task_id,
                "classification_status": IN_PROGRESS
            }
            
        except Exception as e:
            print(f"Error launching async classification: {e}")
            # Fallback - proceed without classification
            return {
                "classification_status": ERROR,
                "grievance_summary": "",
                "grievance_categories": [],
                "grievance_summary_status": SKIP_VALUE,
                "grievance_categories_status": SKIP_VALUE
            }
    
    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        # Check if grievance_new_detail is "completed"
        if tracker.get_slot("grievance_new_detail") == "completed":
            
            return []  # This will deactivate the form
        
        # Otherwise, keep asking for grievance_new_detail
        return ["grievance_new_detail"]
    
    async def _dispatch_openai_message(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]):
        if tracker.latest_message.get("text") == "/submit_details":
            dispatcher.utter_message(text="Calling OpenAI for classification... This may take a few seconds...")

    async def extract_grievance_new_detail(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:

        return await self._handle_slot_extraction(
                                            "grievance_new_detail",
                                            tracker,
                                            dispatcher,
                                            domain,
                                            skip_value=True,  # When skipped, assume confirmed
                                        )

    async def validate_grievance_new_detail(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        """
        Validate the grievance_new_detail slot.
        To gracefully handle the case were users do not use the buttons and keep typing in the text box, we have merged the process of adding more details and submitting the grievance into a single slot.
        The slot is called grievance_new_detail and it is a string that can be either a payload or a text.
        The payloads are:
        - /submit_details
        - /add_more_details
        - /restart
        
        """

        # Handle restart the process
        if slot_value == "/restart":
            return {"grievance_new_detail": None,
                    "grievance_description": None,
                    "grievance_description_status": "restart"}

        if slot_value == "/add_more_details": #reset the slot and set the status to add_more_details to call the right utterance
           return {"grievance_new_detail": None,
                   "grievance_description_status": "add_more_details"}
        
        # Handle form completion
        if slot_value == "/submit_details":
            # Get base slots - async classification will be triggered here
            slots_to_set = {
                "grievance_new_detail": "completed",
                "grievance_description": tracker.get_slot('grievance_description'),
            }
            
            # Trigger async classification when form is completed
            classification_slots = await self._trigger_async_classification(tracker, dispatcher)
            slots_to_set.update(classification_slots)
            ic(slots_to_set)
            return slots_to_set
        
        # Handle valid grievance text
        if slot_value and not slot_value.startswith('/'):
            # Check for sensitive content using keyword detection
            language_code = tracker.get_slot("language_code") or "en"
            detector = get_keyword_detector(language_code)
            detection_result = detector.detect_sensitive_content(slot_value)
            
            #handle the case where sensitive content is detected
            if detection_result.detected and detection_result.action_required:
                ic(f"🚨 SENSITIVE CONTENT DETECTED: {detection_result.category} - {detection_result.level}")
                ic(f"Confidence: {detection_result.confidence}")
                ic(f"Message: {detection_result.message}")
                
                # Store detection result for later use
                slots_to_set = {
                    "sensitive_content_detected": True,
                    "sensitive_content_category": detection_result.category,
                    "sensitive_content_level": detection_result.level.value,
                    "sensitive_content_message": detection_result.message,
                    "sensitive_content_confidence": detection_result.confidence
                }
                
                # Send detection message with buttons
                buttons = detector.get_detection_buttons(detection_result)
                dispatcher.utter_message(
                    text=detection_result.message,
                    buttons=buttons
                )
                
                # Don't process the grievance text yet - wait for user response
                return slots_to_set
            
            #handle the case where sensitive content is not detected
            updated_temp = self._update_grievance_text(tracker.get_slot("grievance_description"), slot_value)
            
            
            return {
                "grievance_new_detail": None,
                "grievance_description": updated_temp,
                "grievance_description_status": "show_options"
            }

        


    def _update_grievance_text(self, current_text: str, new_text: str) -> str:
        """Helper method to update the grievance text."""
        # handle the cases where the new text is a payload
        if new_text.startswith('/'):
            new_text = ""
        updated = current_text + "\n" + new_text if current_text else new_text
        updated = updated.strip()
        return updated
    
class ActionAskGrievanceDetailsFormGrievanceNewDetail(BaseAction):
    def name(self) -> Text:
        return "action_ask_grievance_description_form_grievance_new_detail"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        slot_grievance_description_status = tracker.get_slot("grievance_description_status")
        language_code = tracker.get_slot("language_code") or "en"
        
        if not slot_grievance_description_status:
            utterance = get_utterance("grievance_form", self.name(), 1, language_code)
            dispatcher.utter_message(text=utterance)

        if slot_grievance_description_status == "restart":
            utterance = get_utterance("grievance_form", self.name(), 2, language_code)
            dispatcher.utter_message(text=utterance)

        if slot_grievance_description_status == "add_more_details":
            utterance = get_utterance("grievance_form", self.name(), 3, language_code)
            dispatcher.utter_message(text=utterance)

        if slot_grievance_description_status == "show_options":
            slot_grievance_description = tracker.get_slot("grievance_description")
            utterance = get_utterance("grievance_form", self.name(), 4, language_code).format(grievance_description=slot_grievance_description)
            buttons = get_buttons("grievance_form", self.name(), 4, language_code)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            
        return []


############################ STEP 4 - SUBMIT GRIEVANCE ############################
class ActionSubmitGrievance(BaseAction):
    def __init__(self):
        self.sms_client = SMSClient()
        self.email_client = EmailClient()
        
        
    def name(self) -> Text:
        return "action_submit_grievance"

    def get_current_datetime(self) -> str:
        """Get current date and time in YYYY-MM-DD HH:MM format."""
        return datetime.now().strftime("%Y-%m-%d %H:%M")
    

    def is_valid_email(self, email: str) -> bool:
        """Check if the provided string is a valid email address."""
        if not email:
            return False
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def collect_grievance_data(self, tracker: Tracker) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Collect and separate user and grievance data from slots."""
        # set up the timestamp and timeline
        grievance_timestamp = self.get_current_datetime()
        grievance_timeline = (datetime.strptime(grievance_timestamp, "%Y-%m-%d %H:%M") + 
                            timedelta(days=15)).strftime("%Y-%m-%d")
        
        # user data
        grievance_data={k : tracker.get_slot(k) for k in ["complainant_phone",
                                                          "complainant_email",
                                                          "complainant_full_name",
                                                          "complainant_province",
                                                          "complainant_district",
                                                          "complainant_municipality",
                                                          "complainant_project",
                                                          "complainant_ward",
                                                          "complainant_village",
                                                          "complainant_address",
                                                          "grievance_id",
                                                          "grievance_description",
                                                          "otp_verified",
                                                          "grievance_categories",
                                                          "grievance_summary"
                                                          ]}
        
        grievance_data["grievance_status"] = GRIEVANCE_STATUS["SUBMITTED"]
        grievance_data["submission_type"] = "new_grievance"
        grievance_data["grievance_timestamp"] = grievance_timestamp
        grievance_data["grievance_timeline"] = grievance_timeline
        # grievance_data["complainant_unique_id"] = self.generate_complainant_id(grievance_data)
        # change all the values of the slots_skipped or None to "NOT_PROVIDED"
        grievance_data = self._update_key_values_for_db_storage(grievance_data)
        ic(grievance_data)
                
        return grievance_data

    def _update_key_values_for_db_storage(self, grievance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update the values of the grievance data for the database storage."""
        for key, value in grievance_data.items():
            if value == SKIP_VALUE or value is None:
                grievance_data[key] = DEFAULT_VALUES["NOT_PROVIDED"]
        return grievance_data
    
    def _get_attached_files_info(self, grievance_id: str) -> str:
        """Get information about files attached to a grievance.
        
        Args:
            grievance_id (str): The ID of the grievance to check for files
            
        Returns:
            str: A formatted string containing file information, or empty string if no files
        """
        try:
            files = db_manager.get_grievance_files(grievance_id)
            if not files:
                return {"has_files": False,
                        "files_info": ""}
            else:
                files_info = "\nAttached files:\n" + "\n".join([
                f"- {file['file_name']} ({file['file_size']} bytes)"
                for file in files
            ])
                return {"has_files": True,
                        "files_info": files_info}
        except Exception as e:
            ic(f"❌ Error getting attached files info: {str(e)}")
            ic(f"Traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to get attached files info: {str(e)}")
            return {"has_files": False,
                    "files_info": ""}
        
    def create_confirmation_message(self, 
                                    grievance_data: Dict[str, Any]) -> str:
        """Create a formatted confirmation message."""
        ic(self.language_code)
        
        # Get attached files information using the helper function
        has_files = self._get_attached_files_info(grievance_data['grievance_id'])["has_files"]
        files_info = self._get_attached_files_info(grievance_data['grievance_id'])["files_info"]
        
        message = [get_utterance("grievance_form", 
                                 'create_confirmation_message', 
                                 i, 
                                 self.language_code) for i in ['grievance_id',
                                                                'grievance_timestamp',
                                                         'grievance_description',
                                                         'complainant_email',
                                                         'complainant_phone',
                                                         'grievance_outro',
                                                         'grievance_timeline'] if grievance_data.get(i) is not DEFAULT_VALUES["NOT_PROVIDED"]]
        
        message = "\n".join(message).format(grievance_id=grievance_data['grievance_id'], 
                                            grievance_timestamp=grievance_data['grievance_timestamp'],
                                            grievance_description=grievance_data['grievance_description'],
                                            complainant_email=grievance_data['complainant_email'],
                                            complainant_phone=grievance_data['complainant_phone'],
                                            grievance_timeline=grievance_data['grievance_timeline']
                                           )

        # Add files information to the message
        if has_files:
            message = message + files_info
        return message
    
    async def _send_grievance_recap_email(self, 
                                          to_emails: List[str],
                                          email_data: Dict[str, Any],
                                          body_name: str,
                                          dispatcher: CollectingDispatcher) -> None:
        """Send a recap email to the user."""
        
        json_data = json.dumps(email_data, indent=2, ensure_ascii=False)
        
        if email_data['grievance_categories'] and email_data['grievance_categories'] != DEFAULT_VALUES["NOT_PROVIDED"]:
            categories_html = ''.join(f'<li>{category}</li>' for category in (email_data['grievance_categories'] or []))
        else:
            categories_html = ""
        # Create email body using template
        
        if body_name == "GRIEVANCE_RECAP_complainant_BODY":
            body = EMAIL_TEMPLATES[body_name].format(
            complainant_name=email_data['complainant_full_name'],
            grievance_description=email_data['grievance_description'],
            project=email_data['complainant_project'],
            municipality=email_data['complainant_municipality'],
            village=email_data['complainant_village'],
            address=email_data['complainant_address'],
            phone=email_data['complainant_phone'],
            grievance_id=email_data['grievance_id'],
            email=email_data['complainant_email'],
            grievance_timeline=email_data['grievance_timeline'],
            grievance_timestamp=email_data['grievance_timestamp'],
            grievance_categories=email_data['grievance_categories'],
            grievance_summary=email_data['grievance_summary']
        ) 
        if body_name == "GRIEVANCE_RECAP_ADMIN_BODY":
            body = EMAIL_TEMPLATES[body_name].format(
                json_data=json_data,
                grievance_status=GRIEVANCE_STATUS["SUBMITTED"],
            )

        subject = EMAIL_TEMPLATES["GRIEVANCE_RECAP_SUBJECT"].format(
            grievance_id=email_data['grievance_id']
        )
        try:
            self.email_client.send_email(to_emails,
                                        subject = subject,
                                        body=body
                                        )
            if body_name == "GRIEVANCE_RECAP_complainant_BODY":
                message = get_utterance("grievance_form", self.name(), 2, self.language_code)
                dispatcher.utter_message(text=message)
                
        except Exception as e:
            logger.error(f"Failed to send system notification email: {e}"
            )
            
    # def _grievance_submit_gender_follow_up(self, dispatcher: CollectingDispatcher):
    #         """Handle the case of gender follow up."""
    #         utterance = get_utterance("grievance_form", "action_submit_grievance_gender_follow_up", 1, self.language_code)
    #         buttons = get_buttons("grievance_form", "action_submit_grievance_gender_follow_up", 1, self.language_code)
    #         ic(utterance, buttons)
    #         dispatcher.utter_message(text=utterance, buttons=buttons)
    
    def _send_last_utterance_buttons(self, 
                                     gender_tag: bool, 
                                     has_files: bool, 
                                     dispatcher: CollectingDispatcher) -> str:
        buttons = None
        ic("send last utterance and buttons")
        if gender_tag:
                utterance = get_utterance("grievance_form", "send_last_utterance_buttons", 1, self.language_code)
                buttons = get_buttons("grievance_form", "send_last_utterance_buttons", 1, self.language_code)
        elif not has_files:
            utterance = get_utterance("grievance_form", "send_last_utterance_buttons", 2, self.language_code)
        else:
            utterance = get_utterance("grievance_form", "send_last_utterance_buttons", 3, self.language_code)
        
        ic(utterance, buttons)
        if buttons:
            dispatcher.utter_message(text=utterance, buttons=buttons)
        else:
            dispatcher.utter_message(text=utterance)

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        ic("\n=================== Submitting Grievance ===================")
        self.language_code = tracker.get_slot("language_code") or "en"
        self.gender_issues_reported = tracker.get_slot("gender_issues_reported")
        self.grievance_id = tracker.get_slot("grievance_id")
        self.complainant_id = tracker.get_slot("complainant_id")
        
        ic("Debug - All tracker slots:", tracker.slots)
        ic("Debug - grievance_id from tracker:", self.grievance_id)
        ic("Debug - complainant_id from tracker:", self.complainant_id)
        
        try:
            # Collect grievance data
            grievance_data = self.collect_grievance_data(tracker)
            ic('collected grievance data from tracker', grievance_data)
            # Update the existing grievance with complete data
            try:
                db_manager.submit_grievance_to_db(data=grievance_data)
            except Exception as e:
                ic(f"❌ Error updating grievance: {str(e)}")
                ic(f"Traceback: {traceback.format_exc()}")
                raise Exception("Failed to update grievance in the database")
        

            ic(f"✅ Grievance updated successfully with ID: {self.grievance_id}")
            
            # Create confirmation message to be sent by sms and through the bot
            confirmation_message = self.create_confirmation_message(
                grievance_data
            )
                
            # Send confirmation message
            dispatcher.utter_message(text=confirmation_message)
            
            if grievance_data.get('otp_verified') == True:
                #send sms
                complainant_phone = grievance_data.get('complainant_phone')
                if complainant_phone != DEFAULT_VALUES["NOT_PROVIDED"]:
                    self.sms_client.send_sms(complainant_phone, confirmation_message)
                    #utter sms confirmation message
                    utterance = get_utterance("grievance_form", self.name(), 2, self.language_code).format(complainant_phone=complainant_phone)
                    ic(complainant_phone, utterance)
                    dispatcher.utter_message(text=utterance)
            
            #send email to admin
            await self._send_grievance_recap_email(ADMIN_EMAILS, 
                                                   grievance_data, 
                                                   "GRIEVANCE_RECAP_ADMIN_BODY", 
                                                   dispatcher=dispatcher)
            
            #send email to user
            complainant_email = grievance_data.get('complainant_email')
            if complainant_email and complainant_email != DEFAULT_VALUES["NOT_PROVIDED"]:
                await self._send_grievance_recap_email([complainant_email], 
                                                       grievance_data, 
                                                       "GRIEVANCE_RECAP_complainant_BODY", 
                                                       dispatcher=dispatcher)
                
                # Send email confirmation message
                utterance = get_utterance("grievance_form", self.name(), 3, self.language_code).format(complainant_email=complainant_email)
                dispatcher.utter_message(text=utterance)
            
            #send the last utterance and buttons
            self._send_last_utterance_buttons(self.gender_issues_reported, 
                                              
                                                self._get_attached_files_info(self.grievance_id)["has_files"],
                                                dispatcher=dispatcher)
                
            
            # #deal with the case of gender follow up
            # if self.gender_issues_reported:
            #     self._grievance_submit_gender_follow_up(dispatcher)
            
            # #send utter to users if they have not attached any files or a reminder to attach more files
            # elif not self._get_attached_files_info(grievance_id)["has_files"]:
            #     utterance = get_utterance("grievance_form", self.name(), 4, self.language_code)
            #     dispatcher.utter_message(text=utterance)
            
            # else:
            #         utterance = get_utterance("grievance_form", self.name(), 5, self.language_code)
            #         dispatcher.utter_message(text=utterance)
                
            # Prepare events
            return [
                SlotSet("grievance_status", GRIEVANCE_STATUS["SUBMITTED"])
            ]

        except Exception as e:
            ic(f"❌ Error submitting grievance: {str(e)}")
            ic(f"Traceback: {traceback.format_exc()}")
            utterance = get_utterance("grievance_form", self.name(), 4, self.language_code)
            dispatcher.utter_message(text=utterance)
            return []
        
    
                
            

        



