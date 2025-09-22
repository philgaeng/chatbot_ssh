from typing import Any, Text, Dict, List, Optional, Union, Tuple

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from rasa_sdk.events import SlotSet
from rasa_chatbot.actions.utils.base_classes import BaseFormValidationAction, BaseAction


class ValidateFormStatusCheck(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_status_check"
    
    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        self._initialize_language_and_helpers(tracker)
        if tracker.get_slot("status_check_method") == "grievance_id":
            return ["status_check_method", "status_check_list_grievance_id", "status_check_complainant_phone", "status_check_complainant_full_name"]
        if tracker.get_slot("status_check_method") == "complainant_phone":
            return ["status_check_method", "status_check_complainant_phone", "status_check_complainant_full_name", "status_check_list_grievance_id"]
        if tracker.get_slot("status_check_method") == self.SKIP_VALUE:
            return []
        return ["status_check_method"]
        

    async def extract_status_check_method(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_boolean_and_category_slot_extraction("status_check_method", tracker, dispatcher, domain)

    async def validate_status_check_method(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if "grievance_id" in slot_value:
            return {"status_check_method": "grievance_id"}
        if "phone" in slot_value:
            return {"status_check_method": "complainant_phone"}
        if slot_value == self.SKIP_VALUE:
            return {"status_check_method": self.SKIP_VALUE}
        return {}
        
    
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


        standardized_phone = self.helpers.standardize_phone(language_code=self.language_code, phone=slot_value)
        list_grievances_by_phone = self.db_manager.get_grievance_by_complainant_phone(standardized_phone)
        self.logger.debug(f"validate_status_check_complainant_phone: list_grievances_by_phone: {list_grievances_by_phone}")
        if len(list_grievances_by_phone) == 0:
            return {"status_check_complainant_phone_valid": "no_phone_found"}

        # Convert datetime objects to strings for JSON serialization
        serializable_grievances = []
        for grievance in list_grievances_by_phone:
            serializable_grievance = {}
            for key, value in grievance.items():
                if hasattr(value, 'isoformat'):  # datetime object
                    serializable_grievance[key] = value.isoformat()
                else:
                    serializable_grievance[key] = value
            serializable_grievances.append(serializable_grievance)

        list_full_names = [grievance["complainant_full_name"] for grievance in serializable_grievances]
        unique_full_names = self.match_similar_full_names_in_list(list_full_names)
        if len(unique_full_names) == 1:
            return {"status_check_complainant_phone": slot_value,
                "status_check_list_grievances_by_phone": serializable_grievances,
                "status_check_complainant_name": serializable_grievances[0]["complainant_full_name"],
                "status_check_list_grievance_id": serializable_grievances,
                "status_check_complainant_phone_valid": True}
        else:
                return {"status_check_complainant_phone": slot_value,
                "status_check_list_grievances_by_phone": serializable_grievances,
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
            if self.helpers.match_full_name(full_name, grievance["complainant_full_name"]):
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
        remaining_names = list_full_names.copy()
        
        for full_name in list_full_names:
            if full_name not in unique_full_names:
                # Remove current name from remaining names for comparison
                remaining_names = [name for name in remaining_names if name != full_name]
                # Check if the full name is similar to any of the remaining full names
                if len(self.helpers.match_full_name(full_name, remaining_names)) == 0:
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

        return {"form_skip_status_check_complainant_district": slot_value}
        
    async def extract_form_skip_status_check_complainant_province(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "form_skip_status_check_complainant_province",
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
            return {"form_skip_status_check_complainant_province": None}
        
        #check if the province is valid
        if not self.helpers.check_province(slot_value):
            message = self.get_utterance(2)
            message = message.format(slot_value=slot_value)
            dispatcher.utter_message(
                text=message
            )
            return {"form_skip_status_check_complainant_province": None}
        
        result = self.helpers.check_province(slot_value).title()
        message = self.get_utterance(3) 
        message = message.format(slot_value=slot_value, result=result)
        dispatcher.utter_message(
            text=message
        )
        
        return {"form_skip_status_check_complainant_province": result}
        
    async def extract_form_skip_status_check_complainant_district(
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
        
    async def validate_form_skip_status_check_complainant_district(
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
            return {"form_skip_status_check_complainant_district": None}
            
        province = tracker.get_slot("form_skip_status_check_complainant_province").title()
        if not self.helpers.check_district(slot_value, province):
            message = self.get_utterance(2)
            message = message.format(slot_value=slot_value)
            dispatcher.utter_message(
                text=message
            )
            return {"form_skip_status_check_complainant_district": None}
            
        result = self.helpers.check_district(slot_value, province).title()
        message = self.get_utterance(3)
        message = message.format(slot_value=slot_value, result=result)
        dispatcher.utter_message(
            text=message
        )
        
        return {"form_skip_status_check_complainant_district": result}
        
        
    
    async def extract_form_skip_status_check_complainant_municipality_temp(
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
        
    async def validate_form_skip_status_check_complainant_municipality_temp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        
        #deal with the slot_skipped case
        if slot_value == self.SKIP_VALUE:
            return {"form_skip_status_check_complainant_municipality_temp": self.SKIP_VALUE,
                    "form_skip_status_check_complainant_municipality": self.SKIP_VALUE,
                    "form_skip_status_check_complainant_municipality_confirmed": False}
        
        # First validate string length
        if not self._validate_string_length(slot_value, min_length=2):
            return {"form_skip_status_check_complainant_municipality_temp": None}
                
        # Validate new municipality input with the extract and rapidfuzz functions
        validated_municipality = self.helpers.validate_municipality_input(slot_value, 
                                                                   tracker.get_slot("form_skip_status_check_complainant_province"),
                                                                   tracker.get_slot("form_skip_status_check_complainant_district"))
        
        if validated_municipality:
            return {"form_skip_status_check_complainant_municipality_temp": validated_municipality}
        
        else:
            return {"form_skip_status_check_complainant_municipality_temp": None,
                    "form_skip_status_check_complainant_municipality": None,
                    "form_skip_status_check_complainant_municipality_confirmed": None
                    }

                
    async def extract_form_skip_status_check_complainant_municipality_confirmed(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # First check if we have a municipality to confirm
        if not tracker.get_slot("form_skip_status_check_complainant_municipality_temp"):
            return {}

        return await self._handle_boolean_and_category_slot_extraction(
            "form_skip_status_check_complainant_municipality_confirmed",
            tracker,
            dispatcher,
            domain  # When skipped, assume confirmed
        )
    
    async def validate_form_skip_status_check_complainant_municipality_confirmed(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:

        if slot_value == True:
            
        #save the municipality to the slot
            result = {"form_skip_status_check_complainant_municipality_confirmed": True,
                    "form_skip_status_check_complainant_municipality": tracker.get_slot("form_skip_status_check_complainant_municipality_temp")}
            
        elif slot_value == False:
            result = {"form_skip_status_check_complainant_municipality_confirmed": None,
                    "form_skip_status_check_complainant_municipality_temp": None,
                    "form_skip_status_check_complainant_municipality": None
                    }
        else:
            result = {}
        self.logger.debug(f"Validate complainant_municipality_confirmed: {result}")
        return result
        
        
    ########################## AskActionsFormStatusCheck ######################

    class ActionAskStatusCheckMethod(BaseAction):
        def name(self) -> Text:
            return "action_ask_status_check_method"
        
        async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
            utterance = self.get_utterance(1)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=utterance, buttons=buttons)
            return []

    class ActionAskStatusCheckListGrievanceId(BaseAction):
        def name(self) -> Text:
            return "action_ask_status_check_list_grievance_id"
        
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

    class ActionAskStatusCheckComplainantPhone(BaseAction):
        def name(self) -> Text:
            return "action_ask_status_check_complainant_phone"
        
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

    ########################## AskActionsFormSkipStatusCheck ######################

    class ActionAskFormSkipStatusCheckValidProvinceAndDistrict(BaseAction):
        def name(self) -> Text:
            return "action_ask_form_skip_status_check_valid_province_and_district"
        
        async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
            if tracker.get_slot("form_skip_status_check_valid_province_and_district") == None:
                province = tracker.get_slot("complainant_province")
                district = tracker.get_slot("complainant_district")
                if province and district:
                    utterance = self.get_utterance(1)
                    utterance = utterance.format(province=province, district=district)
                    buttons = self.get_buttons(1)
                    dispatcher.utter_message(text=utterance, buttons=buttons)
                elif province:
                    utterance = self.get_utterance(2)
                    utterance = utterance.format(province=province)
                    buttons = self.get_buttons(1)
                    dispatcher.utter_message(text=utterance, buttons=buttons)
                elif district:
                    utterance = self.get_utterance(3)
                    utterance = utterance.format(district=district)
                    buttons = self.get_buttons(1)
                    dispatcher.utter_message(text=utterance, buttons=buttons)
                else:
                    return [SlotSet("form_skip_status_check_valid_province_and_district", False)]
            return []

    class ActionAskFormSkipStatusCheckComplainantProvince(BaseAction):
        def name(self) -> str:
            return "action_ask_form_skip_status_check_complainant_province"
        
        async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
            
            message = self.get_utterance(1)
            buttons = self.get_buttons(1)
            dispatcher.utter_message(text=message, buttons=buttons)
            return []
    
class ActionAskFormSkipStatusCheckComplainantDistrict(BaseAction):
    def name(self) -> str:
        return "action_ask_form_skip_status_check_complainant_district"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionAskFormSkipStatusCheckComplainantMunicipality(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_skip_status_check_complainant_municipality"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        utterance = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []
            
class ActionAskFormSkipStatusCheckComplainantMunicipalityConfirmed(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_skip_status_check_complainant_municipality_confirmed"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        utterance = self.get_utterance(1).format(validated_municipality=tracker.get_slot("form_skip_status_check_complainant_municipality_temp"))
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []

class ActionAskFormSkipStatusCheckComplainantMunicipalityTemp(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_skip_status_check_complainant_municipality_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        utterance = self.get_utterance(1).format(district=tracker.get_slot("form_skip_status_check_complainant_district"), province=tracker.get_slot("form_skip_status_check_complainant_province"))
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

class ActionFormSkipStatusCheckOutro(BaseAction):
    def name(self) -> Text:
        return "action_form_skip_status_check_outro"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        province = tracker.get_slot("form_skip_status_check_complainant_province")
        district = tracker.get_slot("form_skip_status_check_complainant_district")
        municipality = tracker.get_slot("form_skip_status_check_complainant_municipality")
        office_in_charge_info = self.helpers.get_office_in_charge_info(municipality, district, province)
        office_phone_number = office_in_charge_info.get("office_phone")
        office_name = office_in_charge_info.get("office_name")
        office_address = office_in_charge_info.get("office_address")
        utterances = []
    
        if office_name:
            utterances.append(self.get_utterance(3).format(office_name=office_name))
        if office_address:
            utterances.append(self.get_utterance(4).format(office_address=office_address)) 
        if office_phone_number:
            utterances.append(self.get_utterance(2).format(office_phone_number=office_phone_number))
        if len(utterances) == 0:
            utterance = self.get_utterance(5)
        else:
            utterances.append(self.get_utterance(1))
            utterance = "\n".join(utterances)
        dispatcher.utter_message(text=utterance)
        return []
