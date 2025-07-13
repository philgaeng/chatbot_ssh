import re
import logging
import os
import json
from random import randint

from dotenv import load_dotenv
from typing import Any, Text, Dict, List, Tuple, Union, Optional

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Restarted, FollowupAction, ActiveLoop
from rasa_sdk.types import DomainDict
from utils.base_classes import BaseFormValidationAction, BaseAction, SKIP_VALUE

from backend.services.messaging import Messaging
from utils.utterance_mapping_rasa import BUTTON_SKIP, BUTTON_AFFIRM, BUTTON_DENY
from rapidfuzz import process
from datetime import datetime, timedelta
from backend.config.constants import (
    GRIEVANCE_STATUS, GRIEVANCE_CLASSIFICATION_STATUS, EMAIL_TEMPLATES, DIC_SMS_TEMPLATES, DEFAULT_VALUES,
    ADMIN_EMAILS, CLASSIFICATION_DATA, LIST_OF_CATEGORIES, USER_FIELDS,
    GRIEVANCE_FIELDS, DEFAULT_PROVINCE, DEFAULT_DISTRICT, TASK_STATUS,
    MAX_FILE_SIZE
)



LLM_GENERATED = GRIEVANCE_CLASSIFICATION_STATUS["LLM_generated"]
LLM_FAILED = GRIEVANCE_CLASSIFICATION_STATUS["LLM_failed"]
LLM_ERROR = GRIEVANCE_CLASSIFICATION_STATUS["LLM_error"]
complainant_CONFIRMED = GRIEVANCE_CLASSIFICATION_STATUS["complainant_confirmed"]
OFFICER_CONFIRMED = GRIEVANCE_CLASSIFICATION_STATUS["officer_confirmed"]
SUCCESS = TASK_STATUS["SUCCESS"]
ERROR = TASK_STATUS["ERROR"]
SKIP_VALUE = DEFAULT_VALUES["SKIP_VALUE"]
IN_PROGRESS = TASK_STATUS["IN_PROGRESS"]
FAILED = TASK_STATUS["FAILED"]

############################ STEP 1 - VALIDATE GRIEVANCE SUMMARY AND CATEGORIES ############################

