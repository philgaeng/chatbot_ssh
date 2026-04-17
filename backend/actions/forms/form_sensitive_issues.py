import logging
from typing import Any, Dict, Text, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict
from backend.actions.base_classes.base_classes import BaseFormValidationAction, BaseAction
from random import randint

logger = logging.getLogger(__name__)


class ValidateFormSensitiveIssues(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_sensitive_issues"

    async def required_slots(self, domain_slots: List[Text], dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Text]:
        required_slots = [
            "sensitive_issues_follow_up",
            "seah_victim_survivor_role",
            "complainant_phone",
            "seah_project_identification",
            "sensitive_issues_new_detail",
        ]
        # case where the user declares that the content is not sensitive
        if tracker.get_slot("grievance_sensitive_issue") == False:
            return []
        if tracker.get_slot("seah_victim_survivor_role") == "focal_point":
            required_slots.append("seah_focal_full_name")
            if tracker.get_slot("seah_focal_lookup_status") == "found":
                required_slots.append("seah_focal_otp_input")
            required_slots.extend([
                "seah_focal_survivor_risks",
                "seah_focal_mitigation_measures",
                "seah_focal_other_at_risk_parties",
                "seah_focal_project_risk",
                "seah_focal_reputational_risk",
                "seah_focal_learned_when",
            ])
        required_slots.append("seah_contact_consent_channel")
        return required_slots
        
    async def extract_sensitive_issues_follow_up(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "sensitive_issues_follow_up",
            tracker,
            dispatcher,
            domain
        )
        
    async def validate_sensitive_issues_follow_up(self, slot_value: Any,
                                                   dispatcher: CollectingDispatcher, 
                                                   tracker: Tracker, 
                                                   domain: Dict[Text, Any]
                                                   ) -> List[Dict[Text, Any]]:
        raw = slot_value if isinstance(slot_value, str) else str(slot_value)
        cmd = raw.lstrip("/") if raw else raw

        if cmd == "not_sensitive_content":
            return {"grievance_sensitive_issue": False}

        if cmd == self.SKIP_VALUE:
            cmd = "anonymous"

        if cmd not in {"identified", "anonymous"}:
            dispatcher.utter_message(text=self.get_utterance(2))
            return {"sensitive_issues_follow_up": None}

        updates: Dict[Text, Any] = {"sensitive_issues_follow_up": cmd}
        if cmd == "anonymous":
            updates["complainant_full_name"] = self.SKIP_VALUE
        return updates
        

    async def extract_sensitive_issues_new_detail(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "sensitive_issues_new_detail",
            tracker,
            dispatcher,
            domain
        )
    
    async def validate_sensitive_issues_new_detail(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        slots = {"sensitive_issues_new_detail": self.SKIP_VALUE}
        if slot_value not in [self.SKIP_VALUE, None] and len(slot_value.strip())>3:
            existing_description = tracker.get_slot("grievance_description")
            base_text = (
                existing_description.strip()
                if isinstance(existing_description, str) and existing_description.strip()
                else ""
            )
            new_text = slot_value.strip()
            slots["sensitive_issues_new_detail"] = slot_value
            slots["grievance_description"] = f"{base_text}\n{new_text}" if base_text else new_text
            slots["grievance_description_status"] = "completed"
        return slots

    async def extract_sensitive_issues_nickname(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "sensitive_issues_nickname",
            tracker,
            dispatcher,
            domain
        )
    async def validate_sensitive_issues_nickname(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        if slot_value not in [self.SKIP_VALUE, None] and len(slot_value.strip())>1:
            return {"sensitive_issues_nickname": slot_value}
        else:
            return {"sensitive_issues_nickname": self.SKIP_VALUE}


    async def extract_form_sensitive_issues_complainant_phone(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await self._handle_slot_extraction(
            "complainant_phone",
            tracker,
            dispatcher,
            domain
        )

    async def validate_form_sensitive_issues_complainant_phone(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        """Validate phone number and set validation requirement."""
        if slot_value is None or slot_value == self.SKIP_VALUE or (isinstance(slot_value, (list, str)) and self.SKIP_VALUE in slot_value):
            return {"complainant_phone": self.SKIP_VALUE}
        if isinstance(slot_value, str) and slot_value.strip().startswith("/"):
            return {"complainant_phone": None}
        if not self.helpers.is_valid_phone(slot_value):
            message = self.get_utterance(1)
            dispatcher.utter_message(text=message)
            return {"complainant_phone": None}
        if self.helpers.is_philippine_phone(slot_value):
            dispatcher.utter_message(text="You entered a PH number for validation.")
            return {
                "complainant_phone": self.helpers.is_philippine_phone(slot_value),
                "phone_validation_required": True,
            }
        result = {
            "complainant_phone": slot_value,
            "phone_validation_required": True,
        }
        self.logger.debug(f"Validate complainant_phone: {result['complainant_phone']}")
        return result

    async def extract_seah_victim_survivor_role(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_victim_survivor_role",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_victim_survivor_role(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        value = (slot_value or "").strip() if isinstance(slot_value, str) else slot_value
        if isinstance(value, str):
            value = value.lstrip("/")
        allowed = {"victim_survivor", "not_victim_survivor", "focal_point"}
        if value in allowed:
            return {"seah_victim_survivor_role": value}
        return {"seah_victim_survivor_role": None}

    async def extract_seah_project_identification(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_project_identification",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_project_identification(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value is None:
            return {"seah_project_identification": None}

        value = slot_value.strip() if isinstance(slot_value, str) else slot_value
        if isinstance(value, str):
            value = value.lstrip("/")

        if value == self.SKIP_VALUE:
            value = "cannot_specify"

        if value in ("cannot_specify", "not_adb_project"):
            return {
                "seah_project_identification": value,
                "seah_not_adb_project": value == "not_adb_project",
            }

        if isinstance(value, str) and len(value) >= 2:
            return {"seah_project_identification": value, "seah_not_adb_project": False}

        return {"seah_project_identification": None}

    async def extract_seah_contact_consent_channel(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_contact_consent_channel",
            tracker,
            dispatcher,
            domain,
        )

    async def extract_seah_focal_survivor_risks(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_focal_survivor_risks",
            tracker,
            dispatcher,
            domain,
        )

    async def extract_seah_focal_mitigation_measures(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_focal_mitigation_measures",
            tracker,
            dispatcher,
            domain,
        )

    async def extract_seah_focal_other_at_risk_parties(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_focal_other_at_risk_parties",
            tracker,
            dispatcher,
            domain,
        )

    async def extract_seah_focal_project_risk(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_focal_project_risk",
            tracker,
            dispatcher,
            domain,
        )

    async def extract_seah_focal_reputational_risk(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_focal_reputational_risk",
            tracker,
            dispatcher,
            domain,
        )

    async def extract_seah_focal_learned_when(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_focal_learned_when",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_contact_consent_channel(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        value = (slot_value or "").strip() if isinstance(slot_value, str) else slot_value
        if isinstance(value, str):
            value = value.lstrip("/")
        if value in {"phone", "email", "both", "none"}:
            return {"seah_contact_consent_channel": value}
        return {"seah_contact_consent_channel": None}

    async def validate_seah_focal_survivor_risks(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_survivor_risks")

    async def validate_seah_focal_mitigation_measures(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_mitigation_measures")

    async def validate_seah_focal_other_at_risk_parties(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_other_at_risk_parties")

    async def validate_seah_focal_project_risk(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_project_risk")

    async def validate_seah_focal_reputational_risk(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_reputational_risk")

    async def validate_seah_focal_learned_when(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_learned_when")

    async def extract_seah_focal_full_name(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_focal_full_name",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_focal_full_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if not slot_value or not isinstance(slot_value, str) or len(slot_value.strip()) < 3:
            return {"seah_focal_full_name": None}

        focal_name = slot_value.strip()
        roster = {"john focal", "sita focal", "ram focal"}
        attempts = tracker.get_slot("seah_focal_lookup_attempts") or 0
        normalized = focal_name.lower()

        if normalized in roster:
            return {
                "seah_focal_full_name": focal_name,
                "seah_focal_lookup_status": "found",
                "seah_focal_lookup_attempts": attempts,
            }

        if attempts < 1:
            dispatcher.utter_message(
                text="We could not verify that focal point name. Please try again once, or continue and we will mark for offline verification."
            )
            return {
                "seah_focal_full_name": None,
                "seah_focal_lookup_status": "retry_required",
                "seah_focal_lookup_attempts": attempts + 1,
            }

        dispatcher.utter_message(
            text="We could not verify this focal point in our roster. We will continue and tag this report for offline verification."
        )
        return {
            "seah_focal_full_name": focal_name,
            "seah_focal_lookup_status": "not_found",
            "seah_focal_verification_status": "unverified_focal_point",
            "seah_focal_otp_input": self.SKIP_VALUE,
        }

    async def extract_seah_focal_otp_input(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_focal_otp_input",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_focal_otp_input(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> Dict[Text, Any]:
        if slot_value == self.SKIP_VALUE:
            return {
                "seah_focal_otp_input": self.SKIP_VALUE,
                "seah_focal_verification_status": "unverified_focal_point",
            }

        otp_input = (slot_value or "").strip()
        expected = tracker.get_slot("seah_focal_otp_number")
        attempts = tracker.get_slot("seah_focal_otp_attempts") or 0

        if otp_input and expected and otp_input == expected:
            return {
                "seah_focal_otp_input": otp_input,
                "seah_focal_verification_status": "verified_focal_point",
                "seah_focal_otp_attempts": 0,
            }

        if attempts < 2:
            dispatcher.utter_message(text="Invalid OTP. Please try again.")
            return {
                "seah_focal_otp_input": None,
                "seah_focal_otp_attempts": attempts + 1,
                "seah_focal_verification_status": "otp_retry_required",
            }

        dispatcher.utter_message(
            text="OTP verification failed. We will continue and mark this report as unverified focal point."
        )
        return {
            "seah_focal_otp_input": self.SKIP_VALUE,
            "seah_focal_verification_status": "unverified_focal_point",
            "seah_focal_otp_attempts": 0,
        }

    def _validate_text_or_skip(self, slot_value: Any, slot_name: Text) -> Dict[Text, Any]:
        if slot_value is None or slot_value == self.SKIP_VALUE:
            return {slot_name: self.SKIP_VALUE}
        if isinstance(slot_value, str) and len(slot_value.strip()) >= 2:
            return {slot_name: slot_value.strip()}
        return {slot_name: None}



class ActionAskSensitiveIssuesFollowUp(BaseAction):
    def name(self) -> Text:
        return "action_ask_sensitive_issues_follow_up"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionAskSensitiveIssuesNewDetail(BaseAction):
    def name(self) -> Text:
        return "action_ask_sensitive_issues_new_detail"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        dispatcher.utter_message(text=message)
        return []

class ActionAskSensitiveIssuesNickname(BaseAction):
    def name(self) -> Text:
        return "action_ask_sensitive_issues_nickname"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []

class ActionAskFormSensitiveIssuesComplainantPhone(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_complainant_phone"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []


class ActionAskFormSensitiveIssuesSeahVictimSurvivorRole(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_seah_victim_survivor_role"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []


class ActionAskFormSensitiveIssuesSeahProjectIdentification(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_seah_project_identification"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []


class ActionAskFormSensitiveIssuesSeahContactConsentChannel(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_seah_contact_consent_channel"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []


class ActionAskFormSensitiveIssuesSeahFocalSurvivorRisks(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_seah_focal_survivor_risks"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSensitiveIssuesSeahFocalFullName(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_seah_focal_full_name"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSensitiveIssuesSeahFocalOtpInput(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_seah_focal_otp_input"

    def _generate_otp(self) -> str:
        return "".join(str(randint(0, 9)) for _ in range(6))

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        phone_number = tracker.get_slot("complainant_phone")
        if not phone_number or phone_number == self.SKIP_VALUE:
            dispatcher.utter_message(
                text="No phone number available for OTP. We will continue with offline focal-point verification."
            )
            return [
                {"event": "slot", "name": "seah_focal_verification_status", "value": "unverified_focal_point"},
                {"event": "slot", "name": "seah_focal_otp_input", "value": self.SKIP_VALUE},
            ]

        otp_number = self._generate_otp()
        try:
            self.messaging.send_sms(phone_number, f"Your SEAH focal point verification code is {otp_number}")
        except Exception:
            dispatcher.utter_message(
                text="We could not send OTP right now. We will continue with offline focal-point verification."
            )
            return [
                {"event": "slot", "name": "seah_focal_verification_status", "value": "unverified_focal_point"},
                {"event": "slot", "name": "seah_focal_otp_input", "value": self.SKIP_VALUE},
            ]

        dispatcher.utter_message(text=self.get_utterance(1).format(phone_number=phone_number))
        return [{"event": "slot", "name": "seah_focal_otp_number", "value": otp_number}]


class ActionAskFormSensitiveIssuesSeahFocalMitigationMeasures(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_seah_focal_mitigation_measures"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSensitiveIssuesSeahFocalOtherAtRiskParties(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_seah_focal_other_at_risk_parties"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSensitiveIssuesSeahFocalProjectRisk(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_seah_focal_project_risk"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSensitiveIssuesSeahFocalReputationalRisk(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_seah_focal_reputational_risk"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSensitiveIssuesSeahFocalLearnedWhen(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_sensitive_issues_seah_focal_learned_when"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []

class ActionOutroSensitiveIssues(BaseAction):
    def name(self) -> Text:
        return "action_outro_sensitive_issues"
    
    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        message = self.get_utterance(2) if tracker.get_slot("seah_not_adb_project") else self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []