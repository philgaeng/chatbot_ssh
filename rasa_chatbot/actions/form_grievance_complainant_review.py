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

    def detect_sensitive_categories(self, grievance_categories: List[str]) -> bool:
        """
        Detects sensitive categories in the grievance list of categories
        """
        sensitive_categories = [category  for category in grievance_categories if "gender" in category.lower()]
        
        return sensitive_categories
        

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
            sensitive_categories = self.detect_sensitive_categories(grievance_categories)
            self.logger.debug(f"Sensitive categories: {sensitive_categories}, grievance_categories: {grievance_categories}, grievance_summary: {grievance_summary}")

            if sensitive_categories:
                return [SlotSet('sensitive_issues_detected', True),
                        SlotSet('sensitive_issues_categories', sensitive_categories),
                        SlotSet('grievance_summary_temp', grievance_summary),
                        SlotSet('grievance_categories', grievance_categories), 
                        SlotSet('grievance_summary_status', self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']), 
                        SlotSet('grievance_categories_status', self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']),
                        SlotSet('grievance_complainant_review', False)]


            elif grievance_summary or grievance_categories:
                utterance = self.get_utterance(1)
                buttons = self.get_buttons(1)
                dispatcher.utter_message(text=utterance.format(category_text=', '.join(grievance_categories), summary=grievance_summary))
                return [SlotSet('grievance_summary_temp', grievance_summary),
                        SlotSet('grievance_categories', grievance_categories), 
                        SlotSet('grievance_summary_status', self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']), 
                        SlotSet('grievance_categories_status', self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']),
                        SlotSet('grievance_complainant_review', True)
                        ]
            else :
                self.logger.warning("Classification results not recorded in the database")
                utterance = self.get_utterance(2)
                dispatcher.utter_message(text=utterance)
                return [SlotSet('grievance_summary_temp', 'N/A'),
                        SlotSet('grievance_summary', 'N/A'), 
                        SlotSet('grievance_categories', 'N/A'), 
                        SlotSet('grievance_summary_status', self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']), 
                        SlotSet('grievance_categories_status', self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']),
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
        self.logger.debug(f"Grievance summary form - Values of slots: grievance_categories: {grievance_categories}, grievance_summary: {grievance_summary}, grievance_categories_status: {grievance_categories_status}, grievance_summary_status: {grievance_summary_status}, grievance_cat_modify: {grievance_cat_modify}, grievance_summary_temp: {grievance_summary_temp}")
        
        if tracker.get_slot("sensitive_issues_detected"):
            return [
            ]
        if tracker.get_slot("grievance_categories_status") in [ self.CM_COMFIRMED, self.SKIP_VALUE] and tracker.get_slot("grievance_summary_status") in [self.CM_COMFIRMED, self.SKIP_VALUE]:
            return []
        else:
            self.logger.debug(f"Grievance summary form - Required slots: {domain_slots}")
            return [

                "grievance_categories_status",
                "grievance_cat_modify", 
                "grievance_summary_status",
                "grievance_summary_temp"
            ]
    
    

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
            return {"grievance_categories_status": self.LLM_GENERATED,
                    "grievance_cat_modify": self.SKIP_VALUE,
                    "grievance_categories": tracker.get_slot("grievance_categories"),
                    "grievance_summary": tracker.get_slot("grievance_summary_temp"),
                    "grievance_summary_confirmed": self.SKIP_VALUE,
                    "sensitive_issues_detected": True}

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
        return await self._handle_boolean_slot_extraction(
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
        slot_value = slot_value.strip('/')
        try:      
            if slot_value == self.SKIP_VALUE:
                return {"grievance_categories_status": self.LLM_GENERATED,
                        "grievance_cat_modify": self.SKIP_VALUE}
                
            
            # Fallback to original logic if no async results
            if slot_value == 'slot_confirmed':
                if self._detect_sensitive_issues_category(tracker):
                    return self._report_sensitive_issues_category(dispatcher, tracker)
                else:
                    return {"grievance_categories_status": self.CM_COMFIRMED,
                            "grievance_cat_modify": self.SKIP_VALUE}
                
            elif slot_value == 'add_category':
                #return the slot_value as selected by the user and move to category_modify slot
                return {"grievance_categories_status": self.REVIEWING,
                        "grievance_cat_modify": None}

            elif slot_value == 'delete_category':
                #return the slot_value as selected by the user and move to category_modify slot
                return {"grievance_categories_status": self.REVIEWING,
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
         
        slot_value = slot_value.strip('/')
        self.logger.info(f"validate_grievance_cat_modify: {slot_value}")
        list_of_cat = tracker.get_slot("grievance_categories")
        
        #get the category to modify from the slot_value
        selected_category = self.get_category_to_modify(slot_value)
        
        #if no category is selected or the slot_value is SKIP_VALUE, return the LLM_GENERATED status and the SKIP_VALUE for the grievance_cat_modify slot
        try:
            if not selected_category or slot_value == self.SKIP_VALUE:
                dispatcher.utter_message(text="No category selected. skipping this step.")
                return {"grievance_categories_status": self.LLM_GENERATED,
                    "grievance_cat_modify": self.SKIP_VALUE}
      
            #case 2: delete the category
            if tracker.get_slot("grievance_categories_status") == "slot_deleted":
                #delete the category
                list_of_cat.remove(selected_category)
                
            #case 3: add the category
            if tracker.get_slot("grievance_categories_status") == "slot_added":
                list_of_cat.append(selected_category)
        
        
            #reset the message_display_list_cat to True
            BaseFormValidationAction.message_display_list_cat = True
            
            #deal with the case where sensitive issues is part of list_of_cat
            if self._detect_sensitive_issues_category(tracker):
                return self._report_sensitive_issues_category(dispatcher, tracker)
            #validate the slots
            return {
                "grievance_categories": list_of_cat,
                "grievance_categories_status": None,
                "grievance_cat_modify": "Done",
            }
        except Exception as e:
            self.logger.error(f"Error in validate_grievance_cat_modify: {e}")
            return {"grievance_categories_status": self.LLM_GENERATED,
                    "grievance_cat_modify": self.SKIP_VALUE}
        
        
        
    

    
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
        slot_value = slot_value.strip('/')
        try:
            if slot_value == self.SKIP_VALUE:
                return {"grievance_summary_status": self.LLM_GENERATED,
                    "grievance_summary_temp": self.SKIP_VALUE} #this will validate the slot and the form
            
            
            if slot_value == "slot_confirmed":
                return {"grievance_summary_status": self.CM_COMFIRMED,
                        "grievance_summary_temp": self.SKIP_VALUE} #this will validate the slot and the form
            
            if slot_value == "slot_edited":
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

# class ActionAskFormGrievanceComplainantReview(BaseAction):
#     def name(self) -> Text:
#         return "action_ask_form_grievance_complainant_review"
    
#     async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
#         categories_text = "|".join([v for v in tracker.get_slot("grievance_categories")])
#         utterance = self.get_utterance(1).format(grievance_categories=categories_text, grievance_summary=tracker.get_slot("grievance_summary"))
#         buttons = self.get_buttons(1)
#         dispatcher.utter_message(text=utterance, buttons=buttons)
#         return []



class ActionAskFormGrievanceComplainantReviewGrievanceCategoriesStatus(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_grievance_complainant_review_grievance_categories_status"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        if tracker.get_slot("classification_status") == self.GRIEVANCE_CLASSIFICATION_STATUS['LLM_generated']:
            # Classification is complete, show results
            grievance_categories = tracker.get_slot("grievance_categories")
            category_text = "|".join([v for v in grievance_categories]) if grievance_categories else "[]"
            if len(grievance_categories) == 0:
                utterance = self.get_utterance(1)
                buttons = self.get_buttons(1)
            else:
                utterance = self.get_utterance(2).format(category_text=category_text)

        elif tracker.get_slot("classification_status") == self.GRIEVANCE_CLASSIFICATION_STATUS['REVIEWING']:
            grievance_categories = tracker.get_slot("grievance_categories")
            if len(grievance_categories) > 0:
                category_text = "|".join([v for v in grievance_categories])
                utterance = self.get_utterance(3).format(category_text=category_text)
                buttons = self.get_buttons(3)
            else:
                utterance = self.get_utterance(4)
                buttons = self.get_buttons(4)
            dispatcher.utter_message(text=utterance, buttons=buttons)

        return []


class ActionAskFormGrievanceComplainantReviewGrievanceCatModify(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_grievance_complainant_review_grievance_cat_modify"
    
    async def execute_action(
        self, 
        dispatcher: CollectingDispatcher, 
        tracker: Tracker,
        domain: DomainDict
        ) -> Dict[Text, Any]:
        ask_cat_modify_flag = tracker.get_slot("grievance_categories_status")
        list_of_cat = tracker.get_slot("grievance_categories")
        
        if ask_cat_modify_flag == 'slot_deleted':
            if not list_of_cat:
                utterance = self.get_utterance(1)
                dispatcher.utter_message(text=utterance)
                return {"grievance_categories_status": self.SKIP_VALUE}
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
            utterance = self.get_utterance(1)
            utterance = utterance.format(current_summary=current_summary)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        else:
            utterance = self.get_utterance(1)
            buttons = BUTTON_SKIP
            dispatcher.utter_message(text=utterance)

class ActionAskFormGrievanceComplainantReviewGrievanceSummaryTemp(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_grievance_complainant_review_grievance_summary_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        if tracker.get_slot("grievance_summary_confirmed") == "slot_edited":
            utterance = self.get_utterance(2)
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