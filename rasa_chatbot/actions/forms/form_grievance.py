import re
import json
from random import randint
from typing import Any, Text, Dict, List, Tuple, Union, Optional
from datetime import datetime, timedelta
import traceback
import threading
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Restarted, FollowupAction, ActiveLoop
from rasa_sdk.types import DomainDict
from rasa_chatbot.actions.base_classes.base_classes  import BaseFormValidationAction, BaseAction
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
                SlotSet("story_main", "new_grievance"),
                SlotSet("grievance_sensitive_issue", False)]


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
            # Lazy import: Celery/Redis not required in REST-only envs
            try:
                from backend.task_queue.registered_tasks import classify_and_summarize_grievance_task
            except ImportError as ie:
                self.logger.warning(
                    f"Celery not available (ImportError: {ie}); skipping async classification for grievance {grievance_id}"
                )
                return {
                    "grievance_classification_status": self.SKIP_VALUE,
                    "grievance_summary": "",
                    "grievance_categories": [],
                    "grievance_summary_status": self.SKIP_VALUE,
                    "grievance_categories_status": self.SKIP_VALUE,
                }

            # Prepare input data for Celery task
            # Use tracker.sender_id for REST flow when flask_session_id slot is not set
            session_id = tracker.get_slot("flask_session_id") or tracker.sender_id
            input_data = {
                'grievance_id': grievance_id,
                'complainant_id': tracker.get_slot("complainant_id"),
                'language_code': self.language_code,
                'complainant_province': tracker.get_slot("complainant_province") or self.province,
                'complainant_district': tracker.get_slot("complainant_district") or self.district,
                'flask_session_id': session_id,
                'session_id': session_id,
                'values': {
                    'grievance_description': grievance_description
                }
            }

            # Launch Celery task in a thread so we never block the request (e.g. if Redis is slow/down)
            def _fire():
                try:
                    task_result = classify_and_summarize_grievance_task.delay(input_data)
                    self.logger.info(f"Async classification triggered for grievance {grievance_id} with task ID: {task_result.id}")
                except Exception as e:
                    self.logger.warning(f"Could not queue classification task for {grievance_id}: {e}")

            t = threading.Thread(target=_fire, daemon=True)
            t.start()

            # Return immediately so the flow continues to contact form
            return {}

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

    def _trigger_detect_sensitive_content_task(
        self,
        text: str,
        language_code: str,
        grievance_id: Optional[str] = None,
        session_id: Optional[str] = None,
        complainant_id: Optional[str] = None,
    ) -> None:
        """Fire detect_sensitive_content_task in a background thread (same pattern as async classification). Result is written to DB so Submit can read it."""
        self.logger.info(
            "Firing detect_sensitive_content_task in background (grievance_id=%s, session_id=%s)",
            grievance_id,
            session_id,
        )
        def _fire() -> None:
            try:
                from backend.task_queue.registered_tasks import detect_sensitive_content_task
                detect_sensitive_content_task.delay(
                    text=text,
                    language_code=language_code,
                    grievance_id=grievance_id,
                    session_id=session_id,
                    complainant_id=complainant_id,
                )
            except Exception as e:
                self.logger.warning(f"Could not queue detect_sensitive_content task: {e}")

        t = threading.Thread(target=_fire, daemon=True)
        t.start()

    async def _get_sensitive_issue_slots_on_submit(
        self,
        full_description: str,
        session_id: Optional[str],
        grievance_id: Optional[str],
        dispatcher: CollectingDispatcher,
    ) -> Dict[Text, Any]:
        """On Submit details: prefer DB flag (grievance.grievance_sensitive_issue) set by Celery task.
        To reduce race conditions, briefly poll the DB before falling back to keyword detection.
        """
        flag_from_db = None
        if grievance_id:
            try:
                # Short polling window so the async detect_sensitive_content_task has a chance to write first.
                # Total wait is bounded (e.g. 3 * 0.3s = 0.9s).
                import asyncio  # local import to avoid changing module imports
                self.logger.debug(
                    "Sensitive submit: start DB polling | grievance_id=%s, session_id=%s",
                    grievance_id,
                    session_id,
                )
                for attempt in range(3):
                    grievance = self.db_manager.get_grievance_by_id(grievance_id)
                    if grievance is not None and "grievance_sensitive_issue" in grievance:
                        flag_from_db = grievance.get("grievance_sensitive_issue")
                        self.logger.debug(
                            "Sensitive submit: poll %s | grievance_id=%s, grievance_sensitive_issue=%s",
                            attempt,
                            grievance_id,
                            flag_from_db,
                        )
                        if flag_from_db:
                            return {
                                "grievance_sensitive_issue": True,
                                "sensitive_issues_category": "sensitive_content",
                                "sensitive_issues_level": grievance.get("sensitive_issues_level", "low"),
                                "sensitive_issues_message": grievance.get("sensitive_issues_message", ""),
                                "sensitive_issues_confidence": grievance.get("sensitive_issues_confidence"),
                            }
                    # No flag yet: give the background task a short chance to finish
                    await asyncio.sleep(0.3)
            except Exception as e:
                self.logger.warning(f"Could not read grievance from DB for sensitive slots: {e}")

        # If we saw an explicit False in DB after polling, respect it (no sensitive flow).
        if flag_from_db is False:
            self.logger.debug(
                "Sensitive submit: DB flag is False after polling | grievance_id=%s, session_id=%s",
                grievance_id,
                session_id,
            )
            return {"grievance_sensitive_issue": False}

        # Fallback: keyword detection (only sets grievance_sensitive_issue for sensitive_content) when
        # there is no DB flag at all (task not run or failed).
        self.logger.debug(
            "Sensitive submit: using keyword detection fallback | grievance_id=%s, session_id=%s",
            grievance_id,
            session_id,
        )
        return self.detect_sensitive_content(dispatcher, full_description) or {"grievance_sensitive_issue": False}

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        # Check if grievance_new_detail is "completed" - form completes
        # (sensitive-issues subflow is handled by form_sensitive_issues, not here)
        if tracker.get_slot("grievance_new_detail") == "completed":
            return []  # Form complete; state machine will transition to form_sensitive_issues if sensitive

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
            expected_values = ["restart", "add_more_details", "submit_details"]
            
            
            self.logger.debug(f"Validating grievance_new_detail: {slot_value}")
            # Handle restart the process
            if slot_value == "restart":
                return {"grievance_new_detail": None,
                        "grievance_description": None,
                        "grievance_description_status": "restart"}

            if slot_value == "add_more_details": #reset the slot and set the status to add_more_details to call the right utterance
                return {"grievance_new_detail": None,
                    "grievance_description_status": "add_more_details"}
            
            # Handle form completion
            if slot_value == "submit_details":
                self.logger.debug(f"Submitting details for grievance {tracker.get_slot('grievance_description')}")
                grievance_description = tracker.get_slot("grievance_description")
                session_id = tracker.get_slot("flask_session_id") or tracker.sender_id
                grievance_id = tracker.get_slot("grievance_id")
                sensitive_slots = await self._get_sensitive_issue_slots_on_submit(
                    grievance_description or "",
                    session_id=session_id,
                    grievance_id=grievance_id,
                    dispatcher=dispatcher,
                )
                slots_to_set = {
                    "grievance_new_detail": "completed",
                    "grievance_description": grievance_description,
                    **sensitive_slots,
                }

                # Create or update grievance in DB (same row if already created on first text for sensitive detection)
                grievance_data = {
                    'grievance_id': tracker.get_slot('grievance_id'),
                    'complainant_id': tracker.get_slot('complainant_id'),
                    'grievance_description': tracker.get_slot('grievance_description'),
                    'complainant_province': tracker.get_slot('complainant_province'),
                    'complainant_district': tracker.get_slot('complainant_district'),
                    'complainant_office': tracker.get_slot('complainant_office'),
                    'source': 'bot'
                }
                self.db_manager.create_or_update_complainant(grievance_data)
                self.db_manager.create_or_update_grievance(grievance_data)

                # Notify frontend that grievance now exists in DB so file upload can be enabled
                try:
                    dispatcher.utter_message(
                        json_message={
                            "data": {
                                "grievance_id": grievance_data.get("grievance_id"),
                                "event_type": "grievance_saved_in_db",
                            }
                        }
                    )
                except Exception as e:
                    self.logger.error(f"Failed to emit grievance_saved_in_db event: {e}")

                # Trigger async classification after create (runs in thread so request never blocks)
                if self.LLM_CLASSIFICATION:
                    classification_slots = await self._trigger_async_classification(tracker, dispatcher)
                    slots_to_set.update(classification_slots)
                self.logger.debug(f"Slots to set: {slots_to_set}")
                return slots_to_set
            
            # Handle valid grievance text (free text addition)
            if slot_value and slot_value not in expected_values:
                updated_temp = self._update_grievance_text(tracker.get_slot("grievance_description"), slot_value)
                # Ensure grievance exists in DB so Celery task can update grievance_sensitive_issue (same pattern as classification)
                grievance_id = tracker.get_slot("grievance_id")
                complainant_id = tracker.get_slot("complainant_id")
                if grievance_id and complainant_id:
                    try:
                        self.db_manager.create_or_update_complainant({
                            "complainant_id": complainant_id,
                            "complainant_province": tracker.get_slot("complainant_province"),
                            "complainant_district": tracker.get_slot("complainant_district"),
                        })
                        self.db_manager.create_or_update_grievance({
                            "grievance_id": grievance_id,
                            "complainant_id": complainant_id,
                            "grievance_description": updated_temp,
                            "source": "bot",
                        })
                    except Exception as e:
                        self.logger.warning(f"Could not ensure grievance in DB for sensitive task: {e}")
                session_id = tracker.get_slot("flask_session_id") or tracker.sender_id
                self._trigger_detect_sensitive_content_task(
                    text=updated_temp,
                    language_code=self.language_code,
                    grievance_id=grievance_id,
                    session_id=session_id,
                    complainant_id=complainant_id,
                )
                # Do not set grievance_sensitive_issue here; use stored result or keyword on Submit
                return {
                    "grievance_new_detail": None,
                    "grievance_description": updated_temp,
                    "grievance_description_status": "show_options",
                    "grievance_sensitive_issue": False,
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



        
    
                
            

        



