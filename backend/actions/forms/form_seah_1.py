from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseAction, BaseFormValidationAction


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
        # If user confirms content is not sensitive, stop this flow immediately.
        if tracker.get_slot("grievance_sensitive_issue") is False:
            return []
        return ["sensitive_issues_follow_up", "seah_victim_survivor_role"]

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

        updates: Dict[Text, Any] = {"sensitive_issues_follow_up": cmd}
        if cmd == "anonymous":
            updates["complainant_full_name"] = self.SKIP_VALUE
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
            return {"seah_victim_survivor_role": value}
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
        dispatcher.utter_message(text=self.get_utterance(1), buttons=self.get_buttons(1))
        return []
