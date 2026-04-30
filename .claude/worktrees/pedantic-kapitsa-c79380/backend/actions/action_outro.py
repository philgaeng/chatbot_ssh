"""Shared outro actions for grievance and SEAH flows."""
import asyncio
from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseAction
from backend.actions.action_submit_grievance import BaseActionSubmit
from backend.actions.utils.mapping_buttons import BUTTONS_SEAH_OUTRO
from backend.actions.utils.utterance_mapping_rasa import get_utterance_base


class ActionSeahOutro(BaseAction):
    def name(self) -> Text:
        return "action_seah_outro"

    def _get_seah_utterance(self, utterance_index: int) -> str:
        return get_utterance_base("action_seah_outro", self.name(), utterance_index, self.language_code)

    async def execute_action(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> List[Dict[Text, Any]]:
        self._initialize_language_and_helpers(tracker)
        slots = dict(tracker.current_slot_values())
        variant = self.resolve_seah_outro_variant(slots)
        language_code = tracker.get_slot("language_code") or "en"

        row = self.find_seah_contact_point(tracker)

        contact_block = ""
        events: List[Dict[Text, Any]] = []
        if row:
            contact_block = "\n\n" + self.format_seah_contact_point_block(row, language_code)
            cid = row.get("seah_contact_point_id")
            if cid:
                events.append(SlotSet("seah_contact_point_id", cid))

        order = {
            "focal_default": 1,
            "victim_limited_contact": 2,
            "victim_contact_ok": 3,
            "not_victim_anonymous": 4,
            "not_victim_identified": 5,
        }
        idx = order.get(variant, 2)
        body = self._get_seah_utterance(idx)
        full_text = body + contact_block
        buttons = BUTTONS_SEAH_OUTRO.get(language_code, BUTTONS_SEAH_OUTRO["en"])
        dispatcher.utter_message(text=full_text, buttons=buttons)
        return events


class ActionGrievanceOutro(BaseActionSubmit):
    def _get_grievance_utterance(self, utterance_index: int) -> str:
        return get_utterance_base(
            "action_submit_grievance", self.name(), utterance_index, self.language_code
        )

    def name(self) -> Text:
        return "action_grievance_outro"

    def _prepare_grievance_outro_data(self, tracker: Tracker) -> Dict[str, Any]:
        """Prepare grievance outro data and normalize categories in english."""
        grievance_data = self.collect_grievance_data(tracker, review=True)
        grievance_categories_local = tracker.get_slot("grievance_categories_local")
        current_categories = tracker.get_slot("grievance_categories")

        if grievance_categories_local and self.language_code != "en":
            grievance_categories_en = self._get_categories_in_english(grievance_categories_local)
            grievance_data["grievance_categories"] = grievance_categories_en
        elif current_categories:
            grievance_data["grievance_categories"] = current_categories

        return grievance_data

    async def execute_action(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Any]:
        self.grievance_sensitive_issue = tracker.get_slot("grievance_sensitive_issue")
        self.logger.info("send last utterance and buttons")
        grievance_id = tracker.get_slot("grievance_id")
        language_code = tracker.get_slot("language_code") or "en"
        try:
            if self.grievance_sensitive_issue:
                utterance = self._get_grievance_utterance(1)
            elif not self._get_attached_files_info(grievance_id)["has_files"]:
                utterance = self._get_grievance_utterance(2)
            else:
                utterance = self._get_grievance_utterance(3)
            self.logger.debug(f"action_grievance_outro - utterance: {utterance}")

            # Reuse shared close-session buttons used by SEAH outro for consistent UX.
            buttons = BUTTONS_SEAH_OUTRO.get(language_code, BUTTONS_SEAH_OUTRO["en"])
            dispatcher.utter_message(text=utterance, buttons=buttons)
            self.logger.debug("action_grievance_outro - outro sent")

            grievance_data = self._prepare_grievance_outro_data(tracker)
            self.db_manager.submit_grievance_to_db(grievance_data)
            self.logger.debug(
                f"action_grievance_outro - grievance data saved to the database: {grievance_data}"
            )

            await self._send_grievance_recap_email_to_admin(grievance_data, dispatcher)
            complainant_email = grievance_data.get("complainant_email")
            if complainant_email and self.is_valid_email(complainant_email):
                await self._send_grievance_recap_email_to_complainant(
                    complainant_email, grievance_data, dispatcher
                )
            return []
        except Exception as e:
            self.logger.error(f"Error in action_grievance_outro: {e}")
            return []


class ActionStatusCheckRequestFollowUp(BaseAction):
    """Status-check follow-up outro with shared close-session buttons."""

    def name(self) -> Text:
        return "action_status_check_request_follow_up"

    def _get_status_check_utterance(self, utterance_index: int) -> str:
        return get_utterance_base(
            "form_status_check", self.name(), utterance_index, self.language_code
        )

    async def execute_action(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        self._initialize_language_and_helpers(tracker)
        language_code = tracker.get_slot("language_code") or "en"
        buttons = BUTTONS_SEAH_OUTRO.get(language_code, BUTTONS_SEAH_OUTRO["en"])

        complainant_phone = tracker.get_slot("complainant_phone")
        grievance_id = tracker.get_slot("status_check_grievance_id_selected")

        if tracker.get_slot("otp_status") != "verified":
            dispatcher.utter_message(text=self._get_status_check_utterance(1))
            issue = self.get_follow_up_phone_issue(tracker)
            if issue == "no_phone":
                dispatcher.utter_message(text=self._get_status_check_utterance(3))
            else:
                dispatcher.utter_message(text=self._get_status_check_utterance(4))
            dispatcher.utter_message(buttons=buttons)
        else:
            # Show grievance details before confirmation for context.
            if grievance_id:
                grievance = self.collect_grievance_data_from_id(grievance_id, tracker, domain)
                if grievance:
                    grievance_text = self.prepare_grievance_text_for_display(
                        grievance, display_only_short=False
                    )
                    dispatcher.utter_message(text=grievance_text)

            utterance = self._get_status_check_utterance(2).format(
                grievance_id=grievance_id, complainant_phone=complainant_phone
            )
            dispatcher.utter_message(text=utterance, buttons=buttons)
            self.send_sms(
                sms_data={"grievance_id": grievance_id, "complainant_phone": complainant_phone},
                body_name="GRIEVANCE_STATUS_CHECK_REQUEST_FOLLOW_UP",
            )

        # Send admin recap asynchronously so user-facing response remains fast.
        email_data = self.collect_grievance_data_from_tracker(tracker)
        if grievance_id:
            grievance = self.db_manager.get_grievance_by_id(grievance_id)
            if grievance:
                email_data["grievance_id"] = grievance_id
                email_data["grievance_timeline"] = (
                    grievance.get("grievance_timeline") or self.NOT_PROVIDED
                )
                email_data["grievance_summary"] = (
                    grievance.get("grievance_summary")
                    or grievance.get("grievance_description")
                    or self.NOT_PROVIDED
                )
                email_data["grievance_description"] = (
                    email_data.get("grievance_description")
                    or grievance.get("grievance_description")
                    or self.NOT_PROVIDED
                )
                email_data["grievance_categories"] = (
                    grievance.get("grievance_categories")
                    or email_data.get("grievance_categories")
                    or self.NOT_PROVIDED
                )

        def _log_email_done(task: asyncio.Task) -> None:
            try:
                task.result()
            except Exception as e:
                self.logger.error(f"Background admin recap email failed: {e}", exc_info=True)

        task = asyncio.create_task(
            self.send_recap_email_to_admin(
                email_data, "GRIEVANCE_STATUS_CHECK_REQUEST_FOLLOW_UP", dispatcher
            )
        )
        task.add_done_callback(_log_email_done)
        return []
