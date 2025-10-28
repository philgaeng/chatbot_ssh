from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.events import SlotSet, FollowupAction
from rasa_chatbot.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction


class ActionStartStatusCheck(BaseAction):
    def name(self) -> Text:
        return "action_start_status_check"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        reset_slots = self.reset_slots(tracker, flow = "status_check", output = "slot_list")
        return [SlotSet("story_main", "status_check")] + reset_slots

class ValidateFormStatusCheck1(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_status_check_1"

    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        #cases where the form is quickly validated
        if tracker.get_slot("story_route") == self.SKIP_VALUE:
            return []
        if tracker.get_slot("list_grievance_id") == self.SKIP_VALUE:
                return []
        if tracker.get_slot("status_check_grievance_id_selected") == self.SKIP_VALUE:
                return []
        if tracker.get_slot("story_route") == "route_status_check_grievance_id":
            return ["story_route", "status_check_grievance_id_selected"]
        if tracker.get_slot("story_route") == "route_status_check_phone":
            # Phone collection is now handled by form_otp
                return ["story_route", "complainant_phone"]
        return ["story_route"]    
    
    
    async def extract_story_route(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_and_category_slot_extraction("story_route", tracker, dispatcher, domain)

    async def validate_story_route(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value in ["route_status_check_grievance_id", "route_status_check_grievance_id", self.SKIP_VALUE]:
            return {"story_route": slot_value}
        return {}

    async def extract_status_check_grievance_id_selected(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_slot_extraction("status_check_grievance_id_selected", tracker, dispatcher, domain)
    
    async def validate_status_check_grievance_id_selected(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            return {"status_check_grievance_id_selected": self.SKIP_VALUE,
            "status_check_grievance_selected_action": self.SKIP_VALUE}
        if self.validate_grievance_id_format(slot_value) == False:
            return {"status_check_grievance_id_selected": None,
            "status_check_grievance_id_selected_status": "invalid_format"}
        grievance_id = self.fetch_grievance_id_from_slot(slot_value)
        if grievance_id == False:
            return {"status_check_grievance_id_selected": None}
        if grievance_id:
            return {"status_check_grievance_id_selected": grievance_id}
        else:
            return {"status_check_grievance_id_selected": None,
            "status_check_grievance_id_selected_status": "no_grievance_found"}
        
    
    async def validate_complainant_phone(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        """
        Validate phone and retrieve grievances in one step.
        This optimizes the flow by fetching grievances during phone validation.
        """
        slots = self.base_validate_phone(slot_value, dispatcher)
        self.logger.debug(f"validate_complainant_phone: slots from base_validate_phone: {slots}")
        
        if slots.get("complainant_phone_valid") == True:
            # Phone is valid - retrieve associated grievances
            retrieve_grievance_slots = self._retrieve_and_set_grievances_by_phone(tracker)
            self.logger.debug(f"validate_complainant_phone: retrieve_grievance_slots: {retrieve_grievance_slots}")
            # Merge dictionaries - dict.update() returns None, so we use unpacking
            slots = {**slots, **retrieve_grievance_slots}
        
        return slots


class ValidateFormStatusCheck2(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_status_check_2"
    
    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        
        # Cases where the form is quickly validated
        if tracker.get_slot("story_route") == self.SKIP_VALUE:
            return []
        if tracker.get_slot("status_check_grievance_id_selected") == self.SKIP_VALUE:
                return []
        if tracker.get_slot("status_check_complainant_full_name") == self.SKIP_VALUE:
                return []
        if tracker.get_slot("list_grievance_id") == self.SKIP_VALUE:
                return []
        
        # Check if we need to retrieve grievances by phone first
        if tracker.get_slot("story_route") == "route_status_check_phone":
            self.logger.debug(f"{self.name()}: Need to retrieve grievances first - slot status_check_retrieve_grievances: {tracker.get_slot('status_check_retrieve_grievances')}")
            if not tracker.get_slot("status_check_retrieve_grievances"):
                # Need to retrieve grievances first
                return ["status_check_retrieve_grievances"]
        
        # If grievance already selected (e.g., from single result), skip to end
        if tracker.get_slot("status_check_grievance_id_selected") and "GR-" in tracker.get_slot("status_check_grievance_id_selected").strip()[:6]:
            return []
        
        # Determine what we need based on available data
        list_complainant_full_names = tracker.get_slot("complainant_list_full_names")
        if not list_complainant_full_names:
            return ["status_check_grievance_id_selected"]
        elif len(list_complainant_full_names) == 1:
            return ["status_check_grievance_id_selected"]
        else:
            return ["status_check_complainant_full_name", "status_check_grievance_id_selected"]
        

    
    async def extract_status_check_complainant_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:

        return await self._handle_slot_extraction("status_check_complainant_full_name", tracker, dispatcher, domain)

    async def validate_status_check_complainant_full_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        try:
            if slot_value == self.SKIP_VALUE:
                return {"complainant_full_name": self.SKIP_VALUE,
                "list_grievance_id": self.SKIP_VALUE,
                "story_route": self.SKIP_VALUE,
                "status_check_full_name_validated": False}
            if len(slot_value) < 3:
                return {
                    "status_check_complainant_full_name": None,
                    "status_check_full_name_validated": False,
                    "status_check_complainant_full_name_valid": False
                }
            list_grievances_by_phone = tracker.get_slot("list_grievances_by_phone")
            if not list_grievances_by_phone:
                return {}
            list_full_names = tracker.get_slot("complainant_list_full_names")
            full_name_matches = self.helpers.match_full_name_list(slot_value, list_full_names)
            self.logger.debug(f"validate_status_check_complainant_full_name: full_name_matches: {full_name_matches}")

            if full_name_matches:
                list_grievances_by_full_name = self.select_grievances_from_full_name_list(full_name_matches,  list_grievances_by_phone, dispatcher)
                self.logger.debug(f"validate_status_check_complainant_full_name: list_grievances_by_full_name: {list_grievances_by_full_name}")
                #choose the longest full name in list_grievances_by_full_name / we may implement a selection logic later on
                full_name = max(list_grievances_by_full_name, key=lambda x: len(x["complainant_full_name"]))
                full_name = full_name["complainant_full_name"]
                return {
                    "status_check_complainant_full_name": full_name,
                    "list_grievance_id": list_grievances_by_full_name,
                    "status_check_complainant_full_name_valid": True,
                    "status_check_full_name_validated": True
                    }
            
            self.logger.debug(f"validate_status_check_complainant_full_name: no matches: {full_name_matches} - slot not validated")
            return {
                "status_check_complainant_full_name": None,
                "status_check_full_name_validated": False,
                "status_check_complainant_full_name_valid": False
            }
        except Exception as e:
            self.logger.error(f"validate_status_check_complainant_full_name: error: {e}")
            return {
            }



    async def extract_status_check_grievance_id_selected(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "status_check_grievance_id_selected",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_status_check_grievance_id_selected(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            return {"status_check_grievance_id_selected": self.SKIP_VALUE,
            "status_check_grievance_selected_action": self.SKIP_VALUE}

        grievance_list = tracker.get_slot("list_grievance_id")
        self.logger.debug(f"validate_status_check_grievance_id_selected: slot_value: {slot_value}")
        self.logger.debug(f"validate_status_check_grievance_id_selected: grievance_list: {grievance_list}")
        grievance_id = slot_value.split("|")[1].strip()
        self.logger.debug(f"validate_status_check_grievance_id_selected: grievance_id: {grievance_id}")
        return {"status_check_grievance_id_selected": grievance_id}
        

    async def extract_status_check_grievance_selected_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "status_check_grievance_selected_action",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_status_check_grievance_selected_action(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            return {"status_check_grievance_selected_action": self.SKIP_VALUE}
        if "/" in slot_value:
            self.logger.debug(f"validate_status_check_grievance_selected_action: slot_value: {slot_value}")
            slot_value = slot_value.split("/")[1].strip()
            self.logger.debug(f"validate_status_check_grievance_selected_action: slot_value: {slot_value}")
        return {"status_check_grievance_selected_action": slot_value}




        
########################## AskActionsFormStatusCheck ######################

class ActionAskStatusCheckMethod(BaseAction):
    def name(self) -> Text:
        return "action_ask_status_check_method"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        utterance = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []

class ActionAskStatusCheckRetrieveGrievances(BaseAction):
    def name(self) -> Text:
        return "action_ask_status_check_retrieve_grievances"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        """
        Silent action - doesn't ask user for input.
        This is a trigger slot that processes in the background.
        The actual retrieval logic happens in validate_status_check_retrieve_grievances.
        """
        # Optional: Provide user feedback while processing
        # dispatcher.utter_message(text="🔍 Retrieving your grievances...")
        return []

class ActionAskStatusCheckListGrievanceId(BaseAction):
    def name(self) -> Text:
        return "action_ask_status_check_list_grievance_id"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        status_check_valid_list_grievance_id = tracker.get_slot("list_grievance_id_valid")
        if status_check_valid_list_grievance_id == None:
            utterance = self.get_utterance(1)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        if status_check_valid_list_grievance_id == False:
            utterance = self.get_utterance(2)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            
        return []




class ActionAskStatusCheckComplainantFullName(BaseAction):
    def name(self) -> Text:
        return "action_ask_status_check_complainant_full_name"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if tracker.get_slot("status_check_full_name_validated") == None:
            utterance = self.get_utterance(1)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)

        if tracker.get_slot("status_check_full_name_validated") == False:
            utterance = self.get_utterance(2)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
        return []



class ActionStatusCheckRequestFollowUp(BaseAction):
    def name(self) -> Text:
        return "action_status_check_request_follow_up"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        complainant_phone = tracker.get_slot("complainant_phone")
        grievance_id = tracker.get_slot("status_check_grievance_id_selected")
        if not tracker.get_slot("otp_status") == "verified":
            utterance = self.get_utterance(1)
            dispatcher.utter_message(text=utterance)
        else:
            utterance = self.get_utterance(2)
            utterance = utterance.format(grievance_id=grievance_id, complainant_phone=complainant_phone)
            dispatcher.utter_message(text=utterance)
            self.send_sms(sms_data = {"grievance_id": grievance_id,"complainant_phone": complainant_phone}, body_name="GRIEVANCE_STATUS_CHECK_REQUEST_FOLLOW_UP")

        email_data = self.collect_grievance_data_from_tracker(tracker)
        await self.send_recap_email_to_admin(email_data, "GRIEVANCE_STATUS_CHECK_REQUEST_FOLLOW_UP", dispatcher)
        return []

class ActionStatusCheckModifyGrievance(BaseAction):
    def name(self) -> Text:
        return "action_status_check_modify_grievance"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="utterance - modify grievance")
        return []


class ActionStatusCheckRetrieveComplainantData(BaseAction):
    def name(self) -> Text:
        return "action_status_check_retrieve_complainant_data"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        grievance_id = tracker.get_slot("status_check_grievance_id_selected")
        complainant_data = self.db_manager.get_complainant_data_by_grievance_id(grievance_id)
        
        if complainant_data:
            list_complainant_fields = [
                "complainant_id",
                "complainant_phone",
                "complainant_email",
                "complainant_full_name",
                "complainant_gender",
                "complainant_province",
                "complainant_district",
                "complainant_municipality",
                "complainant_village",
                "complainant_address",
            ]
            
            # Set all complainant data slots
            slot_events = [SlotSet(item, complainant_data.get(item)) 
                          for item in complainant_data.keys() 
                          if item in list_complainant_fields]
            
            # Check if phone is valid and set the validation slot
            if self.helpers.is_valid_phone(complainant_data.get("complainant_phone")):
                slot_events.append(SlotSet("status_check_complainant_phone_valid", True))
            else:
                slot_events.append(SlotSet("status_check_complainant_phone_valid", False))
            
            return slot_events
        else:
            # No complainant data found
            return [
                SlotSet("complainant_phone", None),
                SlotSet("status_check_complainant_phone_valid", False)
            ]



class ActionSkipStatusCheckOutro(BaseAction):
    def name(self) -> Text:
        return "action_skip_status_check_outro"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        province = tracker.get_slot("form_status_check_skip_complainant_province")
        district = tracker.get_slot("form_status_check_skip_complainant_district")
        municipality = tracker.get_slot("form_status_check_skip_complainant_municipality")
        office_in_charge_info = self.helpers.get_office_in_charge_info(municipality, district, province)
        buttons = self.get_buttons(1)
        if not office_in_charge_info: #no location information provided, exit 
            utterance = self.get_utterance(7)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            return []

        self.logger.debug(f"action_skip_status_check_outro: office_in_charge_info: {office_in_charge_info}")
        office_phone = office_in_charge_info.get("office_phone")
        office_name = office_in_charge_info.get("office_name")
        office_address = office_in_charge_info.get("office_address")
        office_pic_name = office_in_charge_info.get("office_pic_name")
        utterances = []
    
        if office_name: # information about the office found, compile and display the information
            utterances.append(self.get_utterance(2).format(office_name=office_name))
        if office_address:
            utterances.append(self.get_utterance(3).format(office_address=office_address)) 
        if office_phone:
            utterances.append(self.get_utterance(4).format(office_phone=office_phone))
        if office_pic_name:
            utterances.append(self.get_utterance(5).format(office_pic_name=office_pic_name))
        if len(utterances) == 0:
            utterance = self.get_utterance(6)
        else:
            utterances = [self.get_utterance(1)] + utterances
            utterance = "\n".join(utterances)
        
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []



class ActionAskStatusCheckGrievanceIdSelected(BaseAction):
    def name(self) -> Text:
        return "action_ask_status_check_grievance_id_selected"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        try:
            story_route = tracker.get_slot("story_route")
            if story_route == "route_status_check_grievance_id":
                status = tracker.get_slot("status_check_grievance_id_selected_status")
                if status == "invalid_format":
                    utterance = self.get_utterance(2)
                elif status == "no_grievance_found":
                    utterance = self.get_utterance(3)
                else:
                    utterance = self.get_utterance(1)
                buttons = self.get_buttons(1)
                dispatcher.utter_message(text=utterance, buttons=buttons)
            if story_route == "route_status_check_phone":
                list_grievances_by_id = tracker.get_slot("list_grievance_id")
                self.logger.debug(f"action_display_grievance_id: list_grievance_id: {list_grievances_by_id}")
                if list_grievances_by_id:
                    buttons = []
                    for grievance in list_grievances_by_id:
                        utterance = self.prepare_grievance_text_for_display(grievance, display_only_short=True)
                        if grievance.get("grievance_id"):
                            button = {"payload": f"/check_status|{grievance['grievance_id']}", "title": f"Check {grievance['grievance_id']}"}
                            buttons.append(button)
                            dispatcher.utter_message(text=utterance)
                        skip_button = self.get_buttons(2)[0]
                    self.logger.debug(f"action_display_grievance_id: skip_button: {skip_button}")
                    self.logger.debug(f"action_display_grievance_id: buttons before appending skip_button: {buttons}")
                    buttons.append(skip_button)
                    utterance = self.get_utterance(4)
                    self.logger.debug(f"action_display_grievance_id: buttons after appending skip_button: {buttons}")
                    dispatcher.utter_message(text=utterance, buttons=buttons)
                else:
                    utterance = self.get_utterance(5)
                    buttons = self.get_buttons(2)
                    dispatcher.utter_message(text=utterance, buttons=buttons)
            return []

        except Exception as e:
            self.logger.error(f"action_display_grievance_id: error: {e}")
            return []
