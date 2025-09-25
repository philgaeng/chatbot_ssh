import re
import json
from random import randint
from typing import Any, Text, Dict, List, Tuple, Union, Optional
from datetime import datetime, timedelta
import traceback
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Restarted, FollowupAction, ActiveLoop
from rasa_sdk.types import DomainDict
from rasa_chatbot.actions.utils.base_classes import BaseFormValidationAction, BaseAction
from backend.task_queue.registered_tasks import classify_and_summarize_grievance_task
from backend.config.constants import EMAIL_TEMPLATES, ADMIN_EMAILS




############################ STEP 0 - GENERIC ACTIONS ############################

class ActionSubmitGrievanceAsIs(BaseAction):
    def name(self) -> Text:
        return "action_submit_grievance_as_is"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
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

    async def execute_action(self, dispatcher, tracker, domain):
        # reset the form parameters
        BaseFormValidationAction.message_display_list_cat = True
        set_id_data = {
            'complainant_province': tracker.get_slot("complainant_province") or self.province,
            'complainant_district': tracker.get_slot("complainant_district") or self.district,
            'complainant_office': tracker.get_slot("complainant_office") or None,
            'source': 'bot'
        }
        # Create the grievance with temporary status and specify source as 'bot'
        complainant_id = self.db_manager.generate_complainant_id(set_id_data)
        grievance_id = self.db_manager.generate_grievance_id(set_id_data)
        self.logger.info(f"Created temporary grievance with ID: {grievance_id} and complainant ID: {complainant_id}")
        
        #reset the slots
        reset_slots = self.reset_slots(tracker, "grievance_submission")
        # # Get utterance and buttons from mapping
        # utterance = self.get_utterance(1)
        
        # # Send utterance with grievance ID in the text
        # dispatcher.utter_message(
        #     text=utterance,
        # )
        
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
                SlotSet("main_story", "new_grievance"),
                SlotSet("sensitive_issues_detected", False)] + reset_slots


############################ STEP 1 - GRIEVANCE FORM DETAILS ############################

