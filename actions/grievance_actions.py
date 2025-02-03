# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
import re
import os
from dotenv import load_dotenv
import openai
from openai import OpenAI
from typing import Any, Text, Dict, List
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, Restarted, FollowupAction, ActiveLoop
from datetime import datetime
import csv
import traceback
from actions.helpers import load_classification_data, load_categories_from_lookup

#define and load variables

load_dotenv('/home/ubuntu/nepal_chatbot/.env')
open_ai_key = os.getenv("OPENAI_API_KEY")

#load the categories
classification_data = load_classification_data()
list_categories_global = load_categories_from_lookup()

# File to store the last grievance ID
COUNTER_FILE = "grievance_counter.txt"


try:
    if open_ai_key:
        print("OpenAI key is loaded")
    else:
        raise ValueError("OpenAI key is not set")
    
except Exception as e:
    print(f"Error loading OpenAI API key: {e}")
    



 
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
    
    # def load_classification_data(self):
    #     """Loads grievance classification data from CSV into a dictionary"""
    #     categories = []
    #     try:
    #         with open(cat_path, "r", encoding="utf-8") as csvfile:
    #             reader = csv.DictReader(csvfile)
    #             for row in reader:
    #                 categories.append(row["Classification"].title() + " - " + row["Generic Grievance Name"].title())  # Normalize case
                    
    #         # Remove duplicates
    #         unique_categories = list(set(categories))

    #         # Save to lookup table
    #         lookup_file_path = "data/lookup_tables/list_category.txt"
    #         with open(lookup_file_path, "w", encoding="utf-8") as lookup_file:
    #             lookup_file.write("\n".join(unique_categories))

    #         print(f"✅ Lookup table updated: {lookup_file_path}")
            
    #     except Exception as e:
    #         print(f"Error loading CSV file: {e}")
    #         traceback.print_exc()
    #     return list(set(categories))
    
    def parse_summary_and_category(self, result: str):
        """
        Parse the result from OpenAI to extract the grievance summary and categories into a structured dictionary.
        """

        # Extract category using regex
        category_match = re.search(r'Category.*?- END Category', result, re.DOTALL)
        category_text = category_match.group(0).replace("- END Category", "").strip() if category_match else ""

        # Extract summary using regex
        summary_match = re.search(r'Grievance Summary: (.*?)- END Summary', result, re.DOTALL)
        grievance_summary = summary_match.group(1).strip() if summary_match else ""
        print(grievance_summary)

        # Initialize result dictionary
        result_dict = {"grievance_summary": grievance_summary}
        

        # Process category string dynamically
        if category_text:
            category_list = category_text.split("Category ")
            category_list = [i for i in category_list if len(i)> 0 and "Category" not in i]
            print(category_list)
            # idx = 1
            for idx, category in enumerate(category_list, start =1):
                print(category)
                result_dict[f"category_{idx}"] = category.split(": ")[1].strip().strip(',') # Extract category name

        return result_dict

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        user_input = tracker.latest_message.get("text")
        print(user_input)
        # Step 1: Save the free text grievance details
        grievance_details = user_input

        # Step 1: use OpenAI but restrict the category choices
        predefined_categories = classification_data# Extract unique categories
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
                        Reply only with the categories, if many categories apply just list them with the following format:
                        Category 1: category, Category 2: category, Category 3: category etc when applicable - END Category
                        Step 2: summarize the grievance with simple and direct words so they can be understood with people with limited litteracy.
                        Provide your answer with the following format
                        Grievance Summary : lorum ipsum etc - END Summary
                    """}
                ],
                model="gpt-4",
            )

            result = response.choices[0].message.content.strip()

            print(f"Raw - gpt mesage : {result}")
            
            #Step 2 : parse the results and fill the slots
            
            result_dict = self.parse_summary_and_category(result)
            print(result_dict)
            temp_categories = [v for k, v in result_dict.items() if "category" in k.lower()]
            slots = [
                SlotSet("grievance_details", grievance_details),
                SlotSet("grievance_summary", result_dict["grievance_summary"]),
                SlotSet("temp_categories", temp_categories)
            ]

            # Step 3: Validate category with the user
            
            #prepare the response message
            # Format category display
            
            n = len(temp_categories)
            
            if n>0:
                category_text = "\n".join([f"- {v}" for v in temp_categories])
                response_message = f"I have identified {len(temp_categories)} categories \n " + category_text + "\n Does this seem correct?"
                
                dispatcher.utter_message(text= response_message,
                                        buttons= [
                    {"title": "Yes", "payload": "/submit_category"},
                    {"title": "Modify", "payload": "/modify_categories"},
                    {"title": "Exit", "payload": "/exit_grievance_process"}
                ])
                
                print(f"Slot - grievance_summary: {result_dict['grievance_summary']}")
                # Save the grievance details and initial category suggestion
                return slots
            else:
                dispatcher.utter_message(text= "I have not identified any category",
                                        buttons= [
                    {"title": "Process without category", "payload": "/submit_category"},
                    {"title": "Edit category", "payload": "/change_category"},
                    {"title": "Exit", "payload": "/exit_grievance_process"}
                ])

        except Exception as e:
            dispatcher.utter_message(text=f"Sorry, there was an issue processing your grievance. Please try again.\n openAI response \n {result} \n result_dict: {str(result_dict)}")
            print(f"OpenAI API Error: {e}")
            return []

class ActionConfirmCategories(Action):
    def name(self) -> str:
        return "action_confirm_categories"

    def run(self, dispatcher, tracker, domain):
        confirmed_categories = tracker.get_slot("temp_categories")

        if not confirmed_categories:
            dispatcher.utter_message(text="I couldn't find any categories to confirm.")
            return []

        # # Save confirmed categories as final slots
        # slots = [SlotSet(f"category_{idx}", category) for idx, category in enumerate(confirmed_categories, start=1)]

        # Confirmation message
        dispatcher.utter_message(
            text="Thank you! The categories have been confirmed."
        )

        # # Ask if they want to add another category manually
        # buttons = [
        #     {"title": "Yes, add category", "payload": "/add_category"},
        #     {"title": "No, continue", "payload": "/continue_process"}
        # ]

        # dispatcher.utter_message(
        #     text="Do you want to add another category manually?",
        #     buttons=buttons
        # )

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
    

class ActionAskForSummary(Action):
    def name(self) -> Text:
        return "action_ask_for_summary"

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
        return [ActiveLoop("edit_summary_form")]

    

class ActionEditGrievanceSummary(Action):
    def name(self) -> Text:
        return "action_edit_grievance_summary"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """Step 2: Handle the user's response and update the slot"""

        new_summary = tracker.get_slot("grievance_summary")

        if new_summary and new_summary.lower() != "skip":
            dispatcher.utter_message(text=f"✅ Your grievance summary has been updated to:\n\n'{new_summary}'")
            return [SlotSet("grievance_summary", new_summary), ActiveLoop(None)]  # Deactivate form
        
        elif new_summary and new_summary.lower() == "skip":
            dispatcher.utter_message(text="✅ Keeping the existing grievance summary.")
            return [ActiveLoop(None)]  # Deactivate form
        
        return []



