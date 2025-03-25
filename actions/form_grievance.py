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
from actions.constants import GRIEVANCE_STATUS, EMAIL_TEMPLATES, SMS_TEMPLATES, DEFAULT_VALUES, ADMIN_EMAILS
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from .db_actions import GrievanceDB
from datetime import datetime
from .messaging import SMSClient, EmailClient
from rapidfuzz import process
import traceback
from .utterance_mapping import get_utterance, get_buttons, BUTTON_SKIP, BUTTON_AFFIRM, BUTTON_DENY
from icecream import ic
#define and load variables

load_dotenv('/home/ubuntu/nepal_chatbot/.env')
open_ai_key = os.getenv("OPENAI_API_KEY")

#load the categories
classification_data = load_classification_data()
LIST_OF_CATEGORIES = load_categories_from_lookup()
LIST_OF_CATEGORIES = [cat.strip("-").strip() for cat in LIST_OF_CATEGORIES]

#load the db
db = GrievanceDB()


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
                SlotSet("grievance_list_cat", None),
                SlotSet("grievance_list_cat_confirmed", None),
                SlotSet("main_story", "new_grievance")]

    
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
         
        return {
            "grievance_details": grievance_details,
            "grievance_summary_temp": result_dict["grievance_summary"],
            "grievance_list_cat": list_of_cat
        }



    
############################ STEP 1 - GRIEVANCE FORM DETAILS ############################

