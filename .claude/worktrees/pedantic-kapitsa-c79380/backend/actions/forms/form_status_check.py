import asyncio
from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.events import SlotSet, FollowupAction
from backend.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction


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
        if slot_value in ["route_status_check_phone", "route_status_check_grievance_id", self.SKIP_VALUE]:
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
        _sv = slot_value if not isinstance(slot_value, str) else (slot_value[:20] + "..." if len(slot_value) > 20 else slot_value)
        self.logger.info("validate_complainant_phone: entry | slot_value=%s", _sv)
        try:
            slots = self.base_validate_phone(slot_value, dispatcher)
            self.logger.info(
                "validate_complainant_phone: base_validate_phone done | complainant_phone_valid=%s",
                slots.get("complainant_phone_valid"),
            )
        except Exception as e:
            self.logger.exception(
                "validate_complainant_phone: base_validate_phone failed: %s",
                e,
            )
            raise

        if slots.get("complainant_phone_valid") == True:
            # Phone is valid - retrieve associated grievances (pass phone from slots;
            # tracker does not have complainant_phone set yet during validation)
            phone_used = slots.get("complainant_phone")
            self.logger.info("validate_complainant_phone: retrieving grievances by phone=%s", phone_used)
            try:
                retrieve_grievance_slots = self._retrieve_and_set_grievances_by_phone(
                    tracker, phone=phone_used
                )
                self.logger.info(
                    "validate_complainant_phone: _retrieve_and_set_grievances_by_phone done | keys=%s",
                    list(retrieve_grievance_slots.keys()) if retrieve_grievance_slots else None,
                )
            except Exception as e:
                self.logger.exception(
                    "validate_complainant_phone: _retrieve_and_set_grievances_by_phone failed: %s",
                    e,
                )
                raise
            slots = {**slots, **retrieve_grievance_slots}

        self.logger.info("validate_complainant_phone: returning slots keys=%s", list(slots.keys()))
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
        """
        Ask the user how they want to retrieve their grievance.

        Guard against duplicate prompts: once a concrete route has already been
        selected (phone or grievance_id), we avoid re-sending this generic
        explanation + buttons again in the same flow step.
        """
        story_route = tracker.get_slot("story_route")
        if story_route in ["route_status_check_phone", "route_status_check_grievance_id"]:
            # Route already chosen; don't repeat the method prompt.
            return []

        utterance = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []


class ActionAskFormStatusCheck1ComplainantPhone(BaseAction):
    """Status-check specific phone prompt (uses action_ask_form_status_check_1_complainant_phone utterance)."""

    def name(self) -> Text:
        return "action_ask_form_status_check_1_complainant_phone"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:
        status_valid = tracker.get_slot("status_check_complainant_phone_valid")
        if status_valid == "no_phone_found":
            message = self.get_utterance(3)
            buttons = self.get_buttons(1)
        elif tracker.get_slot("complainant_phone_valid") is False:
            message = self.get_utterance(2)
            buttons = self.get_buttons(2)
        else:
            message = self.get_utterance(1)
            buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
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



class LegacyActionStatusCheckRequestFollowUp(BaseAction):
    def name(self) -> Text:
        return "action_status_check_request_follow_up_legacy"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        self._initialize_language_and_helpers(tracker)
        complainant_phone = tracker.get_slot("complainant_phone")
        grievance_id = tracker.get_slot("status_check_grievance_id_selected")
        if not tracker.get_slot("otp_status") == "verified":
            utterance = self.get_utterance(1)
            dispatcher.utter_message(text=utterance)
            issue = self.get_follow_up_phone_issue(tracker)
            if issue == "no_phone":
                dispatcher.utter_message(text=self.get_utterance(3))
            else:
                dispatcher.utter_message(text=self.get_utterance(4))
            buttons = self.get_buttons(2)
            dispatcher.utter_message(buttons=buttons)
        else:
            # First, show the grievance details so the user can see what was found.
            if grievance_id:
                grievance = self.collect_grievance_data_from_id(grievance_id, tracker, domain)
                if grievance:
                    grievance_text = self.prepare_grievance_text_for_display(
                        grievance, display_only_short=False
                    )
                    dispatcher.utter_message(text=grievance_text)

            utterance = self.get_utterance(2)
            utterance = utterance.format(grievance_id=grievance_id, complainant_phone=complainant_phone)
            dispatcher.utter_message(text=utterance)
            self.send_sms(sms_data = {"grievance_id": grievance_id,"complainant_phone": complainant_phone}, body_name="GRIEVANCE_STATUS_CHECK_REQUEST_FOLLOW_UP")

        # Build email data and send admin recap in the background so a slow/failing email
        # (e.g. AWS SES timeout) does not block or timeout the chatbot response.
        email_data = self.collect_grievance_data_from_tracker(tracker)
        if grievance_id:
            grievance = self.db_manager.get_grievance_by_id(grievance_id)
            if grievance:
                email_data["grievance_id"] = grievance_id
                email_data["grievance_timeline"] = grievance.get("grievance_timeline") or self.NOT_PROVIDED
                email_data["grievance_summary"] = grievance.get("grievance_summary") or grievance.get("grievance_description") or self.NOT_PROVIDED
                email_data["grievance_description"] = email_data.get("grievance_description") or grievance.get("grievance_description") or self.NOT_PROVIDED
                email_data["grievance_categories"] = grievance.get("grievance_categories") or email_data.get("grievance_categories") or self.NOT_PROVIDED
        def _log_email_done(task: asyncio.Task) -> None:
            try:
                task.result()
            except Exception as e:
                self.logger.error(f"Background admin recap email failed: {e}", exc_info=True)

        task = asyncio.create_task(
            self.send_recap_email_to_admin(email_data, "GRIEVANCE_STATUS_CHECK_REQUEST_FOLLOW_UP", dispatcher)
        )
        task.add_done_callback(_log_email_done)
        return []

class ActionStatusCheckModifyGrievance(BaseAction):
    def name(self) -> Text:
        return "action_status_check_modify_grievance"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        self._initialize_language_and_helpers(tracker)
        utterance = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []


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


# Alias for tests that expect a single status-check form class
ValidateFormStatusCheck = ValidateFormStatusCheck1
