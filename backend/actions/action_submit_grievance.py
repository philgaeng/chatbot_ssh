from typing import Any, Dict, List, Text, Tuple
from datetime import datetime, timedelta
import re
from .base_classes.base_classes import BaseAction
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
import json
import traceback
from backend.config.constants import ADMIN_EMAILS, EMAIL_TEMPLATES, CLASSIFICATION_DATA
from backend.actions.utils.mapping_buttons import BUTTONS_SEAH_OUTRO
from backend.config.database_constants import GRIEVANCE_STATUS
from rasa_sdk.events import SlotSet
from backend.shared_functions.location_mapping import resolve_location_payload





############################ STEP 4 - SUBMIT GRIEVANCE ############################
class BaseActionSubmit(BaseAction):



    
    def check_grievance_high_priority(self, grievance_categories: Any) -> bool:
        """
        Check if any of the grievance categories has high_priority set to True.
        
        Args:
            grievance_categories: List of category names (e.g., ["Economic, Social - Land Acquisition Issues"])
            
        Returns:
            bool: True if at least one category has high_priority = True, False otherwise
        """
        try:
            # Check if any of the grievance categories has high priority
            
            if isinstance(grievance_categories, str):
                # If it's a string, try to parse it as JSON
                try:
                    grievance_categories = json.loads(grievance_categories)
                except (json.JSONDecodeError, TypeError):
                    grievance_categories = [grievance_categories]
            # Check if any of the categories has high_priority = True
            if isinstance(grievance_categories, list):
                for category in grievance_categories:
                    if category in CLASSIFICATION_DATA:
                        if CLASSIFICATION_DATA[category].get('high_priority', False):
                            return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking grievance high priority: {str(e)}")
            return False
    



    def collect_grievance_data(self, tracker: Tracker, review: bool = False) -> Dict[str, Any]:
        """Collect and separate user and grievance data from slots."""
        # set up the timestamp and timeline
        

        keys = ["complainant_id",
                 "complainant_phone",
                 "complainant_email",
                 "complainant_full_name",
                 "complainant_gender",
                 "complainant_province",
                 "complainant_district",
                 "complainant_municipality",
                 "complainant_village",
                 "complainant_address",
                 "grievance_id",
                 "grievance_description",
                 "otp_verified",
                 ]

        if review:
            review_keys = ["grievance_categories",
                           "grievance_summary",
                           "grievance_sensitive_issue"]

            keys = keys + review_keys
        
        
        # collect the data from the tracker
        grievance_data={k : tracker.get_slot(k) for k in keys}
        location_payload = resolve_location_payload(
            db_manager=self.db_manager,
            slots=grievance_data,
            country_code=tracker.get_slot("country_code") or "NP",
        )
        grievance_data.update(location_payload)
        self.logger.info(
            "submission_location_resolution country_code=%s status=%s deepest_level=%s",
            location_payload.get("country_code"),
            location_payload.get("location_resolution_status"),
            location_payload.get("location_deepest_mapped_level", 0),
        )
        grievance_timestamp = self.helpers_repo.get_current_datetime()
        grievance_data["grievance_status"] = self.GRIEVANCE_STATUS["SUBMITTED"]
        if review:
            grievance_data["grievance_high_priority"] = self.check_grievance_high_priority(grievance_data["grievance_categories"])
        
        grievance_timeline = self.helpers_repo.get_timeline_by_status_code(status_update_code=self.GRIEVANCE_STATUS["SUBMITTED"],
        grievance_high_priority=grievance_data.get("grievance_high_priority", False),
        sensitive_issues_detected=grievance_data.get("grievance_sensitive_issue", False))
        

        grievance_data["submission_type"] = "new_grievance"
        grievance_data["grievance_timestamp"] = grievance_timestamp
        grievance_data["grievance_timeline"] = grievance_timeline
        # change all the values of the slots_skipped or None to "NOT_PROVIDED"
        grievance_data = self._update_key_values_for_db_storage(grievance_data)
        self.logger.info(f"Grievance data: {grievance_data}")
                
        return grievance_data

    def _update_key_values_for_db_storage(self, grievance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update the values of the grievance data for the database storage."""
        for key, value in grievance_data.items():
            if value == self.SKIP_VALUE or value is None:
                grievance_data[key] = self.NOT_PROVIDED
        return grievance_data
    
    

        
    def create_confirmation_message(self, 
                                    grievance_data: Dict[str, Any]) -> str:
        """Create a formatted confirmation message."""

        allowed_keys = ['grievance_id',
                        'grievance_timestamp',
                        'grievance_description',
                        'complainant_email',
                        'complainant_phone',
                        'grievance_outro',
                        'grievance_timeline']
        
        message_keys = [i for i in allowed_keys if grievance_data.get(i) and grievance_data.get(i) != self.NOT_PROVIDED]

        all_message_elements =  {
                'grievance_id': {
                    'en': "Your grievance has been filed successfully.\n**Grievance ID: {grievance_id} **",
                    'ne': "तपाईंको गुनासो सफलतापूर्वक दर्ता गरिएको छ।\n**गुनासो ID:** {grievance_id}"
                },
                'grievance_timestamp': {
                    'en': "Grievance filed on: {grievance_timestamp}",
                    'ne': "गुनासो दर्ता गरिएको: {grievance_timestamp}"
                },
                'grievance_summary': {
                    'en': "**Summary: {grievance_summary}**",
                    'ne': "**सारांश: {grievance_summary}**"
                },
                'grievance_categories': {
                    'en': "**Category: {grievance_categories}**",
                    'ne': "**श्रेणी: {grievance_categories}**"
                },
                'grievance_description': {
                    'en': "**Details: {grievance_description}**",
                    'ne': "**विवरण: {grievance_description}**"
                },
                'complainant_email': {
                    'en': "\nA confirmation email will be sent to {complainant_email}",
                    'ne': "\nतपाईंको इमेलमा सुनिश्चित गर्ने ईमेल भेटिन्छ। {complainant_email}"
                },
                'complainant_phone': {
                    'en': "**A confirmation SMS will be sent to your phone: {complainant_phone}**",
                    'ne': "**तपाईंको फोनमा सुनिश्चित गर्ने संदेश भेटिन्छ। {complainant_phone}**"
                },
                'grievance_outro': {
                    'en': "Our team will review it shortly and contact you if more information is needed.",
                    'ne': "हाम्रो टीमले त्यो गुनासोको लागि कल गर्दैछु र तपाईंलाई यदि अधिक जानकारी आवश्यक हुन्छ भने सम्पर्क गर्नेछ।"
                },
                'grievance_timeline': {
                    'en': "The standard resolution time for a grievance is 15 days. Expected resolution date: {grievance_timeline}",
                    'ne': "गुनासोको मानक समयावधि 15 दिन हुन्छ। अपेक्षित समाधान तिथि: {grievance_timeline}"
                },
                'grievance_status': {
                    'en': "**Status:**",
                    'ne': "**स्थिति:**"
                }
            }

        message_elements = [all_message_elements[i][self.language_code] for i in message_keys]

        # Get attached files information using the helper function
        has_files = self._get_attached_files_info(grievance_data['grievance_id'])["has_files"]
        files_info = self._get_attached_files_info(grievance_data['grievance_id'])["files_info"]
        

        
        message = "\n".join(message_elements).format(grievance_id=grievance_data['grievance_id'], 
                                            grievance_timestamp=grievance_data['grievance_timestamp'],
                                            grievance_description=grievance_data['grievance_description'],
                                            complainant_email=grievance_data['complainant_email'],
                                            complainant_phone=grievance_data['complainant_phone'],
                                            grievance_timeline=grievance_data['grievance_timeline']
                                           )

        # Add files information to the message
        if has_files:
            message = message + files_info
        return message
    
    async def _send_grievance_recap_sms(self, 
                                  grievance_data: Dict[str, Any],
                                  dispatcher: CollectingDispatcher) -> None:
        """Send a recap sms to the user."""
        try:
            # Create confirmation message to be sent by sms and through the bot
            confirmation_message = self.create_confirmation_message(
                grievance_data
            )
                
            # Send confirmation message
            dispatcher.utter_message(text=confirmation_message)
            
            if grievance_data.get('otp_verified') == True:
                #send sms
                complainant_phone = grievance_data.get('complainant_phone')
                if complainant_phone != self.NOT_PROVIDED:
                    self.messaging.send_sms(phone_number=complainant_phone, message=confirmation_message)
                    #utter sms confirmation message
                    utterance = self.get_utterance(2)
                    utterance = utterance.format(complainant_phone=complainant_phone)
                    dispatcher.utter_message(text=utterance)
        except Exception as e:
            self.logger.error(f"Failed to send recap sms to {complainant_phone}: {e}")
  
    


    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any], review: bool = False) -> List[Dict[Text, Any]]:
        self.grievance_sensitive_issue = tracker.get_slot("grievance_sensitive_issue")
        self.grievance_id = tracker.get_slot("grievance_id")
        self.complainant_id = tracker.get_slot("complainant_id")
        
        self.logger.debug(f"Submit grievance - All tracker slots: {tracker.slots}")
        self.logger.debug(f"Submit grievance - grievance_id from tracker: {self.grievance_id}")
        self.logger.debug(f"Submit grievance - complainant_id from tracker: {self.complainant_id}")
        
        try:
            # Collect grievance data
            grievance_data = self.collect_grievance_data(tracker, review)
            self.logger.debug(f"Submit grievance - collected grievance data from tracker: {grievance_data}")
            # Update the existing grievance with complete data
            try:
                self.db_manager.submit_grievance_to_db(data=grievance_data)
            except Exception as e:
                self.logger.error(f"❌ Error updating grievance: {str(e)}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                raise Exception("Failed to update grievance in the database")
        

            self.logger.info(f"✅ Grievance updated successfully with ID: {self.grievance_id}")
            
            await self._send_grievance_recap_sms(grievance_data, dispatcher) #call the function that extracts the phone number, generates the confirmation message and sends it to the user
            
            # #send email to admin
            # await self._send_grievance_recap_email_to_admin(grievance_data, dispatcher)
            
            # #send email to complainant
            # complainant_email = grievance_data.get('complainant_email')

            # if complainant_email and self.is_valid_email(complainant_email):
            #     await self._send_grievance_recap_email_to_complainant(complainant_email, grievance_data, dispatcher)
                
                 
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

            result = self.db_manager.submit_seah_to_db(grievance_data)
            if not result.get("ok"):
                raise Exception(result.get("error", "SEAH submission failed"))

            public_ref = result.get("seah_public_ref")
            if language_code == "ne":
                dispatcher.utter_message(
                    text=f"तपाईंको गोप्य SEAH रिपोर्ट दर्ता गरिएको छ। तपाईंको सन्दर्भ नम्बर: **{public_ref}**"
                )
            else:
                dispatcher.utter_message(
                    text=f"Your confidential SEAH report has been submitted. Your reference number is **{public_ref}**."
                )

            return [
                SlotSet("grievance_status", self.GRIEVANCE_STATUS["SUBMITTED"]),
                SlotSet("seah_case_id", result.get("seah_case_id")),
                SlotSet("seah_public_ref", public_ref),
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

