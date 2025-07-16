from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted,ActionExecuted, FollowupAction, Restarted, UserUtteranceReverted, ActiveLoop
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from .utils.base_classes import BaseAction
from backend.config.constants import TASK_STATUS
import json


TASK_SLOTS_TO_UPDATE_MAP = {
    "process_file_upload_task": {"slot_name": "file_upload_status", "followup_action": None},
    "classify_and_summarize_grievance_task": {"slot_name": "classification_status", "followup_action": "action_trigger_summary_form"},
    "translate_grievance_to_english_task": {"slot_name": "translation_status", "followup_action": None},
   }

IN_PROGRESS = TASK_STATUS["IN_PROGRESS"]
SUCCESS = TASK_STATUS["SUCCESS"]
FAILED = TASK_STATUS["FAILED"]
ERROR = TASK_STATUS["ERROR"]
RETRYING = TASK_STATUS["RETRYING"]


class ActionWrapper(BaseAction):
    """Wrapper to catch and log registration errors for actions"""
    @staticmethod
    def wrap_action(action_class):
        try:
            action_instance = action_class()
            # Test the run method signature
            run_method = getattr(action_instance, 'run')
            if run_method.__code__.co_argcount != 4:  # 4 because of 'self' + 3 params
                self.logger.error(f"❌ Action {action_class.__name__} has incorrect number of parameters in run method. "
                           f"Found {run_method.__code__.co_argcount - 1} params, expected 3 "
                           f"(dispatcher, tracker, domain)")
                self.logger.error(f"Parameters found: {run_method.__code__.co_varnames[:run_method.__code__.co_argcount]}")
            return action_instance
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize action {action_class.__name__}: {str(e)}")
            raise



class ActionReopenConversationForEmitStatusUpdate(BaseAction):
    def name(self) -> Text:
        return "action_reopen_conversation_for_emit_status_update"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return []

class ActionEmitStatusUpdate(BaseAction):
    def name(self) -> Text:
        return "action_emit_status_update"
    
    def extract_slots_to_update(self, data: Dict[Text, Any], domain: DomainDict) -> List[Dict[Text, Any]]:
        task_name = data.get("task_name")
        task_status = data.get("status")
        values = data.get("values", {})
        
        # Extract domain slots included in the values
        slots_to_set = []
        for slot_name, slot_value in values.items():
            if slot_name in domain["slots"]:
                slots_to_set.append(SlotSet(slot_name, slot_value))
        
        # Add task-specific slot if mapped
        if task_name in TASK_SLOTS_TO_UPDATE_MAP:
            slot_name = TASK_SLOTS_TO_UPDATE_MAP[task_name]['slot_name']
            slots_to_set.append(SlotSet(slot_name, task_status))
        
        # Clear the data_to_emit slot
        slots_to_set.append(SlotSet("data_to_emit", None))
        
        return slots_to_set

    def extract_followup_action(self, data: Dict[Text, Any], domain: DomainDict) -> Text:
        task_name = data.get("task_name")
        if task_name in TASK_SLOTS_TO_UPDATE_MAP.keys():
            return TASK_SLOTS_TO_UPDATE_MAP[task_name]['followup_action']
        return None

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        self.logger.debug(f"🔍 [RASA DEBUG] ActionEmitStatusUpdate triggered")
        self.logger.debug(f"   - data_to_emit slot: {tracker.get_slot('data_to_emit')}")
        
        if tracker.get_slot("data_to_emit") is None:
            self.logger.error(f"{self.name()} - ❌ [RASA DEBUG] No data to emit - raising exception")
            raise Exception("No data to emit")
        
        data = tracker.get_slot("data_to_emit")
        task_status = data.get("status")
        task_name = data.get("task_name")
        task_id = data.get("task_id", 'not_provided')
        
        self.logger.debug(f"{self.name()} - 🔍 [RASA DEBUG] Processing task: {task_name}, status: {task_status}")
        self.logger.debug(f"{self.name()} -   - Full data: {data}")
        
        if task_status in [SUCCESS, FAILED]:  # Only emit status update for success or failure to not clutter websocket
            # Structure the data for frontend consumption
            structured_data = {
                'task_status': {
                    'task_id': task_id,
                    'status': task_status,
                    'result': data if task_status == SUCCESS else None,
                    'error': data if task_status == FAILED else None
                }
            }
            self.logger.debug(f"{self.name()} - ✅ [RASA DEBUG] Emitting status update via dispatcher.utter_message: {structured_data}")
            dispatcher.utter_message(json_message=structured_data)
            if task_name in TASK_SLOTS_TO_UPDATE_MAP.keys():
                slot_name = TASK_SLOTS_TO_UPDATE_MAP[task_name]['slot_name']
                self.logger.debug(f"{self.name()} -   - Setting slot {slot_name} to {task_status}")
                return [SlotSet(slot_name, task_status)]
                
        if task_status == SUCCESS:
            self.logger.debug(f"{self.name()} - ✅ [RASA DEBUG] Processing SUCCESS status")
            # Structure the data for frontend consumption
            structured_data = {
                'task_status': {
                    'task_id': task_id,
                    'status': task_status,
                    'result': data
                }
            }
            dispatcher.utter_message(json_message=structured_data)
            slots_to_set = self.extract_slots_to_update(data, domain)
            followup_action = self.extract_followup_action(data, domain)
            if followup_action:
                self.logger.debug(f"{self.name()} -   - Adding followup action: {followup_action}")
                slots_to_set.append(FollowupAction(followup_action))
            self.logger.debug(f"{self.name()} -   - Returning slots: {slots_to_set}")
            return slots_to_set
        else:
            self.logger.debug(f"{self.name()} - ⚠️ [RASA DEBUG] Task status not in [SUCCESS, FAILED]: {task_status}")
            return []






