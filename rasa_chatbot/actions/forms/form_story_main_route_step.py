
from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_chatbot.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction





class ValidateMenuForm(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_story_main"
    
    async def required_slots(self, tracker: Tracker) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        return ["language_code", "story_main"]
    
    async def extract_language_code(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "language_code",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_language_code(self, slot_value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        self.logger.info("validate_language_code")
        value = slot_value.strip("/")
        if value not in ["en", "ne"]:
            utterance = self.get_utterance(1)
            dispatcher.utter_message(text=utterance)
            return {"language_code": None}
        return {"language_code": value}
    
    async def extract_story_main(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "story_main",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_story_main(self, slot_value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        
        value = slot_value.strip("/")
        self.logger.info(f"validate_story_main: {value}")
        if value not in ["new_grievance",
                        "check_status",
                        "goodbye"]:
            dispatcher.utter_message(text="Invalid choice - use the buttons/ अवैध छानुहोस् - बटनहरू प्रयोग गर्नुहोस्")
            return {"story_main": None}
        
        slots = self.reset_slots(tracker, value) if value in ["new_grievance", "check_status"] else {}
        slots['story_step'] = None #reset the story step if going to lose the memory of the current step
        slots.update({"story_main": value})
        return slots
    

class ValidateFormStoryStep(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_story_step"
    
    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        return ["story_step"]
    
    async def extract_story_step(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction("story_step", tracker, dispatcher, domain)
    
    async def validate_story_step(self, slot_value: Text, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            return {"story_step": self.SKIP_VALUE}
        else:
            return {"story_step": slot_value}
    
