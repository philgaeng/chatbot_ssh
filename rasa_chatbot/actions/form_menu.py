
import logging
from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Action, Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, SessionStarted, ActionExecuted, FollowupAction, ActiveLoop
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict
from .base_classes import BaseFormValidationAction, BaseAction
from .generic_actions import get_language_code



class AskMenuFormLanguageCode(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_menu_language_code"
    
    def execute_action(self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
        ) -> List[Dict[Text, Any]]:
        language = get_language_code(tracker)
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class AskMenuFormMainStory(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_menu_main_story"
    
    def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = tracker.latest_message.get('text', '')
        language = get_language_code(tracker)
        province = tracker.get_slot("complainant_province")
        district = tracker.get_slot("complainant_district")
        #ic(language, district, province)
        
        if province and district:
            utterance = self.get_utterance(2)
            utterance = utterance.format(
                district=district,
                province=province
            )
        else:
            utterance = self.get_utterance(1)
                
            
        if message and "/" in message:
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        return []

class ValidateMenuForm(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_menu"
    
    async def required_slots(self, tracker: Tracker) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        return ["language_code", "main_story"]
    
    async def extract_language_code(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "language_code",
            tracker,
            dispatcher,
            domain
        )
    
    def validate_language_code(self, slot_value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        self.logger.info("validate_language_code")
        value = slot_value.strip("/")
        if value not in ["en", "ne"]:
            utterance = self.get_utterance(1)
            dispatcher.utter_message(text=utterance)
            return {"language_code": None}
        return {"language_code": value}
    
    async def extract_main_story(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "main_story",
            tracker,
            dispatcher,
            domain
        )
    
    def validate_main_story(self, slot_value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        
        value = slot_value.strip("/")
        self.logger.info(f"validate_main_story: {value}")
        if value not in ["start_grievance_process",
                        "check_status",
                        "goodbye"]:
            dispatcher.utter_message(text="Invalid choice - use the buttons/ अवैध छानुहोस् - बटनहरू प्रयोग गर्नुहोस्")
            return {"main_story": None}
        return {"main_story": value}
    