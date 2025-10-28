"""
Common action_ask methods shared across multiple forms.
These are reusable action_ask methods that don't belong to a specific form.
Uses generic naming (action_ask_slot_name) for better reusability across forms.
"""

from typing import Any, Text, Dict, List
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import FollowupAction
from rasa_sdk.types import DomainDict
from rasa_chatbot.actions.base_classes.base_classes import BaseAction


#-----------------------------------------------------------------------------
# Flow Common Actions
#-----------------------------------------------------------------------------


class ActionAskStoryStep(BaseAction):
    def name(self) -> Text:
        return "action_ask_story_step"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
    
        story_route = tracker.get_slot("story_route")
        if story_route in ["route_status_check_grievance_id", "route_status_check_phone"]:
            grievance_id = tracker.get_slot("status_check_grievance_id_selected")
            if grievance_id:
                grievance_data = self.collect_grievance_data_from_id(grievance_id, tracker, domain)
                if grievance_data:
                    utterance = self.get_utterance(1)
                    buttons = self.get_buttons(1)
                    dispatcher.utter_message(text=utterance)
                    grievance_text = self.prepare_grievance_text_for_display(grievance_data, display_only_short=False)
                    dispatcher.utter_message(text=grievance_text, buttons=buttons)
                else:
                    utterance = self.get_utterance(2)
                    buttons = self.get_buttons(2)
                    dispatcher.utter_message(text=utterance, buttons=buttons)
        return []


class ActionAskStoryRoute(BaseAction):
    def name(self) -> Text:
        return "action_ask_story_route"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        story_main = tracker.get_slot("story_main")
        if story_main == "status_check":
            utterance = self.get_utterance(1)
            buttons = self.get_buttons(1)
            self.logger.info(f"action_ask_story_route: utterance: {utterance}, buttons: {buttons}")
            dispatcher.utter_message(text=utterance, buttons=buttons)
        if story_main == "status_check_modify":
            utterance = self.get_utterance(2)
            buttons = self.get_buttons(2)
            self.logger.info(f"action_ask_story_route: utterance: {utterance}, buttons: {buttons}")
            dispatcher.utter_message(text=utterance, buttons=buttons)
        return []




class ActionAskLanguageCode(BaseAction):
    def name(self) -> Text:
        return "action_ask_language_code"
    
    async def execute_action(self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]
        ) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskStoryMain(BaseAction):
    def name(self) -> Text:
        return "action_ask_story_main"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = tracker.latest_message.get('text', '')
        province = tracker.get_slot("complainant_province")
        district = tracker.get_slot("complainant_district")
        
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

#-----------------------------------------------------------------------------
# Contact/Location Generic Actions (Reusable across forms)
#-----------------------------------------------------------------------------

class ActionAskComplainantPhone(BaseAction):
    def name(self) -> Text:
        return "action_ask_complainant_phone"
    
    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        if tracker.get_slot("complainant_phone_valid") == False:
            message = self.get_utterance(2)
            buttons = self.get_buttons(2)
        else:
            message = self.get_utterance(1)
            buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionAskComplainantLocationConsent(BaseAction):
    def name(self) -> str:
        return "action_ask_complainant_location_consent"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantMunicipalityTemp(BaseAction):
    def name(self) -> str:
        return "action_ask_complainant_municipality_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        province = tracker.get_slot("complainant_province")
        district = tracker.get_slot("complainant_district")
        message = self.get_utterance(1).format(district=district, province=province)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

    
class ActionAskComplainantMunicipalityConfirmed(BaseAction):
    def name(self) -> str:
        return "action_ask_complainant_municipality_confirmed"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        validated_municipality = tracker.get_slot('complainant_municipality_temp')
        message = self.get_utterance(1).format(validated_municipality=validated_municipality)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
       
class ActionAskComplainantVillageTemp(BaseAction):
    def name(self) -> str:
        return "action_ask_complainant_village_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionAskComplainantVillageConfirmed(BaseAction):
    def name(self) -> str:
        return "action_ask_complainant_village_confirmed"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        validated_village = tracker.get_slot('complainant_village_temp')
        validated_ward = tracker.get_slot('complainant_ward')
        message = self.get_utterance(1).format(validated_village=validated_village, validated_ward=validated_ward)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionAskComplainantWard(BaseAction):
    def name(self) -> str:
        return "action_ask_complainant_ward"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantAddressTemp(BaseAction):
    def name(self) -> str:
        return "action_ask_complainant_address_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantAddressConfirmed(BaseAction):
    def name(self) -> str:
        return "action_ask_complainant_address_confirmed"
    
    async def execute_action(self,
                  dispatcher: CollectingDispatcher,
                  tracker: Tracker,
                  domain: dict
                  ):
        #check if the address and village are correct
        municipality = tracker.get_slot('complainant_municipality')
        village = tracker.get_slot('complainant_village')
        address = tracker.get_slot('complainant_address_temp')
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        message = message.format(municipality=municipality, village=village, address=address)
            
        dispatcher.utter_message(
            text=message,
            buttons=buttons
        )
        return []
    

class ActionAskComplainantProvince(BaseAction):
    def name(self) -> str:
        return "action_ask_complainant_province"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantDistrict(BaseAction):
    def name(self) -> str:
        return "action_ask_complainant_district"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
 

class ActionAskComplainantConsent(BaseAction):
    def name(self) -> str:
        return "action_ask_complainant_consent"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantFullName(BaseAction):
    def name(self) -> Text:
        return "action_ask_complainant_full_name"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if tracker.get_slot("grievance_sensitive_issue") ==self.SKIP_VALUE:
            message = self.get_utterance(1)
        else:
            message = self.get_utterance(2)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantEmailTemp(BaseAction):
    def name(self) -> Text:
        return "action_ask_complainant_email_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantEmailConfirmed(BaseAction):
    def name(self) -> Text:
        return "action_ask_complainant_email_confirmed"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        domain_name = tracker.get_slot("complainant_email_temp").split('@')[1]
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        message = message.format(domain_name=domain_name)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []