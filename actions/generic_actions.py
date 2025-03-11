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


logger = logging.getLogger(__name__)

# class ActionSessionStart(Action):
#     def name(self) -> str:
#         return "action_session_start"

#     async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
#         logger.info("ActionSessionStart triggered")
#         events = [SessionStarted(), ActionExecuted("action_listen")]
#         logger.info("Dispatcher is sending response: utter_introduce")  # Debugging line
#         dispatcher.utter_message(response="utter_introduce")
#         # dispatcher.utter_message(text="Hello! Welcome to the Grievance Management Chatbot. I am here to help you file a grievance or check its status. What would you like to do?")
#         logger.info("utter_introduce sent")  # Debugging line
#         return events
# Action to prepopulate location based on QR code



class ActionIntroduce(Action):
    def name(self) -> str:
        return "action_introduce"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        # Extract province and district from the payload
        message = tracker.latest_message.get('text', '')
        entities = tracker.latest_message.get('entities', [])
        
        # Try to get province and district from the message payload
        province = None
        district = None
        
        try:
            import json
            # Check if the message contains JSON data
            if '{' in message and '}' in message:
                json_str = message[message.index('{'):message.rindex('}')+1]
                data = json.loads(json_str)
                province = data.get('province')
                district = data.get('district')
        except:
            pass

        # If we got province and district from the payload, set the slots
        events = []
        if province and district:
            events.extend([
                SlotSet("user_province", province),
                SlotSet("user_district", district)
            ])
            welcome_text = f"""INTRODUCE: Hello! Welcome to the Grievance Management Chatbot.
            You are reaching out to the office of {district} in {province}.
            I am here to help you file a grievance or check its status. What would you like to do?"""
        else:
            welcome_text = """INTRODUCE: Hello! Welcome to the Grievance Management Chatbot.
            I am here to help you file a grievance or check its status. What would you like to do?"""

        dispatcher.utter_message(
            text=welcome_text,
            buttons=[
                {"title": "File a grievance", "payload": "/start_grievance_process"},
                {"title": "Check my status", "payload": "/check_status"},
                {"title": "Exit", "payload": "/goodbye"}
            ]
        )

        return events



class ActionSessionStart(Action):
    def name(self) -> Text:
        return "action_session_start"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        # Initialize session
        events = [SessionStarted()]
        
        # Get the latest message
        message = tracker.latest_message.get('text', '')
        
        # Initialize welcome text
        welcome_text = """Hello! Welcome to the Grievance Management Chatbot.
            I am here to help you file a grievance or check its status. What would you like to do?"""
        
        try:
            import json
            # Check if the message contains JSON data
            if '{' in message and '}' in message:
                json_str = message[message.index('{'):message.rindex('}')+1]
                data = json.loads(json_str)
                province = data.get('province')
                district = data.get('district')
                
                if province and district:
                    events.extend([
                        SlotSet("user_province", province),
                        SlotSet("user_district", district)
                    ])
                    welcome_text = f"""Hello! Welcome to the Grievance Management Chatbot.
                    You are reaching out to the office of {district} in {province}.
                    I am here to help you file a grievance or check its status. What would you like to do?"""
                    print(welcome_text)
                
        except:
            pass
        if message and "/" in message:
            # Send introduction message
            dispatcher.utter_message(
                text=welcome_text,
                buttons=[
                    {"title": "File a grievance", "payload": "/start_grievance_process"},
                    {"title": "Check my status", "payload": "/check_status"},
                    {"title": "Exit", "payload": "/goodbye"}
                ]
            )
            
        # Add the action that listens for the next user message
        events.append(ActionExecuted("action_listen"))
        
        return events



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
    
class ActionCustomFallback(Action):
    def name(self):
        return "action_custom_fallback"

    def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(
            text="I didn't understand that. What would you like to do next?",
            buttons=[
                {"title": "Try Again", "payload": "/restart_story{\"restart_type\": \"story\"}"},
                {"title": "File Grievance as Is", "payload": "/file_grievance_as_is"},
                {"title": "Exit", "payload": "/exit"}
            ]
        )
        return [UserUtteranceReverted()]


    
############################ HELPER ACTION - SKIP HANDLING ############################
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
