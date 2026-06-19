"""Shared outro actions for grievance and SEAH flows."""
import asyncio
from typing import Any, Dict, List, Text

from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from rasa_sdk.types import DomainDict

from backend.actions.base_classes.base_classes import BaseAction
from backend.actions.action_submit_grievance import BaseActionSubmit
from backend.actions.forms.form_dust import is_dust_intake
from backend.actions.utils.utterance_mapping_rasa import get_utterance_base
from backend.actions.utils.mapping_buttons import (
    BUTTONS_CLOSE_BROWSER_ONLY,
    BUTTONS_CLOSE_SESSION_ONLY,
    BUTTONS_FILE_ANOTHER_GRIEVANCE,
    BUTTONS_FILE_ANOTHER_SEAH,
)


def _post_submit_buttons(language_code: str) -> List[Dict[str, str]]:
    lang = language_code if language_code in BUTTONS_CLOSE_SESSION_ONLY else "en"
    buttons = list(BUTTONS_CLOSE_SESSION_ONLY.get(lang, BUTTONS_CLOSE_SESSION_ONLY["en"]))
    buttons.extend(BUTTONS_FILE_ANOTHER_GRIEVANCE.get(lang, BUTTONS_FILE_ANOTHER_GRIEVANCE["en"]))
    return buttons


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
        language_code = tracker.get_slot("language_code") or "en"
        is_focal = slots.get("seah_victim_survivor_role") == "focal_point"

        events: List[Dict[Text, Any]] = []

        if is_focal:
            dispatcher.utter_message(text=self._get_seah_utterance(7))
        else:
            contact_provided = slots.get("seah_contact_provided")
            if contact_provided is None:
                contact_provided = self.compute_seah_contact_provided(slots)

            # Thank-you line depends on whether contact details were shared.
            thank_you_idx = 5 if contact_provided else 4
            dispatcher.utter_message(text=self._get_seah_utterance(thank_you_idx))

            # Nearest support centre only (not the full district list).
            from backend.shared_functions.seah_service_providers import format_provider_details_block

            providers = self.find_seah_service_providers_for_tracker(tracker)
            nearest = providers[0] if providers else self.find_seah_contact_point(tracker)

            if nearest:
                intro = self._get_seah_utterance(6)
                if providers:
                    details = format_provider_details_block(nearest, language_code)
                else:
                    details = self.format_seah_contact_point_block(nearest, language_code)
                dispatcher.utter_message(text=f"{intro}\n\n{details}")

                cid = nearest.get("seah_contact_point_id") or nearest.get("seah_service_provider_id")
                if cid:
                    events.append(SlotSet("seah_contact_point_id", cid))

        # Post-submit buttons only (submit already confirms the report is on record).
        lang = language_code if language_code in BUTTONS_CLOSE_BROWSER_ONLY else "en"
        buttons = list(BUTTONS_CLOSE_BROWSER_ONLY.get(lang, BUTTONS_CLOSE_BROWSER_ONLY["en"]))
        buttons.extend(BUTTONS_FILE_ANOTHER_SEAH.get(lang, BUTTONS_FILE_ANOTHER_SEAH["en"]))
        dispatcher.utter_message(text="", buttons=buttons)
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
        resolved = self._resolve_grievance_categories_for_db(tracker)
        if resolved:
            grievance_data["grievance_categories"] = resolved
        return grievance_data

    async def execute_action(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Any]:
        self.grievance_sensitive_issue = tracker.get_slot("grievance_sensitive_issue")
        self.logger.info("send last utterance and buttons")
        grievance_id = tracker.get_slot("grievance_id") or ""
        language_code = tracker.get_slot("language_code") or "en"
        dust = is_dust_intake(tracker)
        try:
            if dust:
                # Submit already sent filed + reference; only offer next steps.
                buttons = _post_submit_buttons(language_code)
                dispatcher.utter_message(text="", buttons=buttons)
            elif self.grievance_sensitive_issue:
                dispatcher.utter_message(text=self._get_grievance_utterance(4))
                dispatcher.utter_message(
                    text=self._get_grievance_utterance(2).format(grievance_id=grievance_id)
                )
                attachment_msg = self._get_grievance_utterance(3)
                dispatcher.utter_message(text=attachment_msg)
                buttons = list(BUTTONS_CLOSE_BROWSER_ONLY.get(language_code, BUTTONS_CLOSE_BROWSER_ONLY["en"]))
                buttons.extend(
                    BUTTONS_FILE_ANOTHER_SEAH.get(language_code, BUTTONS_FILE_ANOTHER_SEAH["en"])
                )
                dispatcher.utter_message(text="", buttons=buttons)
            else:
                dispatcher.utter_message(text=self._get_grievance_utterance(1))
                dispatcher.utter_message(
                    text=self._get_grievance_utterance(2).format(grievance_id=grievance_id)
                )
                if not self._get_attached_files_info(grievance_id)["has_files"]:
                    attachment_msg = self._get_grievance_utterance(5)
                else:
                    attachment_msg = self._get_grievance_utterance(6)
                dispatcher.utter_message(text=attachment_msg)
                buttons = _post_submit_buttons(language_code)
                dispatcher.utter_message(text="", buttons=buttons)

            if grievance_id and not dust:
                dispatcher.utter_message(
                    json_message={
                        "data": {
                            "event_type": "grievance_filed",
                            "grievance_id": grievance_id,
                        }
                    }
                )

            grievance_data = self._prepare_grievance_outro_data(tracker)
            self.db_manager.submit_grievance_to_db(grievance_data)
            self.logger.debug(
                f"action_grievance_outro - grievance data saved to the database: {grievance_data}"
            )

            await self.send_recap_email_to_admin(
                grievance_data, "GRIEVANCE_RECAP_ADMIN_BODY", dispatcher
            )
            complainant_email = grievance_data.get("complainant_email")
            if complainant_email and self.is_valid_email(complainant_email):
                await self.send_recap_email_to_complainant(
                    complainant_email,
                    "GRIEVANCE_RECAP_COMPLAINANT_BODY",
                    grievance_data,
                    dispatcher,
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

        complainant_phone = tracker.get_slot("complainant_phone")
        grievance_id = tracker.get_slot("status_check_grievance_id_selected")

        if tracker.get_slot("otp_status") != "verified":
            dispatcher.utter_message(text=self._get_status_check_utterance(1))
            issue = self.get_follow_up_phone_issue(tracker)
            if issue == "no_phone":
                dispatcher.utter_message(text=self._get_status_check_utterance(3))
            else:
                dispatcher.utter_message(text=self._get_status_check_utterance(4))
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
            dispatcher.utter_message(text=utterance)
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