class ValidateFormGrievance(BaseFormValidationAction):# Use the singleton instance directly
        
    def name(self) -> Text:
        return "validate_form_grievance"
    
    async def _trigger_async_classification(self, tracker: Tracker, dispatcher: CollectingDispatcher) -> Dict[str, Any]:
        """
        Trigger async classification when grievance details form is completed.
        
        Returns:
            Dict with slots to set for async classification tracking
        """
        grievance_id = tracker.get_slot("grievance_id")
        grievance_description = tracker.get_slot("grievance_description")
        self._initialize_language_and_helpers(tracker)
        
        # If no grievance details or ID, skip classification
        if not grievance_description or not grievance_id:
            return {
                "grievance_classification_status": self.SKIP_VALUE,
                "grievance_summary": "",
                "grievance_categories": [],
                "grievance_summary_status": self.SKIP_VALUE,
                "grievance_categories_status": self.SKIP_VALUE
            }
            
        try:
            
            # Prepare input data for Celery task
            input_data = {
                'grievance_id': grievance_id,
                'complainant_id': tracker.get_slot("complainant_id"),
                'language_code': self.language_code,
                'complainant_province': tracker.get_slot("complainant_province") or self.province,
                'complainant_district': tracker.get_slot("complainant_district") or self.district,
                'flask_session_id': tracker.get_slot("flask_session_id"),  # Get flask_session_id from slot
                'values': {
                    'grievance_description': grievance_description
                }
            }
            
            # Launch Celery task asynchronously
            task_result = classify_and_summarize_grievance_task.delay(input_data)
            task_id = task_result.id
            
            self.logger.info(f"Async classification triggered for grievance {grievance_id} with task ID: {task_id}")
            
            # Return slots to indicate async processing
            return {
            }
            
        except Exception as e:
            self.logger.error(f"Error launching async classification: {e}")
            # Fallback - proceed without classification
            return {
                "grievance_classification_status": self.GRIEVANCE_CLASSIFICATION_STATUS["LLM_error"],
                "grievance_summary": "",
                "grievance_categories": [],
                "grievance_summary_status": self.SKIP_VALUE,
                "grievance_categories_status": self.SKIP_VALUE
            }
    
    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        # Check if grievance_new_detail is "completed"
        if tracker.get_slot("sensitive_issues_detected"):
            return ["sensitive_issues_follow_up", "grievance_new_detail"]
        if tracker.get_slot("grievance_new_detail") == "completed":
            
            return []  # This will deactivate the form
        
        # Otherwise, keep asking for grievance_new_detail
        return ["grievance_new_detail"]
    

    def _update_grievance_text(self, current_text: str, new_text: str) -> str:
        """Helper method to update the grievance text."""
        # handle the cases where the new text is a payload
        if new_text.startswith('/'):
            new_text = ""
        updated = current_text + "\n" + new_text if current_text else new_text
        updated = updated.strip()
        return updated

    async def extract_grievance_new_detail(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        self.logger.debug(f"Extracting grievance_new_detail : {tracker.latest_message.get('text')}")
        return await self._handle_slot_extraction(
                                            "grievance_new_detail",
                                            tracker,
                                            dispatcher,
                                            domain
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
        try:
            self.logger.debug(f"Validating grievance_new_detail: {slot_value}")
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
                self.logger.debug(f"Submitting details for grievance {tracker.get_slot('grievance_description')}")
                # Get base slots - async classification will be triggered here
                slots_to_set = {
                    "grievance_new_detail": "completed",
                    "grievance_description": tracker.get_slot('grievance_description'),
                }
                
                # Trigger async classification when form is completed if LLM_CLASSIFICATION is True
                if self.LLM_CLASSIFICATION:
                    classification_slots = await self._trigger_async_classification(tracker, dispatcher)
                    slots_to_set.update(classification_slots)
                self.logger.debug(f"Slots to set: {slots_to_set}")

                # create the grievance in the database (this is necessary for the classification results to be stored)
                grievance_data = {
                    'grievance_id': tracker.get_slot('grievance_id'),
                    'complainant_id': tracker.get_slot('complainant_id'),
                    'grievance_description': tracker.get_slot('grievance_description'),
                    'complainant_province': tracker.get_slot('complainant_province'),
                    'complainant_district': tracker.get_slot('complainant_district'),
                    'complainant_office': tracker.get_slot('complainant_office'),
                    'source': 'bot'
                }
                await self.db_manager.create_complainant_and_grievance(grievance_data) #create the complainant and grievance in the database in one go and let the user move to the next without waiting for the storage to complete
                return slots_to_set
            
            # Handle valid grievance text
            if slot_value and not slot_value.startswith('/'):
                #update the grievance description with the new detail
                updated_temp = self._update_grievance_text(tracker.get_slot("grievance_description"), slot_value)
                # Check for sensitive content using keyword detection
                sensitive_content_result = self.detect_sensitive_content(dispatcher, slot_value)
                if sensitive_content_result:
                    sensitive_content_result["grievance_description"] = updated_temp
                    sensitive_content_result["grievance_new_detail"] = "completed"
                    return sensitive_content_result
                
                #handle the case where sensitive content is not detected
                return {
                    "grievance_new_detail": None,
                    "grievance_description": updated_temp,
                    "grievance_description_status": "show_options",
                    "sensitive_issues_detected": False
                }
            return {}
        except Exception as e:
            self.logger.error(f"Error in validate_grievance_new_detail: {e}")
            raise Exception(f"Error in validate_grievance_new_detail: {e}")


    
class ActionAskGrievanceNewDetail(BaseAction):
    def name(self) -> Text:
        return "action_ask_grievance_new_detail"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        slot_grievance_description_status = tracker.get_slot("grievance_description_status")
        
        if not slot_grievance_description_status:
            utterance = self.get_utterance(1)
            dispatcher.utter_message(text=utterance)

        if slot_grievance_description_status == "restart":
            utterance = self.get_utterance(2)
            dispatcher.utter_message(text=utterance)

        if slot_grievance_description_status == "add_more_details":
            utterance = self.get_utterance(3)
            dispatcher.utter_message(text=utterance)

        if slot_grievance_description_status == "show_options":
            slot_grievance_description = tracker.get_slot("grievance_description")
            utterance = self.get_utterance(4).format(grievance_description=slot_grievance_description)
            buttons = self.get_buttons(4)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            
        return []



        
    
                
            

        



