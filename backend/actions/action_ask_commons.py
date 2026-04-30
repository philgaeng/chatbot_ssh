"""
Common action_ask methods shared across multiple forms.
These are reusable action_ask methods that don't belong to a specific form.
Uses generic naming (action_ask_slot_name) for better reusability across forms.
"""

from typing import Any, Text, Dict, List, Optional
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import FollowupAction
from rasa_sdk.types import DomainDict
from backend.actions.base_classes.base_classes import BaseAction
from backend.actions.utils.mapping_buttons import BUTTONS_SKIP
from backend.actions.utils.utterance_mapping_rasa import UTTERANCE_MAPPING


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
                    otp_verified = tracker.get_slot("otp_status") == "verified"
                    # If OTP was skipped/unverified in phone route, do not offer modify.
                    if story_route == "route_status_check_phone" and not otp_verified:
                        buttons = self.get_buttons(2)
                    else:
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

class ProfileAwareAskAction(BaseAction):
    """Shared helpers for profile-aware ask prompts in action_ask_commons."""

    ASK_COMMONS_MAPPING = UTTERANCE_MAPPING.get("action_ask_commons", {})
    FOCAL_REPORTER_STAGES = {"bootstrap_reporter_otp", "bootstrap_reporter_contact", "focal_point_1"}
    FOCAL_COMPLAINANT_STAGES = {"complainant_otp", "complainant_contact", "focal_point_2"}

    def _get_ask_profile(self, tracker: Tracker) -> str:
        story_main = tracker.get_slot("story_main")
        seah_role = tracker.get_slot("seah_victim_survivor_role")

        if story_main in ("new_grievance", "grievance_submission"):
            return "grievance"
        if story_main != "seah_intake":
            return "grievance"
        if seah_role == "victim_survivor":
            return "seah-victim"
        if seah_role == "not_victim_survivor":
            return "seah-other"
        if seah_role == "focal_point":
            return "seah-focal"
        return "grievance"

    def _get_focal_prompt_phase(self, tracker: Tracker) -> str:
        seah_focal_stage = tracker.get_slot("seah_focal_stage")
        if seah_focal_stage in self.FOCAL_REPORTER_STAGES:
            return "reporter"
        if seah_focal_stage in self.FOCAL_COMPLAINANT_STAGES:
            return "complainant"
        return "complainant"

    def _get_profile_utterance(self, tracker: Tracker, utterance_index: int = 1) -> Optional[str]:
        action_mapping = self.ASK_COMMONS_MAPPING.get(self.name(), {})
        profile_mapping = action_mapping.get("profile_utterances", {})
        profile = self._get_ask_profile(tracker)
        language_code = tracker.get_slot("language_code") or "en"
        profile_values = profile_mapping.get(profile)
        if not profile_values:
            return None

        if profile == "seah-focal":
            phase_map = profile_values.get(self._get_focal_prompt_phase(tracker), {})
            return phase_map.get(utterance_index, {}).get(language_code)
        return profile_values.get(utterance_index, {}).get(language_code)

class ActionAskComplainantPhone(ProfileAwareAskAction):
    def name(self) -> Text:
        return "action_ask_complainant_phone"
    
    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        if tracker.get_slot("complainant_phone_valid") == False:
            message = self._get_profile_utterance(tracker, 2) or self.get_utterance(2)
            buttons = self.get_buttons(2)
        else:
            message = self._get_profile_utterance(tracker, 1) or self.get_utterance(1)
            buttons = self.get_buttons(1)
        if (
            self._get_ask_profile(tracker) == "seah-focal"
            and self._get_focal_prompt_phase(tracker) == "reporter"
        ):
            # Focal reporter phone is mandatory.
            buttons = []
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionAskComplainantLocationConsent(ProfileAwareAskAction):
    def name(self) -> str:
        return "action_ask_complainant_location_consent"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = self._get_profile_utterance(tracker, 1) or self.get_utterance(1)
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
        # Force skip-only buttons for municipality prompt to avoid cross-form button leakage.
        language_code = tracker.get_slot("language_code") or "en"
        buttons = BUTTONS_SKIP.get(language_code, BUTTONS_SKIP["en"])
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

    
class ActionAskComplainantMunicipalityConfirmed(ProfileAwareAskAction):
    def name(self) -> str:
        return "action_ask_complainant_municipality_confirmed"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        validated_municipality = tracker.get_slot('complainant_municipality_temp')
        message = self._get_profile_utterance(tracker, 1) or self.get_utterance(1)
        message = message.format(validated_municipality=validated_municipality)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
       
class ActionAskComplainantVillageTemp(ProfileAwareAskAction):
    def name(self) -> str:
        return "action_ask_complainant_village_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = self._get_profile_utterance(tracker, 1) or self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionAskComplainantVillageConfirmed(ProfileAwareAskAction):
    def name(self) -> str:
        return "action_ask_complainant_village_confirmed"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        validated_village = tracker.get_slot('complainant_village_temp')
        validated_ward = tracker.get_slot('complainant_ward')
        message = self._get_profile_utterance(tracker, 1) or self.get_utterance(1)
        message = message.format(validated_village=validated_village, validated_ward=validated_ward)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionAskComplainantWard(ProfileAwareAskAction):
    def name(self) -> str:
        return "action_ask_complainant_ward"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = self._get_profile_utterance(tracker, 1) or self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantAddressTemp(ProfileAwareAskAction):
    def name(self) -> str:
        return "action_ask_complainant_address_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        message = self._get_profile_utterance(tracker, 1) or self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantAddressConfirmed(ProfileAwareAskAction):
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
        message = self._get_profile_utterance(tracker, 1) or self.get_utterance(1)
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
 

class ActionAskComplainantConsent(ProfileAwareAskAction):
    def name(self) -> str:
        return "action_ask_complainant_consent"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self._get_profile_utterance(tracker, 1) or self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantFullName(ProfileAwareAskAction):
    def name(self) -> Text:
        return "action_ask_complainant_full_name"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if tracker.get_slot("grievance_sensitive_issue") ==self.SKIP_VALUE:
            message = self._get_profile_utterance(tracker, 1) or self.get_utterance(1)
        else:
            message = self._get_profile_utterance(tracker, 2) or self.get_utterance(2)
        buttons = self.get_buttons(1)
        if (
            self._get_ask_profile(tracker) == "seah-focal"
            and tracker.get_slot("seah_focal_stage") == "bootstrap_reporter_contact"
        ):
            # Focal reporter name is mandatory.
            buttons = []
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantEmailTemp(ProfileAwareAskAction):
    def name(self) -> Text:
        return "action_ask_complainant_email_temp"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        message = self._get_profile_utterance(tracker, 1) or self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
    
class ActionAskComplainantEmailConfirmed(BaseAction):
    def name(self) -> Text:
        return "action_ask_complainant_email_confirmed"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        email_temp = tracker.get_slot("complainant_email_temp")
        if email_temp and isinstance(email_temp, str) and "@" in email_temp:
            domain_name = email_temp.split("@")[-1]
        else:
            domain_name = "your email"
        try:
            message = self.get_utterance(1)
            buttons = self.get_buttons(1)
            message = message.format(domain_name=domain_name)
        except Exception:
            message = (
                "The email domain is not recognized as a common Nepali provider. "
                "Please confirm if this is correct or try again with a different email."
            )
            buttons = []
        dispatcher.utter_message(text=message, buttons=buttons)
        return []