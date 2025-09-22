from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_chatbot.actions.utils.base_classes import BaseFormValidationAction, BaseAction


class ValidateFormStatusCheck(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_status_check"
    
    async def required_slots(self, tracker: Tracker) -> List[Text]:
        if tracker.get_slot("status_check_method") == "grievance_id":
            return ["status_check_method", "status_check_list_grievance_id", "status_check_complainant_phone", "status_check_complainant_full_name"]
        if tracker.get_slot("status_check_method") == "complainant_phone":
            return ["status_check_method", "status_check_complainant_phone", "status_check_complainant_full_name", "status_check_list_grievance_id"]
        if tracker.get_slot("status_check_method") == self.SKIP_VALUE:
            return []
        

    async def extract_status_check_method(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_boolean_and_category_slot_extraction("status_check_method", tracker, dispatcher, domain)

    async def validate_status_check_method(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if "grievance_id" in slot_value:
            return {"status_check_method": "grievance_id"}
        if "phone" in slot_value:
            return {"status_check_method": "complainant_phone"}
        if slot_value == self.SKIP_VALUE:
            return {"status_check_method": self.SKIP_VALUE}
        
    
    async def extract_status_check_list_grievance_id(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction("status_check_list_grievance_id", tracker, dispatcher, domain)

    async def validate_status_check_list_grievance_id(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            return {"status_check_list_grievances_by_id": self.SKIP_VALUE}
        if "phone" in slot_value:
            return {"status_check_list_grievances_by_id": None,
            "status_check_method": "complainant_phone"}
        else:
            if self.db_manager.is_valid_grievance_id(slot_value):
                return {"status_check_list_grievances_by_id": [slot_value],
                "status_check_list_grievance_id_valid": True}
            else:
                return {"status_check_list_grievance_id_valid": False}

    async def extract_status_check_complainant_phone(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction("status_check_complainant_phone", tracker, dispatcher, domain)

    async def validate_status_check_complainant_phone(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        """Validate phone number and set validation requirement.
        - check if the phone is of valid format
        - retrieve the list of grievances from db if the phone is valid
        Then -check if grievances are retrived
        - if grievances are retrived, check if there is only one grievance
        - if there is only one grievance, return the grievance id
        - if there are multiple grievances, check if the full name of the complainant is the same
        - if the full name is the same, return the grievance id and skip the full name validation by returning the full name inside the complainant_name slot
        - if the full name is not the same, validate complainant_phone slot and move to the next slot eg full name validation
        """
        if slot_value == self.SKIP_VALUE:
            return {"status_check_complainant_phone": self.SKIP_VALUE}
        
        if not self.helpers.is_valid_phone(slot_value):
                return {"status_check_complainant_phone_valid": "invalid_number"}


        standardized_phone = self.helpers._standardize_phone_number(slot_value)
        list_grievances_by_phone = self.db_manager.get_grievance_by_complainant_phone(standardized_phone)
        if len(list_grievances_by_phone) == 0:
            return {"status_check_complainant_phone_valid": "no_phone_found"}

        list_full_names = [grievance["complainant_name"] for grievance in list_grievances_by_phone]
        unique_full_names = self.match_similar_full_names_in_list(list_full_names)
        if len(self.unique_full_names) == 1:
            return {"status_check_complainant_phone": slot_value,
                "status_check_list_grievances_by_phone": list_grievances_by_phone,
                "status_check_complainant_name": list_grievances_by_phone[0]["complainant_name"],
                "status_check_list_grievance_id": list_grievances_by_phone,
                "status_check_complainant_phone_valid": True}
        else:
                return {"status_check_complainant_phone": slot_value,
                "status_check_list_grievances_by_phone": list_grievances_by_phone,
                "status_check_complainant_phone_valid": True,
                "status_check_unique_full_names": unique_full_names}


    async def extract_status_check_complainant_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:

        return await self._handle_slot_extraction("status_check_complainant_full_name", tracker, dispatcher, domain)

    async def validate_status_check_complainant_full_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            return {"status_check_complainant_full_name": self.SKIP_VALUE,
            "status_check_list_grievance_id": self.SKIP_VALUE,
            "status_check_full_name_validated": False}
        unique_full_names = tracker.get_slot("status_check_unique_full_names")
        full_name_matches = self.helpers.match_full_name(slot_value, unique_full_names)
        if len(full_name_matches) == 0:
            return {"status_check_complainant_full_name": None,
            "status_check_full_name_validated": False}
        else:
            match_full_name = full_name_matches[0][0]
            list_grievances_by_phone = tracker.get_slot("status_check_list_grievances_by_phone")
            list_grievances_by_full_name = self.select_grievances_from_full_name_list(match_full_name,  list_grievances_by_phone, dispatcher)
            return {"status_check_complainant_full_name": slot_value,
            "status_check_list_grievances_by_full_name": list_grievances_by_full_name,
            "status_check_complainant_full_name_valid": True,
            "status_check_full_name_validated": True}

    def select_grievances_from_full_name_list(self, full_name: str, list_grievances_by_phone: list, dispatcher: CollectingDispatcher) -> List[str]:
        matching_grievance_list = []
        for grievance in list_grievances_by_phone:
            if self.match_full_name(full_name, grievance["complainant_name"]):
                matching_grievance_list.append(grievance)
        if len(matching_grievance_list) == 0:
            return []
        #sort the matching grievances by status and status date
        #first we sort by status, where all the closed cases are at the end and the rest are at the beginning
        #amongst the rest we sort by status date
        matching_grievance_not_closed = [grievance for grievance in matching_grievance_list if grievance["grievance_status"] not in ["CLOSED"]]
        matching_grievance_not_closed.sort(key=lambda x: x["grievance_creation_date"], reverse=True)
        matching_grievance_closed = [grievance for grievance in matching_grievance_list if grievance["grievance_status"] in ["CLOSED"]]
        matching_grievance_closed.sort(key=lambda x: x["grievance_creation_date"], reverse=True)
        return matching_grievance_not_closed + matching_grievance_closed
        
    def match_similar_full_names_in_list(self, list_full_names: list) -> list:
        unique_full_names = []
        for full_name in list_full_names:
            list_full_names = list_full_names.pop(0)
            if full_name not in unique_full_names:
                #we check if the full name is similar to any of the remaining full names in the list and add it to the resuls if it is not.
                if len(self.helpers.match_full_name(full_name, list_full_names)) == 0:
                    unique_full_names.append(full_name)
        return unique_full_names



class ValidateFormSkipStatusCheck(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_skip_status_check"

    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        """Determine required slots based on validation status"""
        
        # Case 1: Province and district are already valid - only need municipality
        if tracker.get_slot("form_skip_status_check_valid_province_and_district"):
            return ["form_skip_status_check_complainant_municipality_temp", "form_skip_status_check_complainant_municipality_confirmed"]
        
        # Case 2: Province and district are invalid - need to re-collect all location data
        if tracker.get_slot("form_skip_status_check_valid_province_and_district") == False:
            return [
                "form_skip_status_check_complainant_province", 
                "form_skip_status_check_complainant_district", 
                "form_skip_status_check_complainant_municipality_temp", 
                "form_skip_status_check_complainant_municipality_confirmed"
            ]
        
        # Case 3: No validation status set yet - need to validate existing data
        if tracker.get_slot("form_skip_status_check_valid_district") is None:
            return ["status_check_valid_province_and_district"]
        
        # Default case - no slots required
        return []

    async def extract_form_skip_status_check_complainant_district(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_boolean_and_category_slot_extraction(
            "form_skip_status_check_complainant_district",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_form_skip_status_check_complainant_district(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_slot_validation(
            "form_skip_status_check_complainant_district",
            slot_value,
            dispatcher,
            tracker,
            domain
        )
        return {"form_skip_status_check_complainant_district": slot_value}
        
    async def extract_form_skip_status_check_complainant_province(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_province",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_form_skip_status_check_complainant_province(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            message = self.get_utterance(1)
            dispatcher.utter_message(
                text=message
            )
            return {"complainant_province": None}
        
        #check if the province is valid
        if not self.helpers.check_province(slot_value):
            message = self.get_utterance(2)
            message = message.format(slot_value=slot_value)
            dispatcher.utter_message(
                text=message
            )
            return {"complainant_province": None}
        
        result = self.helpers.check_province(slot_value).title()
        message = self.get_utterance(3) 
        message = message.format(slot_value=slot_value, result=result)
        dispatcher.utter_message(
            text=message
        )
        
        return {"complainant_province": result}
        
    async def extract_complainant_district(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(  
            "complainant_district",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_complainant_district(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        if slot_value == self.SKIP_VALUE:
            message = self.get_utterance(1)
            dispatcher.utter_message(
                text=message
            )
            return {"complainant_district": None}
            
        province = tracker.get_slot("complainant_province").title()
        if not self.helpers.check_district(slot_value, province):
            message = self.get_utterance(2)
            message = message.format(slot_value=slot_value)
            dispatcher.utter_message(
                text=message
            )
            return {"complainant_district": None}
            
        result = self.helpers.check_district(slot_value, province).title()
        message = self.get_utterance(3)
        message = message.format(slot_value=slot_value, result=result)
        dispatcher.utter_message(
            text=message
        )
        
        return {"complainant_district": result}
        
        
    
    async def extract_complainant_municipality_temp(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "complainant_municipality_temp",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_complainant_municipality_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        
        #deal with the slot_skipped case
        if slot_value == self.SKIP_VALUE:
            return {"complainant_municipality_temp": self.SKIP_VALUE,
                    "complainant_municipality": self.SKIP_VALUE,
                    "complainant_municipality_confirmed": False}
        
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            return {"complainant_municipality_temp": None}
                
        # Validate new municipality input with the extract and rapidfuzz functions
        validated_municipality = self.helpers.validate_municipality_input(slot_value, 
                                                                   tracker.get_slot("complainant_province"),
                                                                   tracker.get_slot("complainant_district"))
        
        if validated_municipality:
            return {"complainant_municipality_temp": validated_municipality}
        
        else:
            return {"complainant_municipality_temp": None,
                    "complainant_municipality": None,
                    "complainant_municipality_confirmed": None
                    }
                
                
    async def extract_complainant_municipality_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # First check if we have a municipality to confirm
        if not tracker.get_slot("complainant_municipality_temp"):
            return {}

        return await self._handle_boolean_and_category_slot_extraction(
            "complainant_municipality_confirmed",
            tracker,
            dispatcher,
            domain  # When skipped, assume confirmed
        )
    
    async def validate_complainant_municipality_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        if slot_value == True:
            
        #save the municipality to the slot
            result = {"complainant_municipality_confirmed": True,
                    "complainant_municipality": tracker.get_slot("complainant_municipality_temp")}
            
        elif slot_value == False:
            result = {"complainant_municipality_confirmed": None,
                    "complainant_municipality_temp": None,
                    "complainant_municipality": None
                    }
        else:
            result = {}
        self.logger.debug(f"Validate complainant_municipality_confirmed: {result}")
        return result
        
        
    ########################## AskActionsFormStatusCheck ######################

    class ActionAskFormStatusCheckMethod(BaseAction):
        def name(self) -> Text:
            return "action_ask_form_status_check_method"
        
        async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
            utterance = self.get_utterance(1)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            return []

    class ActionAskFormStatusCheckListGrievanceId(BaseAction):
        def name(self) -> Text:
            return "action_ask_form_status_check_list_grievance_id"
        
        async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
            status_check_valid_list_grievance_id = tracker.get_slot("status_check_list_grievance_id_valid")
            if status_check_valid_list_grievance_id == None:
                utterance = self.get_utterance(1)
                buttons = self.get_buttons(1)
                dispatcher.utter_message(text=utterance, buttons=buttons)
            if status_check_valid_list_grievance_id == False:
                utterance = self.get_utterance(2)
                buttons = self.get_buttons(1)
                dispatcher.utter_message(text=utterance, buttons=buttons)
                
            return []

    class ActionAskFormStatusCheckComplainantPhone(BaseAction):
        def name(self) -> Text:
            return "action_ask_form_status_check_complainant_phone"
        
        async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
            if tracker.get_slot("status_check_complainant_phone_valid") == "invalid_number":
                utterance = self.get_utterance(2)
                buttons = self.get_buttons(1)
            if tracker.get_slot("status_check_complainant_phone_valid") == "no_phone_found":
                utterance = self.get_utterance(3)
                buttons = self.get_buttons(1)
            else:
                utterance = self.get_utterance(1)
                buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            return []

    class ActionAskFormStatusCheckComplainantFullName(BaseAction):
        def name(self) -> Text:
            return "action_ask_form_status_check_complainant_full_name"
        
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

    ########################## AskActionsFormSkipStatusCheck ######################

    class ActionAskFormSkipStatusCheckValidProvinceAndDistrict(BaseAction):
        def name(self) -> Text:
            return "action_ask_form_skip_status_check_valid_province_and_district"
        
        async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
            if tracker.get_slot("form_skip_status_check_valid_province_and_district") == None:
                province = tracker.get_slot("complainant_province")
                district = tracker.get_slot("complainant_district")
                utterance = self.get_utterance(1)
                utterance = utterance.format(province=province, district=district)
                buttons = self.get_buttons(1)
                dispatcher.utter_message(text=utterance, buttons=buttons)
            return []


    ########################## DisplayActionsFormStatusCheck ######################

    class ActionDisplayGrievanceId(BaseAction):
        def name(self) -> Text:
            return "action_display_grievance_id"
        
        async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
            list_grievances_by_id = tracker.get_slot("status_check_list_grievances_by_id")
            for grievance in list_grievances_by_id:
                utterance = self.display_grievance_id(grievance)
                dispatcher.utter_message(text=utterance)
            utterance = self.get_utterance(1)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            return []

        def display_grievance_id(self, grievance: Dict) -> str:
            key_mapping_language = {
                "grievance_id": {"en": "grievance_id", "ne": "गुनासो ID"},
                "grievance_creation_date": {"en": "Grievance creation date", "ne": "गुनासो सिर्जना गरिएको"},
                "grievance_status": {"en": "Grievance status", "ne": "गुनासो स्थिति"},
                "grievance_status_update_date": {"en": "Grievance status update date", "ne": "गुनासो स्थिति अपडेट गरिएको"},
                "grievance_categories": {"en": "Grievance categories", "ne": "गुनासो श्रेणी"},
            }
            utterance = []
            for k,v in grievance.items():
                if k in key_mapping_language:
                    denomination = key_mapping_language[k][self.language_code]
                    if k == "grievance_status":
                        v = self.get_status_and_description_str_in_language(v)
                    if v:
                        utterance.append(f"{denomination}: {v}")
            utterance = "\n".join(utterance)
            return utterance