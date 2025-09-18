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
from rasa_chatbot.actions.utils.base_classes import BaseFormValidationAction, BaseAction, SKIP_VALUE
from rasa_chatbot.actions.action_submit_grievance import BaseActionSubmit

from backend.services.messaging import Messaging
from rasa_chatbot.actions.utils.utterance_mapping_rasa import BUTTON_SKIP, BUTTON_AFFIRM, BUTTON_DENY
from rapidfuzz import process
from datetime import datetime, timedelta
from backend.config.constants import (
    GRIEVANCE_STATUS, GRIEVANCE_CLASSIFICATION_STATUS, EMAIL_TEMPLATES, DEFAULT_VALUES,
    ADMIN_EMAILS, CLASSIFICATION_DATA, LIST_OF_CATEGORIES,
    TASK_STATUS,
)



LLM_GENERATED = GRIEVANCE_CLASSIFICATION_STATUS["LLM_generated"]
LLM_FAILED = GRIEVANCE_CLASSIFICATION_STATUS["LLM_failed"]
LLM_ERROR = GRIEVANCE_CLASSIFICATION_STATUS["LLM_error"]
complainant_CONFIRMED = GRIEVANCE_CLASSIFICATION_STATUS["complainant_confirmed"]
OFFICER_CONFIRMED = GRIEVANCE_CLASSIFICATION_STATUS["officer_confirmed"]
SUCCESS = TASK_STATUS["SUCCESS"]
SKIP_VALUE = DEFAULT_VALUES["SKIP_VALUE"]
FAILED = TASK_STATUS["FAILED"]

############################ STEP 1 - VALIDATE GRIEVANCE SUMMARY AND CATEGORIES ############################


