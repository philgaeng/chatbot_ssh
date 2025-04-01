import re
import logging
import os
import json
from .base_form import BaseFormValidationAction
from dotenv import load_dotenv
from openai import OpenAI
from typing import Any, Text, Dict, List, Tuple, Union
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Restarted, FollowupAction, ActiveLoop
from actions.helpers import load_classification_data, load_categories_from_lookup, get_next_grievance_number
from actions.constants import GRIEVANCE_STATUS, EMAIL_TEMPLATES, DIC_SMS_TEMPLATES, DEFAULT_VALUES, ADMIN_EMAILS
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from .db_manager import db_manager
from datetime import datetime, timedelta
from .messaging import SMSClient, EmailClient
from rapidfuzz import process
import traceback
from .utterance_mapping import get_utterance, get_buttons, BUTTON_SKIP, BUTTON_AFFIRM, BUTTON_DENY
from icecream import ic
import uuid

#define and load variables

load_dotenv('/home/ubuntu/nepal_chatbot/.env')
open_ai_key = os.getenv("OPENAI_API_KEY")

#load the categories
classification_data = load_classification_data()
LIST_OF_CATEGORIES = load_categories_from_lookup()
LIST_OF_CATEGORIES = [cat.strip("-").strip() for cat in LIST_OF_CATEGORIES]

#load the db
db = db_manager


logger = logging.getLogger(__name__)

try:
    if open_ai_key:
        print("OpenAI key is loaded")
    else:
        raise ValueError("OpenAI key is not set")
    
except Exception as e:
    print(f"Error loading OpenAI API key: {e}")
    
############################ STEP 0 - GENERIC ACTIONS ############################

class ActionSubmitGrievanceAsIs(Action):
    def name(self) -> Text:
        return "action_submit_grievance_as_is"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        grievance_details = tracker.get_slot("grievance_details")
        if grievance_details:
            dispatcher.utter_message(response="utter_grievance_submitted_as_is", grievance_details=grievance_details)
        else:
            dispatcher.utter_message(response="utter_grievance_submitted_no_details_as_is")
            
        # Trigger the submit grievance action
        return [FollowupAction("action_submit_grievance")]
    
class ActionStartGrievanceProcess(Action):
    def name(self) -> Text:
        return "action_start_grievance_process"

    async def run(self, dispatcher, tracker, domain):
        # reset the form parameters
        ValidateGrievanceSummaryForm.message_display_list_cat = True
        print("######################### RESET FORM PARAMETERS ##############")
        print("Value of message_display_list_cat: ", ValidateGrievanceSummaryForm.message_display_list_cat)
        print("---------------------------------------------")
        
        # Get language code from tracker
        language_code = tracker.get_slot("language_code") or "en"
        
        # Get utterance and buttons from mapping
        utterance = get_utterance("grievance_form", "action_start_grievance_process", 1, language_code)
        buttons = get_buttons("grievance_form", "action_start_grievance_process", 1, language_code)
        ic(utterance)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        
        # reset the slots used by the form grievance_details_form and grievance_summary_form and set verification_context to new_user
        return [SlotSet("grievance_new_detail", None),
                SlotSet("grievance_details", None),
                SlotSet("grievance_summary_temp", None),
                SlotSet("grievance_summary_confirmed", None),
                SlotSet("grievance_summary", None),
                SlotSet("grievance_categories", None),
                SlotSet("grievance_categories_confirmed", None),
                SlotSet("main_story", "new_grievance")]
        

class ActionSetGrievanceId(Action):
    def __init__(self):
        self.db = db_manager

    def name(self) -> Text:
        return "action_set_grievance_id"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """Generate and set a new grievance ID with temporary status"""
        ic('-------action_set_grievance_id-------')
        # Create the grievance with temporary status
        grievance_id = self.db.create_grievance()
        ic(f"Created temporary grievance with ID: {grievance_id}")
        return [SlotSet("grievance_id", grievance_id)]
                

    
