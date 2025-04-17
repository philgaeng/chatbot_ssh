from typing import Any, Text, Dict, List, Optional
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction
from actions_server.db_manager import db_manager
from .utterance_mapping_rasa import get_utterance, get_buttons
from .base_classes import BaseFormValidationAction, BaseAction
from icecream import ic
# Initialize database connection
db = db_manager

class GrievanceHelpers:
    """Utility class for formatting grievance messages and buttons. Not a Rasa action."""
        
    def get_message_grievance_details(self, 
                                      language_code: str,
                                      grievance_dict: Dict) -> str:
        message = []
        for k,v in grievance_dict.items():
            ic(message)
            ic(k,v)
            utter = get_utterance("check_status", "actions_helpers", k, language_code)
            if utter:
                if v:
                    utter = utter.replace(f"{{{k}}}", v)
                else:
                    if language_code == "en":
                        utter = utter.replace(f"{{{k}}}", "Not provided")
                    else:
                        utter = utter.replace(f"{{{k}}}", "अप्रत्याशित")
            if utter:
                message.append(utter)
        message = "\n".join(message)
        return message
    
    def get_buttons_grievance_id(self,
                                 language_code: str,
                                grievance_id_list: Dict) -> List[Dict]:
        buttons = []
        buttons_dict = get_buttons("check_status", "actions_helpers", "grievance_id_buttons", language_code)
        title_buttons = buttons_dict.get("title")
        for k in grievance_id_list:
            buttons.append({"payload": f"/check_status{{'grievance_id': '{k}'}}", "title": f"{title_buttons} {k}"})
        return buttons

class ActionCheckStatusStart(BaseAction):
    def name(self) -> Text:
        return "action_check_status_start"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("main_story", "status_update")]

