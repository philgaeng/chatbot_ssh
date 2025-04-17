import logging
from typing import Any, Text, Dict, List
from random import randint
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted,ActionExecuted, FollowupAction, Restarted, UserUtteranceReverted
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from twilio.rest import Client
from actions_server.constants import  MAX_FILE_SIZE  # Import MAX_FILE_SIZE
from .utterance_mapping_rasa import get_utterance, get_buttons
from icecream import ic
from .base_classes import BaseAction
import json


# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ActionWrapper:
    """Wrapper to catch and log registration errors for actions"""
    @staticmethod
    def wrap_action(action_class):
        try:
            action_instance = action_class()
            # Test the run method signature
            run_method = getattr(action_instance, 'run')
            if run_method.__code__.co_argcount != 4:  # 4 because of 'self' + 3 params
                logger.error(f"❌ Action {action_class.__name__} has incorrect number of parameters in run method. "
                           f"Found {run_method.__code__.co_argcount - 1} params, expected 3 "
                           f"(dispatcher, tracker, domain)")
                logger.error(f"Parameters found: {run_method.__code__.co_varnames[:run_method.__code__.co_argcount]}")
            return action_instance
        except Exception as e:
            logger.error(f"❌ Failed to initialize action {action_class.__name__}: {str(e)}")
            raise

def get_language_code(tracker: Tracker) -> str:
    """Helper function to get the language code from tracker with English as fallback."""
    return tracker.get_slot("language_code") or "en"


class ActionSessionStart(BaseAction):
    def name(self) -> Text:
        return "action_session_start"
    
    def run(self, 
            dispatcher: CollectingDispatcher, 
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        ic("action_session_start")
        return [SessionStarted()]
    
class ActionIntroduce(BaseAction):
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
    

class ActionSetEnglish(BaseAction):
    def name(self) -> Text:
        return "action_set_english"
    
    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("language_code", "en")]
    
class ActionSetNepali(BaseAction):
    def name(self) -> Text:
        return "action_set_nepali"
    
    def run(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("language_code", "ne")]

class ActionMenu(BaseAction):
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
        #ic(language, district, province)
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
class ActionSetCurrentProcess(BaseAction):
    def name(self) -> Text:
        return "action_set_current_process"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        current_story = "Filing a Complaint"  # Replace with dynamic logic if needed
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language).format(current_story=current_story)
        dispatcher.utter_message(text=message)
        return [SlotSet("current_process", current_story)]




    
#navigation actions
class ActionGoBack(BaseAction):
    def name(self):
        return "action_go_back"

    def run(self, dispatcher, tracker, domain):
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message)
        return [UserUtteranceReverted()]


    
    
class ActionRestartStory(BaseAction):
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

    
    
class ActionShowCurrentStory(BaseAction):
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
class ActionHandleMoodGreat(BaseAction):
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

        
class ActionRespondToChallenge(BaseAction):
    def name(self) -> Text:
        return "action_respond_to_challenge"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message)
        return []
    
class ActionCustomFallback(BaseAction):
    def name(self):
        return "action_custom_fallback"

    def run(self, dispatcher, tracker, domain):
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        buttons = get_buttons('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message, buttons=buttons)
        return [UserUtteranceReverted()]


    
############################ HELPER ACTION - SKIP HANDLING ############################
class ActionHandleSkip(BaseAction):
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

class ActionGoodbye(BaseAction):
    def name(self) -> Text:
        return "action_goodbye"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message)
        return []
        
class ActionMoodUnhappy(BaseAction):
    def name(self) -> Text:
        return "action_mood_unhappy"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message)
        return []
        
class ActionExitWithoutFiling(BaseAction):
    def name(self) -> Text:
        return "action_exit_without_filing"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        buttons = get_buttons('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []



# Clear session action
class ActionClearSession(BaseAction): # Corrected class name if it was typo
    def name(self) -> Text:
        return "action_clear_session"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        ic("ActionClearSession triggered")
        # Optional: Send a confirmation text
        # language = get_language_code(tracker)
        # text_message = "Clearing the chat window..." # Or get from utterance map
        
        # Send the command via custom JSON payload
        dispatcher.utter_message(
            # text=text_message, # Uncomment if you want text
            json_message={"custom": {"clear_window": True}} # Use custom field
        )
        ic("Sent clear_window command")
        # This action doesn't modify Rasa's state directly, 
        # just sends a command to the frontend.
        # If you ALSO wanted to reset slots or restart the conversation, 
        # you would return events like Restarted() here.
        return []


class ActionCloseBrowserTab(BaseAction):
    def name(self) -> Text:
        return "action_close_browser_tab"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        ic("ActionCloseBrowserTab triggered")
        # Optional: Send a confirmation text
        # language = get_language_code(tracker)
        # text_message = "Clearing the chat window..." # Or get from utterance map
        
        # Send the command via custom JSON payload
        dispatcher.utter_message(
            # text=text_message, # Uncomment if you want text
            json_message={"custom": {"close_browser_tab": True}} # Use custom field
        )
        ic("Sent close_browser_tab command")
        # This action doesn't modify Rasa's state directly, 
        # just sends a command to the frontend.
        # If you ALSO wanted to reset slots or restart the conversation, 
        # you would return events like Restarted() here.
        return []

class ActionCleanWindowOptions(BaseAction):
    def name(self) -> Text:
        return "action_clean_window_options"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('generic_actions', self.name(), 1, language)
        buttons = get_buttons('generic_actions', self.name(), 1, language)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []