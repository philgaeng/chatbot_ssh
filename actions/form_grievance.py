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
from actions.constants import GRIEVANCE_STATUS
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from .db_actions import GrievanceDB
from datetime import datetime
import traceback

#define and load variables

load_dotenv('/home/ubuntu/nepal_chatbot/.env')
open_ai_key = os.getenv("OPENAI_API_KEY")

#load the categories
classification_data = load_classification_data()
LIST_OF_CATEGORIES = load_categories_from_lookup()

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
        # Only set the slot, no messaging
        return [SlotSet("verification_context", "new_user")]
    
############################ STEP 1 - GRIEVANCE FORM DETAILS ############################

class ValidateGrievanceDetailsForm(BaseFormValidationAction):
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
    
    async def extract_grievance_new_detail(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        latest_message = tracker.latest_message
        if latest_message:
            # Get the latest message and inten
            input_text = latest_message.get("text")
            intent = latest_message.get("intent")
            
            if input_text == "/start_grievance_process":
                dispatcher.utter_message(text="Great! Let's start by understanding your grievance...")
            print("######################### EXTRACT GRIEVANCE NEW DETAIL ##############")
            
            
            
            print(f"Latest message: {input_text}")
            print(f"Intent: {intent}")
            print(f"grievance_details: {tracker.get_slot('grievance_details')}")
            
            # Only extract when this slot is requested
            if tracker.get_slot("requested_slot") == "grievance_new_detail":
                return await self._handle_slot_extraction(
                "grievance_new_detail",
                tracker,
                dispatcher,
                domain,
                skip_value=True  # When skipped, assume confirmed
            )

        
            return {}
        return {}
    # async def set_slot_validation_context(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

    #     return [SlotSet("verification_context", None)]

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
        if "/submit_details" in slot_value:
            print("######################### LAST VALIDATION ##############")
            print("🎯 FORM: Handling submit_details intent")
            dispatcher.utter_message(text="Calling OpenAI for classification ... Please wait a few seconds...")
            current_temp = tracker.get_slot('grievance_temp')
            print(f"grievance_temp: {current_temp}")
            print(f"grievance_details: {current_temp}")
            print("########################################################")
            return {
                "grievance_new_detail": "completed",
                "grievance_details": current_temp,
            }

        # Handle valid grievance text
        if slot_value and not slot_value.startswith('/'):
            print("✅ FORM: Processing valid grievance text")
            print(f"slot_value: {slot_value}")
            updated_temp = self._update_grievance_text(current_temp, slot_value)
            self._show_options_buttons(dispatcher)
            
            print("🔄 FORM: Returning updated slots")
            print(f"Updated grievance_temp: {updated_temp}")
            
            return {
                "grievance_new_detail": None,
                "grievance_temp": updated_temp
            }
        if not slot_value or slot_value == "/start_grievance_process":
            dispatcher.utter_message(text="Great! Let's start by understanding your grievance...")
        # Handle invalid inputs - mostly payloads
        print("⚠️ FORM: Invalid input detected")
        print(f"Slot value: {slot_value}")
        print(f"update grievance details: {current_temp}")
        
        if slot_value == "/add_more_details":
            dispatcher.utter_message(text="Please enter more details...")
        
        return {"grievance_new_detail": None}

    def _show_options_buttons(self, dispatcher: CollectingDispatcher) -> None:
        """Helper method to show the standard options buttons."""
        print("\n🔘 FORM: Showing options buttons")
        dispatcher.utter_message(
            text="Thank you for your entry. Do you want to add more details to your grievance, such as:\n"
                 "- Location information\n"
                 "- Persons involved\n"
                 "- Quantification of damages (e.g., number of bags of rice lost)\n"
                 "- Monetary value of damages",
            buttons=[
                {"title": "File as is", "payload": "/submit_details"},
                {"title": "Add more details", "payload": "/add_more_details"},
                {"title": "Cancel filing", "payload": "/exit_without_filing"}
            ]
        )

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

class ValidateGrievanceSummaryForm(BaseFormValidationAction):
        
    def name(self) -> Text:
        return "validate_grievance_summary_form"
    
    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        print("######################### REQUESTED SLOTS ##############")
        requested_slot = tracker.get_slot("requested_slot")
        print(f"requested_slot: {requested_slot}")
        if not requested_slot:
            requested_slot = ["grievance_list_cat", "grievance_list_cat_confirmed"]
        if tracker.get_slot("grievance_list_cat_confirmed") in ["slot_deleted", "slot_added"]:
            requested_slot.append("grievance_cat_modify")
        if tracker.get_slot("grievance_list_cat_confirmed") in ["slot_skipped", "slot_confirmed"]:
            requested_slot.append("grievance_summary_confirmed", "grievance_summary_temp", "grievance_summary")
        # if tracker.get_slot("grievance_summary_confirmed") == "slot_edited":
        #     requested_slot.append("grievance_summary_temp")
        #remove duplicates  
        requested_slot = list(set(requested_slot))
        return requested_slot
        
    ############ STEP 1 - PROCESSING GRIEVANCE DETAILS WITH OPENAI AND POPULATE SLOTS ############
    
    def parse_summary_and_category(self, response: str):
        """
        Parses OpenAI response directly into a structured dictionary.
        Expects response to be a valid JSON dictionary.
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

    async def validate_grievance_list_cat(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        print("################### VALIDATE GRIEVANCE LIST CAT ##########")
        if tracker.get_slot("requested_slot") == "grievance_list_cat":
            grievance_details = tracker.get_slot("grievance_temp")
            print(f"grievance_details_from_grievance_temp: {grievance_details}")
            
            if not grievance_details:
                dispatcher.utter_message(text="There was an issue processing your grievance. Please try again.",
                                        buttons=[
                                            {"title": "Try again", "payload": "/start_grievance_process"},
                                                {"title": "Exit", "payload": "/exit_without_filing"}
                                                ]
                                            )
                return {}

            print(f"Raw - grievance_details: {grievance_details}")
            # Step 1: Call OpenAI for classification
            result = await self._call_openai_for_classification(grievance_details)
            
            if result is None:
                dispatcher.utter_message(text="⚠ Sorry, there was an issue processing your grievance. Please try again.")
                return {}

            print(f"Raw - gpt message: {result}")

            # Step 2: Parse the results and fill the slots
            result_dict = self.parse_summary_and_category(result)
            print(result_dict)



            # Step 3: Dispatch the message to the user to validate the categories
            grievance_list_cat = result_dict["list_categories"]
            n = len(grievance_list_cat)

            if n > 0:
                category_text = "\n".join([v for v in grievance_list_cat])
                response_message = f"I have identified {n} categories:\n{category_text}\nDoes this seem correct?"
                
                dispatcher.utter_message(text=response_message,
                                        buttons=[
                                            {"title": "Yes", "payload": "/submit_category"},
                                            {"title": "Add category", "payload": "/add_category"},
                                            {"title": "Delete category", "payload": "/delete_category"},
                                            {"title": "Exit", "payload": "/skip"}
                                        ])
                
                return {
                    "grievance_details": grievance_details,
                    "grievance_summary_temp": result_dict["grievance_summary"],
                    "grievance_list_cat": result_dict["list_categories"]
                }
            else:
                dispatcher.utter_message(text="I have not identified any category",
                                        buttons=[
                                            {"title": "Process without category", "payload": "/submit_category"},
                                            {"title": "Add category", "payload": "/add_category"},
                                            {"title": "Exit", "payload": "/skip"}
                                        ])
            return {
                "grievance_details": grievance_details,
                "grievance_summary_temp": result_dict["grievance_summary"],
                "grievance_list_cat" : []
                    }
        return {}


            
    async def extract_grievance_list_cat_confirmed(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if tracker.get_slot("requested_slot") == "grievance_list_cat_confirmed":
            return await self._handle_string_slot_extraction(
                "grievance_list_cat_confirmed",
                tracker,
                dispatcher,
                domain
            )
        return {}
    
    async def validate_grievance_list_cat_confirmed(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        
        #initialize the list of cat
        list_of_cat = tracker.get_slot("grievance_list_cat")
        list_of_cat_to_add = LIST_OF_CATEGORIES if not list_of_cat else [cat for cat in LIST_OF_CATEGORIES if cat not in list_of_cat]
            
        if slot_value == 'delete_category':
            
            if not list_of_cat:
                dispatcher.utter_message(text="No categories selected. Skipping this step.")
                return {"grievance_list_cat_confirmed": "slot_skipped"}
            else:
                buttons = [
                    {"title": category, "payload": f"/delete_category{{\"category_to_delete\": \"{category}\"}}"}
                    for category in list_of_cat
                ]
                buttons.append({"title": "Skip", "payload": "/skip"})

                dispatcher.utter_message(
                    text="Which category would you like to delete?",
                    buttons=buttons
                )
                return {
                    "grievance_list_cat_confirmed": "slot_deleted",
                    # "requested_slot": requested_slot
                }
                
        if slot_value == "add_category":
            list_cat_to_add = [cat for cat in LIST_OF_CATEGORIES if cat not in list_of_cat]
            #display the new category to the user with buttons
            buttons = [{"title": cat, "payload": f'/{"category": "{cat}"}'} for cat in list_cat_to_add[:10]]
            dispatcher.utter_message(
                text="Please select the new category from the list below:",
                buttons=buttons
            )
            
            return {
                "grievance_list_cat_confirmed": "slot_added",
            }
            
        # Dispatch the message to the user to validate the summary
        if slot_value in ["slot_skipped", "slot_confirmed"]:
            current_summary = tracker.get_slot("grievance_summary_temp")

            if current_summary:
                dispatcher.utter_message(
                    text=f"Here is the current summary:\n\n'{current_summary}'\n\n Choose your next action.",
                    buttons=[
                        {"title": "Edit summary", "payload": "/edit_summary"},
                        {"title": "Validate summary", "payload": "/validate_summary"},
                        {"title": "Skip", "payload": "/skip"}
                    ]
                )
                return {
                "grievance_list_cat_confirmed": slot_value
            }
            else:
                dispatcher.utter_message(
                    text="There is no summary yet. Please type a new summary for your grievance or type 'skip' to proceed without a summary."
                )
                return {
                    "grievance_list_cat_confirmed": "slot_value",
                    "grievance_summary_temp": None,
                    "grievance_summary_confirmed": "slot_edited"
                }
           
        return {}
    
    
    
    async def extract_grievance_cat_modify(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if tracker.get_slot("requested_slot") == "grievance_choose_category_to_modify":
            return await self._handle_string_slot_extraction(
                "grievance_choose_category_to_modify",
                tracker,
                dispatcher,
                domain
            )
        return {}
    
    
    async def validate_grievance_cat_modify(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        
        if slot_value == "slot_skipped":
            return {
                "grievance_list_cat_confirmed": "slot_skipped",
                "grievance_cat_modify": "slot_skipped"
            }
        
        for c in LIST_OF_CATEGORIES:
            if c in slot_value:
                selected_category = c
                print("c extracted from message : " , c)
                
        if not selected_category:
            dispatcher.utter_message(text="No category selected. skipping this step.")
            return {"grievance_cat_modify": "slot_skipped",
                    "grievance_list_cat_confirmed": "slot_skipped"
                    }
        #case 2: delete the category
        if tracker.get_slot("grievance_list_cat_confirmed") == "slot_deleted":
            #delete the category
            list_of_cat = tracker.get_slot("grievance_list_cat")
            list_of_cat.remove(selected_category)
            
        #case 3: add the category
        if tracker.get_slot("grievance_list_cat_confirmed") == "slot_added":
            list_of_cat.append(selected_category)
        
        if tracker.get_slot("grievance_list_cat_confirmed") in ["slot_skipped", "slot_confirmed"]:
            #update the list of cat
            return {
                "grievance_list_cat_confirmed": None,
                "grievance_list_cat": list_of_cat
            }
        return {}

    
    async def extract_grievance_summary_confirmed(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if tracker.get_slot("requested_slot") == "grievance_summary_confirmed":
            return await self._handle_string_slot_extraction(
                "grievance_summary_confirmed",
                tracker,
                dispatcher,
                domain
            )
        return {}
    
    
    async def validate_grievance_summary_comfirmed(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        if slot_value == "slot_skipped":
            return {
                "grievance_summary_confirmed": "slot_skipped",
                "grievance_summary": "slot_skipped"
            }
        if slot_value == "slot_confirmed":
            return {
                "grievance_summary_confirmed": "slot_confirmed",
                "grievance_summary": tracker.get_slot("grievance_summary_temp")
            }
        
        if slot_value == "slot_edited":
            dispatcher.utter_message(text="Please enter the new summary and confirm again.")
            return {
                "grievance_summary_confirmed": "slot_edited",
                "grievance_summary_temp": None
            }
            
                
        return {}
    
    async def extract_grievance_summary_temp(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if tracker.get_slot("requested_slot") == "grievance_summary_temp":
            return await self._handle_string_slot_extraction(
                "grievance_summary_temp",
                tracker,
                dispatcher,
                domain
            )
        return {}
    
    async def validate_grievance_summary_temp(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        if slot_value == "slot_skipped":
            return {
                "grievance_summary_confirmed": "slot_skipped",
                "grievance_summary": "slot_skipped"
            }
        
        if slot_value:
            return {
                "grievance_summary_confirmed": "slot_edited",
                "grievance_summary_temp": slot_value
            }


# class ActionAskForUserSummary(Action):
#     def name(self) -> Text:
#         return "action_ask_for_user_summary"

#     async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#         """Step 1: Ask the user to provide a summary"""

#         current_summary = tracker.get_slot("grievance_summary")

#         if current_summary:
#             dispatcher.utter_message(
#                 text=f"Here is the current summary:\n\n'{current_summary}'\n\nPlease type a new summary or type 'skip' to keep it."
#             )
#         else:
#             dispatcher.utter_message(
#                 text="There is no summary yet. Please type a new summary for your grievance or type 'skip' to proceed without a summary."
#             )

#         # Activate form so Rasa expects `grievance_summary`
#         return [SlotSet("grievance_summary", None), ActiveLoop("edit_summary_form")]

    

# class ActionEditGrievanceSummary(Action):
#     def name(self) -> Text:
#         return "action_edit_grievance_summary"

#     async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#         """Step 2: Handle the user's response and update the slot"""

#         new_summary = tracker.get_slot("grievance_summary")

#         if new_summary:
#             dispatcher.utter_message(text=f"✅ Your grievance summary has been updated to:\n\n'{new_summary}'")
#             return [SlotSet("grievance_summary", new_summary), ActiveLoop(None)]  # Deactivate form
        
#         elif new_summary and new_summary.lower() == "skip":
#             dispatcher.utter_message(text="✅ Keeping the existing grievance summary.")
#             return [ActiveLoop(None)]  # Deactivate form
        
#         return []


############################ STEP 4 - SUBMIT GRIEVANCE ############################
class ActionSubmitGrievance(Action):
    def __init__(self):
        self.db = GrievanceDB() 
        
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
            'grievance_summary': tracker.get_slot('grievance_summary'),
            'grievance_details': tracker.get_slot('grievance_details'),
            'grievance_category': tracker.get_slot('grievance_list_cat'),
            'grievance_claimed_amount': tracker.get_slot('grievance_claimed_amount'),
            'grievance_location': f"{user_data['user_municipality']}, Ward {user_data['user_ward']}"
        }

        return user_data, grievance_data

    def create_confirmation_message(self, grievance_id: str, grievance_data: Dict[str, Any], user_email: str = None) -> str:
        """Create a formatted confirmation message."""
        message = [
            f"Your grievance has been filed successfully.",
            f"\n**Grievance ID:** {grievance_id}"
        ]

        # Add summary if available
        if grievance_data['grievance_summary']:
            message.append(f"**Summary:** {grievance_data['grievance_summary']}")
        else:
            message.append("**Summary:** [Not Provided]")

        # Add category if available
        if grievance_data['grievance_category']:
            message.append(f"**Category:** {grievance_data['grievance_category']}")
        else:
            message.append("**Category:** [Not Provided]\nYou can add the category later if needed.")

        # Add details if available
        if grievance_data['grievance_details']:
            message.append(f"**Details:** {grievance_data['grievance_details']}")

        message.append("\nOur team will review it shortly and contact you if more information is needed.")

        # Add email notification info if available
        if user_email:
            message.append(f"\nA confirmation email will be sent to {user_email}")

        return "\n".join(message)

    def determine_follow_up_actions(self, user_email: str) -> List[Dict[Text, Any]]:
        """Determine which follow-up actions to trigger."""
        base_actions = [
            FollowupAction("action_send_system_notification_email")
        ]
        
        if self.is_valid_email(user_email):
            base_actions.append(FollowupAction("action_send_grievance_recap_email"))
            
        return base_actions

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        print("\n=================== Submitting Grievance ===================")
        
        try:
            # Collect grievance data
            user_data, grievance_data = self.collect_grievance_data(tracker)
            user_email = user_data.get('user_contact_email')

            print(f"📝 User data: {user_data}")
            print(f"📝 Grievance data: {grievance_data}")
            
            # Create grievance in database
            grievance_id = self.db.create_grievance(user_data, grievance_data)
            
            if not grievance_id:
                raise Exception("Failed to create grievance in database")

            print(f"✅ Grievance created successfully with ID: {grievance_id}")

            # Create confirmation message
            confirmation_message = self.create_confirmation_message(
                grievance_id, 
                grievance_data,
                user_email if self.is_valid_email(user_email) else None
            )
            
            # Send confirmation message
            dispatcher.utter_message(text=confirmation_message)

            # Prepare events
            events = [
                SlotSet("grievance_id", grievance_id),
                SlotSet("grievance_status", GRIEVANCE_STATUS["SUBMITTED"])
            ]
            
            # Add follow-up actions
            events.extend(self.determine_follow_up_actions(user_email))

            return events

        except Exception as e:
            print(f"❌ Error submitting grievance: {str(e)}")
            print(f"Traceback: {traceback.format_exc()}")
            dispatcher.utter_message(
                text="I apologize, but there was an error submitting your grievance. "
                "Please try again or contact support."
            )
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

        
# class ActionApplyCategoryChange(Action):
#     def name(self) -> str:
#         return "action_apply_category_change"

