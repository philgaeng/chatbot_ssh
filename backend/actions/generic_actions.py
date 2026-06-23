"""Generic flow actions used by the orchestrator (intro, language, menu, routing)."""

import os
from typing import Any, Text, Dict, List

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction

from .base_classes.base_classes import BaseAction
from backend.actions.services.intro.qr import parse_introduce_payload, resolve_qr_token


class ActionNextAction(BaseAction):
    def name(self) -> Text:
        return "action_next_action"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        next_action = self.get_next_action_for_form(tracker)
        self.logger.debug(f"{self.name()} - Next action selected: {next_action}")
        return [FollowupAction(next_action)]


class ActionIntroduce(BaseAction):
    def name(self) -> Text:
        return "action_introduce"

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events: List[Dict[Text, Any]] = []
        message = tracker.latest_message.get('text', '')
        self.logger.debug(f"{self.name()} - 🔍 [RASA DEBUG] Message: {message}")

        if message and "introduce" in message.lower():
            payload = parse_introduce_payload(message, self.logger)

            province = payload.get('province')
            district = payload.get('district')
            flask_session_id = payload.get('flask_session_id')
            token = payload.get('t')

            qr_bundle = resolve_qr_token(self.db_manager, token, self.logger) if token else {}

            if qr_bundle:
                qr_district = qr_bundle.get("complainant_district")
                qr_province = qr_bundle.get("complainant_province")

                slot_pairs = [
                    ("qr_token", qr_bundle.get("qr_token")),
                    ("package_id", qr_bundle.get("package_id")),
                    ("package_label", qr_bundle.get("package_label")),
                    ("project_code", qr_bundle.get("project_code")),
                    ("location_code", qr_bundle.get("location_code")),
                    ("complainant_province", qr_province or province),
                    ("complainant_district", qr_district or district),
                ]
                for slot_name, slot_value in slot_pairs:
                    if slot_value:
                        events.append(SlotSet(slot_name, slot_value))
            else:
                if province and district:
                    events.extend([
                        SlotSet("complainant_province", province),
                        SlotSet("complainant_district", district),
                    ])

            if flask_session_id:
                events.append(SlotSet("flask_session_id", flask_session_id))

        utterance = self.get_utterance(1)
        buttons = self.get_buttons(1)
        self.logger.debug(f"{self.name()} - 🔍 [RASA DEBUG] Message: {utterance}")
        self.logger.debug(f"{self.name()} - 🔍 [RASA DEBUG] Buttons: {buttons}")
        dispatcher.utter_message(text=utterance, buttons=buttons)
        return events


class ActionSetEnglish(BaseAction):
    def name(self) -> Text:
        return "action_set_english"

    async def execute_action(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("language_code", "en")]


class ActionSetNepali(BaseAction):
    def name(self) -> Text:
        return "action_set_nepali"

    async def execute_action(
            self,
            dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("language_code", "ne")]


class ActionMainMenu(BaseAction):
    def name(self) -> Text:
        return "action_main_menu"

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        district = tracker.get_slot("complainant_district")
        province = tracker.get_slot("complainant_province")
        package_label = tracker.get_slot("package_label")

        if package_label and district:
            # QR-scanned arrival: include the package label in the welcome.
            message = self.get_utterance(3)
            message = message.format(
                package_label=package_label,
                district=district,
                province=province or "",
            )
        elif district and province:
            message = self.get_utterance(2)
            message = message.format(
                district=district,
                province=province,
            )
        else:
            message = self.get_utterance(1)
        buttons = self.get_buttons(1)
        seah_enabled = os.environ.get("ENABLE_SEAH_DEDICATED_FLOW", "true").strip().lower() in ("1", "true", "yes")
        if not seah_enabled:
            buttons = [b for b in buttons if b.get("payload") != "/seah_intake"]
        dispatcher.utter_message(text=message, buttons=buttons)

        return [SlotSet("story_main", None)]
