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
from rasa_sdk.events import SlotSet, SessionStarted,ActionExecuted, FollowupAction, Restarted
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from twilio.rest import Client
from rasa_sdk.events import UserUtteranceReverted, Restarted

logger = logging.getLogger(__name__)

# class ActionSessionStart(Action):
#     def name(self) -> str:
#         return "action_session_start"

#     async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
#         logger.info("ActionSessionStart triggered")
#         events = [SessionStarted(), ActionExecuted("action_listen")]
#         logger.info("Dispatcher is sending response: utter_introduce")  # Debugging line
#         # dispatcher.utter_message(response="utter_introduce")
#         dispatcher.utter_message(text="Hello! Welcome to the Grievance Management Chatbot. I am here to help you file a grievance or check its status. What would you like to do?")
#         logger.info("utter_introduce sent")  # Debugging line
#         return events


#helpers
class ActionSetCurrentProcess(Action):
    def name(self) -> Text:
        return "action_set_current_process"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        current_story = "Filing a Complaint"  # Replace with dynamic logic if needed
        dispatcher.utter_message(response="utter_set_current_process", current_story=current_story)
        return [SlotSet("current_process", current_story)]




    
#navigation actions
class ActionGoBack(Action):
    def name(self):
        return "action_go_back"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(response="utter_go_back")
        return [UserUtteranceReverted()]


    
    
class ActionRestartStory(Action):
    def name(self) -> str:
        return "action_restart_story"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        current_process = tracker.get_slot("current_process")
        current_story = tracker.get_slot("current_story")

        process_name = current_process if current_process else "current process"
        story_name = current_story if current_story else "current story"

        buttons = [
            {"title": f"Restart the {process_name}", "payload": "/restart_story{\"restart_type\": \"process\"}"},
            {"title": f"Restart the {story_name}", "payload": "/restart_story{\"restart_type\": \"story\"}"},
            {"title": "Go back to the main menu", "payload": "/main_menu"}
        ]

        dispatcher.utter_message(response="utter_restart_story", buttons=buttons)
        return []

    
    
class ActionShowCurrentStory(Action):
    def name(self):
        return "action_show_current_story"

    def run(self, dispatcher, tracker, domain):
        current_story = tracker.get_slot("current_story")
        if current_story:
            dispatcher.utter_message(response="utter_show_current_story", current_story=current_story)
        else:
            dispatcher.utter_message(response="utter_show_current_story_unknown")
        return []

#mood actions
class ActionHandleMoodGreat(Action):
    def name(self) -> str:
        return "action_handle_mood_great"

    def run(self, dispatcher, tracker, domain):
        previous_action = tracker.get_slot("previous_state")

        if previous_action:
            dispatcher.utter_message(response="utter_mood_great_continue")
            return [FollowupAction(previous_action)]
        else:
            dispatcher.utter_message(response="utter_mood_great_next_step")
            return []

        
class ActionRespondToChallenge(Action):
    def name(self) -> Text:
        return "action_respond_to_challenge"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(response="utter_respond_to_challenge")
        return []