#     def run(self, dispatcher, tracker, domain):
#         old_category = tracker.get_slot("old_category")
#         selected_categories = tracker.get_slot("grievance_list_cat") or []
#         dismissed_categories = tracker.get_slot("dismissed_categories") or []
#         new_category = None

#         # Get the exact category from the message
#         message_text = tracker.latest_message.get("text", "").strip()

#         # Exact matching instead of partial
#         for category in LIST_OF_CATEGORIES:
#             if message_text == category:
#                 new_category = category
#                 break

#         if not new_category:
#             dispatcher.utter_message(text="⚠ Please select a valid category from the list.")
#             return []

#         # Update category selection
#         if old_category in selected_categories:
#             selected_categories.remove(old_category)
#             dismissed_categories.append(old_category)
#             selected_categories.append(new_category)
            
#             dispatcher.utter_message(text=f"✅ '{old_category}' has been changed to '{new_category}'.")
#         else:
#             dispatcher.utter_message(text=f"⚠ '{old_category}' was not found in the selected categories.")

#         return [
#             SlotSet("grievance_list_cat", selected_categories),
#             SlotSet("category_modify", None),
#             SlotSet("old_category", None),  # Clear the old category
#             SlotSet("new_category", None),  # Clear the new category
#             SlotSet("dismissed_categories", dismissed_categories)
#         ]


