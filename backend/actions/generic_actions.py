from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted,ActionExecuted, FollowupAction, Restarted, UserUtteranceReverted, ActiveLoop
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from .base_classes.base_classes  import BaseAction
from backend.actions.utils.ticketing_dispatch import fetch_qr_scan
from backend.config.database_constants import TASK_STATUS
from backend.shared_functions.location_mapping import resolve_location_code_to_names
import json
import os


TASK_SLOTS_TO_UPDATE_MAP = {
    "process_file_upload_task": {"slot_name": "file_upload_status", "followup_action": None},
    "classify_and_summarize_grievance_task": {"slot_name": "grievance_classification_status"},
    "translate_grievance_to_english_task": {"slot_name": "translation_status", "followup_action": None},
}


def _deprecated_action_warning(logger, action_name: str) -> None:
    logger.warning(
        "[DEPRECATED_ACTION] %s is deprecated and kept only for backward compatibility.",
        action_name,
    )


class ActionNextAction(BaseAction):
    def name(self) -> Text:
        return "action_next_action"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        next_action = self.get_next_action_for_form(tracker)
        self.logger.debug(f"{self.name()} - Next action selected: {next_action}")
        return [FollowupAction(next_action)]

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



class ActionSessionStart(BaseAction):
    def name(self) -> Text:
        return "action_session_start"
    
    async def execute_action(self, 
            dispatcher: CollectingDispatcher, 
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SessionStarted()]
    
class ActionIntroduce(BaseAction):
    def name(self) -> Text:
        return "action_introduce"

    def parse_introduce_payload(self, message: str) -> Dict[str, Any]:
        """Extract the JSON payload embedded in the /introduce message.

        Recognised keys: province, district, flask_session_id, t (QR token).
        Any other keys are ignored. Returns an empty dict on parse failure.
        """
        if not message or '{' not in message or '}' not in message:
            return {}
        try:
            json_str = message[message.index('{'):message.rindex('}') + 1]
            data = json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as exc:
            self.logger.warning(f"{self.name()} - failed to parse introduce payload: {exc}")
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def _resolve_qr_token(self, token: str) -> Dict[str, Any]:
        """Resolve a QR token to a slot bundle (token + scan + place names).

        Always returns a dict — empty when the token is missing/invalid so the
        caller can fall back to the standard geo questions.
        """
        if not token:
            return {}
        scan = fetch_qr_scan(token)
        if not scan:
            self.logger.info(f"{self.name()} - QR token unresolved, falling back to geo questions: token={token}")
            return {}

        location_code = scan.get("location_code")
        names: Dict[str, Any] = {}
        if location_code:
            try:
                names = resolve_location_code_to_names(self.db_manager, location_code) or {}
            except Exception as exc:  # pylint: disable=broad-except
                self.logger.warning(f"{self.name()} - location code resolution failed: {exc}")
                names = {}

        bundle = {
            "qr_token": token,
            "package_id": scan.get("package_id"),
            "package_label": scan.get("label"),
            "project_code": scan.get("project_code"),
            "location_code": location_code,
            "complainant_province": names.get("province_name"),
            "complainant_district": names.get("district_name"),
        }
        self.logger.info(
            f"{self.name()} - QR token resolved: token=%s package_id=%s project_code=%s "
            f"location_code=%s district=%s province=%s",
            token,
            bundle.get("package_id"),
            bundle.get("project_code"),
            bundle.get("location_code"),
            bundle.get("complainant_district"),
            bundle.get("complainant_province"),
        )
        return bundle

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events: List[Dict[Text, Any]] = []
        message = tracker.latest_message.get('text', '')
        self.logger.debug(f"{self.name()} - 🔍 [RASA DEBUG] Message: {message}")

        if message and "introduce" in message.lower():
            payload = self.parse_introduce_payload(message)

            province = payload.get('province')
            district = payload.get('district')
            flask_session_id = payload.get('flask_session_id')
            token = payload.get('t')

            qr_bundle = self._resolve_qr_token(token) if token else {}

            if qr_bundle:
                qr_district = qr_bundle.get("complainant_district")
                qr_province = qr_bundle.get("complainant_province")

                slot_pairs = [
                    ("qr_token", qr_bundle.get("qr_token")),
                    ("package_id", qr_bundle.get("package_id")),
                    ("package_label", qr_bundle.get("package_label")),
                    ("project_code", qr_bundle.get("project_code")),
                    ("location_code", qr_bundle.get("location_code")),
                    ("complainant_province", qr_province or province),
                    ("complainant_district", qr_district or district),
                ]
                for slot_name, slot_value in slot_pairs:
                    if slot_value:
                        events.append(SlotSet(slot_name, slot_value))
            else:
                if province and district:
                    events.extend([
                        SlotSet("complainant_province", province),
                        SlotSet("complainant_district", district),
                    ])

            if flask_session_id:
                events.append(SlotSet("flask_session_id", flask_session_id))

        utterance = self.get_utterance(1)
        buttons = self.get_buttons(1)
        self.logger.debug(f"{self.name()} - 🔍 [RASA DEBUG] Message: {utterance}")
        self.logger.debug(f"{self.name()} - 🔍 [RASA DEBUG] Buttons: {buttons}")
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return events
    

