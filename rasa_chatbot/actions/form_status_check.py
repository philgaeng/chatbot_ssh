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
        if slot_value:
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
            return {"status_check_list_grievance_id": self.SKIP_VALUE,
            "status_check_method": self.SKIP_VALUE}
        if "phone" in slot_value:
            return {"status_check_list_grievance_id": None,
            "status_check_method": "complainant_phone"}
        else:
            if self.db_manager.is_valid_grievance_id(slot_value):
                return {"status_check_list_grievance_id": [slot_value],
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
            return {"status_check_complainant_phone": self.SKIP_VALUE,
            "status_check_method": self.SKIP_VALUE}
        
        if not self.helpers.is_valid_phone(slot_value):
            self.logger.debug(f"validate_status_check_complainant_phone: phone not valid - the slot is not validated and shoule be asked again")
            return {
                "status_check_complainant_phone_valid": "invalid_number",
                "status_check_complainant_phone": None
                }


        standardized_phone = self.helpers.standardize_phone(language_code=self.language_code, phone=slot_value)
        list_grievances_by_phone = self.db_manager.get_grievance_by_complainant_phone(standardized_phone)
        self.logger.debug(f"validate_status_check_complainant_phone: list_grievances_by_phone: {list_grievances_by_phone}")

        if len(list_grievances_by_phone) == 0:
            self.logger.debug(f"validate_status_check_complainant_phone: no phone found - the slot is not validated and shoule be asked again")
            return {
                "status_check_complainant_phone_valid": "no_phone_found",
                "status_check_complainant_phone": None
                }

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
        self.logger.debug(f"validate_status_check_complainant_phone: list_full_names: {list_full_names}")
        unique_full_names = self.match_similar_full_names_in_list(list_full_names)
        self.logger.debug(f"validate_status_check_complainant_phone: unique_full_names: {unique_full_names}")
        if len(unique_full_names) == 1:
            return {
                "status_check_complainant_phone": slot_value,
                "status_check_list_grievances_by_phone": serializable_grievances,
                "status_check_complainant_full_name": serializable_grievances[0]["complainant_full_name"],
                "status_check_list_grievance_id": serializable_grievances,
                "status_check_complainant_phone_valid": True,
                "status_check_unique_full_names": unique_full_names
                }
        else:
                return {
                    "status_check_complainant_phone": slot_value,
                "status_check_list_grievances_by_phone": serializable_grievances,
                "status_check_complainant_phone_valid": True,
                "status_check_unique_full_names": unique_full_names
                }


    async def extract_status_check_complainant_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:

        return await self._handle_slot_extraction("status_check_complainant_full_name", tracker, dispatcher, domain)

    async def validate_status_check_complainant_full_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        try:
            if slot_value == self.SKIP_VALUE:
                return {"status_check_complainant_full_name": self.SKIP_VALUE,
                "status_check_list_grievance_id": self.SKIP_VALUE,
                "status_check_method": self.SKIP_VALUE,
                "status_check_full_name_validated": False}
            unique_full_names = tracker.get_slot("status_check_unique_full_names")
            full_name_matches = self.helpers.match_full_name(slot_value, unique_full_names)
            list_grievances_by_phone = tracker.get_slot("status_check_list_grievances_by_phone")
            self.logger.debug(f"validate_status_check_complainant_full_name: full_name_matches: {full_name_matches}")
            if len(full_name_matches) == 0:
                self.logger.debug(f"validate_status_check_complainant_full_name: no matches: {full_name_matches} - slot not validated")
                return {
                    "status_check_complainant_full_name": None,
                "status_check_full_name_validated": False
                }

            if full_name_matches:
                list_grievances_by_full_name = self.select_grievances_from_full_name_list(full_name_matches,  list_grievances_by_phone, dispatcher)
                self.logger.debug(f"validate_status_check_complainant_full_name: list_grievances_by_full_name: {list_grievances_by_full_name}")
                if list_grievances_by_full_name:
                    return {
                        "status_check_complainant_full_name": list_grievances_by_full_name[0]["complainant_full_name"],
                    "status_check_list_grievances_by_full_name": list_grievances_by_full_name, "status_check_list_grievance_id": list_grievances_by_full_name,
                        "status_check_complainant_full_name_valid": True,
                        "status_check_full_name_validated": True
                        }
                else:
                    return {
                        "status_check_complainant_full_name": None,
                    "status_check_complainant_full_name_valid": False,
                    "status_check_full_name_validated": False
                    }
        except Exception as e:
            self.logger.error(f"validate_status_check_complainant_full_name: error: {e}")
            return {
            }

    def select_grievances_from_full_name_list(self, full_name_matches: List[Tuple[str, float, int]], list_grievances_by_phone: list, dispatcher: CollectingDispatcher) -> List[str]:
        matching_grievance_list = []
        self.logger.debug(f"select_grievances_from_full_name_list: full_name: {full_name_matches}")
        self.logger.debug(f"select_grievances_from_full_name_list: list_grievances_by_phone: {list_grievances_by_phone}")
        for grievance in list_grievances_by_phone:
            for full_name in full_name_matches:
                if grievance["complainant_full_name"] == full_name[0]:
                    matching_grievance_list.append(grievance)
        self.logger.debug(f"select_grievances_from_full_name_list: matching_grievance_list: {matching_grievance_list}")
        if len(matching_grievance_list) == 0:
            return []
        #sort the matching grievances by status and status date
        #first we sort by status, where all the closed cases are at the en d and the rest are at the beginning
        #amongst the rest we sort by status date
        matching_grievance_not_closed = [grievance for grievance in matching_grievance_list if grievance.get("grievance_status") and grievance.get("grievance_status") not in ["CLOSED"]]
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
        # self.logger.debug(f"validate_form_skip_status_check: form_skip_status_check_valid_province_and_district: {tracker.get_slot('form_skip_status_check_valid_province_and_district')}")
        # # Case 1: Province and district are already valid - only need municipality
        # if tracker.get_slot("form_skip_status_check_valid_province_and_district"):
        #     self.logger.debug(f"validate_form_skip_status_check: form_skip_status_check_valid_province_and_district: True - collect municipality data")
        #     required_slots = ["form_skip_status_check_complainant_municipality_temp", "form_skip_status_check_complainant_municipality_confirmed"]
        #     self.logger.debug(f"validate_form_skip_status_check: required_slots: {required_slots}")
        #     return required_slots
        if tracker.get_slot("form_skip_status_check_valid_province_and_district") == self.SKIP_VALUE:
            return []
        # Case 2: Province and district are invalid - need to re-collect all location data
        if tracker.get_slot("form_skip_status_check_valid_province_and_district") == False:
            self.logger.debug(f"validate_form_skip_status_check: form_skip_status_check_valid_province_and_district: False - re-collect all location data")
            required_slots = ["form_skip_status_check_valid_province_and_district",
                # "form_skip_status_check_complainant_province", 
                "form_skip_status_check_complainant_district", 
                "form_skip_status_check_complainant_municipality_temp", 
                "form_skip_status_check_complainant_municipality_confirmed"
            ]
            self.logger.debug(f"validate_form_skip_status_check: required_slots: {required_slots}")
            return required_slots
        
        # Default case - no slots required
        required_slots = ["form_skip_status_check_valid_province_and_district", 
        "form_skip_status_check_complainant_municipality_temp",
        "form_skip_status_check_complainant_municipality_confirmed"
        ]
        self.logger.debug(f"validate_form_skip_status_check: required_slots: {required_slots}")
        return required_slots

    async def extract_form_skip_status_check_valid_province_and_district(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return await self._handle_boolean_and_category_slot_extraction(
            "form_skip_status_check_valid_province_and_district",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_form_skip_status_check_valid_province_and_district(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value:
            return {"form_skip_status_check_valid_province_and_district": slot_value,
            "form_skip_status_check_complainant_province": tracker.get_slot("complainant_province"),
            "form_skip_status_check_complainant_district": tracker.get_slot("complainant_district"),
            }
        else:
            return {"form_skip_status_check_valid_province_and_district": slot_value}
    
        
    async def validate_form_skip_status_check_complainant_province(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        self.logger.debug(f"validate_form_skip_status_check_complainant_province: slot_value: {slot_value}")
        if slot_value == self.SKIP_VALUE:
            message = self.get_utterance(1)
            dispatcher.utter_message(
                text=message
            )
            return {"form_skip_status_check_complainant_province": None}
        self.logger.debug(f"validate_form_skip_status_check_complainant_province: valid province: {self.helpers.check_province(slot_value)}")
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
            "form_skip_status_check_complainant_district",
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
        self.logger.debug(f"validate_form_skip_status_check_complainant_district: slot_value: {slot_value}")
        if slot_value == self.SKIP_VALUE:
            message = self.get_utterance(1)
            dispatcher.utter_message(
                text=message
            )
            return {"form_skip_status_check_complainant_district": None}
            
        province = tracker.get_slot("form_skip_status_check_complainant_province").title()
        self.logger.debug(f"validate_form_skip_status_check_complainant_district: province: {province}")
        result = self.helpers.check_district(slot_value, province).title()
        self.logger.debug(f"validate_form_skip_status_check_complainant_district: valid district: {result}")
        if not result:
            message = self.get_utterance(2)
            message = message.format(slot_value=slot_value)
            dispatcher.utter_message(
                text=message
            )
            return {"form_skip_status_check_complainant_district": None}
            
        
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
            "form_skip_status_check_complainant_municipality_temp",
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
            return {
                "form_skip_status_check_complainant_municipality_temp": self.SKIP_VALUE,
                    "form_skip_status_check_complainant_municipality": self.SKIP_VALUE,
                    "form_skip_status_check_complainant_municipality_confirmed": False
                    }
        
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
            intro_utterance = self.get_utterance(1)
            dispatcher.utter_message(text=intro_utterance)
            if tracker.get_slot("form_skip_status_check_valid_province_and_district") == None:
                province = tracker.get_slot("complainant_province")
                district = tracker.get_slot("complainant_district")
                if province and district:
                    utterance = self.get_utterance(2)
                    utterance = utterance.format(province=province, district=district)
                    buttons = self.get_buttons(1)
                    dispatcher.utter_message(text=utterance, buttons=buttons)
                elif province:
                    utterance = self.get_utterance(3)
                    utterance = utterance.format(province=province)
                    buttons = self.get_buttons(1)
                    dispatcher.utter_message(text=utterance, buttons=buttons)
                elif district:
                    utterance = self.get_utterance(4)
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
        self.logger.debug(f"action_ask_form_skip_status_check_complainant_municipality_temp: ")
        utterance = self.get_utterance(1).format(district=tracker.get_slot("form_skip_status_check_complainant_district"), province=tracker.get_slot("form_skip_status_check_complainant_province"))
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return []


########################## DisplayActionsFormStatusCheck ######################

class ActionDisplayGrievanceId(BaseAction):
    def name(self) -> Text:
        return "action_display_grievance_id"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        try:
            list_grievances_by_id = tracker.get_slot("status_check_list_grievance_id")
            self.logger.debug(f"action_display_grievance_id: status_check_list_grievance_id: {list_grievances_by_id}")
            if list_grievances_by_id:
                buttons = []
                for grievance in list_grievances_by_id:
                    utterance = self.display_grievance_id(grievance)
                    if grievance.get("grievance_id"):
                        button = {"payload": f"""/check_status{{"grievance_id_status_check": "{grievance['grievance_id']}"}}""", "title": f"Check {grievance['grievance_id']}"}
                        buttons.append(button)
                        dispatcher.utter_message(text=utterance)
                skip_button = self.get_buttons(1)[0]
                self.logger.debug(f"action_display_grievance_id: skip_button: {skip_button}")
                self.logger.debug(f"action_display_grievance_id: buttons before appending skip_button: {buttons}")
                buttons.append(skip_button)
                utterance = self.get_utterance(1)
                self.logger.debug(f"action_display_grievance_id: buttons after appending skip_button: {buttons}")
                dispatcher.utter_message(text=utterance, buttons=buttons)
            else:
                utterance = self.get_utterance(2)
                buttons = self.get_buttons(1)
                dispatcher.utter_message(text=utterance, buttons=buttons)
            return []
        except Exception as e:
            self.logger.error(f"action_display_grievance_id: error: {e}")
            return []

    def display_grievance_id(self, grievance: Dict, display_only_short: bool = True) -> str:
        key_mapping_language_short = {
            "grievance_id": {"en": "grievance_id", "ne": "गुनासो ID"},
            
            "grievance_status": {"en": "Grievance status", "ne": "गुनासो स्थिति"},
            "grievance_timeline": {"en": "Grievance timeline", "ne": "गुनासो टाइमलाइन"},
            "grievance_status_update_date": {"en": "Grievance status update date", "ne": "गुनासो स्थिति अपडेट गरिएको"},"grievance_creation_date": {"en": "Grievance creation date", "ne": "गुनासो सिर्जना गरिएको"},
            "grievance_categories": {"en": "Grievance categories", "ne": "गुनासो श्रेणी"},
        }

        key_mapping_language_long = {
            "grievance_description": {"en": "Grievance description", "ne": "गुनासो विवरण"},
            "grievance_summary": {"en": "Grievance summary", "ne": "गुनासो सारांश"}, 
        }

        if display_only_short:
            key_mapping_language = key_mapping_language_short
        else:
            key_mapping_language = key_mapping_language_short.update(key_mapping_language_long)

        utterance = []
        i = 0
        for k,v in grievance.items():
            i += 1
            self.logger.debug(f"display_grievance_id: grievance {i}: {grievance}")
            if k in key_mapping_language:
                denomination = key_mapping_language[k][self.language_code]
                if k == "grievance_status":
                    v = self.get_status_and_description_str_in_language(v)
                if v:
                    utterance.append(f"{denomination}: {v}")
        self.logger.debug(f"display_grievance_id: utterance_list: {utterance}")
        utterance = "\n".join(utterance)
        return utterance

class ActionSkipStatusCheckOutro(BaseAction):
    def name(self) -> Text:
        return "action_skip_status_check_outro"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        province = tracker.get_slot("form_skip_status_check_complainant_province")
        district = tracker.get_slot("form_skip_status_check_complainant_district")
        municipality = tracker.get_slot("form_skip_status_check_complainant_municipality")
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

class ActionDisplayGrievanceDetailsInit(BaseAction):
    def name(self) -> Text:
        return "action_display_grievance_details_init"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        latest_message = tracker.get_latest_message()
        grievance_list = tracker.get_slot("status_check_list_grievance_id")

        self.logger.debug(f"action_display_grievance_details_init: latest_message: {latest_message}")
        self.logger.debug(f"action_display_grievance_details_init: grievance_list: {grievance_list}")
        if tracker.get_slot("grievance_id_status_check"):
            grievance_id = tracker.get_slot("grievance_id_status_check")
            grievance = [g for g in grievance_list if g.get("grievance_id") == grievance_id]
            if grievance:
                grievance = grievance[0]
                return [SlotSet("status_check_grievance_selected", grievance)]
        if latest_message:
            if latest_message.get("intent").get("name") == "choose_grievance_details":
                text = latest_message.get("text")
                self.logger.debug(f"action_display_grievance_details_init: text: {text}")
                grievance_id = text.split(":")[1].strip('"')
                grievance = [g for g in grievance_list if g.get("grievance_id") == grievance_id]
                if grievance:
                    grievance = grievance[0]
                    return [SlotSet("status_check_grievance_selected", grievance)]
        return []

class ActionDisplayGrievanceDetails(BaseAction):
    def name(self) -> Text:
        return "action_display_grievance_details"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        grievance = tracker.get_slot("status_check_grievance_selected")
        if grievance:
            utterance = self.get_utterance(1)
            utterance_text = self.display_grievance_id(grievance, display_only_short=False)
            dispatcher.utter_message(text=utterance)
            dispatcher.utter_message(text=utterance_text)


        else:
            utterance = self.get_utterance(2)
            
            dispatcher.utter_message(text=utterance)
        self.get_utterance(1)
        return []