# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
import logging
from typing import Any, Text, Dict, List
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted,ActionExecuted, FollowupAction, Restarted, UserUtteranceReverted
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from twilio.rest import Client
from .constants import QR_PROVINCE, QR_DISTRICT, DISTRICT_LIST  # Import the constants
from .utterance_mapping import get_utterance, get_buttons
from icecream import ic
import json
import uuid
from .db_actions import GrievanceDB


def get_language_code(tracker: Tracker) -> str:
    """Helper function to get the language code from tracker with English as fallback."""
    return tracker.get_slot("language_code") or "en"


class ActionSessionStart(Action):
    def name(self) -> Text:
        return "action_session_start"
    
    def run(self, 
            dispatcher: CollectingDispatcher, 
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        ic("action_session_start")
        return [SessionStarted()]
    
class ActionIntroduce(Action):
    def name(self) -> Text:
        return "action_introduce"
    
    def get_province_and_district(self, message: str) -> str:
        if '{' in message and '}' in message:
            json_str = message[message.index('{'):message.rindex('}')+1]
            data = json.loads(json_str)
            province = data.get('province')
            district = data.get('district')
            return province, district
        else:
            return None, None


    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        message = tracker.latest_message.get('text', '')
        ic(tracker.latest_message)
        ic(message)
        if message:
            if "introduce" in message.lower():
                province, district = self.get_province_and_district(message)
                if province and district:
                    events.extend([
                        SlotSet("user_province", province),
                        SlotSet("user_district", district)
                    ])
        #dispatch message to choose language
        text = get_utterance('generic_actions', self.name(), 1, 'en')
        buttons = get_buttons('generic_actions', self.name(), 1, 'en')
        ic(text)
        ic(buttons)
        dispatcher.utter_message(text=text, buttons=buttons)
        ic(events)
        return events
    

class ActionSetEnglish(Action):
    def name(self) -> Text:
        return "action_set_english"
    
    def run(
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("language_code", "en")]
    
class ActionSetNepali(Action):
    def name(self) -> Text:
        return "action_set_nepali"
    
    def run(
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("language_code", "ne")]

class ActionMenu(Action):
    def name(self) -> Text:
        return "action_menu"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        
        # Get language, district and province
        language = get_language_code(tracker)
        district = tracker.get_slot("user_district")
        province = tracker.get_slot("user_province")
        ic(language, district, province)
        if district and province:
            welcome_text = get_utterance('generic_actions', self.name(), 2, language).format(
                district=district,
                province=province
            )
        else:
            welcome_text = get_utterance('generic_actions', self.name(), 1, language)
        buttons = get_buttons('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=welcome_text, buttons=buttons)
        return []



#helpers
class ActionSetCurrentProcess(Action):
    def name(self) -> Text:
        return "action_set_current_process"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        current_story = "Filing a Complaint"  # Replace with dynamic logic if needed
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language).format(current_story=current_story)
        dispatcher.utter_message(text=message)
        return [SlotSet("current_process", current_story)]




    
#navigation actions
class ActionGoBack(Action):
    def name(self):
        return "action_go_back"

    def run(self, dispatcher, tracker, domain):
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message)
        return [UserUtteranceReverted()]


    
    
class ActionRestartStory(Action):
    def name(self) -> str:
        return "action_restart_story"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        current_process = tracker.get_slot("current_process")
        current_story = tracker.get_slot("current_story")
        language = get_language_code(tracker)

        process_name = current_process if current_process else "current process"
        story_name = current_story if current_story else "current story"

        message = get_utterance('generic_actions', self.name(), 1, language)
        buttons = get_buttons('generic_actions', self.name(), 1, language)

        dispatcher.utter_message(text=message, buttons=buttons)
        return []

    
    
class ActionShowCurrentStory(Action):
    def name(self):
        return "action_show_current_story"

    def run(self, dispatcher, tracker, domain):
        current_story = tracker.get_slot("current_story")
        language = get_language_code(tracker)
        
        if current_story:
            message = get_utterance('generic_actions', self.name(), 1, language).format(current_story=current_story)
        else:
            message = get_utterance('generic_actions', self.name(), 2, language)
            
        dispatcher.utter_message(text=message)
        return []

#mood actions
class ActionHandleMoodGreat(Action):
    def name(self) -> str:
        return "action_handle_mood_great"

    def run(self, dispatcher, tracker, domain):
        previous_action = tracker.get_slot("previous_state")
        language = get_language_code(tracker)

        if previous_action:
            message = get_utterance('generic_actions', self.name(), 1, language)
            dispatcher.utter_message(text=message)
            return [FollowupAction(previous_action)]
        else:
            message = get_utterance('generic_actions', self.name(), 2, language)
            dispatcher.utter_message(text=message)
            return []

        
class ActionRespondToChallenge(Action):
    def name(self) -> Text:
        return "action_respond_to_challenge"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message)
        return []
    