class ValidateGrievanceDetailsForm(BaseFormValidationAction):
    def __init__(self):
        super().__init__()
        
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
            openai_slots = await openai_action.run(dispatcher, tracker, domain)
            slots_to_set.update(openai_slots)
            
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

    # def _show_options_buttons(self, dispatcher: CollectingDispatcher) -> None:
    #     """Helper method to show the standard options buttons."""
    #     print("\n🔘 FORM: Showing options buttons")
    #     dispatcher.utter_message(
    #         text="Thank you for your entry. Do you want to add more details to your grievance, such as:\n"
    #              "- Location information\n"
    #              "- Persons involved\n"
    #              "- Quantification of damages (e.g., number of bags of rice lost)\n"
    #              "- Monetary value of damages",
    #         buttons=[
    #             {"title": "File as is", "payload": "/submit_details"},
    #             {"title": "Add more details", "payload": "/add_more_details"},
    #             {"title": "Cancel filing", "payload": "/exit_without_filing"}
    #         ]
    #     )

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
        
        # if not slot_grievance or slot_grievance == "/start_grievance_process":
        #     print("######################### ASK GRIEVANCE TEMP ##############")
        #     utterance = get_utterance("grievance_form", self.name(), 1, language_code)
        #     buttons = get_buttons("grievance_form", self.name(), 1, language_code)
        #     dispatcher.utter_message(text=utterance, buttons=buttons)
        
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
        super().__init__()
        self.message_display_list_cat = True
        
    def name(self) -> Text:
        return "validate_grievance_summary_form"
    
    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        print("######################### REQUIRED SLOTS ##############")
        
        updated_slots = domain_slots
        print(f"required_slots input: {domain_slots}")
        if not domain_slots:
            updated_slots = ["grievance_list_cat_confirmed"]
        
        grievance_list_cat_confirmed = tracker.get_slot("grievance_list_cat_confirmed")
        grievance_cat_modify = tracker.get_slot("grievance_cat_modify")
        # print(f"grievance_list_cat_confirmed: {grievance_list_cat_confirmed}")
        # print(f"grievance_cat_modify: {grievance_cat_modify}")  
        
        # After category modification is complete, go back to confirmation
        if grievance_cat_modify:
            print(" category modify detected")
            updated_slots = ["grievance_list_cat_confirmed"]  # Reset to ask for confirmation again

        if grievance_list_cat_confirmed in ["slot_skipped", "slot_confirmed"]:
            # Use extend to add multiple items to the list
            updated_slots = [
                "grievance_summary_confirmed",
                "grievance_summary_temp",
                "grievance_summary"
            ]
            
        if grievance_list_cat_confirmed in ["slot_added", "slot_deleted"]:
            print(" category added or deleted detected")
            updated_slots = ["grievance_cat_modify"]  # Simplified - only ask for the modification

        print(f"list of cat as in required_slots: {tracker.get_slot('grievance_list_cat')}")

        print(f"Input slots: {domain_slots} \n Updated slots: {updated_slots}")
        print(f"Value grievance_list_cat_confirmed: {grievance_list_cat_confirmed}, Value grievance_cat_modify: {tracker.get_slot('grievance_cat_modify')}")
        print(f"next requested slot: {tracker.get_slot('requested_slot')}")
        print(f"message_display_list_cat: {ValidateGrievanceSummaryForm.message_display_list_cat}")
        print("--------- END REQUIRED SLOTS ---------")

        return updated_slots

            
    async def extract_grievance_list_cat_confirmed(self, 
                                                   dispatcher: CollectingDispatcher,
                                                   tracker: Tracker,
                                                   domain: Dict[Text, Any]
                                                   ) -> Dict[Text, Any]:
        print("######################### EXTRACT GRIEVANCE LIST CAT CONFIRMED ##############")
        return await self._handle_slot_extraction(
            "grievance_list_cat_confirmed",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_grievance_list_cat_confirmed(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        print("######################### VALIDATE GRIEVANCE LIST CAT CONFIRMED ##############")

        slot_value = slot_value.strip('/')
         #initialize the list of cat
        # list_of_cat = tracker.get_slot("grievance_list_cat")
        # list_of_cat_to_add = LIST_OF_CATEGORIES if not list_of_cat else [cat for cat in LIST_OF_CATEGORIES if cat not in list_of_cat]
        # print(f"message_display_list_cat: {ValidateGrievanceSummaryForm.message_display_list_cat}")
        
        print(f"grievance_list_cat_confirmed: {slot_value}")
        
        if slot_value in ["slot_skipped", "slot_confirmed"]:
            print(slot_value, "EXPECTED SLOT VALUE")
            # self.utter_summary_message(dispatcher, tracker)
            return {"grievance_list_cat_confirmed": slot_value,
                    "grievance_cat_modify": slot_value}
        
                
        return {"grievance_list_cat_confirmed": slot_value}
    
    
    
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
                - grievance_list_cat: Updated list of categories
                - grievance_list_cat_confirmed: Reset to None after processing
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

        list_of_cat = tracker.get_slot("grievance_list_cat")
        print("list_of_cat: ", list_of_cat)
        
        
        selected_category = self.get_category_to_modify(slot_value)
                
        print("c extracted from message : " , selected_category)
                
        if not selected_category or slot_value == "slot_skipped":
            dispatcher.utter_message(text="No category selected. skipping this step.")
            return {"grievance_list_cat_confirmed": "slot_skipped",
                    "grievance_cat_modify": "slot_skipped"}
      
        #case 2: delete the category
        if tracker.get_slot("grievance_list_cat_confirmed") == "slot_deleted":
            #delete the category
            list_of_cat.remove(selected_category)
            
        #case 3: add the category
        if tracker.get_slot("grievance_list_cat_confirmed") == "slot_added":
            list_of_cat.append(selected_category)
        
        #reset the message_display_list_cat to True
        ValidateGrievanceSummaryForm.message_display_list_cat = True
        print("updated list of cat: ", list_of_cat)
        #update the slots
        return {"grievance_list_cat": list_of_cat,
                "grievance_list_cat_confirmed": None,
                "grievance_cat_modify": None,
                "requested_slot": "grievance_list_cat_confirmed"}

    
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


class ActionAskGrievanceSummaryFormGrievanceListCatConfirmed(Action):
    def name(self) -> Text:
        return "action_ask_grievance_summary_form_grievance_list_cat_confirmed"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        print(f"ACTION ASK GRIEVANCE SUMMARY FORM GRIEVANCE LIST CAT CONFIRMED\n called with message_display_list_cat: {ValidateGrievanceSummaryForm.message_display_list_cat}")
            
        if ValidateGrievanceSummaryForm.message_display_list_cat:
            grievance_list_cat = tracker.get_slot("grievance_list_cat")
            print(f"Current categories: {grievance_list_cat}")
            
            if not grievance_list_cat or grievance_list_cat == []:
                print("No categories found, sending no categories message")
                utterance = get_utterance("grievance_form", self.name(), 1, language_code)
                buttons = get_buttons("grievance_form", self.name(), 1, language_code)
                dispatcher.utter_message(text=utterance, buttons=buttons)
            
            else:
                print(f"Sending message with categories: {grievance_list_cat}")
                category_text = "\n".join([v for v in grievance_list_cat])
                utterance = get_utterance("grievance_form", self.name(), 2, language_code).format(category_text=category_text)  
                buttons = get_buttons("grievance_form", self.name(), 2, language_code)
                dispatcher.utter_message(text=utterance, buttons=buttons)

            ValidateGrievanceSummaryForm.message_display_list_cat = False
            print(f"Set message_display_list_cat to {ValidateGrievanceSummaryForm.message_display_list_cat}")

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
        flag = tracker.get_slot("grievance_list_cat_confirmed")
        print("ask_cat_modify flag :", flag)
        list_of_cat = tracker.get_slot("grievance_list_cat")
        
        if flag == 'slot_deleted':
            if not list_of_cat:
                utterance = get_utterance("grievance_form", self.name(), 1, language_code)
                dispatcher.utter_message(text=utterance)
                return {"grievance_list_cat_confirmed": "slot_skipped"}
            else:
                buttons = [
                    {"title": cat, "payload": f'/delete_category{{"category_to_delete": "{cat}"}}'}
                    for cat in list_of_cat
                ]
                buttons.append({"title": "Skip", "payload": "/skip"})
                utterance = get_utterance("grievance_form", self.name(), 2, language_code)
                dispatcher.utter_message(text=utterance, buttons=buttons)
                
        if flag == "slot_added":
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



############################ STEP 4 - SUBMIT GRIEVANCE ############################
class ActionSubmitGrievance(Action):
    def __init__(self):
        self.db = GrievanceDB()
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
        # User-related data
        user_data = {
            'user_contact_phone': tracker.get_slot('user_contact_phone'),
            'user_contact_email': tracker.get_slot('user_contact_email'),
            'user_full_name': tracker.get_slot('user_full_name'),
            'user_province': tracker.get_slot('user_province'),
            'user_district': tracker.get_slot('user_district'),
            'user_municipality': tracker.get_slot('user_municipality'),
            'user_ward': tracker.get_slot('user_ward'),
            'user_village': tracker.get_slot('user_village'),
            'user_address': tracker.get_slot('user_address'),
        }

        # Grievance-related data
        grievance_data = {
            'grievance_id': tracker.get_slot('grievance_id'),
            'grievance_summary': tracker.get_slot('grievance_summary'),
            'grievance_details': tracker.get_slot('grievance_details'),
            'grievance_category': tracker.get_slot('grievance_list_cat'),
            'grievance_claimed_amount': tracker.get_slot('grievance_claimed_amount')
        }
        
        grievance_status = {
            "grievance_status": GRIEVANCE_STATUS["SUBMITTED"],
            'submission_type': "new_grievance",
            "timestamp": self.get_current_datetime()
        }
        
        # change all the values of the slots_skipped or None to "NOT_PROVIDED"
        for key, value in user_data.items():
            if value == "slot_skipped" or value is None:
                user_data[key] = DEFAULT_VALUES["NOT_PROVIDED"]
                
        for key, value in grievance_data.items():
            if value == "slot_skipped" or value is None:
                grievance_data[key] = DEFAULT_VALUES["NOT_PROVIDED"]
                

        return user_data, grievance_data, grievance_status

    def create_confirmation_message(self, 
                                    grievance_data: Dict[str, Any],
                                    user_data: Dict[str, Any]) -> str:
        """Create a formatted confirmation message."""
        ic(self.language_code)
        message = [get_utterance("grievance_form", 
                                 'create_confirmation_message', 
                                 i, 
                                 self.language_code) for i in ['grievance_id',
                                                         'grievance_summary',
                                                         'grievance_category',
                                                         'grievance_details',
                                                         'grievance_email',
                                                         'grievance_phone',
                                                         'grievance_outro',
                                                         'grievance_timeline']]
        
        message = "\n".join(message).format(grievance_id=grievance_data['grievance_id'], 
                                            grievance_summary=grievance_data['grievance_summary'],
                                            grievance_category=grievance_data['grievance_category'],
                                            grievance_details=grievance_data['grievance_details'],
                                            grievance_email=user_data['user_contact_email'],
                                            grievance_phone=user_data['user_contact_phone'],
                                           )
        
        # Add summary if available
        # if grievance_data['grievance_summary']:
        #     if language_code == "ne":
        #         message.append(f"**सारांश:** {grievance_data['grievance_summary']}")
        #     else:   
        #         message.append(f"**Summary:** {grievance_data['grievance_summary']}")
        # else:
        #     if language_code == "ne":
        #         message.append("**सारांश:** [Not Provided]")
        #     else:
        #         message.append("**Summary:** [Not Provided]")

        # # Add category if available
        # if grievance_data['grievance_category']:
        #     if language_code == "ne":
        #         message.append(f"**श्रेणी:** {grievance_data['grievance_category']}")
        #     else:
        #         message.append(f"**Category:** {grievance_data['grievance_category']}")
        # else:
        #     if language_code == "ne":
        #         message.append("**श्रेणी:** [प्रदान गरिएन]\n यदि आवश्यक भएमा तपाईंले पछि श्रेणी थप्न सक्नुहुन्छ")
        #     else:
        #         message.append("**Category:** [Not Provided]\nYou can add the category later if needed.")

        # # Add details if available
        # if grievance_data['grievance_details']:
        #     if language_code == "ne":
        #         message.append(f"**विवरण:** {grievance_data['grievance_details']}")
        #     else:
        #         message.append(f"**Details:** {grievance_data['grievance_details']}")
        # if language_code == "ne":
        #     message.append("\nहाम्रो टीमले तपाईंको गुनासो थुप्रै जानकारी गर्नेछौं र अगाडि जानकारी आवश्यक भएको छ भन्ने सम्झौतामा तपाईंलाई सम्पर्क गर्नेछौं।")
        # else:
        #     message.append("\nOur team will review it shortly and contact you if more information is needed.")

        # # Add email notification info if available
        # if user_email:
        #     if language_code == "ne":
        #         message.append(f"\nतपाईंको इमेलमा सुनिश्चित गर्ने ईमेल भेटिन्छ। {user_email}")
        #     else:
        #         message.append(f"\nA confirmation email will be sent to {user_email}")

        return message
    
    async def _send_grievance_recap_email(self, 
                                          to_emails: List[str],
                                          email_data: Dict[str, Any],
                                          body_name: str,
                                          dispatcher: CollectingDispatcher) -> None:
        """Send a recap email to the user."""
        
        json_data = json.dumps(email_data, indent=2, ensure_ascii=False)
        
        # categories_html = ''.join(f'<li>{category}</li>' for category in (email_data['grievance_category'] or []))
        categories_html = ''.join(f'<li>{category}</li>' for category in (email_data['grievance_category'] or []))
        # Create email body using template
        
        if body_name == "GRIEVANCE_RECAP_USER_BODY":
            body = EMAIL_TEMPLATES[body_name].format(
            user_name=email_data['user_full_name'],
            grievance_summary=email_data['grievance_summary'],
            grievance_details=email_data['grievance_details'],
            categories_html=categories_html,
            municipality=email_data['user_municipality'],
            village=email_data['user_village'],
            address=email_data['user_address'],
            phone=email_data['user_contact_phone'],
            grievance_id=email_data['grievance_id'],
            email=email_data['user_contact_email']
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
            user_data, grievance_data, grievance_status = self.collect_grievance_data(tracker)
            user_email = user_data.get('user_contact_email')
            user_email = user_email if self.is_valid_email(user_email) else None
            if user_data.get('otp_verified') == True:
                user_contact_phone = user_data.get('user_contact_phone')
            else:
                user_contact_phone = None

            print(f"📝 User data: {user_data}")
            print(f"📝 Grievance data: {grievance_data}")
            
            # Create grievance in database
            grievance_id = self.db.create_grievance(user_data, grievance_data)
            
            if not grievance_id:
                raise Exception("Failed to create grievance in database")

            print(f"✅ Grievance created successfully with ID: {grievance_id}")
            
            
            # Create confirmation message to be sent by sms and through the bot
            confirmation_message = self.create_confirmation_message(
                grievance_data,
                user_data 
            )
                
            # Send confirmation message
            dispatcher.utter_message(text=confirmation_message)
            
            if user_contact_phone:
                #send sms
                self.sms_client.send_sms(user_contact_phone, confirmation_message)
            

            #prepare email data for compiling the email by combining user_data, grievance_data and grievance_status
            email_data = {**user_data, **grievance_data, **grievance_status}
            email_data['grievance_id'] = grievance_id
            
            #send email to admin
            await self._send_grievance_recap_email(ADMIN_EMAILS, 
                                                   email_data, 
                                                   "GRIEVANCE_RECAP_ADMIN_BODY", 
                                                   dispatcher=dispatcher)
            
            #send email to user
            print("user_email :", user_email)
            if user_email:
                await self._send_grievance_recap_email([user_email], 
                                                       email_data, 
                                                       "GRIEVANCE_RECAP_USER_BODY", 
                                                       dispatcher=dispatcher)
                
                # Send email confirmation message
                utterance = get_utterance("grievance_form", self.name(), 2, self.language_code)
                dispatcher.utter_message(text=utterance)
        
            # Prepare events
            return [
                SlotSet("grievance_id", grievance_id),
                SlotSet("grievance_status", GRIEVANCE_STATUS["SUBMITTED"])
            ]


        except Exception as e:
            print(f"❌ Error submitting grievance: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            utterance = get_utterance("grievance_form", self.name(), 3, self.language_code)
            dispatcher.utter_message(text=utterance)
            return []
        
        

    
############################ ALTERNATE PATH - CATEGORY MODIFICATION ############################

# class ActionAskForCategoryModification(Action):
#     def name(self) -> str:
#         return "action_ask_for_category_modification"

#     def run(self, dispatcher, tracker, domain):
#         grievance_list_cat = tracker.get_slot("grievance_list_cat")

#         if not grievance_list_cat:
#             dispatcher.utter_message(text="No categories selected.")
#             return []

#         # Display categories as buttons for modification
#         buttons = [
#             {"title": category, "payload": f"/modify_category{{\"category_modify\": \"{category}\"}}"}
#             for category in grievance_list_cat
#         ]
#         buttons.append({"title": "✅ Confirm & Continue", "payload": "/confirm_selection"})

#         dispatcher.utter_message(
#             text="Which category would you like to modify?",
#             buttons=buttons
#         )

#         return []
    
# class ActionSetCategoryToModify(Action):
#     def name(self) -> str:
#         return "action_set_category_to_modify"

#     def run(self, dispatcher, tracker, domain):
#         # selected_category = tracker.get_slot("category_modify")  # Extract from intent payload
#         # print("ActionSetCagoryToModify - from slot :", selected_category)
        
        
#         for c in LIST_OF_CATEGORIES:
#             if c in tracker.latest_message.get("text"):
#                 selected_category = c
#                 print("c extracted from message : " , c)
                
#         if not selected_category:
#             dispatcher.utter_message(text="No category selected.")
#             return []

#         # Set the category_to_modify slot
#         print("category_modify", selected_category)
#         return [SlotSet("category_modify", selected_category)]


# class ActionModifyOrDeleteCategory(Action):
#     def name(self) -> str:
#         return "action_modify_or_delete_category"

#     def run(self, dispatcher, tracker, domain):
#         category_modify = tracker.get_slot("category_modify")
#         try:
#             print('############ action_modify_or_delete_category ###########')
#             print("category_modify", category_modify)
#         except: 
#             pass
#         if not category_modify:
#             dispatcher.utter_message(text="No category selected for modification.")
#             return []

#         buttons = [
#             {"title": "🗑 Delete", "payload": "/delete_category"},
#             {"title": "✏ Change", "payload": "/change_category"},
#             {"title": "Cancel", "payload": "/cancel_modification"}
#         ]

#         dispatcher.utter_message(
#             text=f"You selected '{category_modify}'. Would you like to delete it or change it?",
#             buttons=buttons
#         )

#         print("old_category", category_modify)
#         return [SlotSet("old_category", category_modify)]
    
    
# class ActionChangeCategory(Action):
#     def name(self) -> str:
#         return "action_change_category"

#     def run(self, dispatcher, tracker, domain):
#         # Path to the lookup file
#         print('############ action_change_category ###########')

#         # Retrieve categories already selected and dismissed
        
#         print("old_category", tracker.get_slot("old_category"))
#         selected_categories = tracker.get_slot("grievance_list_cat") or []
#         dismissed_categories = tracker.get_slot("dismissed_categories") or []

#         # Filter out selected and dismissed categories
#         available_categories = [cat for cat in LIST_OF_CATEGORIES if cat not in selected_categories and cat not in dismissed_categories]

#         if not available_categories:
#             dispatcher.utter_message(text="⚠ No more categories available for selection.")
#             return []

#         # Generate buttons for category selection (limit to 10 for readability)
#         buttons = [{"title": cat, "payload": f'/set_apply_category_change{{"category": "{cat}"}}'} for cat in available_categories[:10]]

#         # Add a "Cancel" and a skip button
#         buttons = [{"title": "Cancel", "payload": "/cancel_modification_category"},
#                     {"title": "Skip this step", "payload": "/skip_category"}] + buttons

#         dispatcher.utter_message(
#             text="📋 Please select a new category from the list below:",
#             buttons=buttons
#         )

#         return []

        