class ActionTriggerSummaryForm(BaseAction):
    def name(self) -> Text:
        return "action_trigger_summary_form"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Trigger the grievance summary form only if classification is complete.
        This action should be called after ActionEmitStatusUpdate when classification results are received.
        """
        classification_status = tracker.get_slot("classification_status")
        grievance_status = tracker.get_slot("grievance_status")
        grievance_categories = tracker.get_slot("grievance_categories")
        grievance_summary = tracker.get_slot("grievance_summary")
        
        # Check if we have classification results
        if classification_status == SUCCESS and grievance_status == GRIEVANCE_STATUS["SUBMITTED"] and grievance_categories and grievance_summary:
            # Classification is complete, activate the form
            return [ActiveLoop("grievance_summary_form")]
        elif classification_status == FAILED: #no followup action is needed
            return []

class ValidateGrievanceSummaryForm(BaseFormValidationAction):
    # Class variable to track messagBe display
    BaseFormValidationAction.message_display_list_cat = True
    
    def __init__(self):
        """Initialize form action"""
        super().__init__()
        
    def name(self) -> Text:
        return "validate_grievance_summary_form"
    
    
    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        self.language_code = tracker.get_slot("language_code")
        # The form is only activated when classification is complete, so we can simply return the required slots
        return [
            "grievance_categories_status",
            "grievance_cat_modify", 
            "grievance_summary_status",
            "grievance_summary_temp"
        ]
    
    

    def _detect_gender_issues(self, tracker: Tracker) -> bool:
        """
        Detects gender issues in the grievance list of categories
        """
        
        categories = tracker.get_slot("grievance_categories")
        gender_issues_detected = any("gender" in category.lower() for category in categories)
        #check if the string "gender" is in any of the categories in the list_of_cat
        return gender_issues_detected
    
    def _report_gender_issues(self, 
                                 dispatcher: CollectingDispatcher, 
                                 tracker: Tracker):
            """
            Helper function to report gender issues and return the specific updated slots
            the changes in requested_slot are not handled in that specific function
            the utterance and buttons are handled in the action_ask_grievance_summary_form_gender_follow_up
            """
            # update all the regular slots to validate the form and add the gender_issues_reported slot
            return {"grievance_categories_status": LLM_GENERATED,
                    "grievance_cat_modify": SKIP_VALUE,
                    "grievance_categories": tracker.get_slot("grievance_categories"),
                    "grievance_summary": tracker.get_slot("grievance_summary_temp"),
                    "grievance_summary_confirmed": SKIP_VALUE,
                    "gender_issues_reported": True}
            
    async def extract_grievance_categories_status(self, 
                                                   dispatcher: CollectingDispatcher,
                                                   tracker: Tracker,
                                                   domain: Dict[Text, Any]
                                                   ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "grievance_categories_status",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_grievance_categories_status(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        slot_value = slot_value.strip('/')
        try:      
            if slot_value == SKIP_VALUE:
                return {"grievance_categories_status": LLM_GENERATED}
            
            # Fallback to original logic if no async results
            if slot_value == "slot_confirmed":
                if self._detect_gender_issues(tracker):
                    return self._report_gender_issues(dispatcher, tracker)
                else:
                    return {"grievance_categories_status": complainant_CONFIRMED}
                
            else:
                #return the slot_value as selected by the user and move to category_modify slot
                return {"grievance_categories_status": slot_value}
        except Exception as e:
            self.logger.error(f"Error in validate_grievance_categories_status: {e}")
            return {"grievance_categories_status": LLM_GENERATED}
    
    
    
    async def extract_grievance_cat_modify(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "grievance_cat_modify",
            tracker,
            dispatcher,
            domain
        )
    
    def get_category_to_modify(self, input_text: str) -> str:
        """
        Extracts the category from the slot_value by matching it from the list of categories using rapidfuzz
        Returns None if no categories in slot_value
        
        """
        selected_category = None
        if ":" in input_text:
             #initialize the selected category
            temp_cat = input_text.split(":")[1].strip()
            for c in LIST_OF_CATEGORIES:
                if c in input_text:
                        selected_category = c
                if not selected_category:
                    #select the category c in the list_of_cat that is the closest match to the temp_cat using rapidfuzz
                    selected_category = process.extractOne(input_text, LIST_OF_CATEGORIES)
                    
        return selected_category
    
    async def validate_grievance_cat_modify(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        # provide the detailed doc of the function
        """
        Validates the modification of grievance categories.
        
        This function handles the validation of category modifications (adding or deleting) 
        from the list of grievance categories. It processes the user's selection and updates 
        the category list accordingly.

        Args:
            slot_value (Any): The value received from the user input, typically a category selection
            dispatcher (CollectingDispatcher): The dispatcher used to send messages to the user
            tracker (Tracker): The tracker containing the conversation state
            domain (Dict[Text, Any]): The domain specification containing all domain information

        Returns:
            Dict[Text, Any]: A dictionary containing updated slot values:
                - grievance_categories: Updated list of categories
                - grievance_categories_status: Reset to None after processing
                - grievance_cat_modify: Reset to None after processing
                
        Note:
            The function handles three main cases:
            1. Skip operation: When user chooses to skip the modification
            2. Delete operation: Removes selected category from the list
            3. Add operation: Appends new category to the existing list
        """
         
        slot_value = slot_value.strip('/')
        self.logger.info(f"validate_grievance_cat_modify: {slot_value}")
        list_of_cat = tracker.get_slot("grievance_categories")
        
        #get the category to modify from the slot_value
        selected_category = self.get_category_to_modify(slot_value)
        
        #if no category is selected or the slot_value is SKIP_VALUE, return the LLM_GENERATED status and the SKIP_VALUE for the grievance_cat_modify slot
        try:
            if not selected_category or slot_value == SKIP_VALUE:
                dispatcher.utter_message(text="No category selected. skipping this step.")
                return {"grievance_categories_status": LLM_GENERATED,
                    "grievance_cat_modify": SKIP_VALUE}
      
            #case 2: delete the category
            if tracker.get_slot("grievance_categories_status") == "slot_deleted":
                #delete the category
                list_of_cat.remove(selected_category)
                
            #case 3: add the category
            if tracker.get_slot("grievance_categories_status") == "slot_added":
                list_of_cat.append(selected_category)
        
        
            #reset the message_display_list_cat to True
            BaseFormValidationAction.message_display_list_cat = True
            
            #deal with the case where gender issues is part of list_of_cat
            if self._detect_gender_issues(tracker):
                return self._report_gender_issues(dispatcher, tracker)
                
            return {
                "grievance_categories": list_of_cat,
                "grievance_categories_status": None,
                "grievance_cat_modify": "Done",
            }
        except Exception as e:
            self.logger.error(f"Error in validate_grievance_cat_modify: {e}")
            return {"grievance_categories_status": LLM_GENERATED,
                    "grievance_cat_modify": SKIP_VALUE}
        
        
        
    

    
    async def extract_grievance_summary_status(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "grievance_summary_status",
            tracker,
            dispatcher,
            domain
        )
    
    
    async def validate_grievance_summary_status(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        slot_value = slot_value.strip('/')
        try:
            if slot_value == SKIP_VALUE:
                return {"grievance_summary_status": LLM_GENERATED,
                    "grievance_summary_temp": SKIP_VALUE} #this will validate the slot and the form
            
            
            if slot_value == "slot_confirmed":
                return {"grievance_summary_status": complainant_CONFIRMED,
                        "grievance_summary_temp": SKIP_VALUE} #this will validate the slot and the form
            
            if slot_value == "slot_edited":
                return {"grievance_summary_status": "slot_edited",
                        "grievance_summary_temp": None
                        }
        except Exception as e:
            self.logger.error(f"Error in validate_grievance_summary_status: {e}")
            return {"grievance_summary_status": LLM_GENERATED,
                    "grievance_summary_temp": SKIP_VALUE}

    
    async def extract_grievance_summary_temp(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "grievance_summary_temp",
            tracker,
            dispatcher,
            domain
        )

    
    async def validate_grievance_summary_temp(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        slot_value = slot_value.strip('/')
        try:
            if slot_value == SKIP_VALUE:
                self.logger.info("SKIP_VALUE in validate_grievance_summary_temp")
                return {"grievance_summary_status": LLM_GENERATED,
                    "grievance_summary_temp": SKIP_VALUE}
        
            if slot_value:
                self.logger.info(f"validate_grievance_summary_temp: {slot_value}")
                return {"grievance_summary_status": None,
                        "grievance_summary_temp": slot_value,
                        "grievance_summary": slot_value}
                
            return {}
        except Exception as e:
            self.logger.error(f"Error in validate_grievance_summary_temp: {e}")
            return {}

    async def extract_gender_follow_up(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "gender_follow_up",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_gender_follow_up(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        
        slots = {"complainant_location_consent": False,
                    "complainant_municipality_temp": SKIP_VALUE,
                    "complainant_municipality": SKIP_VALUE,
                    "complainant_municipality_confirmed": False,
                    "complainant_village": SKIP_VALUE,
                    "complainant_address_temp": SKIP_VALUE,
                    "complainant_address": SKIP_VALUE,
                    "complainant_address_confirmed": False,
                    "complainant_consent": SKIP_VALUE,
                    "complainant_full_name": SKIP_VALUE,
                    "complainant_phone": SKIP_VALUE,
                    "phone_validation_required": False,
                    "complainant_email_temp": SKIP_VALUE,
                    "complainant_email_confirmed": SKIP_VALUE
                    }
        
        if slot_value == "/exit" or SKIP_VALUE in slot_value:
            return slots
        if slot_value == "/anonymous_with_phone":
            slots["complainant_consent"] = "anonymous_with_phone"
            slots["complainant_full_name"] = None
            slots["complainant_phone"] = None
            slots["phone_validation_required"] = True
            return slots
        return {}

class ActionAskGrievanceSummaryFormGrievanceListCatStatus(BaseAction):
    def name(self) -> Text:
        return "action_ask_grievance_summary_form_grievance_categories_status"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        classification_status = tracker.get_slot("classification_status")
        
        # Handle async classification status
        if classification_status == "processing":
            utterance = self.get_utterance( 3 )
            dispatcher.utter_message(text=utterance)
            return []
        elif classification_status == "failed":
            utterance = self.get_utterance(2)
            dispatcher.utter_message(text=utterance)
            return []
        elif classification_status == "skipped":
            # No classification available, proceed with manual input
            utterance = self.get_utterance(4)
            dispatcher.utter_message(text=utterance)
            return []
        elif classification_status == "completed":
            # Classification is complete, show results
            grievance_categories = tracker.get_slot("grievance_categories")
            grievance_summary_temp = tracker.get_slot("grievance_summary_temp")
            
            if grievance_categories and grievance_summary_temp:
                
                # Show success message
                utterance = self.get_utterance(5)
                dispatcher.utter_message(text=utterance)
            
        if BaseFormValidationAction.message_display_list_cat:
            grievance_categories = tracker.get_slot("grievance_categories")
            print(f"Current categories: {grievance_categories}")
            
            if not grievance_categories or grievance_categories == []:
                print("No categories found, sending no categories message")
                utterance = self.get_utterance(1)
                buttons = self.get_buttons(1)
                dispatcher.utter_message(text=utterance, buttons=buttons)
            
            else:
                print(f"Sending message with categories: {grievance_categories}")
                category_text = "\n".join([v for v in grievance_categories])
                utterance = self.get_utterance(2)
                utterance = utterance.format(category_text=category_text)  
                buttons = self.get_buttons(2)
                dispatcher.utter_message(text=utterance, buttons=buttons)

            BaseFormValidationAction.message_display_list_cat = False

        return []


class ActionAskGrievanceSummaryFormGrievanceCatModify(BaseAction):
    def name(self) -> Text:
        return "action_ask_grievance_summary_form_grievance_cat_modify"
    
    async def execute_action(
        self, 
        dispatcher: CollectingDispatcher, 
        tracker: Tracker,
        domain: DomainDict
        ) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        ask_cat_modify_flag = tracker.get_slot("grievance_categories_status")
        list_of_cat = tracker.get_slot("grievance_categories")
        
        if ask_cat_modify_flag == 'slot_deleted':
            if not list_of_cat:
                utterance = self.get_utterance(1)
                dispatcher.utter_message(text=utterance)
                return {"grievance_categories_status": SKIP_VALUE}
            else:
                buttons = [
                    {"title": cat, "payload": f'/delete_category{{"category_to_delete": "{cat}"}}'}
                    for cat in list_of_cat
                ]
                buttons.append({"title": "Skip", "payload": "/skip"})
                utterance = self.get_utterance(2)
                dispatcher.utter_message(text=utterance, buttons=buttons)
                
        if ask_cat_modify_flag == "slot_added":
            list_cat_to_add = [cat for cat in LIST_OF_CATEGORIES if cat not in list_of_cat]
            buttons = [
                {"title": cat, "payload": f'/add_category{{"category": "{cat}"}}'} 
                for cat in list_cat_to_add[:10]
            ]
            utterance = self.get_utterance(3)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        return []
    
    
class ActionAskGrievanceSummaryFormGrievanceSummaryStatus(BaseAction):
    def name(self) -> Text:
        return "action_ask_grievance_summary_form_grievance_summary_status"
    
    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict
        ) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        current_summary = tracker.get_slot("grievance_summary_temp")
        if current_summary:
            utterance = self.get_utterance(1)
            utterance = utterance.format(current_summary=current_summary)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        else:
            utterance = self.get_utterance(1)
            buttons = BUTTON_SKIP
            dispatcher.utter_message(text=utterance)

class ActionAskGrievanceSummaryFormGrievanceSummaryTemp(BaseAction):
    def name(self) -> Text:
        return "action_ask_grievance_summary_form_grievance_summary_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        if tracker.get_slot("grievance_summary_confirmed") == "slot_edited":
            utterance = self.get_utterance(2)
            dispatcher.utter_message(text=utterance)
        return []

class ActionAskGrievanceSummaryFormGenderFollowUp(BaseAction):
    def name(self) -> Text:
        return "action_ask_grievance_summary_form_gender_follow_up"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        for i in range(1, 4):
            utterance = self.get_utterance(i)
            dispatcher.utter_message(text=utterance)
        utterance = self.get_utterance(4)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)


############################ STEP 2 - SUBMIT VALIDATED GRIEVANCE ############################
class ActionSubmitLLMValidatedGrievance(BaseAction):
    def name(self) -> Text:
        return "action_submit_llm_validated_grievance"

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
                                                          "grievance_summary",
                                                          "grievance_description",
                                                          "grievance_categories",
                                                          "grievance_claimed_amount",
                                                          "otp_verified"
                                                          ]}
        
        grievance_data["grievance_status"] = GRIEVANCE_STATUS["SUBMITTED"]
        grievance_data["submission_type"] = "new_grievance"
        grievance_data["grievance_timestamp"] = grievance_timestamp
        grievance_data["grievance_timeline"] = grievance_timeline
        # grievance_data["complainant_unique_id"] = self.generate_complainant_id(grievance_data)
        # change all the values of the slots_skipped or None to "NOT_PROVIDED"
        grievance_data = self._update_key_values_for_db_storage(grievance_data)
                
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
            files = self.db_manager.get_grievance_files(grievance_id)
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
            self.logger.error(f"Error in get_attached_files_info: {e}")
            return {"has_files": False,
                    "files_info": ""}
        
    def create_confirmation_message(self, 
                                    grievance_data: Dict[str, Any]) -> str:
        """Create a formatted confirmation message."""
        
        # Get attached files information using the helper function
        has_files = self.db_manager.get_attached_files_info(grievance_data['grievance_id'])["has_files"]
        files_info = self.db_manager.get_attached_files_info(grievance_data['grievance_id'])["files_info"]
        
        message = [self.get_utterance("form_grievance", 
                                 'create_confirmation_message', 
                                 i, 
                                 self.language_code) for i in ['grievance_id',
                                                                'grievance_timestamp',
                                                         'grievance_summary',
                                                         'grievance_categories',
                                                         'grievance_description',
                                                         'complainant_email',
                                                         'complainant_phone',
                                                         'grievance_outro',
                                                         'grievance_timeline'] if grievance_data.get(i) is not DEFAULT_VALUES["NOT_PROVIDED"]]
        
        message = "\n".join(message).format(grievance_id=grievance_data['grievance_id'], 
                                            grievance_timestamp=grievance_data['grievance_timestamp'],
                                            grievance_summary=grievance_data['grievance_summary'],
                                            grievance_categories=grievance_data['grievance_categories'],
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
        
        categories_html = ''.join(f'<li>{category}</li>' for category in (email_data['grievance_categories'] or []))
        # Create email body using template
        
        if body_name == "GRIEVANCE_RECAP_complainant_BODY":
            body = EMAIL_TEMPLATES[body_name].format(
            complainant_name=email_data['complainant_full_name'],
            grievance_summary=email_data['grievance_summary'],
            grievance_description=email_data['grievance_description'],
            categories_html=categories_html,
            project=email_data['complainant_project'],
            municipality=email_data['complainant_municipality'],
            village=email_data['complainant_village'],
            address=email_data['complainant_address'],
            phone=email_data['complainant_phone'],
            grievance_id=email_data['grievance_id'],
            email=email_data['complainant_email'],
            grievance_timeline=email_data['grievance_timeline'],
            grievance_timestamp=email_data['grievance_timestamp']
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
            self.messaging.send_email(to_emails,
                                        subject = subject,
                                        body=body
                                        )
            if body_name == "GRIEVANCE_RECAP_complainant_BODY":
                utterance = self.get_utterance(2)
                utterance = utterance.format(complainant_email=email_data['complainant_email'])
                dispatcher.utter_message(text=utterance)
                
        except Exception as e:
            print(f"Failed to send system notification email: {e}"
            )
            
    # def _grievance_submit_gender_follow_up(self, dispatcher: CollectingDispatcher):
    #         """Handle the case of gender follow up."""
    #         utterance = self.get_utterance("form_grievance", "action_submit_grievance_gender_follow_up", 1, self.language_code)
    #         buttons = self.get_buttons("form_grievance", "action_submit_grievance_gender_follow_up", 1, self.language_code)
    #         dispatcher.utter_message(text=utterance, buttons=buttons)
    
    def _send_last_utterance_buttons(self, 
                                     gender_tag: bool, 
                                     has_files: bool, 
                                     dispatcher: CollectingDispatcher) -> str:
        buttons = None
        if gender_tag:
                utterance = self.get_utterance(1)
                buttons = self.get_buttons(1)
        elif not has_files:
            utterance = self.get_utterance(2)
        else:
            utterance = self.get_utterance(3)
        
        if buttons:
            dispatcher.utter_message(text=utterance, buttons=buttons)
        else:
            dispatcher.utter_message(text=utterance)

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        self.language_code = tracker.get_slot("language_code") or "en"
        self.gender_issues_reported = tracker.get_slot("gender_issues_reported")
        self.grievance_id = tracker.get_slot("grievance_id")
        self.complainant_id = tracker.get_slot("complainant_id")
        
        self.logger.info("Debug - All tracker slots:", tracker.slots)
        self.logger.info("Debug - grievance_id from tracker:", self.grievance_id)
        self.logger.info("Debug - complainant_id from tracker:", self.complainant_id)
        
        try:
            # Collect grievance data
            grievance_data = self.collect_grievance_data(tracker)
            self.helpers.grievance_repo.update_grievance(grievance_id=self.grievance_id,
                                                    data=grievance_data)
            self.helpers.grievance_repo.update_grievance_status(grievance_id=self.grievance_id,
                                                    status=GRIEVANCE_STATUS["SUBMITTED"])

        
            
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
                    self.messaging.send_sms(complainant_phone, confirmation_message)
                    #utter sms confirmation message
                    utterance = self.get_utterance(2)
                    utterance = utterance.format(complainant_phone=complainant_phone)
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
                utterance = self.get_utterance(3)
                utterance = utterance.format(complainant_email=complainant_email)
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
            #     utterance = self.get_utterance("form_grievance", self.name(), 4, self.language_code)
            #     dispatcher.utter_message(text=utterance)
            
            # else:
            #         utterance = self.get_utterance("form_grievance", self.name(), 5, self.language_code)
            #         dispatcher.utter_message(text=utterance)
                
            # Prepare events
            return [
                SlotSet("grievance_status", GRIEVANCE_STATUS["SUBMITTED"])
            ]

        except Exception as e:
            utterance = self.get_utterance("form_grievance", self.name(), 4, self.language_code)
            dispatcher.utter_message(text=utterance)
            return []
        