class ActionSubmitGrievance(Action):
    def name(self) -> Text:
        return "action_submit_grievance"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Retrieve grievance details, summary, and category from slots
        grievance_details = tracker.get_slot("grievance_details")
        grievance_summary = tracker.get_slot("grievance_summary")
        grievance_category = tracker.get_slot("temp_category")

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

# class ActionSetCategory(Action):
#     def name(self) -> str:
#         return "action_set_category"

#     async def run(self, dispatcher, tracker, domain):
#         grievance_category = tracker.get_slot("grievance_category")
#         return [SlotSet("grievance_category", grievance_category)]
    

class ActionAskForCategoryModification(Action):
    def name(self) -> str:
        return "action_ask_for_category_modification"

    def run(self, dispatcher, tracker, domain):
        temp_categories = tracker.get_slot("temp_categories")

        if not temp_categories:
            dispatcher.utter_message(text="No categories selected.")
            return []

        # Display categories as buttons for modification
        buttons = [
            {"title": category, "payload": f"/modify_category{{\"category_modify\": \"{category}\"}}"}
            for category in temp_categories
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
        
        return [SlotSet("old_category", category_modify)]
    
    
class ActionChangeCategory(Action):
    def name(self) -> str:
        return "action_change_category"

    def run(self, dispatcher, tracker, domain):
        # Path to the lookup file
        lookup_file_path = "data/lookup_tables/list_category.txt"

        # Load categories from the lookup table
        category_list = list_categories_global
        # Retrieve categories already selected and dismissed
        selected_categories = tracker.get_slot("temp_categories") or []
        dismissed_categories = tracker.get_slot("dismissed_categories") or []

        # Filter out selected and dismissed categories
        available_categories = [cat for cat in category_list if cat not in selected_categories and cat not in dismissed_categories]

        if not available_categories:
            dispatcher.utter_message(text="⚠ No more categories available for selection.")
            return []

        # Generate buttons for category selection (limit to 10 for readability)
        buttons = [{"title": cat, "payload": f'/set_new_category{{"category": "{cat}"}}'} for cat in available_categories[:10]]

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
        selected_categories = tracker.get_slot("temp_categories") or []
        new_category = None
        print("temp_categories before update: ", selected_categories)
        # # Extract the new category from the user's latest message (button selection)
        # new_category = tracker.get_slot("new_category")
        # print("old_category", old_category)
        # print("new_category_from_slot", new_category)

        # Fallback: Try extracting directly from latest user message (in case slot is not set)
        latest_message = tracker.latest_message.get("text", "")
        # entities = tracker.latest_message.get("entities", [])
        # for entity in entities:
        #     if entity.get("entity") == "category":
        #         new_category = entity.get("value")
        #         break
        category_list = list_categories_global #load the categories
        
        for c in category_list:
            if c in tracker.latest_message.get("text", ""):
                new_category = c
                print("c extracted from message : " , c)
            
        print("old_category", old_category)
        print("new_category_from_message", new_category)
        # Ensure new_category is valid before updating
        if not new_category:
            dispatcher.utter_message(text="⚠ No valid category was selected.")
            return []

        # Update category selection
        if old_category in selected_categories:
            selected_categories.remove(old_category)
            selected_categories.append(new_category)
            print("temp_categories after update: ", selected_categories)

            dispatcher.utter_message(text=f"✅ '{old_category}' has been changed to '{new_category}'.")
        else:
            dispatcher.utter_message(text=f"⚠ '{old_category}' was not found in the selected categories.")

        return [
            SlotSet("temp_categories", selected_categories),
            SlotSet("category_modify", None),
            SlotSet("old_category", None),
            SlotSet("new_category", new_category)
        ]


class ActionConfirmCategories(Action):
    def name(self) -> str:
        return "action_confirm_categories"

    def run(self, dispatcher, tracker, domain):
        selected_categories = tracker.get_slot("temp_categories")
        
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
        temp_categories = tracker.get_slot("temp_categories") or []
        dismissed_categories = tracker.get_slot("dismissed_categories") or []

        if category_to_delete in temp_categories:
            temp_categories.remove(category_to_delete)
            dispatcher.utter_message(text=f"✅ '{category_to_delete}' has been removed.")

            # Add to dismissed categories if not already present
            if category_to_delete not in dismissed_categories:
                dismissed_categories.append(category_to_delete)

        else:
            dispatcher.utter_message(text=f"⚠ '{category_to_delete}' was not found in the selected categories.")

        # Update slots
        return [
            SlotSet("temp_categories", temp_categories), 
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