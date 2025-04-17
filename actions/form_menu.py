import re
import logging
from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from .base_classes import BaseFormValidationAction, BaseAction
from .utterance_mapping_rasa import get_utterance, get_buttons
from .generic_actions import get_language_code
logger = logging.getLogger(__name__)



class AskMenuFormLanguageCode(BaseAction):
    def name(self) -> Text:
        return "action_ask_menu_form_language_code"
    
    def run(self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
        ) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = get_utterance('menu_form', self.name(), 1, language)
        buttons = get_buttons('menu_form', self.name(), 1, language)
        print(message)
        print(buttons)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class AskMenuFormMainStory(BaseAction):
    def name(self) -> Text:
        return "action_ask_menu_form_main_story"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = tracker.latest_message.get('text', '')
        language = get_language_code(tracker)
        province = tracker.get_slot("user_province")
        district = tracker.get_slot("user_district")
        #ic(language, district, province)
        
        if province and district:
            welcome_text = get_utterance('menu_form', self.name(), 2, language).format(
                district=district,
                province=province
            )
        else:
            welcome_text = get_utterance('menu_form', self.name(), 1, language)
                
            
        if message and "/" in message:
            buttons = get_buttons('menu_form', self.name(), 1, language)
            dispatcher.utter_message(text=welcome_text, buttons=buttons)
        return []

class ValidateMenuForm(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_menu_form"
    
    async def required_slots(self, tracker: Tracker) -> List[Text]:
        return ["language_code", "main_story"]
    
    async def extract_language_code(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "language_code",
            tracker,
            dispatcher,
            domain
        )
    
    def validate_language_code(self, slot_value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        print("######################### validate_language_code #########################")
        value = slot_value.strip("/")
        if value not in ["en", "ne"]:
            dispatcher.utter_message(text="Invalid choice - use the buttons/ अवैध छानुहोस् - बटनहरू प्रयोग गर्नुहोस्")
            return {"language_code": None}
        ic(value)
        return {"language_code": value}
    
    async def extract_main_story(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "main_story",
            tracker,
            dispatcher,
            domain
        )
    
    def validate_main_story(self, slot_value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        print("######################### validate_main_story #########################")
        value = slot_value.strip("/")
        if value not in ["start_grievance_process",
                        "check_status",
                        "goodbye"]:
            dispatcher.utter_message(text="Invalid choice - use the buttons/ अवैध छानुहोस् - बटनहरू प्रयोग गर्नुहोस्")
            return {"main_story": None}
        ic(slot_value)
        return {"main_story": value}
    