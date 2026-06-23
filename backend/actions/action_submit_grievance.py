from typing import Any, Dict, List, Optional, Text
import traceback
from .base_classes.base_classes import BaseAction
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
from backend.actions.services.submit import collect as submit_collect
from backend.actions.services.submit import confirmation as submit_confirmation
from backend.actions.services.submit import storage as submit_storage
from backend.actions.utils.mapping_buttons import BUTTONS_SEAH_OUTRO
from backend.actions.utils.ticketing_dispatch import dispatch_grievance_from_tracker
from backend.actions.utils.utterance_mapping_rasa import get_utterance_base
from backend.config.database_constants import GRIEVANCE_STATUS
from rasa_sdk.events import SlotSet





############################ STEP 4 - SUBMIT GRIEVANCE ############################
class BaseActionSubmit(BaseAction):



    
    def check_grievance_high_priority(self, grievance_categories: Any) -> bool:
        return submit_confirmation.check_grievance_high_priority(grievance_categories)

    def collect_grievance_data(self, tracker: Tracker, review: bool = False) -> Dict[str, Any]:
        return submit_collect.collect_grievance_data(
            tracker,
            db_manager=self.db_manager,
            helpers_repo=self.helpers_repo,
            grievance_status_submitted=self.GRIEVANCE_STATUS["SUBMITTED"],
            skip_value=self.SKIP_VALUE,
            not_provided=self.NOT_PROVIDED,
            llm_classification_enabled=self.LLM_CLASSIFICATION,
            grievance_classification_status=self.GRIEVANCE_CLASSIFICATION_STATUS,
            review=review,
            check_high_priority=self.check_grievance_high_priority,
        )

    def _merge_role_party_payloads(self, grievance_data: Dict[str, Any]) -> Dict[str, Any]:
        return submit_storage.merge_role_party_payloads(grievance_data)

    def create_confirmation_message(self, grievance_data: Dict[str, Any]) -> str:
        return submit_confirmation.create_confirmation_message(
            grievance_data,
            language_code=self.language_code,
            not_provided=self.NOT_PROVIDED,
            db_manager=self.db_manager,
        )

    async def _send_grievance_recap_sms(
        self,
        grievance_data: Dict[str, Any],
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
    ) -> None:
        try:
            confirmation_message = self.create_confirmation_message(grievance_data)
            submit_confirmation.emit_chat_filed_confirmation(
                dispatcher,
                grievance_data,
                language_code=self.language_code,
                tracker=tracker,
            )
            
            if grievance_data.get('otp_verified') == True:
                #send sms
                complainant_phone = grievance_data.get('complainant_phone')
                if complainant_phone != self.NOT_PROVIDED:
                    from backend.clients.messaging_api import send_sms as send_sms_via_api

                    send_sms_via_api(
                        str(complainant_phone),
                        confirmation_message,
                        context={
                            "source_system": "chatbot",
                            "purpose": "grievance_submit_confirmation",
                            "grievance_id": grievance_data.get("grievance_id"),
                            "channel": "sms",
                        },
                    )
                    #utter sms confirmation message
                    utterance = self.get_utterance(2)
                    utterance = utterance.format(complainant_phone=complainant_phone)
                    dispatcher.utter_message(text=utterance)
        except Exception as e:
            self.logger.error(f"Failed to send grievance filed confirmation: {e}")
  
    


    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any], review: bool = False) -> List[Dict[Text, Any]]:
        self.grievance_sensitive_issue = tracker.get_slot("grievance_sensitive_issue")
        self.grievance_id = tracker.get_slot("grievance_id")
        self.complainant_id = tracker.get_slot("complainant_id")
        
        slot_keys = sorted(tracker.slots.keys()) if getattr(tracker, "slots", None) else []
        self.logger.debug(
            "Submit grievance - tracker slot_keys=%s grievance_id=%s complainant_id=%s",
            slot_keys,
            self.grievance_id,
            self.complainant_id,
        )
        
        try:
            # Collect grievance data
            grievance_data = self.collect_grievance_data(tracker, review)
            self.logger.debug(
                "Submit grievance - collected data keys=%s",
                sorted(grievance_data.keys()) if isinstance(grievance_data, dict) else type(grievance_data).__name__,
            )
            # Update the existing grievance with complete data
            try:
                self.db_manager.submit_grievance_to_db(data=grievance_data)
            except Exception as e:
                self.logger.error(f"❌ Error updating grievance: {str(e)}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                raise Exception("Failed to update grievance in the database")
        

            self.logger.info(f"✅ Grievance updated successfully with ID: {self.grievance_id}")

            await self._send_grievance_recap_sms(grievance_data, dispatcher, tracker)

            # #send email to admin
            # await self._send_grievance_recap_email_to_admin(grievance_data, dispatcher)

            # #send email to complainant
            # complainant_email = grievance_data.get('complainant_email')

            # if complainant_email and self.is_valid_email(complainant_email):
            #     await self._send_grievance_recap_email_to_complainant(complainant_email, grievance_data, dispatcher)

            # INTEGRATION POINT: chatbot → ticketing webhook (fire-and-forget, never blocks)
            dispatch_grievance_from_tracker(
                tracker,
                grievance_data,
                log=self.logger,
                grievance_id=self.grievance_id,
                complainant_id=self.complainant_id,
                is_seah=bool(self.grievance_sensitive_issue),
                priority=(
                    "HIGH"
                    if grievance_data.get("grievance_high_priority")
                    else None
                ),
            )

            return [
                SlotSet("grievance_status", self.GRIEVANCE_STATUS["SUBMITTED"])
            ]

        except Exception as e:
            self.logger.error(f"❌ Error submitting grievance: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            utterance = self.get_utterance(4)
            dispatcher.utter_message(text=utterance)
            return []

class ActionSubmitGrievance(BaseActionSubmit):
    def name(self) -> Text:
        return "action_submit_grievance"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await super().execute_action(dispatcher, tracker, domain, review = False)


class ActionSubmitSeah(BaseActionSubmit):
    def name(self) -> Text:
        return "action_submit_seah"

    def _resolve_seah_focal_phone(self, tracker: Tracker) -> Optional[str]:
        for key in ("complainant_phone", "seah_focal_phone"):
            value = tracker.get_slot(key)
            if self._slot_nonempty(value):
                return str(value).strip()
        return None

    def _seah_submit_follow_up_text(self, tracker: Tracker, language_code: str) -> str:
        if tracker.get_slot("seah_victim_survivor_role") == "focal_point":
            phone = self._resolve_seah_focal_phone(tracker)
            if phone:
                return get_utterance_base(
                    "action_submit_seah", "action_submit_seah", 2, language_code
                ).format(phone=phone)
        return get_utterance_base("action_submit_seah", "action_submit_seah", 1, language_code)

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        try:
            language_code = tracker.get_slot("language_code") or "en"
            grievance_data = self.collect_grievance_data(tracker, review=False)
            grievance_data["language_code"] = language_code
            grievance_data["seah_not_adb_project"] = tracker.get_slot("seah_not_adb_project")
            grievance_data["seah_contact_consent_channel"] = tracker.get_slot("seah_contact_consent_channel")

            seah_fields = [
                "sensitive_issues_follow_up",
                "seah_victim_survivor_role",
                "seah_project_identification",
                "sensitive_issues_new_detail",
                "seah_focal_survivor_risks",
                "seah_focal_mitigation_measures",
                "seah_focal_other_at_risk_parties",
                "seah_focal_project_risk",
                "seah_focal_reputational_risk",
                "seah_focal_learned_when",
                "seah_focal_reporter_consent_to_report",
                "seah_focal_referred_to_support",
                "seah_focal_phone",
                "seah_focal_city",
                "seah_focal_village",
                "seah_focal_full_name",
                "seah_focal_lookup_status",
                "seah_focal_verification_status",
            ]
            for field in seah_fields:
                grievance_data[field] = tracker.get_slot(field)

            slot_map = dict(tracker.current_slot_values())
            cp = tracker.get_slot("seah_contact_provided")
            if cp is None:
                cp = self.compute_seah_contact_provided(slot_map)
            grievance_data["seah_contact_provided"] = cp
            ar = tracker.get_slot("seah_anonymous_route")
            if ar is None:
                ar = tracker.get_slot("sensitive_issues_follow_up") == "anonymous"
            grievance_data["seah_anonymous_route"] = ar
            grievance_data["project_uuid"] = tracker.get_slot("project_uuid")
            grievance_data["seah_contact_point_id"] = tracker.get_slot("seah_contact_point_id")
            grievance_data["complainant_consent"] = tracker.get_slot("complainant_consent")
            grievance_data["active_party_role"] = tracker.get_slot("active_party_role")
            grievance_data["party_contacts"] = tracker.get_slot("party_contacts") or {}
            grievance_data["party_victim_survivor"] = tracker.get_slot("party_victim_survivor")
            grievance_data["party_witness"] = tracker.get_slot("party_witness")
            grievance_data["party_relative"] = tracker.get_slot("party_relative")
            grievance_data["party_seah_focal_point"] = tracker.get_slot("party_seah_focal_point")
            grievance_data["party_other_reporter"] = tracker.get_slot("party_other_reporter")
            grievance_data = self._merge_role_party_payloads(grievance_data)

            result = self.db_manager.submit_seah_to_db(grievance_data)
            if not result.get("ok"):
                raise Exception(result.get("error", "SEAH submission failed"))

            # INTEGRATION POINT: chatbot → ticketing webhook (fire-and-forget, never blocks)
            complainant_ref = (
                result.get("complainant_id")
                or grievance_data.get("complainant_id")
                or tracker.get_slot("complainant_id")
            )
            dispatch_grievance_from_tracker(
                tracker,
                grievance_data,
                log=self.logger,
                grievance_id=result.get("grievance_id") or self.grievance_id,
                complainant_id=complainant_ref,
                is_seah=True,
                priority="HIGH",
            )

            grievance_ref = result.get("grievance_id")
            follow_up = self._seah_submit_follow_up_text(tracker, language_code)
            if language_code == "ne":
                dispatcher.utter_message(text="तपाईंको गोप्य SEAH रिपोर्ट सफलतापूर्वक दर्ता भयो।")
                dispatcher.utter_message(
                    text=f"तपाईंको सन्दर्भ नम्बर: **{grievance_ref}**"
                )
                dispatcher.utter_message(text=follow_up)
            else:
                dispatcher.utter_message(
                    text="Your confidential SEAH report has been filed successfully."
                )
                dispatcher.utter_message(
                    text=f"Your reference number is **{grievance_ref}**."
                )
                dispatcher.utter_message(text=follow_up)
            dispatcher.utter_message(
                json_message={
                    "data": {
                        "event_type": "grievance_filed",
                        "grievance_id": grievance_ref,
                    }
                }
            )

            return [
                SlotSet("grievance_status", self.GRIEVANCE_STATUS["SUBMITTED"]),
                SlotSet("grievance_id", grievance_ref),
            ]
        except Exception as e:
            self.logger.error(f"❌ Error submitting SEAH report: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            lc = tracker.get_slot("language_code") or "en"
            outro_buttons = BUTTONS_SEAH_OUTRO.get(lc, BUTTONS_SEAH_OUTRO["en"])
            if lc == "ne":
                dispatcher.utter_message(
                    text=(
                        "हामीले अहिले तपाईंको SEAH रिपोर्ट पेस गर्न सकेनौं। कृपया पछि फेरि प्रयास गर्नुहोस्।\n\n"
                        "तत्काल सहयोग चाहिएमा नजिकको SEAH सहयोग सेवा वा आपतकालीन सेवामा सम्पर्क गर्न सक्नुहुन्छ।"
                    ),
                    buttons=outro_buttons,
                )
            else:
                dispatcher.utter_message(
                    text=(
                        "We could not submit your SEAH report right now. Please try again.\n\n"
                        "If you need immediate help, you can reach a local SEAH support service or emergency services."
                    ),
                    buttons=outro_buttons,
                )
            return []