class ActionChooseRetrievalMethod(BaseAction):
    def name(self) -> Text:
        return "action_choose_retrieval_method"

    def run(self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        ic(f"------ {self.name()} ------")
        self.language_code = tracker.get_slot("language_code")
        message = get_utterance("check_status", "action_choose_retrieval_method", 1, self.language_code)
        buttons = get_buttons("check_status", "action_choose_retrieval_method", 1, self.language_code)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionDisplayGrievance(BaseAction):
    def __init__(self):
        self.grievance_helpers = GrievanceHelpers()

    def name(self) -> Text:
        return "action_display_grievance"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        self.language_code = tracker.get_slot("language_code")
        grievance_id = tracker.get_slot("grievance_id")
        phone_number = tracker.get_slot("user_contact_phone")
        if grievance_id:
            grievance_details = db.get_grievance_by_id(grievance_id)
            ic(grievance_details)
            if grievance_details:
                self._display_single_grievance(dispatcher, grievance_details)
            else:
                message = get_utterance("check_status", self.name(), 1, self.language_code)
                dispatcher.utter_message(text=message)
        elif phone_number:
            grievances = db.get_grievances_by_phone(phone_number)
            ic(grievances)
            if grievances:
                self._display_multiple_grievances(dispatcher, grievances)
            else:
                message = get_utterance("check_status", self.name(), 2, self.language_code)
                dispatcher.utter_message(text=message)
        else:
            message = get_utterance("check_status", self.name(), 3, self.language_code)
            dispatcher.utter_message(text=message)
        return []

    def _display_single_grievance(self, dispatcher: CollectingDispatcher, grievance_dict: Dict):
        try:
            message = self.grievance_helpers.get_message_grievance_details(language_code=self.language_code, 
                                                                         grievance_dict=grievance_dict) 
            dispatcher.utter_message(text=message)
        except:
            message = self.grievance_helpers.get_message_grievance_details(language_code=self.language_code, 
                                                                        grievance_dict=grievance_dict) 
                
            dispatcher.utter_message(text="\n\n".join(message))
        self._offer_status_check(dispatcher)

    def _display_multiple_grievances(self, 
                                     dispatcher: CollectingDispatcher, 
                                     grievances_list: List[Dict]):
        #deal with single grievance
        if len(grievances_list) == 1:
            self._display_single_grievance(dispatcher, grievances_list[0])
            return

        #deal with multiple grievances
        #launch the intro message
        message = get_utterance("check_status", 
                                "_display_multiple_grievances", 
                                1, self.language_code).format(len(grievances_list))
        dispatcher.utter_message(text=message)
        
        #create the message for each grievance
        for grievance in grievances_list:
            try:
                message = self.grievance_helpers.get_message_grievance_details(language_code=self.language_code, 
                                                                            grievance_dict=grievance)
            except:
                message_list = [
                    f"🔍 **ID:** {grievance['grievance_id']}",
                    f"📝 **Summary:** {grievance['grievance_summary']}",
                    f"📊 **Status:** {grievance['grievance_status']}",
                    f"📅 **Filed:** {grievance['grievance_creation_date']}"
                ]
            
                if grievance.get('grievance_next_step'):
                    message_list.append(f"➡️ **Next Step:** {grievance['grievance_next_step']}")
                
                message_list.append("-------------------")
                message = "\n".join(message_list)
            
            dispatcher.utter_message(text=message)
        
        #create the final message and related buttons
        grievances_id_list = [g['grievance_id'] for g in grievances_list]
        message = get_utterance("check_status", "_display_multiple_grievances", 2, self.language_code)
        try:
            buttons = self.grievance_helpers.get_buttons_grievance_id(language_code=self.language_code, 
                                                                   grievance_id_list=grievances_id_list)
        except:
            buttons = [{"payload": f"/check_status{{'grievance_id': '{g['grievance_id']}'}}", 
                     "title": f"Check {g['grievance_id']}"} for g in grievances_id_list]
        
        #display the final message and buttons
        dispatcher.utter_message(
            text=message,
            buttons=buttons
        )

    def _offer_status_check(self, dispatcher: CollectingDispatcher):
        message = get_utterance("check_status", "_offer_status_check", 1, self.language_code)
        buttons = get_buttons("check_status", "_offer_status_check", 1, self.language_code)
        dispatcher.utter_message(
            text=message,
            buttons=buttons
        )

class ActionCheckStatus(BaseAction):
    def __init__(self):
        self.grievance_helpers = GrievanceHelpers()

    def name(self) -> Text:
        return "action_check_status"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        self.language_code = tracker.get_slot("language_code")
        grievance_id = tracker.get_slot("grievance_id")
        if not grievance_id:
            message = get_utterance("check_status", self.name(), 1, self.language_code)
            dispatcher.utter_message(text=message)
            return []

        history = db.get_grievance_history(grievance_id)
        if not history:
            message = get_utterance("check_status", self.name(), 2, self.language_code)
            dispatcher.utter_message(text=message)
            return []

        latest = history[0]
        try:
            message = self.grievance_helpers.get_message_grievance_details(language_code=self.language_code, 
                                                                         grievance_dict=latest)
            
        except:
            message = [
                f"📊 **Current Status:** {latest['new_status']}",
                f"🕒 **Last Updated:** {latest['update_date']}"
            ]

            if latest.get('next_step'):
                message.append(f"➡️ **Next Step:** {latest['next_step']}")

            if latest.get('expected_resolution_date'):
                message.append(f"🎯 **Expected Resolution:** {latest['expected_resolution_date']}")

            if latest.get('notes'):
                message.append(f"📝 **Notes:** {latest['notes']}")
        utterance = get_utterance("check_status", self.name(), 3, self.language_code)
        buttons = get_buttons("check_status", self.name(), 1, self.language_code)

        dispatcher.utter_message(text="\n\n".join(message))

        dispatcher.utter_message(
            text= utterance,
            buttons=buttons
        )
        return []

class ValidateGrievanceIdForm(BaseFormValidationAction):
    def __init__(self):
        
        self.grievance_helpers = GrievanceHelpers()

    def name(self) -> Text:
        return "validate_grievance_id_form"
    
    async def extract_grievance_id(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Text:
        return await self._handle_slot_extraction(
            'grievance_id',
            tracker,
            dispatcher,
            domain
        )

    async def validate_grievance_grievance_id(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        ic(self.name())
        self.language_code = tracker.get_slot("language_code")
        
        # Check if the input is empty or not a string
        if not slot_value or not isinstance(slot_value, str):
            message = get_utterance("check_status", self.name(), 3, self.language_code)
            dispatcher.utter_message(text=message)
            return {"grievance_id": None}
            
        # Check if the ID starts with GR and contains only alphanumeric characters
        if not slot_value.startswith('GR') or not slot_value[2:].replace('-', '').isalnum():
            message = get_utterance("check_status", self.name(), 4, self.language_code)
            dispatcher.utter_message(text=message)
            return {"grievance_id": None}
            
        # Check if the grievance exists in the database
        if db.is_valid_grievance_id(slot_value):
            ic(slot_value)
            message = get_utterance("check_status", self.name(), 1, self.language_code)
            dispatcher.utter_message(text=message.format(grievance_id=slot_value))
            return {"grievance_id": slot_value}
        else:
            message = get_utterance("check_status", self.name(), 2, self.language_code)
            dispatcher.utter_message(text=message)
            return {"grievance_id": None}
        
class ActionAskGrievanceIdFormGrievanceId(BaseAction):
    def name(self) -> Text:
        return "action_ask_grievance_id_form_grievance_id"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        self.language_code = tracker.get_slot("language_code")
        message = get_utterance("check_status", self.name(), 1, self.language_code)
        dispatcher.utter_message(text=message)
        return []

class ActionRetrieveWithPhone(BaseAction):
    def __init__(self):
        self.grievance_helpers = GrievanceHelpers()

    def name(self) -> Text:
        return "action_retrieve_with_phone"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        self.language_code = tracker.get_slot("language_code")
        return [
            SlotSet("verification_context", "retrieval"),
        ]

class ActionShowStatusHistory(BaseAction):
    def __init__(self):
        
        self.grievance_helpers = GrievanceHelpers()

    def name(self) -> Text:
        return "action_show_status_history"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        self.language_code = tracker.get_slot("language_code")
        grievance_id = tracker.get_slot("grievance_id")
        if not grievance_id:
            message = get_utterance("check_status", self.name(), 1, self.language_code)
            dispatcher.utter_message(text=message)
            return []

        # Get full history
        history = db.get_grievance_history(grievance_id)
        if not history:
            message = get_utterance("check_status", self.name(), 2, self.language_code)
            dispatcher.utter_message(text=message)
            return []
        
        # Display header
        message = get_utterance("check_status", self.name(), 3, self.language_code).format(grievance_id)
        dispatcher.utter_message(text=message)
        try:
            list_of_messages = [get_utterance("check_status", self.name(), i, self.language_code)for i in range(4, 11)]
            final_list_of_messages = []
            for i in list_of_messages:
                if 'entry' in i:
                    for entry in history:
                        if str(entry) in i:
                            final_list_of_messages.append(i.format(entry))
                else:
                    final_list_of_messages.append(i)
                
            message = "\n".join(final_list_of_messages)
            dispatcher.utter_message(text=message)
        # # Display each status change
        except:
            message = []
            for entry in history:
                # Status change
                if entry['previous_status']:
                    
                    message.append(f"🔄 Status changed from '{entry['previous_status']}' to '{entry['new_status']}'")
                else:
                    message.append(f"📝 Initial status: '{entry['new_status']}'")
                
                # Date and updater
                message.append(f"📅 On: {entry['update_date']}")
                if entry.get('updated_by'):
                    message.append(f"👤 By: {entry['updated_by']}")
                
                # Next steps and resolution date
                if entry.get('next_step'):
                    message.append(f"➡️ Next Step: {entry['next_step']}")
                if entry.get('expected_resolution_date'):
                    message.append(f"🎯 Expected Resolution: {entry['expected_resolution_date']}")
                
                # Notes
                if entry.get('notes'):
                    message.append(f"📝 Notes: {entry['notes']}")
                
                # Send each entry as a separate message with a divider
                dispatcher.utter_message(text="\n".join(message))
            dispatcher.utter_message(text="-------------------")

        # Offer next actions    
        message = get_utterance("check_status", self.name(), 11, self.language_code)
        buttons = get_buttons("check_status", self.name(), 1, self.language_code)
        dispatcher.utter_message(
            text=message,
            buttons=buttons
        )
        return []

