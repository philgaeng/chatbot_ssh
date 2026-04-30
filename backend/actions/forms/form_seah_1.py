from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseAction, BaseFormValidationAction
from backend.actions.utils.mapping_buttons import BUTTONS_SEAH_VICTIM_SURVIVOR_ROLE


class ValidateFormSeah1(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_seah_1"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        # Ensure language/helpers are initialized before any validator utterance
        # path that may call self.get_utterance() in this form turn.
        self._initialize_language_and_helpers(tracker)
        # If user confirms content is not sensitive, stop this flow immediately.
        if tracker.get_slot("grievance_sensitive_issue") is False:
            return []
        role = tracker.get_slot("seah_victim_survivor_role")
        # First question: role selection.
        if role == "victim_survivor":
            # Second question: anonymity mode for victim/survivor.
            return ["seah_victim_survivor_role", "sensitive_issues_follow_up"]
        if role == "not_victim_survivor":
            consent = tracker.get_slot("seah_witness_victim_consent_to_file")
            if consent is None:
                return [
                    "seah_victim_survivor_role",
                    "seah_witness_victim_consent_to_file",
                ]
            if consent == "yes":
                return [
                    "seah_victim_survivor_role",
                    "seah_witness_victim_consent_to_file",
                ]
            return [
                "seah_victim_survivor_role",
                "seah_witness_victim_consent_to_file",
                "seah_witness_immediate_danger",
            ]
        return ["seah_victim_survivor_role"]

    async def extract_seah_witness_victim_consent_to_file(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_witness_victim_consent_to_file",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_witness_victim_consent_to_file(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        value = (slot_value or "").strip() if isinstance(slot_value, str) else slot_value
        if isinstance(value, str):
            value = value.lstrip("/")
        if value in {"yes", "no"}:
            if value == "yes":
                language_code = tracker.get_slot("language_code") or "en"
                if language_code == "ne":
                    dispatcher.utter_message(
                        text="धन्यवाद। यहाँ पीडित/उत्तरजीवीलाई सहयोग गर्न सक्ने सम्भावित सहयोग सेवाहरू छन्: [list to be provided]."
                    )
                else:
                    dispatcher.utter_message(
                        text="Thank you. Here are the potential support services that can help the victim-survivor: [list to be provided]."
                    )
            return {
                "seah_witness_victim_consent_to_file": value,
                "seah_witness_immediate_danger": None if value == "yes" else tracker.get_slot("seah_witness_immediate_danger"),
                "seah_witness_exit_without_filing": True if value == "yes" else tracker.get_slot("seah_witness_exit_without_filing"),
            }
        return {"seah_witness_victim_consent_to_file": None}

    async def extract_seah_witness_immediate_danger(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_witness_immediate_danger",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_witness_immediate_danger(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        value = (slot_value or "").strip() if isinstance(slot_value, str) else slot_value
        if isinstance(value, str):
            value = value.lstrip("/")
        if value in {"yes", "no"}:
            language_code = tracker.get_slot("language_code") or "en"
            if language_code == "ne":
                dispatcher.utter_message(
                    text="धन्यवाद। यहाँ पीडित/उत्तरजीवीलाई सहयोग गर्न सक्ने सम्भावित सहयोग सेवाहरू छन्: [list to be provided]."
                )
            else:
                dispatcher.utter_message(
                    text="Thank you. Here are the potential support services that can help the victim-survivor: [list to be provided]."
                )
            return {"seah_witness_immediate_danger": value, "seah_witness_exit_without_filing": True}
        return {"seah_witness_immediate_danger": None}

    async def extract_sensitive_issues_follow_up(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "sensitive_issues_follow_up",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_sensitive_issues_follow_up(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        raw = slot_value if isinstance(slot_value, str) else str(slot_value)
        cmd = raw.lstrip("/") if raw else raw

        if cmd == "not_sensitive_content":
            return {"grievance_sensitive_issue": False}

        if cmd == self.SKIP_VALUE:
            cmd = "anonymous"

        if cmd not in {"identified", "anonymous"}:
            dispatcher.utter_message(text=self.get_utterance(2))
            return {"sensitive_issues_follow_up": None}

        updates: Dict[Text, Any] = {
            "sensitive_issues_follow_up": cmd,
            "seah_anonymous_route": cmd == "anonymous",
        }
        if cmd == "identified":
            # Identified path already carries contact via OTP/phone collection,
            # so prefill consent to avoid asking the same question again later.
            updates["complainant_consent"] = True
        if cmd == "identified":
            updates["active_party_role"] = "victim_survivor"
        elif cmd == "anonymous":
            updates["active_party_role"] = "victim_survivor"
        if cmd == "anonymous":
            updates.update(
                {
                    "complainant_full_name": self.SKIP_VALUE,
                    # Do not prefill phone/OTP slots in anonymous route. We still ask
                    # phone via OTP form (same hop as identified route) so users can
                    # optionally provide contact while remaining anonymous.
                    "complainant_phone": None,
                    "otp_consent": None,
                    "otp_number": None,
                    "otp_status": None,
                    "otp_verified": False,
                    "otp_input": None,
                    "otp_resend_count": 0,
                }
            )
        updates.update(
            self.seah_contact_provided_update(
                tracker.get_slot("story_main"),
                dict(tracker.current_slot_values()),
                updates,
            )
        )
        return updates

    async def extract_seah_victim_survivor_role(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_victim_survivor_role",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_victim_survivor_role(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        value = (slot_value or "").strip() if isinstance(slot_value, str) else slot_value
        if isinstance(value, str):
            value = value.lstrip("/")
        allowed = {"victim_survivor", "not_victim_survivor", "focal_point"}
        if value in allowed:
            updates = {
                "seah_victim_survivor_role": value,
                "active_party_role": self._normalize_party_role(value),
                "seah_witness_victim_consent_to_file": None,
                "seah_witness_immediate_danger": None,
                "seah_witness_exit_without_filing": False,
            }
            # Focal-point path skips anonymity question.
            if value == "focal_point":
                updates["seah_anonymous_route"] = False
                updates["sensitive_issues_follow_up"] = "identified"
            return updates
        return {"seah_victim_survivor_role": None}


class ActionAskFormSeah1SensitiveIssuesFollowUp(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_1_sensitive_issues_follow_up"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1), buttons=self.get_buttons(1))
        return []


class ActionAskFormSeah1SeahVictimSurvivorRole(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_1_seah_victim_survivor_role"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        language_code = tracker.get_slot("language_code") or "en"
        buttons = BUTTONS_SEAH_VICTIM_SURVIVOR_ROLE.get(
            language_code, BUTTONS_SEAH_VICTIM_SURVIVOR_ROLE["en"]
        )
        dispatcher.utter_message(text=self.get_utterance(1), buttons=buttons)
        return []


class ActionAskFormSeah1SeahWitnessVictimConsentToFile(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_1_seah_witness_victim_consent_to_file"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1), buttons=self.get_buttons(1))
        return []


class ActionAskFormSeah1SeahWitnessImmediateDanger(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_1_seah_witness_immediate_danger"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1), buttons=self.get_buttons(1))
        return []