class ActionCallOpenAI(Action):
    def name(self) -> Text:
        return "action_call_openai_classification"
    
    def parse_summary_and_category(self, response: str):
        """
        Parses OpenAI response directly into a structured dictionary.
        """
        print("############# parse_summary_and_category #######")

        try:
            result_dict = json.loads(response)  # Convert JSON string to dictionary
            return {
                "grievance_summary": result_dict.get("grievance_summary", ""),
                "list_categories": result_dict.get("list_categories", [])
            }
        except json.JSONDecodeError:
            print("⚠ Error: Response is not valid JSON")
            return {"grievance_summary": "", "list_categories": []}  # Return default empty values
        

    async def _call_openai_for_classification(self, grievance_details: str):
        """
        Calls OpenAI API to classify the grievance details into predefined categories.
        """
        predefined_categories = classification_data
        category_list_str = "\n".join(f"- {c}" for c in predefined_categories)

        try:            
            client = OpenAI(api_key=open_ai_key)

            response = client.chat.completions.create(  # Removed await since OpenAI client handles async
                messages=[
                    {"role": "system", "content": "You are an assistant helping to categorize grievances."},
                    {"role": "user", "content": f"""
                        Step 1:
                        Categorize this grievance: "{grievance_details}"
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
                            "list_categories": ["Category 1", "Category 2"]
                        }}
                    """}
                ],
                model="gpt-4",
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"OpenAI API Error: {e}")
            return None

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        
        language_code = tracker.get_slot("language_code") or "en"
        grievance_details = tracker.get_slot("grievance_temp")
        print(f"grievance_details_from_grievance_temp: {grievance_details}")
        
        if not grievance_details:
            
            utterance = get_utterance("grievance_form", self.name(), 1, language_code)
            buttons = get_buttons("grievance_form", self.name(), 1, language_code)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            return {}

        print(f"Raw - grievance_details: {grievance_details}")
        # Step 1: Call OpenAI for classification
        result = await self._call_openai_for_classification(grievance_details)
        
        if result is None:
            utterance = get_utterance("grievance_form", self.name(), 2, language_code)
            buttons = get_buttons("grievance_form", self.name(), 2, language_code)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            return {}

        print(f"Raw - gpt message: {result}")

        # Step 2: Parse the results and fill the slots
        result_dict = self.parse_summary_and_category(result)
        
        list_of_cat = result_dict["list_categories"] if result_dict["list_categories"] else []
        
        grievance_open_ai_slots = {
            "grievance_details": grievance_details,
            "grievance_summary_temp": result_dict["grievance_summary"],
            "grievance_categories": list_of_cat
        }
        
        ic(grievance_open_ai_slots)
        return grievance_open_ai_slots



    
############################ STEP 1 - GRIEVANCE FORM DETAILS ############################

