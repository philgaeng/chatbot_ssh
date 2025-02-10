# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
import re
import logging
import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from typing import Any, Text, Dict, List, Tuple
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

#define and load variables

load_dotenv('/home/ubuntu/nepal_chatbot/.env')
open_ai_key = os.getenv("OPENAI_API_KEY")

#load the categories
classification_data = load_classification_data()
list_categories_global = load_categories_from_lookup()

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
    

class ActionStartGrievanceProcess(Action):
    def name(self) -> Text:
        return "action_start_grievance_process"

    async def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(response="utter_start_grievance_process")
        return [SlotSet("verification_context", "new_user")]

class ActionCaptureGrievanceText(Action):
    def name(self) -> Text:
        return "action_capture_grievance_text"
    
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
        

    def _call_openai_for_classification(self, grievance_details: str):
        """
        Calls OpenAI API to classify the grievance details into predefined categories.
        """
        predefined_categories = classification_data  # Extract unique categories
        category_list_str = "\n".join(f"- {c}" for c in predefined_categories)  # Format as list

        try:
            client = OpenAI(api_key=open_ai_key)

            response = client.chat.completions.create(
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
            return None  # Return None in case of failure

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_input = tracker.latest_message.get("text")
        print(user_input)

        # Step 1: Save the free text grievance details
        grievance_details = user_input

        print("################### action_capture_grievance_text ##########")

        # Call OpenAI for category classification
        result = self._call_openai_for_classification(grievance_details)
        
        if result is None:
            dispatcher.utter_message(text="⚠ Sorry, there was an issue processing your grievance. Please try again.")
            return []

        print(f"Raw - gpt message: {result}")

        # Step 2: Parse the results and fill the slots
        result_dict = self.parse_summary_and_category(result)
        print(result_dict)

        slots = [
            SlotSet("grievance_details", grievance_details),
            SlotSet("grievance_summary", result_dict["grievance_summary"]),
            SlotSet("list_of_cat_for_summary", result_dict["list_categories"])
        ]

        # Step 3: Validate category with the user
        list_of_cat_for_summary = result_dict["list_categories"]
        n = len(list_of_cat_for_summary)

        if n > 0:
            category_text = "\n".join([v for v in list_of_cat_for_summary])
            response_message = f"I have identified {n} categories:\n{category_text}\nDoes this seem correct?"
            
            dispatcher.utter_message(text=response_message,
                                     buttons=[
                                         {"title": "Yes", "payload": "/submit_category"},
                                         {"title": "Modify", "payload": "/modify_categories"},
                                         {"title": "Exit", "payload": "/exit_grievance_process"}
                                     ])
            
            print(f"Slot - grievance_summary: {result_dict['grievance_summary']}")
            return slots
        else:
            dispatcher.utter_message(text="I have not identified any category",
                                     buttons=[
                                         {"title": "Process without category", "payload": "/submit_category"},
                                         {"title": "Edit category", "payload": "/change_category"},
                                         {"title": "Exit", "payload": "/exit_grievance_process"}
                                     ])

        return []




class ActionValidateSummary(Action):
    def name(self) -> Text:
        return "action_validate_summary"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Retrieve the grievance summary from the slot
        grievance_summary = tracker.get_slot("grievance_summary")
        print(grievance_summary)
        # Default message if no summary exists
        if not grievance_summary:
            dispatcher.utter_message(text="No summary has been provided yet.",
            buttons = [
            {"title": "No, let me edit", "payload": "/edit_grievance_summary"},
            {"title": "Skip", "payload": "/skip_summary"}
            ]
            )
            return []

        # Ask the user to confirm the summary with dynamic buttons
        buttons = [
            {"title": "Yes", "payload": "/validate_summary"},
            {"title": "No, let me edit", "payload": "/edit_grievance_summary"},
            {"title": "Skip", "payload": "/skip_summary"}
        ]

        dispatcher.utter_message(
            text=f"Here's the summary of your grievance: '{grievance_summary}'. Does this look correct?",
            buttons=buttons
        )

        return []
    

class ActionAskForUserSummary(Action):
    def name(self) -> Text:
        return "action_ask_for_user_summary"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """Step 1: Ask the user to provide a summary"""

        current_summary = tracker.get_slot("grievance_summary")

        if current_summary:
            dispatcher.utter_message(
                text=f"Here is the current summary:\n\n'{current_summary}'\n\nPlease type a new summary or type 'skip' to keep it."
            )
        else:
            dispatcher.utter_message(
                text="There is no summary yet. Please type a new summary for your grievance or type 'skip' to proceed without a summary."
            )

        # Activate form so Rasa expects `grievance_summary`
        return [SlotSet("grievance_summary", None), ActiveLoop("edit_summary_form")]

    

class ActionEditGrievanceSummary(Action):
    def name(self) -> Text:
        return "action_edit_grievance_summary"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """Step 2: Handle the user's response and update the slot"""

        new_summary = tracker.get_slot("grievance_summary")

        if new_summary:
            dispatcher.utter_message(text=f"✅ Your grievance summary has been updated to:\n\n'{new_summary}'")
            return [SlotSet("grievance_summary", new_summary), ActiveLoop(None)]  # Deactivate form
        
        elif new_summary and new_summary.lower() == "skip":
            dispatcher.utter_message(text="✅ Keeping the existing grievance summary.")
            return [ActiveLoop(None)]  # Deactivate form
        
        return []



class ActionSubmitGrievance(Action):
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
            'grievance_category': tracker.get_slot('list_of_cat_for_summary'),
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

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Collect grievance data
        user_data, grievance_data = self.collect_grievance_data(tracker)
        user_email = user_data.get('user_contact_email')

        try:
            # Create grievance in database
            grievance_id = db.create_grievance(user_data, grievance_data)
            
            if not grievance_id:
                raise Exception("Failed to create grievance in database")

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
            print(f"Error submitting grievance: {e}")
            dispatcher.utter_message(
                text="I apologize, but there was an error submitting your grievance. "
                "Please try again or contact support."
            )
            return []


class ActionHandleSkip(Action):
    def name(self) -> Text:
        return "action_handle_skip"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        skip_count = tracker.get_slot("skip_count") or 0
        skip_count += 1

        if skip_count >= 2:
            dispatcher.utter_message(response="utter_ask_file_as_is")
            return [SlotSet("skip_count", 0)]
        else:
            dispatcher.utter_message(response="utter_skip_confirmation")
            return [SlotSet("skip_count", skip_count)]




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

    

class ActionAskForCategoryModification(Action):
    def name(self) -> str:
        return "action_ask_for_category_modification"

    def run(self, dispatcher, tracker, domain):
        list_of_cat_for_summary = tracker.get_slot("list_of_cat_for_summary")

        if not list_of_cat_for_summary:
            dispatcher.utter_message(text="No categories selected.")
            return []

        # Display categories as buttons for modification
        buttons = [
            {"title": category, "payload": f"/modify_category{{\"category_modify\": \"{category}\"}}"}
            for category in list_of_cat_for_summary
        ]
        buttons.append({"title": "✅ Confirm & Continue", "payload": "/confirm_selection"})

        dispatcher.utter_message(
            text="Which category would you like to modify?",
            buttons=buttons
        )

        return []
    
class ActionSetCategoryToModify(Action):
    def name(self) -> str:
        return "action_set_category_to_modify"

    def run(self, dispatcher, tracker, domain):
        # selected_category = tracker.get_slot("category_modify")  # Extract from intent payload
        # print("ActionSetCagoryToModify - from slot :", selected_category)
        
        # if not selected_category:
            #extract from message
            # Load categories from the lookup table
        category_list = list_categories_global #load the categories
        
        for c in category_list:
            if c in tracker.latest_message.get("text"):
                selected_category = c
                print("c extracted from message : " , c)
                
        if not selected_category:
            dispatcher.utter_message(text="No category selected.")
            return []

        # Set the category_to_modify slot
        print("category_modify", selected_category)
        return [SlotSet("category_modify", selected_category)]


class ActionModifyOrDeleteCategory(Action):
    def name(self) -> str:
        return "action_modify_or_delete_category"

    def run(self, dispatcher, tracker, domain):
        category_modify = tracker.get_slot("category_modify")
        try:
            print('############ action_modify_or_delete_category ###########')
            print("category_modify", category_modify)
        except: 
            pass
        if not category_modify:
            dispatcher.utter_message(text="No category selected for modification.")
            return []

        buttons = [
            {"title": "🗑 Delete", "payload": "/delete_category"},
            {"title": "✏ Change", "payload": "/change_category"},
            {"title": "Cancel", "payload": "/cancel_modification"}
        ]

        dispatcher.utter_message(
            text=f"You selected '{category_modify}'. Would you like to delete it or change it?",
            buttons=buttons
        )

        print("old_category", category_modify)
        return [SlotSet("old_category", category_modify)]
    
    
class ActionChangeCategory(Action):
    def name(self) -> str:
        return "action_change_category"

    def run(self, dispatcher, tracker, domain):
        # Path to the lookup file
        print('############ action_change_category ###########')
        # Load categories from the lookup table
        category_list = list_categories_global
        # Retrieve categories already selected and dismissed
        
        print("old_category", tracker.get_slot("old_category"))
        selected_categories = tracker.get_slot("list_of_cat_for_summary") or []
        dismissed_categories = tracker.get_slot("dismissed_categories") or []

        # Filter out selected and dismissed categories
        available_categories = [cat for cat in category_list if cat not in selected_categories and cat not in dismissed_categories]

        if not available_categories:
            dispatcher.utter_message(text="⚠ No more categories available for selection.")
            return []

        # Generate buttons for category selection (limit to 10 for readability)
        buttons = [{"title": cat, "payload": f'/set_apply_category_change{{"category": "{cat}"}}'} for cat in available_categories[:10]]

        # Add a "Cancel" and a skip button
        buttons = [{"title": "Cancel", "payload": "/cancel_modification_category"},
                    {"title": "Skip this step", "payload": "/skip_category"}] + buttons

        dispatcher.utter_message(
            text="📋 Please select a new category from the list below:",
            buttons=buttons
        )

        return []

        
class ActionApplyCategoryChange(Action):
    def name(self) -> str:
        return "action_apply_category_change"

    def run(self, dispatcher, tracker, domain):
        old_category = tracker.get_slot("old_category")
        selected_categories = tracker.get_slot("list_of_cat_for_summary") or []
        dismissed_categories = tracker.get_slot("dismissed_categories") or []
        new_category = None
        print('############ action_apply_category_change ###########')
        print("list_of_cat_for_summary before update: ", selected_categories)
        print("old_category", old_category)
        print("new_category_from_message", new_category)
        print("list_of_cat_for_summary", selected_categories)

        category_list = list_categories_global #load the categories
        
        for c in category_list:
            if c in tracker.latest_message.get("text", ""):
                new_category = c
                print("c extracted from message : " , c)
            

        # Ensure new_category is valid before updating
        if not new_category:
            dispatcher.utter_message(text="⚠ No valid category was selected.")
            return []

        # Update category selection
        if old_category in selected_categories:
            selected_categories.remove(old_category)
            dismissed_categories.append(old_category)
            selected_categories.append(new_category)
            print("list_of_cat_for_summary after update: ", selected_categories)

            dispatcher.utter_message(text=f"✅ '{old_category}' has been changed to '{new_category}'.")
        else:
            dispatcher.utter_message(text=f"⚠ '{old_category}' was not found in the selected categories.")

        return [
            SlotSet("list_of_cat_for_summary", selected_categories),
            SlotSet("category_modify", None),
            SlotSet("old_category", old_category),
            SlotSet("new_category", new_category),
            SlotSet("dismissed_categories", dismissed_categories)
        ]


class ActionConfirmCategories(Action):
    def name(self) -> str:
        return "action_confirm_categories"

    def run(self, dispatcher, tracker, domain):
        selected_categories = tracker.get_slot("list_of_cat_for_summary")
        
          # Remove None values from the list
        selected_categories = [cat for cat in selected_categories if cat]

        if not selected_categories:
            dispatcher.utter_message(text="No categories remain selected.")
            return []

        buttons = [
            {"title": "✅ Confirm & Continue", "payload": "/finalize_categories"},
            {"title": "Modify", "payload": "/modify_categories"}
        ]

        dispatcher.utter_message(
            text=f"📋 Here are your updated categories:\n- " + "\n- ".join(selected_categories) + "\n\nDoes this look correct?",
            buttons=buttons
        )

        return []
    

class ActionDeleteCategory(Action):
    def name(self) -> str:
        return "action_delete_category"

    def run(self, dispatcher, tracker, domain):
        category_to_delete = tracker.get_slot("category_modify")
        list_of_cat_for_summary = tracker.get_slot("list_of_cat_for_summary") or []
        dismissed_categories = tracker.get_slot("dismissed_categories") or []

        if category_to_delete in list_of_cat_for_summary:
            list_of_cat_for_summary.remove(category_to_delete)
            dispatcher.utter_message(text=f"✅ '{category_to_delete}' has been removed.")

            # Add to dismissed categories if not already present
            if category_to_delete not in dismissed_categories:
                dismissed_categories.append(category_to_delete)

        else:
            dispatcher.utter_message(text=f"⚠ '{category_to_delete}' was not found in the selected categories.")

        # Update slots
        return [
            SlotSet("list_of_cat_for_summary", list_of_cat_for_summary), 
            SlotSet("category_modify", None),
            SlotSet("dismissed_categories", dismissed_categories)  # Track dismissed category
        ]
        
class ActionCancelModificationCategory(Action):
    def name(self) -> str:
        return "action_cancel_modification_category"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(text="🚫 Category modification has been canceled.Keeping the existing categories.")
        return [SlotSet("category_modify", None)]
    
class ActionSkipCategory(Action):
    def name(self) -> str:
        return "action_skip_category"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(text="⏭ Skipping category selection. You can update it later if needed. \n Let's proceed with your location details")
        return []