# class ActionConfirmCategories(Action):
#     def name(self) -> str:
#         return "action_confirm_categories"

#     def run(self, dispatcher, tracker, domain):
#         selected_categories = tracker.get_slot("grievance_list_cat")
        
#           # Remove None values from the list
#         selected_categories = [cat for cat in selected_categories if cat]

#         if not selected_categories:
#             dispatcher.utter_message(text="No categories remain selected.")
#             return []

#         buttons = [
#             {"title": "✅ Confirm & Continue", "payload": "/finalize_categories"},
#             {"title": "Modify", "payload": "/modify_categories"}
#         ]

#         dispatcher.utter_message(
#             text=f"📋 Here are your updated categories:\n- " + "\n- ".join(selected_categories) + "\n\nDoes this look correct?",
#             buttons=buttons
#         )

#         return []
    

# class ActionDeleteCategory(Action):
#     def name(self) -> str:
#         return "action_delete_category"

#     async def run(self, dispatcher, tracker, domain):
#         category_to_delete = tracker.get_slot("category_modify")
#         grievance_list_cat = tracker.get_slot("grievance_list_cat") or []
#         dismissed_categories = tracker.get_slot("dismissed_categories") or []

#         if category_to_delete in grievance_list_cat:
#             grievance_list_cat.remove(category_to_delete)
#             dispatcher.utter_message(text=f"✅ '{category_to_delete}' has been removed.")

#             # Add to dismissed categories if not already present
#             if category_to_delete not in dismissed_categories:
#                 dismissed_categories.append(category_to_delete)

#         else:
#             dispatcher.utter_message(text=f"⚠ '{category_to_delete}' was not found in the selected categories.")

#         # Update slots
#         return [
#             SlotSet("grievance_list_cat", grievance_list_cat), 
#             SlotSet("category_modify", None),
#             SlotSet("dismissed_categories", dismissed_categories)  # Track dismissed category
#         ]
        
# class ActionCancelModificationCategory(Action):
#     def name(self) -> str:
#         return "action_cancel_modification_category"

#     async def run(self, dispatcher, tracker, domain):
#         dispatcher.utter_message(text="🚫 Category modification has been canceled.Keeping the existing categories.")
#         return [SlotSet("category_modify", None)]
    
# class ActionSkipCategory(Action):
#     def name(self) -> str:
#         return "action_skip_category"

#     async def run(self, dispatcher, tracker, domain):
#         dispatcher.utter_message(text="⏭ Skipping category selection. You can update it later if needed. \n Let's proceed with your location details")
#         return []