class ActionCustomFallback(Action):
    def name(self):
        return "action_custom_fallback"

    def run(self, dispatcher, tracker, domain):
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        buttons = get_buttons('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message, buttons=buttons)
        return [UserUtteranceReverted()]


    
############################ HELPER ACTION - SKIP HANDLING ############################
class ActionHandleSkip(Action):
    def name(self) -> Text:
        return "action_handle_skip"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        skip_count = tracker.get_slot("skip_count") or 0
        skip_count += 1
        language = get_language_code(tracker)

        if skip_count >= 2:
            message = get_utterance('generic_actions', self.name(), 1, language)
            dispatcher.utter_message(text=message)
            return [SlotSet("skip_count", 0)]
        else:
            message = get_utterance('generic_actions', self.name(), 2, language)
            dispatcher.utter_message(text=message)
            return [SlotSet("skip_count", skip_count)]

class ActionGoodbye(Action):
    def name(self) -> Text:
        return "action_goodbye"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message)
        return []
        
class ActionMoodUnhappy(Action):
    def name(self) -> Text:
        return "action_mood_unhappy"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message)
        return []
        
class ActionExitWithoutFiling(Action):
    def name(self) -> Text:
        return "action_exit_without_filing"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        buttons = get_buttons('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
    ############### ATTACHMENT ACTIONS #########################
    
class ActionAttachFile(Action):
    def name(self) -> Text:
        return "action_attach_file"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """Handle file attachments sent by the user"""
        language = get_language_code(tracker)
        
        # Debug the incoming message in detail
        ic("ActionAttachFile triggered")
        ic("Latest message content:", tracker.latest_message)
        
        # Get the current grievance ID
        grievance_id = tracker.get_slot("grievance_id")
        ic("Current grievance ID:", grievance_id)
        
        # Get file references - check all possible locations where they might be found
        latest_message = tracker.latest_message
        file_references = []
        
        # 1. First check if they're directly in the message
        direct_refs = latest_message.get('file_references', [])
        if direct_refs:
            ic("Found file references directly in message:", direct_refs)
            file_references = direct_refs
        
        # 2. Check if they're in the metadata (common with custom data)
        elif 'metadata' in latest_message:
            metadata = latest_message.get('metadata', {})
            ic("Message metadata:", metadata)
            
            # Try common locations for file references
            meta_refs = metadata.get('file_references', [])
            if meta_refs:
                ic("Found file references in metadata[file_references]:", meta_refs)
                file_references = meta_refs
        
        # 3. Check if they're in custom_data (common with socket.io transport)
        custom_data = latest_message.get('custom_data', {})
        if not file_references and custom_data:
            ic("Message custom_data:", custom_data)
            custom_refs = custom_data.get('file_references', [])
            if custom_refs:
                ic("Found file references in custom_data:", custom_refs)
                file_references = custom_refs
                
        # 4. Check additional data that might be sent from socket.io
        additional_data = latest_message.get('additional_data', {})
        if not file_references and additional_data:
            ic("Additional data:", additional_data)
            additional_refs = additional_data.get('file_references', [])
            if additional_refs:
                ic("Found file references in additional_data:", additional_refs)
                file_references = additional_refs
        
        # 5. Parse entities for file references (sometimes channels encode it this way)
        entities = latest_message.get('entities', [])
        if not file_references and entities:
            ic("Message entities:", entities)
            for entity in entities:
                if entity.get('entity') == 'file_reference':
                    file_references.append(entity.get('value'))
                    ic("Found file reference in entity:", entity.get('value'))
        
        # 6. Last resort - check raw text for encoded file references
        if not file_references:
            text = latest_message.get('text', '')
            ic("Message text:", text)
            # Try to extract JSON from the text if it contains file references
            if 'file_references' in text or 'files' in text:
                try:
                    # Find JSON-like content between curly braces
                    import re
                    json_content = re.search(r'\{.*\}', text)
                    if json_content:
                        import json
                        parsed = json.loads(json_content.group(0))
                        if 'file_references' in parsed:
                            file_references = parsed['file_references']
                            ic("Extracted file references from text:", file_references)
                except Exception as e:
                    ic("Error parsing JSON from text:", str(e))
        
        ic("Final file references found:", file_references)
        
        if not file_references:
            # No files were attached
            ic("No file references found after all checks")
            message = get_utterance('generic_actions', self.name(), 1, language)
            dispatcher.utter_message(text=message)
            return []
        
        if not grievance_id:
            # No grievance ID is available, store files temporarily
            ic("No grievance ID available, using temporary ID")
            temp_grievance_id = f"temp_{tracker.sender_id}"
            message = get_utterance('generic_actions', self.name(), 3, language)
            dispatcher.utter_message(text=message)
            return []
        
        # Files have been attached and we have a grievance ID
        file_names = []
        for file_ref in file_references:
            if isinstance(file_ref, dict):
                name = file_ref.get('name', file_ref.get('filename', 'Unknown file'))
                ic("Processing file reference (dict):", file_ref, "Name:", name)
                file_names.append(name)
            else:
                ic("Processing file reference (non-dict):", file_ref)
                file_names.append(str(file_ref))
        
        # Send confirmation message
        if len(file_names) == 1:
            message = get_utterance('generic_actions', self.name(), 2, language).format(
                file_name=file_names[0]
            )
        else:
            files_str = ", ".join(file_names)
            message = get_utterance('generic_actions', self.name(), 4, language).format(
                count=len(file_names),
                files=files_str
            )
        
        ic("Sending response message:", message)
        dispatcher.utter_message(text=message)
        
        # Return the grievance ID in the custom data
        return []


    