class ActionRetrieveClassificationResults(BaseActionSubmit):
    def name(self) -> Text:
        return "action_retrieve_classification_results"

    def detect_sensitive_categories(self, grievance_categories: List[str]) -> List[str]:
        """
        Detects sensitive categories in the grievance list of categories
        """
        try:
            if grievance_categories:
                return [category  for category in grievance_categories if "gender" in category.lower()]
            else:
                return []
        except Exception as e:
            self.logger.error(f"Error detecting sensitive categories: input_categories: {grievance_categories}, error: {e}")
            return []
    
        

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Handle classification results from the database
        - query the database for the classification results
        - set the slots with the classification results
        - send a message to the user about the classification results
        """
        try:
            grievance_data = self.db_manager.get_grievance_by_id(tracker.get_slot("grievance_id"))
            self.logger.debug(f"Grievance data: {grievance_data}")
            grievance_summary = grievance_data.get('grievance_summary', '')
            grievance_categories = grievance_data.get('grievance_categories', [])
            grievance_categories_alternative = grievance_data.get('grievance_categories_alternative', [])
            follow_up_question = grievance_data.get('follow_up_question', '')
            sensitive_categories = self.detect_sensitive_categories(grievance_categories)
            self.logger.debug(f"Sensitive categories: {sensitive_categories}, grievance_categories: {grievance_categories}, grievance_summary: {grievance_summary}, grievance_categories_alternative: {grievance_categories_alternative}")
                
            if sensitive_categories:
                grievance_categories_local = self._get_categories_in_local_language(grievance_categories)
                self.logger.debug(f"Sensitive categories detected: {sensitive_categories}")
                return [SlotSet('sensitive_issues_detected', True),
                        SlotSet('sensitive_issues_categories', sensitive_categories),
                        SlotSet('grievance_classification_status', self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']),
                        SlotSet('grievance_summary_temp', grievance_summary),
                        SlotSet('grievance_categories', grievance_categories), 
                        SlotSet('grievance_categories_local', grievance_categories_local),
                        SlotSet('follow_up_question', follow_up_question),
                        SlotSet('grievance_summary_status', self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']), 
                        SlotSet('grievance_categories_status', self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']),
                        SlotSet('grievance_complainant_review', False)]


            elif grievance_summary or grievance_categories:
                # we are setting the slots to the values of the grievance summary and categories so they can be validated in the next step
                utterance = self.get_utterance(1)
                buttons = self.get_buttons(1)
                dispatcher.utter_message(text=utterance.format(category_text=', '.join(grievance_categories), summary=grievance_summary))
                grievance_categories_local = self._get_categories_in_local_language(grievance_categories)
                grievance_categories_alternative_local = self._get_categories_in_local_language(grievance_categories_alternative)
                return [SlotSet('grievance_classification_status', self.  GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']),
                        SlotSet('grievance_summary_temp', grievance_summary),
                        SlotSet('grievance_categories', grievance_categories),
                        SlotSet('grievance_categories_alternative', grievance_categories_alternative),
                        SlotSet('grievance_categories_local', grievance_categories_local),
                        SlotSet('grievance_categories_alternative_local', grievance_categories_alternative_local),
                        SlotSet('follow_up_question', follow_up_question),
                        SlotSet('grievance_complainant_review', True)
                        ]
            else :
                self.logger.warning("Classification results not recorded in the database")
                utterance = self.get_utterance(2)
                dispatcher.utter_message(text=utterance)
                return [SlotSet('grievance_summary_temp', 'N/A'),
                        SlotSet('grievance_summary', 'N/A'), 
                        SlotSet('grievance_categories', 'N/A'), 
                        SlotSet('grievance_categories_alternative', 'N/A'),
                        SlotSet('grievance_categories_local', 'N/A'),
                        SlotSet('grievance_categories_alternative_local', 'N/A'),
                        SlotSet('follow_up_question', 'N/A'),
                        SlotSet('grievance_complainant_review', False),
                        SlotSet('grievance_classification_status', self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_failed']),
                        SlotSet('grievance_complainant_review', False)
                        ]
                
        except Exception as e:
            self.logger.error(f"Error handling classification results: {str(e)}")
            return []

class ValidateFormGrievanceComplainantReview(BaseFormValidationAction):
    # Class variable to track messagBe display
    BaseFormValidationAction.message_display_list_cat = True
    
    def __init__(self):
        """Initialize form action"""
        super().__init__()
        self.LLM_GENERATED = self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']
        self.CM_COMFIRMED = self.GRIEVANCE_CLASSIFICATION_STATUS['complainant_confirmed']
        self.REVIEWING = self.GRIEVANCE_CLASSIFICATION_STATUS['REVIEWING']
        
    def name(self) -> Text:
        return "validate_form_grievance_complainant_review"
    
    
    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        grievance_categories = tracker.get_slot("grievance_categories")
        grievance_summary = tracker.get_slot("grievance_summary")
        grievance_categories_status = tracker.get_slot("grievance_categories_status")
        grievance_summary_status = tracker.get_slot("grievance_summary_status")
        grievance_cat_modify = tracker.get_slot("grievance_cat_modify")
        grievance_summary_temp = tracker.get_slot("grievance_summary_temp")
        self.logger.debug(f"form_grievance_complainant_review - Values of slots: grievance_categories: {grievance_categories}, grievance_summary: {grievance_summary}, grievance_categories_status: {grievance_categories_status}, grievance_summary_status: {grievance_summary_status}, grievance_cat_modify: {grievance_cat_modify}, grievance_summary_temp: {grievance_summary_temp}")


        #display the values of required slots from the tracker
        #case where sensitive issues are detected, form is skipped
        if tracker.get_slot("sensitive_issues_detected"):
            self.logger.debug(f"form_grievance_complainant_review - sensitive issues detected - form skipped")
            return [
            ]
        #case where grievance classification is failed, form is skipped
        elif tracker.get_slot("grievance_classification_status") == self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_failed']:
            self.logger.debug(f"form_grievance_complainant_review - grievance classification failed - form skipped")
            return [
            ]

        #case where the complainant does not want to review the grievance classification (after validation)
        elif (tracker.get_slot("grievance_classification_consent") == False and 
              tracker.get_slot("grievance_summary_status") is not None):
            self.logger.debug(f"form_grievance_complainant_review - complainant does not want to review the grievance classification - form completed")
            return []

        #case where form is completed by the complainant
        elif tracker.get_slot("grievance_categories_status") in [ self.CM_COMFIRMED, self.SKIP_VALUE] and tracker.get_slot("grievance_summary_status") in [self.CM_COMFIRMED, self.SKIP_VALUE]:
            self.logger.debug(f"form_grievance_complainant_review - form is completed")
            return []
        #case where form is not completed by the complainant
        else:
            slots_to_validate = [
                "grievance_classification_consent",
                "grievance_categories_status",
                "grievance_cat_modify", 
                "grievance_summary_status",
                "grievance_summary_temp"
            ]
            self.logger.debug(f"form_grievance_complainant_review - Required slots: {slots_to_validate}")
            return slots_to_validate
    
    

    def _detect_sensitive_issues_category(self, tracker: Tracker) -> bool:
        """
        Detects sensitive issues in the grievance list of categories
        """
        
        categories = tracker.get_slot("grievance_categories")
        sensitive_issues_detected = any("sensitive" in category.lower() for category in categories)
        #check if the string "sensitive" is in any of the categories in the list_of_cat
        return sensitive_issues_detected
    
    def _report_sensitive_issues_category(self, 
                                 dispatcher: CollectingDispatcher, 
                                 tracker: Tracker):
            """
            Helper function to report gender issues and return the specific updated slots
            the changes in requested_slot are not handled in that specific function
            the utterance and buttons are handled in the action_ask_form_grievance_complainant_review_gender_follow_up
            """
            # update all the regular slots to validate the form and add the sensitive_issues_detected slot
            return {"grievance_classification_status": False,
                "grievance_categories_status": self.LLM_GENERATED,
                    "grievance_cat_modify": self.SKIP_VALUE,
                    "grievance_categories": tracker.get_slot("grievance_categories"),
                    "grievance_summary": tracker.get_slot("grievance_summary_temp"),
                    "grievance_summary_confirmed": self.SKIP_VALUE,
                    "sensitive_issues_detected": True}

    async def extract_grievance_classification_consent(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_and_category_slot_extraction(
            "grievance_classification_consent",
            tracker,
            dispatcher,
            domain
        )

    async def validate_grievance_classification_consent(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        if slot_value == True:
            self.logger.debug(f"validate_grievance_classification_consent: User wants to review - returning consent only")
            return {"grievance_classification_consent": slot_value}
        elif slot_value == False:
            grievance_summary_temp = tracker.get_slot("grievance_summary_temp")
            self.logger.debug(f"validate_grievance_classification_consent: User doesn't want to review")
            self.logger.debug(f"validate_grievance_classification_consent: grievance_summary_temp = {grievance_summary_temp}")
            
            result = {
                "grievance_classification_consent": slot_value,
                "grievance_classification_status": self.LLM_GENERATED,
                "grievance_summary_status": self.LLM_GENERATED,
                "grievance_summary": grievance_summary_temp
            }
            self.logger.debug(f"validate_grievance_classification_consent: Returning slots: {result}")
            return result


    async def extract_grievance_categorization_update(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "grievance_categorization_update",
            tracker,
            dispatcher,
            domain
        )
    async def validate_grievance_categorization_update(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> Dict[Text, Any]:
        if slot_value == True:
            return {"grievance_categorization_update": True}
        elif slot_value == False:
            return {"grievance_categorization_update": False} 


    async def extract_grievance_categories_status(self, 
                                                   dispatcher: CollectingDispatcher,
                                                   tracker: Tracker,
                                                   domain: Dict[Text, Any]
                                                   ) -> Dict[Text, Any]:
        return await self._handle_boolean_and_category_slot_extraction(
            "grievance_categories_status",
            tracker,
            dispatcher,
            domain
        )

    
    async def validate_grievance_categories_status(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> Dict[Text, Any]:
        self.logger.debug(f"validate_grievance_categories_status: {slot_value}")
        try:      
            if self.SKIP_VALUE in slot_value:
                return {"grievance_categories_status": self.LLM_GENERATED,
                        "grievance_cat_modify": self.SKIP_VALUE}
                
            
            # Fallback to original logic if no async results
            if 'slot_confirmed' in slot_value:
                if self._detect_sensitive_issues_category(tracker):
                    return self._report_sensitive_issues_category(dispatcher, tracker)
                else:
                    return {"grievance_categories_status": slot_value,
                            "grievance_classification_status": self.CM_COMFIRMED,
                            "grievance_cat_modify": self.CM_COMFIRMED}
                
            elif 'slot_added' in slot_value:
                #return the slot_value as selected by the user and move to category_modify slot
                return {"grievance_categories_status": slot_value,
                        "grievance_classification_status": self.REVIEWING,
                        "grievance_cat_modify": None}

            elif 'slot_deleted' in slot_value:
                #return the slot_value as selected by the user and move to category_modify slot
                return {"grievance_categories_status": slot_value,
                        "grievance_classification_status": self.REVIEWING,
                        "grievance_cat_modify": None}

        except Exception as e:
            self.logger.error(f"Error in validate_grievance_categories_status: {e}")
            return {"grievance_categories_status": self.LLM_GENERATED}
    
    
    
    async def extract_grievance_cat_modify(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "grievance_cat_modify",
            tracker,
            dispatcher,
            domain
        )
    
    def get_category_to_modify(self, alternative_categories: List[str], input_text: str) -> str:
        """
        Extracts the category from the slot_value by matching it from the list of categories using rapidfuzz
        Returns None if no categories in slot_value
        
        """
        selected_category = None
        if ":" in input_text:
             #initialize the selected category
            temp_cat = input_text.split(":")[1].strip()
            for c in alternative_categories:
                if c in input_text:
                        selected_category = c
                if not selected_category:
                    #select the category c in the list_of_cat that is the closest match to the temp_cat using rapidfuzz
                    selected_category = process.extractOne(input_text, alternative_categories)
                    
        return selected_category
    
    async def validate_grievance_cat_modify(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> Dict[Text, Any]:
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
        
        if slot_value:

            grievance_categories = tracker.get_slot("grievance_categories_local")
            alternative_categories = tracker.get_slot("grievance_categories_alternative_local")
            self.logger.info(f"validate_grievance_cat_modify input: {slot_value}, grievance_categories: {grievance_categories}, alternative_categories: {alternative_categories}")
            #get the category to modify from the slot_value
            selected_category = self.get_category_to_modify(alternative_categories = alternative_categories + grievance_categories, input_text=slot_value) #we add the grievance_categories to the alternative_categories to get the complete list of categories that can be deleted
            #if no category is selected or the slot_value is SKIP_VALUE, return slot_confirmed as this means the user is happy with the current selection and the SKIP_VALUE for the grievance_cat_modify slot
            try:
                if not selected_category or slot_value == self.SKIP_VALUE:
                    message = self.get_utterance(1)
                    dispatcher.utter_message(text=message)
                    return {"grievance_categories_status": None,
                        "grievance_cat_modify": self.SKIP_VALUE,
                        }
        
                #case 2: delete the category
                if tracker.get_slot("grievance_categories_status") == "slot_deleted":
                    #delete the category
                    grievance_categories.remove(selected_category)
                    alternative_categories.append(selected_category)
                    
                #case 3: add the category
                if tracker.get_slot("grievance_categories_status") == "slot_added":
                    grievance_categories.append(selected_category)
                    alternative_categories.remove(selected_category)
            
                self.logger.debug(f"validate_grievance_cat_modify output: selected_category: {selected_category}, grievance_categories_local: {grievance_categories}, alternative_categories_local: {alternative_categories}")
                #reset the message_display_list_cat to True
                BaseFormValidationAction.message_display_list_cat = True
                
                #deal with the case where sensitive issues is part of list_of_cat
                if self._detect_sensitive_issues_category(tracker):
                    return self._report_sensitive_issues_category(dispatcher, tracker)
                #validate the slots
                return {
                    "grievance_categories_locaL": grievance_categories,
                    "grievance_categories_alternative_local": alternative_categories,
                    "grievance_categories_status": None,
                    "grievance_cat_modify": "Done",
                }
            except Exception as e:
                self.logger.error(f"Error in validate_grievance_cat_modify: {e}")
                return {"grievance_categories_status": self.LLM_GENERATED,
                        "grievance_cat_modify": self.SKIP_VALUE}
        else:
            return {}
        
        
        
    

    
    async def extract_grievance_summary_status(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
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
                                                   ) -> Dict[Text, Any]:
        try:
            if slot_value == self.SKIP_VALUE:
                return {"grievance_summary_status": self.LLM_GENERATED,
                    "grievance_summary_temp": self.SKIP_VALUE} #this will validate the slot and the form
            
            
            if slot_value == "/slot_confirmed":
                return {"grievance_summary_status": self.CM_COMFIRMED,
                        "grievance_summary_temp": self.SKIP_VALUE} #this will validate the slot and the form
            
            if slot_value == "/slot_edited":
                return {"grievance_summary_status": self.REVIEWING,
                        "grievance_summary_temp": None
                        }
        except Exception as e:
            self.logger.error(f"Error in validate_grievance_summary_status: {e}")
            return {"grievance_summary_status": self.LLM_GENERATED,
                    "grievance_summary_temp": self.SKIP_VALUE}

    
    async def extract_grievance_summary_temp(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
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
                                                   ) -> Dict[Text, Any]:
        slot_value = slot_value.strip('/')
        try:
            if slot_value == SKIP_VALUE:
                self.logger.info("SKIP_VALUE in validate_grievance_summary_temp")
                return {"grievance_summary_status": self.LLM_GENERATED,
                    "grievance_summary_temp": self.SKIP_VALUE}
        
            if slot_value:
                self.logger.info(f"validate_grievance_summary_temp: {slot_value}")
                return {"grievance_summary_status": None,
                        "grievance_summary_temp": slot_value,
                        "grievance_summary": slot_value}
                
            return {}
        except Exception as e:
            self.logger.error(f"Error in validate_grievance_summary_temp: {e}")
            return {}

############ ASK ACTIONS FOR THE FORM ############################


class ActionAskFormGrievanceComplainantReviewGrievanceClassificationConsent(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_grievance_complainant_review_grievance_classification_consent"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        utterance = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []

class ActionAskFormGrievanceComplainantReviewGrievanceCategoriesStatus(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_grievance_complainant_review_grievance_categories_status"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        self.logger.debug(f"action_ask_form_grievance_complainant_review_grievance_categories_status - grievance_classification_status: {tracker.get_slot('grievance_classification_status')}")
        buttons = None
        utterance = None
        grievance_categories = tracker.get_slot("grievance_categories_local")
        category_text = "|".join([v for v in grievance_categories]) if grievance_categories else "[]"
        
        if tracker.get_slot("grievance_classification_status") == self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']:
            # Classification is complete, show results
            if grievance_categories:
                utterance = self.get_utterance(1).format(category_text=category_text)
                buttons = self.get_buttons(1)
            else:
                utterance = self.get_utterance(2)
                buttons = self.get_buttons(2)


        elif tracker.get_slot("grievance_classification_status") == self.GRIEVANCE_CLASSIFICATION_STATUS['REVIEWING']:
            if grievance_categories:
                utterance = self.get_utterance(3).format(category_text=category_text)
                buttons = self.get_buttons(1)
            else:
                utterance = self.get_utterance(4)
                buttons = self.get_buttons(2)
        if buttons and utterance:
            dispatcher.utter_message(text=utterance, buttons=buttons)
        self.logger.debug(f"action_ask_form_grievance_complainant_review_grievance_categories_status -grievance_categories : {grievance_categories if grievance_categories else 'None'} - utterance - retrieved: {utterance if utterance else 'None'} - buttons - retrieved: {buttons if buttons else 'None'}")
        return []


class ActionAskFormGrievanceComplainantReviewGrievanceCatModify(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_grievance_complainant_review_grievance_cat_modify"
    
    async def execute_action(
        self, 
        dispatcher: CollectingDispatcher, 
        tracker: Tracker,
        domain: DomainDict
        ) -> List[Dict[Text, Any]]:
        grievance_categories_status = tracker.get_slot("grievance_categories_status")
        grievance_categories = tracker.get_slot("grievance_categories")
        self.logger.debug(f"action_ask_form_grievance_complainant_review_grievance_cat_modify - grievance_categories_status: {grievance_categories_status} - grievance_categories: {grievance_categories}")
        
        if grievance_categories_status == 'slot_deleted':
            if not grievance_categories:
                utterance = self.get_utterance(1)
                dispatcher.utter_message(text=utterance)
                return [SlotSet("grievance_categories_status", self.SKIP_VALUE)]
            else:
                buttons = [
                    {"title": cat, "payload": f'/delete_category{{"category_to_delete": "{cat}"}}'}
                    for cat in grievance_categories
                ]
                buttons.append({"title": "Skip", "payload": "/skip"})
                utterance = self.get_utterance(2)
                dispatcher.utter_message(text=utterance, buttons=buttons)
                
        if grievance_categories_status == "slot_added":
            alternative_categories = tracker.get_slot("grievance_categories_alternative")
            self.logger.debug(f"action_ask_form_grievance_complainant_review_grievance_cat_modify - alternative_categories: {alternative_categories}")
            buttons = [
                {"title": cat, "payload": f'/add_category{{"category": "{cat}"}}'} 
                for cat in alternative_categories
            ]
            utterance = self.get_utterance(3)
            buttons.append({"title": "Skip", "payload": "/skip"})
            dispatcher.utter_message(text=utterance, buttons=buttons)
        return []
    
    
class ActionAskFormGrievanceComplainantReviewGrievanceSummaryStatus(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_grievance_complainant_review_grievance_summary_status"
    
    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict
        ) -> List[Dict[Text, Any]]:
        current_summary = tracker.get_slot("grievance_summary_temp")
        if current_summary:
            utterance = self.get_utterance(1).format(current_summary=current_summary)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        else:
            utterance = self.get_utterance(2)
            buttons = self.get_buttons(2)
            dispatcher.utter_message(text=utterance, buttons=buttons)

class ActionAskFormGrievanceComplainantReviewGrievanceSummaryTemp(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_grievance_complainant_review_grievance_summary_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        if tracker.get_slot("grievance_summary_confirmed") == "slot_edited":
            utterance = self.get_utterance(1)
            dispatcher.utter_message(text=utterance)
        return []

class ActionAskFormGrievanceComplainantReviewGenderFollowUp(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_grievance_complainant_review_gender_follow_up"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        for i in range(1, 4):
            utterance = self.get_utterance(i)
            dispatcher.utter_message(text=utterance)
        utterance = self.get_utterance(4)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)


############# ACTION UPDATE CATEGORIZATION ############################

class ActionUpdateGrievanceCategorization(BaseAction):
    def name(self) -> Text:
        return "action_update_grievance_categorization"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
       
        grievance_categories_status = tracker.get_slot("grievance_categories_status")
        grievance_summary_status = tracker.get_slot("grievance_summary_status")
        #deal with the case where no changes are made
        if grievance_categories_status == self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated'] and grievance_summary_status == self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']:
            self.logger.info("No changes made to the grievance categorization")
            return []
        else:
            grievance_id = tracker.get_slot("grievance_id") 
            grievance_categories = tracker.get_slot("grievance_categories")
            grievance_summary = tracker.get_slot("grievance_summary")

            grievance_cat_modify = tracker.get_slot("grievance_cat_modify")
            grievance_summary_temp = tracker.get_slot("grievance_summary_temp")
            
            data_to_update = {
                "grievance_categories": grievance_categories,
                "grievance_summary": grievance_summary,
                "grievance_categories_status": grievance_categories_status,
                "grievance_summary_status": grievance_summary_status,
                "grievance_cat_modify": grievance_cat_modify,
                "grievance_summary_temp": grievance_summary_temp
            }
            self.db_manager.update_grievance(grievance_id = grievance_id, 
            data = data_to_update)
            self.logger.info(f"Grievance categorization updated in db: {grievance_id}")
        return []