class ValidateGrievanceDetailsForm(BaseFormValidationAction):
    def __init__(self):
        """Initialize form action"""
        super().__init__()
        self.db = db_manager  # Use the singleton instance directly
        
    def name(self) -> Text:
        return "validate_grievance_details_form"
    
    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        # Check if grievance_new_detail is "completed"
        if tracker.get_slot("grievance_new_detail") == "completed":
            print("######################### DEACTIVATING FORM ##############")
            print("value of slot grievance_details", tracker.get_slot("grievance_details"))
            print("########################################################")
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
        result = {}
        latest_message = tracker.latest_message
        requested_slot = tracker.get_slot("requested_slot")=="grievance_new_detail"
        if latest_message and requested_slot:
        # Only extract when the value is not None slot is requested
            result = await self._handle_slot_extraction(
                                            "grievance_new_detail",
                                            tracker,
                                            dispatcher,
                                            domain,
                                            skip_value=True,  # When skipped, assume confirmed
                                        )
        return result

    async def validate_grievance_new_detail(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        print("\n✨ FORM: Starting validation of grievance_new_detail")
        print(f"Received slot_value: {slot_value}")

        # initiate grievance_temp and handle the cases where the temp is a payload
        current_temp = ""
        if tracker.get_slot("grievance_temp"):
            if not tracker.get_slot("grievance_temp").startswith("/"):
                current_temp = tracker.get_slot("grievance_temp")
                
        print(f"current_grievance_details: {current_temp}")
        
        # Handle form completion
        if slot_value and "/submit_details" in slot_value:
            print("######################### LAST VALIDATION ##############")
            print("🎯 FORM: Handling submit_details intent")
            #call action_ask_grievance_details_form_grievance_temp
            await ActionAskGrievanceDetailsFormGrievanceTemp().run(dispatcher, tracker, domain)
            
            # Get base slots
            slots_to_set = {
                "grievance_new_detail": "completed",
                "grievance_temp": tracker.get_slot('grievance_temp'),
            }
            print(f"-------- end of validate_grievance_new_detail --------")
            # Add OpenAI results
            openai_action = ActionCallOpenAI()
            grievance_openai_slots = await openai_action.run(dispatcher, tracker, domain)
            slots_to_set.update(grievance_openai_slots) 
            
            print(f"slots_to_set_openAI: {slots_to_set}")

            return slots_to_set

        # Handle valid grievance text
        if slot_value and not slot_value.startswith('/'):
            print("✅ FORM: Processing valid grievance text")
            print(f"slot_value: {slot_value}")
            
            #call action_ask_grievance_details_form_grievance_temp
            await ActionAskGrievanceDetailsFormGrievanceTemp().run(dispatcher, tracker, domain)
            
            updated_temp = self._update_grievance_text(current_temp, slot_value)
            
            print("🔄 FORM: Returning updated slots")
            print(f"Updated grievance_temp: {updated_temp}")
            print(f"-------- end of validate_grievance_new_detail --------")
            
            return {
                "grievance_new_detail": None,
                "grievance_temp": updated_temp
            }
        # Handle invalid inputs - mostly payloads and reinitialize the slot
        print("⚠️ FORM: Invalid input detected - setting the slot to None")
        print(f"Slot value: {slot_value}")
        print(f"update grievance details: {current_temp}")
        print(f"-------- end of validate_grievance_new_detail --------")
        return {"grievance_new_detail": None}


    def _update_grievance_text(self, current_text: str, new_text: str) -> str:
        """Helper method to update the grievance text."""
        print(f"\n📝 FORM: Updating grievance text")
        print(f"Current text: {current_text}")
        print(f"New text: {new_text}")
        # handle the cases where the new text is a payload
        if new_text in ["/submit_details", "/add_more_details", "/exit_without_filing", "/start_grievance_process"]:
            print("new_text is a payload")
            new_text = ""
        updated = current_text + "\n" + new_text if current_text else new_text
        updated = updated.strip()
        print(f"Updated text: {updated}")
        return updated
    
class ActionAskGrievanceDetailsFormGrievanceTemp(Action):
    def name(self) -> Text:
        return "action_ask_grievance_details_form_grievance_temp"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        slot_grievance = tracker.get_slot("grievance_new_detail")
        language_code = tracker.get_slot("language_code") or "en"
        
        if slot_grievance == "/add_more_details":
            utterance = get_utterance("grievance_form", self.name(), 2, language_code)
            dispatcher.utter_message(text=utterance)
            
        if "/submit_details" in slot_grievance:
            utterance = get_utterance("grievance_form", self.name(), 3, language_code)
            dispatcher.utter_message(text=utterance)
            
        if slot_grievance and not slot_grievance.startswith('/'):
            utterance = get_utterance("grievance_form", self.name(), 4, language_code)
            buttons = get_buttons("grievance_form", self.name(), 1, language_code)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            
        return []

class ValidateGrievanceSummaryForm(BaseFormValidationAction):
        # Class variable to track message display
    message_display_list_cat = True
    
    def __init__(self):
        """Initialize form action"""
        super().__init__()
        self.message_display_list_cat = True
        self.db = db_manager  # Use the singleton instance directly
        
    def name(self) -> Text:
        return "validate_grievance_summary_form"
    
    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        print("######################### REQUIRED SLOTS ##############")
        
        updated_slots = domain_slots
        #ic(tracker.get_slot("gender_issues_reported"))
        #ic(domain_slots)
        if not domain_slots:
            updated_slots = ["grievance_categories_confirmed"]
        
        grievance_categories_confirmed = tracker.get_slot("grievance_categories_confirmed")
        grievance_cat_modify = tracker.get_slot("grievance_cat_modify")
 
        
        # After category modification is complete, go back to confirmation
        if grievance_cat_modify:
            print(" category modify detected")
            updated_slots = ["grievance_categories_confirmed"]  # Reset to ask for confirmation again
        
        #deal with the case where gender issues is part of list_of_cat by adding one slot to the updated_slots
        if tracker.get_slot("gender_issues_reported") and "gender_follow_up" not in updated_slots:
            updated_slots = updated_slots + ["gender_follow_up"]
            #ic(updated_slots)
            
        elif grievance_categories_confirmed in ["slot_skipped", "slot_confirmed"]:
            # Use extend to add multiple items to the list
            updated_slots = [
                "grievance_summary_confirmed",
                "grievance_summary_temp",
                "grievance_summary"
            ]
            
        elif grievance_categories_confirmed in ["slot_added", "slot_deleted"]:
            print(" category added or deleted detected")
            updated_slots = ["grievance_cat_modify"]  # Simplified - only ask for the modification

        print(f"list of cat as in required_slots: {tracker.get_slot('grievance_categories')}")

        print(f"Input slots: {domain_slots} \n Updated slots: {updated_slots}")
        print(f"Value grievance_categories_confirmed: {grievance_categories_confirmed}, Value grievance_cat_modify: {tracker.get_slot('grievance_cat_modify')}")
        print(f"next requested slot: {tracker.get_slot('requested_slot')}")
        print(f"message_display_list_cat: {ValidateGrievanceSummaryForm.message_display_list_cat}")
        print("--------- END REQUIRED SLOTS ---------")

        return updated_slots
    
    
    def _detect_gender_issues(self, tracker: Tracker) -> bool:
        """
        Detects gender issues in the grievance list of categories
        """
        list_of_cat = tracker.get_slot("grievance_categories")
        #check if the string "gender" is in any of the categories in the list_of_cat
        return any("gender" in category.lower() for category in list_of_cat)
    
    def _report_gender_issues(self, 
                                 dispatcher: CollectingDispatcher, 
                                 tracker: Tracker):
            """
            Helper function to report gender issues and return the specific updated slots
            the changes in requested_slot are not handled in that specific function
            the utterance and buttons are handled in the action_ask_grievance_summary_form_gender_follow_up
            """
            ic("run _report_gender_issues")
            # update all the regular slots to validate the form and add the gender_issues_reported slot
            return {"grievance_categories_confirmed": "slot_confirmed",
                    "grievance_cat_modify": "slot_skipped",
                    "grievance_categories": tracker.get_slot("grievance_categories"),
                    "grievance_summary": tracker.get_slot("grievance_summary_temp"),
                    "grievance_summary_confirmed": "slot_skipped",
                    "gender_issues_reported": True}
            
    async def extract_grievance_categories_confirmed(self, 
                                                   dispatcher: CollectingDispatcher,
                                                   tracker: Tracker,
                                                   domain: Dict[Text, Any]
                                                   ) -> Dict[Text, Any]:
        print("######################### EXTRACT GRIEVANCE LIST CAT CONFIRMED ##############")
        return await self._handle_slot_extraction(
            "grievance_categories_confirmed",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_grievance_categories_confirmed(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        print("######################### VALIDATE GRIEVANCE LIST CAT CONFIRMED ##############")

        slot_value = slot_value.strip('/')
        list_of_cat = tracker.get_slot("grievance_categories") #get the list of cat from the slot to check for gender issues
        
        print(f"grievance_categories_confirmed: {slot_value}")
        
        if slot_value in ["slot_skipped", "slot_confirmed"]:
            if self._detect_gender_issues(tracker):
                ic("validate_grievance_categories_confirmed: gender issues detected in list_of_cat")
                return self._report_gender_issues(dispatcher, tracker)
            else:
                ic("validate_grievance_categories_confirmed: no gender issues detected in list_of_cat")
                return {"grievance_categories_confirmed": slot_value,
                        "grievance_cat_modify": slot_value}
            
        return {"grievance_categories_confirmed": slot_value}
    
    
    
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
                - grievance_categories_confirmed: Reset to None after processing
                - grievance_cat_modify: Reset to None after processing
                
        Note:
            The function handles three main cases:
            1. Skip operation: When user chooses to skip the modification
            2. Delete operation: Removes selected category from the list
            3. Add operation: Appends new category to the existing list
        """
        
        print("######################### VALIDATE GRIEVANCE CAT MODIFY ##############")
       
            
        slot_value = slot_value.strip('/')
        #initalize the slots
        print("slot_value: ", slot_value)

        list_of_cat = tracker.get_slot("grievance_categories")
        print("list_of_cat: ", list_of_cat)
        
        
        selected_category = self.get_category_to_modify(slot_value)
                
        print("c extracted from message : " , selected_category)
                
        if not selected_category or slot_value == "slot_skipped":
            dispatcher.utter_message(text="No category selected. skipping this step.")
            return {"grievance_categories_confirmed": "slot_skipped",
                    "grievance_cat_modify": "slot_skipped"}
      
        #case 2: delete the category
        if tracker.get_slot("grievance_categories_confirmed") == "slot_deleted":
            #delete the category
            list_of_cat.remove(selected_category)
            
        #case 3: add the category
        if tracker.get_slot("grievance_categories_confirmed") == "slot_added":
            list_of_cat.append(selected_category)
        
        #reset the message_display_list_cat to True
        ValidateGrievanceSummaryForm.message_display_list_cat = True
        print("updated list of cat: ", list_of_cat)
        
        # #deal with the case where gender issues is part of list_of_cat
        # if self._detect_gender_issues(tracker):
        #     ic("validate_grievance_cat_modify: gender issues detected in list_of_cat")
        #     return self._report_gender_issues(dispatcher, tracker)
            
        #update the slots
        grievance_slots_to_set = {
            "grievance_categories": list_of_cat,
            "grievance_categories_confirmed": None,
            "grievance_cat_modify": None,
            "requested_slot": "grievance_categories_confirmed"
        }
        ic(grievance_slots_to_set)
        return grievance_slots_to_set
        
        
    

    
    async def extract_grievance_summary_confirmed(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "grievance_summary_confirmed",
            tracker,
            dispatcher,
            domain
        )
    
    
    async def validate_grievance_summary_confirmed(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        slot_value = slot_value.strip('/')
        #initalize the slots
        
        if slot_value == "slot_skipped":
            return {"grievance_summary_confirmed": "slot_skipped",
                    "grievance_summary": "slot_skipped"}
            
            
        if slot_value == "slot_confirmed":
            return {"grievance_summary_confirmed": "slot_confirmed",
                    "grievance_summary": tracker.get_slot("grievance_summary_temp")}
        
        if slot_value == "slot_edited":
            return {"grievance_summary_confirmed": "slot_edited",
                    "grievance_summary_temp": None}

    
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
       
        if slot_value == "slot_skipped":
            return {"grievance_summary_confirmed": "slot_skipped",
                    "grievance_summary": "slot_skipped"}
        
        if slot_value:
            return {"grievance_summary_confirmed": None,
                    "grievance_summary_temp": slot_value}
            
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
        
        slots = {"user_location_consent": False,
                    "user_municipality_temp": "slot_skipped",
                    "user_municipality": "slot_skipped",
                    "user_municipality_confirmed": False,
                    "user_village": "slot_skipped",
                    "user_address_temp": "slot_skipped",
                    "user_address": "slot_skipped",
                    "user_address_confirmed": False,
                    "user_contact_consent": "slot_skipped",
                    "user_full_name": "slot_skipped",
                    "user_contact_phone": "slot_skipped",
                    "phone_validation_required": False,
                    "user_contact_email_temp": "slot_skipped",
                    "user_contact_email_confirmed": "slot_skipped"
                    }
        
        if slot_value == "/exit" or "slot_skipped" in slot_value:
            return slots
        if slot_value == "/anonymous_with_phone":
            slots["user_contact_consent"] = "anonymous_with_phone"
            slots["user_full_name"] = None
            slots["user_contact_phone"] = None
            slots["phone_validation_required"] = True
            return slots
        return {}

class ActionAskGrievanceSummaryFormGrievanceListCatConfirmed(Action):
    def name(self) -> Text:
        return "action_ask_grievance_summary_form_grievance_categories_confirmed"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        print(f"ACTION ASK GRIEVANCE SUMMARY FORM GRIEVANCE LIST CAT CONFIRMED\n called with message_display_list_cat: {ValidateGrievanceSummaryForm.message_display_list_cat}")
            
        if ValidateGrievanceSummaryForm.message_display_list_cat:
            grievance_categories = tracker.get_slot("grievance_categories")
            print(f"Current categories: {grievance_categories}")
            
            if not grievance_categories or grievance_categories == []:
                print("No categories found, sending no categories message")
                utterance = get_utterance("grievance_form", self.name(), 1, language_code)
                buttons = get_buttons("grievance_form", self.name(), 1, language_code)
                dispatcher.utter_message(text=utterance, buttons=buttons)
            
            else:
                print(f"Sending message with categories: {grievance_categories}")
                category_text = "\n".join([v for v in grievance_categories])
                utterance = get_utterance("grievance_form", self.name(), 2, language_code).format(category_text=category_text)  
                buttons = get_buttons("grievance_form", self.name(), 2, language_code)
                dispatcher.utter_message(text=utterance, buttons=buttons)

            ValidateGrievanceSummaryForm.message_display_list_cat = False
            ic(ValidateGrievanceSummaryForm.message_display_list_cat)

        return []


class ActionAskGrievanceSummaryFormGrievanceCatModify(Action):
    def name(self) -> Text:
        return "action_ask_grievance_summary_form_grievance_cat_modify"
    
    async def run(
        self, 
        dispatcher: CollectingDispatcher, 
        tracker: Tracker,
        domain: DomainDict
        ) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        ask_cat_modify_flag = tracker.get_slot("grievance_categories_confirmed")
        ic(ask_cat_modify_flag)
        list_of_cat = tracker.get_slot("grievance_categories")
        
        if ask_cat_modify_flag == 'slot_deleted':
            if not list_of_cat:
                utterance = get_utterance("grievance_form", self.name(), 1, language_code)
                dispatcher.utter_message(text=utterance)
                return {"grievance_categories_confirmed": "slot_skipped"}
            else:
                buttons = [
                    {"title": cat, "payload": f'/delete_category{{"category_to_delete": "{cat}"}}'}
                    for cat in list_of_cat
                ]
                buttons.append({"title": "Skip", "payload": "/skip"})
                utterance = get_utterance("grievance_form", self.name(), 2, language_code)
                dispatcher.utter_message(text=utterance, buttons=buttons)
                
        if ask_cat_modify_flag == "slot_added":
            list_cat_to_add = [cat for cat in LIST_OF_CATEGORIES if cat not in list_of_cat]
            buttons = [
                {"title": cat, "payload": f'/add_category{{"category": "{cat}"}}'} 
                for cat in list_cat_to_add[:10]
            ]
            utterance = get_utterance("grievance_form", self.name(), 3, language_code)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        return []
    
    
class ActionAskGrievanceSummaryFormGrievanceSummaryConfirmed(Action):
    def name(self) -> Text:
        return "action_ask_grievance_summary_form_grievance_summary_confirmed"
    
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict
        ) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        current_summary = tracker.get_slot("grievance_summary_temp")
        if current_summary:
            utterance = get_utterance("grievance_form", self.name(), 1, language_code).format(current_summary=current_summary)
            buttons = get_buttons("grievance_form", self.name(), 1, language_code)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        else:
            utterance = get_utterance("grievance_form", self.name(), 1, language_code)
            buttons = BUTTON_SKIP
            dispatcher.utter_message(text=utterance)

class ActionAskGrievanceSummaryFormGrievanceSummaryTemp(Action):
    def name(self) -> Text:
        return "action_ask_grievance_summary_form_grievance_summary_temp"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        if tracker.get_slot("grievance_summary_confirmed") == "slot_edited":
            utterance = get_utterance("grievance_form", 
                                      self.name(), 
                                      2, 
                                      language_code)
            dispatcher.utter_message(text=utterance)
        return []

class ActionAskGrievanceSummaryFormGenderFollowUp(Action):
    def name(self) -> Text:
        return "action_ask_grievance_summary_form_gender_follow_up"
    
    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        for i in range(1, 4):
            utterance = get_utterance("grievance_form", self.name(), i, language_code)
            dispatcher.utter_message(text=utterance)
        utterance = get_utterance("grievance_form", self.name(), 4, language_code)
        buttons = get_buttons("grievance_form", self.name(), 1, language_code)
        dispatcher.utter_message(text=utterance, buttons=buttons)

############################ STEP 4 - SUBMIT GRIEVANCE ############################
class ActionSubmitGrievance(Action):
    def __init__(self):
        self.db = db_manager
        self.sms_client = SMSClient()
        self.email_client = EmailClient()
        
    def name(self) -> Text:
        return "action_submit_grievance"

    def get_current_datetime(self) -> str:
        """Get current date and time in YYYY-MM-DD HH:MM format."""
        return datetime.now().strftime("%Y-%m-%d %H:%M")
    
    def generate_user_id(self, grievance_data: Dict[str, Any]) -> str:
        """Generate a unique user ID using Nepal time and UUID.

        Returns:
            str: A unique user ID in the format USR{YYYYMMDD}{UUID[:6]}
        """
        province = grievance_data.get('user_province')
        district = grievance_data.get('user_district')
        municipality = grievance_data.get('user_municipality')
        project = grievance_data.get('user_project')
        if province:
            province_code = province[:3].upper()
        else:
            province_code = "XX"
        if district:
            district_code = district[:3].upper()
        else:
            district_code = "XX"
        if municipality:
            municipality_code = municipality[:3].upper()
        else:
            municipality_code = "XX"
        if project:
            project_code = project[:2].upper()
        else:
            project_code = "XX"
        return f"{province_code}-{district_code}-{project_code}-{municipality_code}-{uuid.uuid4().hex[:6].upper()}"


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
        grievance_data={k : tracker.get_slot(k) for k in ["user_contact_phone",
                                                          "user_contact_email",
                                                          "user_full_name",
                                                          "user_province",
                                                          "user_district",
                                                          "user_municipality",
                                                          "user_project",
                                                          "user_ward",
                                                          "user_village",
                                                          "user_address",
                                                          "grievance_id",
                                                          "grievance_summary",
                                                          "grievance_details",
                                                          "grievance_categories",
                                                          "grievance_claimed_amount"
                                                          ]}
        
        grievance_data["grievance_status"] = GRIEVANCE_STATUS["SUBMITTED"]
        grievance_data["submission_type"] = "new_grievance"
        grievance_data["grievance_timestamp"] = grievance_timestamp
        grievance_data["grievance_timeline"] = grievance_timeline
        grievance_data["user_unique_id"] = self.generate_user_id(grievance_data)
        # change all the values of the slots_skipped or None to "NOT_PROVIDED"
        grievance_data = self._update_key_values_for_db_storage(grievance_data)
        ic(grievance_data)
                
        return grievance_data

    def _update_key_values_for_db_storage(self, grievance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update the values of the grievance data for the database storage."""
        for key, value in grievance_data.items():
            if value == "slot_skipped" or value is None:
                grievance_data[key] = DEFAULT_VALUES["NOT_PROVIDED"]
        return grievance_data
    
    
    def create_confirmation_message(self, 
                                    grievance_data: Dict[str, Any]) -> str:
        """Create a formatted confirmation message."""
        ic(self.language_code)
        message = [get_utterance("grievance_form", 
                                 'create_confirmation_message', 
                                 i, 
                                 self.language_code) for i in ['grievance_id',
                                                                'grievance_timestamp',
                                                         'grievance_summary',
                                                         'grievance_categories',
                                                         'grievance_details',
                                                         'user_contact_email',
                                                         'user_contact_phone',
                                                         'grievance_outro',
                                                         'grievance_timeline'] if grievance_data.get(i) is not DEFAULT_VALUES["NOT_PROVIDED"]]
        
        message = "\n".join(message).format(grievance_id=grievance_data['grievance_id'], 
                                            grievance_timestamp=grievance_data['grievance_timestamp'],
                                            grievance_summary=grievance_data['grievance_summary'],
                                            grievance_categories=grievance_data['grievance_categories'],
                                            grievance_details=grievance_data['grievance_details'],
                                            user_contact_email=grievance_data['user_contact_email'],
                                            user_contact_phone=grievance_data['user_contact_phone'],
                                            grievance_timeline=grievance_data['grievance_timeline']
                                           )

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
        
        if body_name == "GRIEVANCE_RECAP_USER_BODY":
            body = EMAIL_TEMPLATES[body_name].format(
            user_name=email_data['user_full_name'],
            grievance_summary=email_data['grievance_summary'],
            grievance_details=email_data['grievance_details'],
            categories_html=categories_html,
            project=email_data['user_project'],
            municipality=email_data['user_municipality'],
            village=email_data['user_village'],
            address=email_data['user_address'],
            phone=email_data['user_contact_phone'],
            grievance_id=email_data['grievance_id'],
            email=email_data['user_contact_email'],
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
            self.email_client.send_email(to_emails,
                                        subject = subject,
                                        body=body
                                        )
            if body_name == "GRIEVANCE_RECAP_USER_BODY":
                message = get_utterance("grievance_form", self.name(), 2, self.language_code)
                dispatcher.utter_message(text=message)
                
        except Exception as e:
            logger.error(f"Failed to send system notification email: {e}"
            )

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        print("\n=================== Submitting Grievance ===================")
        self.language_code = tracker.get_slot("language_code") or "en"
        
        try:
            # Collect grievance data
            grievance_data = self.collect_grievance_data(tracker)
            
            user_contact_email = grievance_data.get('user_contact_email')
            user_contact_email = user_contact_email if self.is_valid_email(user_contact_email) else None
            if grievance_data.get('otp_verified') == True:
                user_contact_phone = grievance_data.get('user_contact_phone')
            else:
                user_contact_phone = None

            ic('collected grievance data from tracker', grievance_data)
            
            # Update the existing grievance with complete data
            grievance_id = self.db.update_grievance_db(grievance_data)
            if not grievance_id:
                raise Exception("Failed to update grievance in the database")

            ic(f"✅ Grievance updated successfully with ID: {grievance_id}")
            
            # Create confirmation message to be sent by sms and through the bot
            confirmation_message = self.create_confirmation_message(
                grievance_data
            )
                
            # Send confirmation message
            dispatcher.utter_message(text=confirmation_message)
            
            if user_contact_phone:
                #send sms
                self.sms_client.send_sms(user_contact_phone, confirmation_message)
                #utter sms confirmation message
                utterance = get_utterance("grievance_form", self.name(), 3, self.language_code).format(user_contact_phone=user_contact_phone)
                dispatcher.utter_message(text=utterance)
            
            #send email to admin
            await self._send_grievance_recap_email(ADMIN_EMAILS, 
                                                   grievance_data, 
                                                   "GRIEVANCE_RECAP_ADMIN_BODY", 
                                                   dispatcher=dispatcher)
            
            #send email to user
            print("user_contact_email :", user_contact_email)
            if user_contact_email:
                await self._send_grievance_recap_email([user_contact_email], 
                                                       grievance_data, 
                                                       "GRIEVANCE_RECAP_USER_BODY", 
                                                       dispatcher=dispatcher)
                
                # Send email confirmation message
                utterance = get_utterance("grievance_form", self.name(), 2, self.language_code).format(user_contact_email=user_contact_email)
                dispatcher.utter_message(text=utterance)
        
            # Prepare events
            return [
                SlotSet("grievance_id", grievance_id),
                SlotSet("grievance_status", GRIEVANCE_STATUS["SUBMITTED"])
            ]

        except Exception as e:
            print(f"❌ Error submitting grievance: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            utterance = get_utterance("grievance_form", self.name(), 4, self.language_code)
            dispatcher.utter_message(text=utterance)
            return []
        
        

        