class ActionSetEnglish(BaseAction):
    def name(self) -> Text:
        return "action_set_english"
    
    async def execute_action(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("language_code", "en")]
    
class ActionSetNepali(BaseAction):
    def name(self) -> Text:
        return "action_set_nepali"
    
    async def execute_action(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("language_code", "ne")]

class ActionMainMenu(BaseAction):
    def name(self) -> Text:
        return "action_main_menu"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        district = tracker.get_slot("complainant_district")
        province = tracker.get_slot("complainant_province")
        package_label = tracker.get_slot("package_label")

        if package_label and district:
            # QR-scanned arrival: include the package label in the welcome.
            message = self.get_utterance(3)
            message = message.format(
                package_label=package_label,
                district=district,
                province=province or "",
            )
        elif district and province:
            message = self.get_utterance(2)
            message = message.format(
                district=district,
                province=province,
            )
        else:
            message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        seah_enabled = os.environ.get("ENABLE_SEAH_DEDICATED_FLOW", "true").strip().lower() in ("1", "true", "yes")
        if not seah_enabled:
            buttons = [b for b in buttons if b.get("payload") != "/seah_intake"]
        dispatcher.utter_message(text=message, buttons=buttons)


        return [SlotSet("story_main", None)]

class ActionOutro(BaseAction):
    def name(self) -> Text:
        return "action_outro"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        _deprecated_action_warning(self.logger, self.name())
        return []

#helpers
class ActionSetCurrentProcess(BaseAction):
    def name(self) -> Text:
        return "action_set_current_process"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        _deprecated_action_warning(self.logger, self.name())
        return []




    
#navigation actions
class ActionGoBack(BaseAction):
    def name(self):
        return "action_go_back"

    async def execute_action(self, dispatcher, tracker, domain):
        _deprecated_action_warning(self.logger, self.name())
        return []


    
    
class ActionRestartStory(BaseAction):
    def name(self) -> str:
        return "action_restart_story"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        current_process = tracker.get_slot("current_process")
        story_current = tracker.get_slot("story_current")

        process_name = current_process if current_process else "current process"
        story_name = story_current if story_current else "current story"

        message = self.get_utterance(1)
        buttons = self.get_buttons(1)

        dispatcher.utter_message(text=message, buttons=buttons)
        return []

    
    
class ActionShowCurrentStory(BaseAction):
    def name(self):
        return "action_show_story_current"

    async def execute_action(self, dispatcher, tracker, domain):
        _deprecated_action_warning(self.logger, self.name())
        return []

#mood actions
class ActionHandleMoodGreat(BaseAction):
    def name(self) -> str:
        return "action_handle_mood_great"

    async def execute_action(self, dispatcher, tracker, domain):
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

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return []
    
class ActionCustomFallback(BaseAction):
    def name(self):
        return "action_custom_fallback"

    async def execute_action(self, dispatcher, tracker, domain):
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return [UserUtteranceReverted()]


    
############################ HELPER ACTION - SKIP HANDLING ############################
class ActionHandleSkip(BaseAction):
    def name(self) -> Text:
        return "action_handle_skip"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        _deprecated_action_warning(self.logger, self.name())
        return []

class ActionGoodbye(BaseAction):
    def name(self) -> Text:
        return "action_goodbye"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return []
        
class ActionMoodUnhappy(BaseAction):
    def name(self) -> Text:
        return "action_mood_unhappy"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return []
        
class ActionExitWithoutFiling(BaseAction):
    def name(self) -> Text:
        return "action_exit_without_filing"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []



# Clear session action
class ActionClearSession(BaseAction): # Corrected class name if it was typo
    def name(self) -> Text:
        return "action_clear_session"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        self.logger.debug(f"{self.name()} - 🔍 [RASA DEBUG] ActionClearSession triggered")

        dispatcher.utter_message(
            # text=text_message, # Uncomment if you want text
            json_message={"custom": {"clear_window": True}} # Use custom field
        )
        return []





class ActionCloseBrowserTab(BaseAction):
    def name(self) -> Text:
        return "action_close_browser_tab"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
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

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        _deprecated_action_warning(self.logger, self.name())
        return []

class ActionAttachFiles(BaseAction):
    def name(self) -> Text:
        return "action_question_attach_files"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return []

class ActionDefaultFallback(BaseAction):
    def name(self) -> Text:
        return "action_default_fallback"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        #run the action_main_menu action
        return [ActionExecuted("action_main_menu")]

class ActionFileUploadStatus(BaseAction):
    def name(self) -> Text:
        return "action_file_upload_status"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        _deprecated_action_warning(self.logger, self.name())
        return []


