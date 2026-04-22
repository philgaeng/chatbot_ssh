from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseAction, BaseFormValidationAction


class ValidateFormSeahFocalPoint1(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_seah_focal_point_1"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        if tracker.get_slot("grievance_sensitive_issue") is False:
            return []
        if tracker.get_slot("seah_victim_survivor_role") != "focal_point":
            return []

        return [
            "seah_focal_learned_when",
            "seah_focal_reporter_consent_to_report",
            "sensitive_issues_follow_up",
        ]

    async def extract_seah_focal_learned_when(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_focal_learned_when",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_focal_learned_when(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_learned_when")

    async def extract_seah_focal_reporter_consent_to_report(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_focal_reporter_consent_to_report",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_focal_reporter_consent_to_report(
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
            updates: Dict[Text, Any] = {"seah_focal_reporter_consent_to_report": value}
            if value == "no":
                updates.update(
                    {
                        "sensitive_issues_follow_up": self.SKIP_VALUE,
                        "complainant_phone": self.SKIP_VALUE,
                        "complainant_full_name": self.SKIP_VALUE,
                        "complainant_email": self.SKIP_VALUE,
                        "seah_contact_consent_channel": self.SKIP_VALUE,
                        "seah_anonymous_route": True,
                        "seah_contact_provided": False,
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
        return {"seah_focal_reporter_consent_to_report": None}

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
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        value = (slot_value or "").strip() if isinstance(slot_value, str) else slot_value
        if isinstance(value, str):
            value = value.lstrip("/")
        if value == self.SKIP_VALUE:
            value = "anonymous"
        if value in {"identified", "anonymous"}:
            merged = {
                "sensitive_issues_follow_up": value,
                "seah_anonymous_route": value == "anonymous",
            }
            merged.update(
                self.seah_contact_provided_update(
                    tracker.get_slot("story_main"),
                    dict(tracker.current_slot_values()),
                    merged,
                )
            )
            return merged
        return {"sensitive_issues_follow_up": None}

    def _validate_text_or_skip(self, slot_value: Any, slot_name: Text) -> Dict[Text, Any]:
        if slot_value is None or slot_value == self.SKIP_VALUE:
            return {slot_name: self.SKIP_VALUE}
        if isinstance(slot_value, str):
            cleaned = slot_value.strip().lstrip("/")
            if len(cleaned) >= 2:
                return {slot_name: cleaned}
        return {slot_name: None}


class ValidateFormSeahFocalPoint2(BaseFormValidationAction):
    def name(self) -> Text:
        return "validate_form_seah_focal_point_2"

    async def required_slots(
        self,
        domain_slots: List[Text],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Text]:
        if tracker.get_slot("grievance_sensitive_issue") is False:
            return []
        required = ["seah_project_identification", "sensitive_issues_new_detail"]
        if tracker.get_slot("seah_project_identification") != "not_adb_project":
            required.extend(
                [
                    "seah_focal_survivor_risks",
                    "seah_focal_mitigation_measures",
                    "seah_focal_other_at_risk_parties",
                    "seah_focal_project_risk",
                    "seah_focal_reputational_risk",
                ]
            )
            consent_to_report = tracker.get_slot("seah_focal_reporter_consent_to_report")
            has_any_contact = (
                tracker.get_slot("complainant_phone") not in (None, self.SKIP_VALUE)
                or tracker.get_slot("complainant_email") not in (None, self.SKIP_VALUE)
            )
            if consent_to_report != "no" and has_any_contact:
                required.append("seah_contact_consent_channel")
        required.append("seah_focal_referred_to_support")
        return required

    async def extract_seah_project_identification(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        latest_text = (tracker.latest_message or {}).get("text")
        if isinstance(latest_text, str) and latest_text.strip().startswith("/"):
            return {"seah_project_identification": latest_text.strip().lstrip("/")}
        return await self._handle_slot_extraction(
            "seah_project_identification",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_project_identification(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        lang = getattr(self, "language_code", None) or tracker.get_slot("language_code") or "en"
        return self.validate_seah_project_identification_value(
            slot_value,
            language_code=lang,
        )

    async def extract_sensitive_issues_new_detail(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "sensitive_issues_new_detail",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_sensitive_issues_new_detail(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        expected_values = {"restart", "add_more_details", "submit_details"}
        if isinstance(slot_value, str):
            slot_value = slot_value.strip()
            slot_value = slot_value.lstrip("/")

        if slot_value == "restart":
            return {
                "sensitive_issues_new_detail": None,
                "grievance_description": None,
                "grievance_description_status": "restart",
            }

        if slot_value == "add_more_details":
            return {
                "sensitive_issues_new_detail": None,
                "grievance_description_status": "add_more_details",
            }

        if slot_value == "submit_details":
            return {
                "sensitive_issues_new_detail": "completed",
                "grievance_description": tracker.get_slot("grievance_description"),
                "grievance_description_status": "completed",
            }

        slots = {"sensitive_issues_new_detail": self.SKIP_VALUE}
        if slot_value not in [self.SKIP_VALUE, None] and slot_value not in expected_values and len(slot_value.strip()) > 3:
            existing_description = tracker.get_slot("grievance_description")
            base_text = (
                existing_description.strip()
                if isinstance(existing_description, str) and existing_description.strip()
                else ""
            )
            new_text = slot_value.strip()
            slots["sensitive_issues_new_detail"] = None
            slots["grievance_description"] = f"{base_text}\n{new_text}" if base_text else new_text
            slots["grievance_description_status"] = "show_options"
        return slots

    async def extract_seah_contact_consent_channel(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction(
            "seah_contact_consent_channel",
            tracker,
            dispatcher,
            domain,
        )

    async def validate_seah_contact_consent_channel(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return self.validate_seah_contact_channel_selection(slot_value, tracker)

    async def extract_seah_focal_survivor_risks(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction("seah_focal_survivor_risks", tracker, dispatcher, domain)

    async def extract_seah_focal_mitigation_measures(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction("seah_focal_mitigation_measures", tracker, dispatcher, domain)

    async def extract_seah_focal_other_at_risk_parties(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction("seah_focal_other_at_risk_parties", tracker, dispatcher, domain)

    async def extract_seah_focal_project_risk(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction("seah_focal_project_risk", tracker, dispatcher, domain)

    async def extract_seah_focal_reputational_risk(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction("seah_focal_reputational_risk", tracker, dispatcher, domain)

    async def extract_seah_focal_referred_to_support(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        return await self._handle_slot_extraction("seah_focal_referred_to_support", tracker, dispatcher, domain)

    async def validate_seah_focal_survivor_risks(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_survivor_risks")

    async def validate_seah_focal_mitigation_measures(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_mitigation_measures")

    async def validate_seah_focal_other_at_risk_parties(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_other_at_risk_parties")

    async def validate_seah_focal_project_risk(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_project_risk")

    async def validate_seah_focal_reputational_risk(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        return self._validate_text_or_skip(slot_value, "seah_focal_reputational_risk")

    async def validate_seah_focal_referred_to_support(
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
            return {"seah_focal_referred_to_support": value}
        if value == self.SKIP_VALUE:
            return {"seah_focal_referred_to_support": self.SKIP_VALUE}
        return {"seah_focal_referred_to_support": None}

    def _validate_text_or_skip(self, slot_value: Any, slot_name: Text) -> Dict[Text, Any]:
        if slot_value is None or slot_value == self.SKIP_VALUE:
            return {slot_name: self.SKIP_VALUE}
        if isinstance(slot_value, str) and len(slot_value.strip()) >= 2:
            return {slot_name: slot_value.strip()}
        return {slot_name: None}


class ActionPrepareSeahFocalComplainantCapture(BaseAction):
    def name(self) -> Text:
        return "action_prepare_seah_focal_complainant_capture"

    async def execute_action(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict
    ) -> List[Dict[Text, Any]]:
        return [
            {"event": "slot", "name": "seah_focal_phone", "value": tracker.get_slot("complainant_phone")},
            {"event": "slot", "name": "seah_focal_full_name", "value": tracker.get_slot("complainant_full_name")},
            {"event": "slot", "name": "seah_focal_city", "value": tracker.get_slot("complainant_municipality")},
            {"event": "slot", "name": "seah_focal_village", "value": tracker.get_slot("complainant_village")},
            {"event": "slot", "name": "complainant_phone", "value": None},
            {"event": "slot", "name": "complainant_full_name", "value": None},
            {"event": "slot", "name": "complainant_email", "value": None},
            {"event": "slot", "name": "complainant_email_temp", "value": None},
            {"event": "slot", "name": "complainant_email_confirmed", "value": None},
            {"event": "slot", "name": "complainant_consent", "value": None},
            {"event": "slot", "name": "complainant_municipality", "value": None},
            {"event": "slot", "name": "complainant_village", "value": None},
        ]


class ActionAskFormSeahFocalPoint1SeahFocalLearnedWhen(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_1_seah_focal_learned_when"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSeahFocalPoint1SeahFocalReporterConsentToReport(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_1_seah_focal_reporter_consent_to_report"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1), buttons=self.get_buttons(1))
        return []


class ActionAskFormSeahFocalPoint1SensitiveIssuesFollowUp(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_1_sensitive_issues_follow_up"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1), buttons=self.get_buttons(1))
        return []


class ActionAskFormSeahFocalPoint2SeahProjectIdentification(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_2_seah_project_identification"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        buttons = self.build_seah_project_identification_buttons(
            tracker, max_projects=12
        )
        dispatcher.utter_message(text=self.get_utterance(1), buttons=buttons)
        return []


class ActionAskFormSeahFocalPoint2SeahFocalSurvivorRisks(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_2_seah_focal_survivor_risks"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSeahFocalPoint2SeahFocalMitigationMeasures(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_2_seah_focal_mitigation_measures"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSeahFocalPoint2SeahFocalOtherAtRiskParties(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_2_seah_focal_other_at_risk_parties"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSeahFocalPoint2SeahFocalProjectRisk(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_2_seah_focal_project_risk"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSeahFocalPoint2SeahFocalReputationalRisk(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_2_seah_focal_reputational_risk"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1))
        return []


class ActionAskFormSeahFocalPoint2SensitiveIssuesNewDetail(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_2_sensitive_issues_new_detail"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        description_status = tracker.get_slot("grievance_description_status")
        if description_status in ("show_options", "add_more_details"):
            grievance_description = tracker.get_slot("grievance_description") or ""
            dispatcher.utter_message(
                text=self.get_utterance(2).format(grievance_description=grievance_description),
                buttons=self.get_buttons(2),
            )
        else:
            dispatcher.utter_message(text=self.get_utterance(1), buttons=self.get_buttons(1))
        return []


class ActionAskFormSeahFocalPoint2SeahContactConsentChannel(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_2_seah_contact_consent_channel"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        buttons = self.build_seah_contact_channel_buttons(
            buttons=self.get_buttons(1),
            phone_value=tracker.get_slot("complainant_phone"),
            email_value=tracker.get_slot("complainant_email"),
        )
        dispatcher.utter_message(text=self.get_utterance(1), buttons=buttons)
        return []


class ActionAskFormSeahFocalPoint2SeahFocalReferredToSupport(BaseAction):
    def name(self) -> Text:
        return "action_ask_form_seah_focal_point_2_seah_focal_referred_to_support"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text=self.get_utterance(1), buttons=self.get_buttons(1))
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
        if tracker.get_slot("story_main") == "seah_intake":
            from backend.actions.action_seah_outro import ActionSeahOutro

            return await ActionSeahOutro().execute_action(dispatcher, tracker, domain)
        message = self.get_utterance(2) if tracker.get_slot("seah_not_adb_project") else self.get_utterance(1)
        buttons = self.get_buttons(1)
        dispatcher.utter_message(text=message, buttons=buttons)
        return []