class ActionSessionStart(BaseAction):
    def name(self) -> Text:
        return "action_session_start"
    
    def execute_action(self, 
            dispatcher: CollectingDispatcher, 
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
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


    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        message = tracker.latest_message.get('text', '')
        self.logger.debug(f"{self.name()} - 🔍 [RASA DEBUG] Message: {message}")
        if message:
            if "introduce" in message.lower():
                province, district = self.get_province_and_district(message)
                if province and district:
                    events.extend([
                        SlotSet("complainant_province", province),
                        SlotSet("complainant_district", district)
                    ])
        #dispatch message to choose language
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return events
    

class ActionSetEnglish(BaseAction):
    def name(self) -> Text:
        return "action_set_english"
    
    def execute_action(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("language_code", "en")]
    
class ActionSetNepali(BaseAction):
    def name(self) -> Text:
        return "action_set_nepali"
    
    def execute_action(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("language_code", "ne")]

class ActionMenu(BaseAction):
    def name(self) -> Text:
        return "action_menu"

    def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        
        # Get language, district and province
        district = tracker.get_slot("complainant_district")
        province = tracker.get_slot("complainant_province")
        #ic(language, district, province)
        if district and province:
            message = self.get_utterance(2)
            message = message.format(
                district=district,
                province=province
            )
        else:
            message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionOutro(BaseAction):
    def name(self) -> Text:
        return "action_outro"
    
    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return []

#helpers
class ActionSetCurrentProcess(BaseAction):
    def name(self) -> Text:
        return "action_set_current_process"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        current_story = "Filing a Complaint"  # Replace with dynamic logic if needed
        message = self.get_utterance(1)
        message = message.format(current_story=current_story)
        dispatcher.utter_message(text=message)
        return [SlotSet("current_process", current_story)]




    
#navigation actions
class ActionGoBack(BaseAction):
    def name(self):
        return "action_go_back"

    def execute_action(self, dispatcher, tracker, domain):
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return [UserUtteranceReverted()]


    
    
class ActionRestartStory(BaseAction):
    def name(self) -> str:
        return "action_restart_story"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        current_process = tracker.get_slot("current_process")
        current_story = tracker.get_slot("current_story")

        process_name = current_process if current_process else "current process"
        story_name = current_story if current_story else "current story"

        message = self.get_utterance(1)
        buttons = self.get_buttons(1)

        dispatcher.utter_message(text=message, buttons=buttons)
        return []

    
    
class ActionShowCurrentStory(BaseAction):
    def name(self):
        return "action_show_current_story"

    def execute_action(self, dispatcher, tracker, domain):
        current_story = tracker.get_slot("current_story")
        
        if current_story:
            message = self.get_utterance(1)
            message = message.format(current_story=current_story)
        else:
            message = self.get_utterance(2)
            
        dispatcher.utter_message(text=message)
        return []

#mood actions
class ActionHandleMoodGreat(BaseAction):
    def name(self) -> str:
        return "action_handle_mood_great"

    def execute_action(self, dispatcher, tracker, domain):
        previous_action = tracker.get_slot("previous_state")

        if previous_action:
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            return [FollowupAction(previous_action)]
        else:
            message = self.get_utterance(2)
            dispatcher.utter_message(text=message)
            return []

        
class ActionRespondToChallenge(BaseAction):
    def name(self) -> Text:
        return "action_respond_to_challenge"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return []
    
class ActionCustomFallback(BaseAction):
    def name(self):
        return "action_custom_fallback"

    def execute_action(self, dispatcher, tracker, domain):
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return [UserUtteranceReverted()]


    
############################ HELPER ACTION - SKIP HANDLING ############################
class ActionHandleSkip(BaseAction):
    def name(self) -> Text:
        return "action_handle_skip"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        skip_count = tracker.get_slot("skip_count") or 0
        skip_count += 1

        if skip_count >= 2:
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            return [SlotSet("skip_count", 0)]
        else:
            message = self.get_utterance(2)
            dispatcher.utter_message(text=message)
            return [SlotSet("skip_count", skip_count)]

class ActionGoodbye(BaseAction):
    def name(self) -> Text:
        return "action_goodbye"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return []
        
class ActionMoodUnhappy(BaseAction):
    def name(self) -> Text:
        return "action_mood_unhappy"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return []
        
class ActionExitWithoutFiling(BaseAction):
    def name(self) -> Text:
        return "action_exit_without_filing"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []



# Clear session action
class ActionClearSession(BaseAction): # Corrected class name if it was typo
    def name(self) -> Text:
        return "action_clear_session"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        self.logger.debug(f"{self.name()} - 🔍 [RASA DEBUG] ActionClearSession triggered")

        dispatcher.utter_message(
            # text=text_message, # Uncomment if you want text
            json_message={"custom": {"clear_window": True}} # Use custom field
        )
        return []





class ActionCloseBrowserTab(BaseAction):
    def name(self) -> Text:
        return "action_close_browser_tab"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        self.logger.debug(f"{self.name()} - 🔍 [RASA DEBUG] ActionCloseBrowserTab triggered")

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

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionAttachFiles(BaseAction):
    def name(self) -> Text:
        return "action_question_attach_files"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return []

class ActionDefaultFallback(BaseAction):
    def name(self) -> Text:
        return "action_default_fallback"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        #run the action_menu action
        return [ActionExecuted("action_menu")]

class ActionFileUploadStatus(BaseAction):
    def name(self) -> Text:
        return "action_file_upload_status"

    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # You can pass these as slots or from tracker.latest_message
        file_id = tracker.get_slot("file_id")
        status = tracker.get_slot("file_status")
        file_name = tracker.get_slot("file_name")
        # Add any other info you want to send

        dispatcher.utter_message(
            json_message={
                "event_type": "file_upload_status",
                "file_id": file_id,
                "status": status,
                "file_name": file_name,
                # ... any other fields
            }
        )
        return []

