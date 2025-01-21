# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
import os
import openai
from typing import Any, Text, Dict, List
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Restarted, FollowupAction
from datetime import datetime


# Set up the OpenAI API key
openai.api_key = os.getenv("OPENAI_API_KEY")  # Load from environment variable
# File to store the last grievance ID
COUNTER_FILE = "grievance_counter.txt"

def get_next_grievance_number():
    # Get today's date in YYmmDD format
    today_date = datetime.now().strftime("%y%m%d")

    # Initialize grievance ID if the file doesn't exist or is empty
    if not os.path.exists(COUNTER_FILE) or os.stat(COUNTER_FILE).st_size == 0:
        initial_id = f"GR-{today_date}-0001"
        with open(COUNTER_FILE, "w") as f:
            f.write(initial_id)
        return initial_id

    # Read the last grievance ID
    with open(COUNTER_FILE, "r") as f:
        last_grievance_id = f.read().strip()

    try:
        # Validate format and parse the date and counter from the last grievance ID
        if not last_grievance_id.startswith("GR-"):
            raise ValueError(f"Invalid format in counter file: {last_grievance_id}")
        
        parts = last_grievance_id.split("-")
        if len(parts) != 3:
            raise ValueError(f"Invalid format in counter file: {last_grievance_id}")

        _, last_date, last_counter = parts
        last_counter_number = int(last_counter)

        # If the date is different from today, reset the counter
        if last_date != today_date:
            new_grievance_id = f"GR-{today_date}-0001"
        else:
            # Increment the counter if the date is the same
            new_counter_number = last_counter_number + 1
            new_grievance_id = f"GR-{today_date}-{new_counter_number:04d}"

    except Exception as e:
        # Handle any parsing error by resetting the counter
        print(f"Error parsing grievance ID: {e}. Resetting counter.")
        new_grievance_id = f"GR-{today_date}-0001"

    # Save the new grievance ID to the file
    with open(COUNTER_FILE, "w") as f:
        f.write(new_grievance_id)

    return new_grievance_id


class ActionStartGrievanceProcess(Action):
    def name(self) -> str:
        return "action_start_grievance_process"

    async def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(response="utter_start_grievance_process")
        return []


class ActionCaptureGrievanceText(Action):
    def name(self) -> Text:
        return "action_capture_grievance_text"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_input = tracker.latest_message.get("text")

        # Step 1: Save the free text grievance details
        grievance_details = user_input

        # Step 2: Call OpenAI API for summarization and categorization
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an assistant helping to summarize and categorize grievances."},
                    {"role": "user", "content": f"Summarize and categorize this grievance: {grievance_details}"}
                ]
            )

            result = response['choices'][0]['message']['content']
            summary, category = self.parse_summary_and_category(result)

            # Step 3: Validate category with the user
            buttons = [
                {"title": "Yes", "payload": "/affirm"},
                {"title": "No, choose another category", "payload": "/deny"},
                {"title": "Exit", "payload": "/exit_grievance_process"}
            ]

            dispatcher.utter_message(
                text=f"Here's the category I identified: '{category}'. Does this seem correct?",
                buttons=buttons
            )

            # Save the grievance details and initial category suggestion
            return [
                SlotSet("grievance_details", grievance_details),
                SlotSet("grievance_summary", summary),
                SlotSet("grievance_category", category)
            ]

        except Exception as e:
            dispatcher.utter_message(text="Sorry, there was an issue processing your grievance. Please try again.")
            print(f"OpenAI API Error: {e}")
            return []

    def parse_summary_and_category(self, result: str) -> (str, str):
        # Simple parsing logic to split the summary and category (can be improved)
        lines = result.split("\n")
        summary = lines[0].strip()
        category = lines[1].strip() if len(lines) > 1 else "General"

        return summary, category


class ActionValidateCategory(Action):
    def name(self) -> Text:
        return "action_validate_category"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Retrieve the current category slot value
        current_category = tracker.get_slot("grievance_category")

        # If there is no current category, suggest categories directly
        if not current_category:
            dispatcher.utter_message(text="No category has been assigned to your grievance yet.")
        else:
            # Ask the user to confirm the current category
            dispatcher.utter_message(
                text=f"The current category for your grievance is '{current_category}'. Is this correct?",
                buttons=[
                    {"title": "Yes", "payload": "/affirm"},
                    {"title": "No", "payload": "/deny"},
                    {"title": "Skip", "payload": "/skip"}
                ]
            )
            return []

        # If the user denies, suggest alternative categories
        buttons = [
            {"title": "Infrastructure", "payload": '/set_category{"grievance_category": "Infrastructure"}'},
            {"title": "Health", "payload": '/set_category{"grievance_category": "Health"}'},
            {"title": "Education", "payload": '/set_category{"grievance_category": "Education"}'},
            {"title": "Other", "payload": '/set_category{"grievance_category": "Other"}'},
            {"title": "Skip Category", "payload": "/skip"}
        ]

        dispatcher.utter_message(
            text="Please select the correct category for your grievance or skip if you're unsure:",
            buttons=buttons
        )

        return []

class ActionValidateSummary(Action):
    def name(self) -> Text:
        return "action_validate_summary"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Retrieve the grievance summary from the slot
        grievance_summary = tracker.get_slot("grievance_summary")

        # Default message if no summary exists
        if not grievance_summary:
            dispatcher.utter_message(text="No summary has been provided yet.")
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
    
class ActionEditGrievanceSummary(Action):
    def name(self) -> Text:
        return "action_edit_grievance_summary"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Retrieve the current grievance summary from the slot
        current_summary = tracker.get_slot("grievance_summary")

        # Provide the current summary if available
        if current_summary:
            dispatcher.utter_message(
                text=f"Here is the current summary:\n\n'{current_summary}'\n\nPlease provide the updated summary or type 'skip' to proceed without updating."
            )
        else:
            dispatcher.utter_message(
                text="There is no summary yet. Please provide a new summary for your grievance or type 'skip' to proceed without a summary."
            )

        return []


class ActionSubmitGrievance(Action):
    def name(self) -> Text:
        return "action_submit_grievance"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Retrieve grievance details, summary, and category from slots
        grievance_details = tracker.get_slot("grievance_details")
        grievance_summary = tracker.get_slot("grievance_summary")
        grievance_category = tracker.get_slot("grievance_category")

        # Generate a unique grievance ID
        grievance_id = get_next_grievance_number()

        # Construct the confirmation message
        confirmation_message = f"Your grievance has been filed successfully.\n\n**Grievance ID:** {grievance_id}\n"

        if grievance_summary:
            confirmation_message += f"**Summary:** {grievance_summary}\n"
        else:
            confirmation_message += "**Summary:** [Not Provided]\n"

        if grievance_category:
            confirmation_message += f"**Category:** {grievance_category}\n"
        else:
            confirmation_message += "**Category:** [Not Provided]\n\nYou can add the category later if needed."

        if grievance_details:
            confirmation_message += f"**Details:** {grievance_details}\n"

        confirmation_message += "\nOur team will review it shortly and contact you if more information is needed."

        # Send the confirmation message
        dispatcher.utter_message(text=confirmation_message)

        # Set the grievance ID in the slot
        return [SlotSet("grievance_id", grievance_id)]


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
        return []

class ActionSetCategory(Action):
    def name(self) -> str:
        return "action_set_category"

    async def run(self, dispatcher, tracker, domain):
        grievance_category = tracker.get_slot("grievance_category")
        return [SlotSet("grievance_category", grievance_category)]