from typing import Any, Dict, List, Text, Tuple
from datetime import datetime, timedelta
import re
from .utils.base_classes import BaseAction
from rasa_sdk import Tracker
from rasa_sdk.executor import CollectingDispatcher
import json
import traceback
from backend.config.constants import ADMIN_EMAILS, EMAIL_TEMPLATES
from rasa_sdk.events import SlotSet





############################ STEP 4 - SUBMIT GRIEVANCE ############################
class BaseActionSubmit(BaseAction):


    def get_current_datetime(self) -> str:
        """Get current date and time in YYYY-MM-DD HH:MM format."""
        return datetime.now().strftime("%Y-%m-%d %H:%M")
    



    def collect_grievance_data(self, tracker: Tracker, review: bool = False) -> Dict[str, Any]:
        """Collect and separate user and grievance data from slots."""
        # set up the timestamp and timeline
        grievance_timestamp = self.get_current_datetime()
        grievance_timeline = (datetime.strptime(grievance_timestamp, "%Y-%m-%d %H:%M") + 
                            timedelta(days=15)).strftime("%Y-%m-%d")

        keys = ["complainant_id",
                 "complainant_phone",
                 "complainant_email",
                 "complainant_full_name",
                 "complainant_gender",
                 "complainant_province",
                 "complainant_district",
                 "grievance_id",
                 "grievance_description",
                 "otp_verified",
                 "grievance_categories",
                 "grievance_summary"]

        if review:
            review_keys = ["grievance_categories",
                           "grievance_summary"]
            keys = keys + review_keys
        
        
        # collect the data from the tracker
        grievance_data={k : tracker.get_slot(k) for k in keys}
        
        grievance_data["grievance_status"] = self.GRIEVANCE_STATUS["SUBMITTED"] if not review else self.GRIEVANCE_STATUS["REVIEW"]

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
    
    def _get_attached_files_info(self, grievance_id: str) -> Dict[str, Any]:
        """Get information about files attached to a grievance.
        
        Args:
            grievance_id (str): The ID of the grievance to check for files
            
        Returns:
            str: A formatted string containing file information, or empty string if no files
        """
        try:
            files = self.db_manager.get_grievance_files(grievance_id)
            if not files:
                return {"has_files": False,
                        "files_info": ""}
            else:
                files_info = "\nAttached files:\n" + "\n".join([
                f"- {file['file_name']} ({file['file_size']} bytes)"
                for file in files
            ])
                return {"has_files": True,
                        "files_info": files_info}

        except Exception as e:
            self.logger.error(f"❌ Error getting attached files info: {str(e)}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            raise Exception(f"Failed to get attached files info: {str(e)}")

        
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
    
    def _prepare_recap_email(self, 
                                          to_emails: List[str],
                                          email_data: Dict[str, Any],
                                          body_name: str) -> Tuple[str]:
        """Send a recap email to the user."""
        
        json_data = json.dumps(email_data, indent=2, ensure_ascii=False)
        
        if email_data['grievance_categories'] and email_data['grievance_categories'] != self.NOT_PROVIDED:
            categories_html = ''.join(f'<li>{category}</li>' for category in (email_data['grievance_categories'] or []))
        else:
            categories_html = ""
        # Create email body using template
        
        if body_name == "GRIEVANCE_RECAP_complainant_BODY":
            body = EMAIL_TEMPLATES[body_name].format(
            complainant_name=email_data['complainant_full_name'],
            grievance_description=email_data['grievance_description'],
            project=email_data['complainant_project'],
            municipality=email_data['complainant_municipality'],
            village=email_data['complainant_village'],
            address=email_data['complainant_address'],
            phone=email_data['complainant_phone'],
            grievance_id=email_data['grievance_id'],
            email=email_data['complainant_email'],
            grievance_timeline=email_data['grievance_timeline'],
            grievance_timestamp=email_data['grievance_timestamp'],
            grievance_categories=email_data['grievance_categories'],
            grievance_summary=email_data['grievance_summary']
        ) 
        if body_name == "GRIEVANCE_RECAP_ADMIN_BODY":
            body = EMAIL_TEMPLATES[body_name].format(
                json_data=json_data,
                grievance_status=self.GRIEVANCE_STATUS["SUBMITTED"],
            )

        subject = EMAIL_TEMPLATES["GRIEVANCE_RECAP_SUBJECT"].format(
            grievance_id=email_data['grievance_id']
        )
        
        return body, subject
    
    async def _send_grievance_recap_email(self, to_emails: List[str],
                                                         grievance_data: Dict[str, Any],
                                                         body_name: str
                                                         ) -> None:
        """Prepare and send a recap email according to the body name."""
        #send email to user
        try:    
            body, subject = self._prepare_recap_email(to_emails, 
                                                    grievance_data, 
                                                    body_name)
            
            self.messaging.send_email(to_emails,
                                            subject = subject,
                                            body=body
                                            )       
        except Exception as e:
            self.logger.error(f"Failed to send system notification email: {e}"
            )
            
    async def _send_grievance_recap_email_to_admin(self, 
                                                   grievance_data: Dict[str, Any],
                                                   dispatcher: CollectingDispatcher) -> None:
        """Send a recap email to the admin."""
        try:
            await self._send_grievance_recap_email(ADMIN_EMAILS, 
                                                grievance_data, 
                                                body_name = "GRIEVANCE_RECAP_ADMIN_BODY"
                                                )
            message = self.get_utterance(2)
            dispatcher.utter_message(text=message)
        except Exception as e:
            self.logger.error(f"Failed to send recap email to admin: {e}")


    async def _send_grievance_recap_email_to_complainant(self, 
                                                         complainant_email: str,
                                                         grievance_data: Dict[str, Any],
                                                         dispatcher: CollectingDispatcher) -> None:
        """Send a recap email to the complainant."""
        try:
            await self._send_grievance_recap_email([complainant_email], 
                                                grievance_data, 
                                                body_name = "GRIEVANCE_RECAP_COMPLAINANT_BODY"
                                                )
            message = self.get_utterance(3)
            utterance = message.format(complainant_email=complainant_email)
            dispatcher.utter_message(text=utterance)
        except Exception as e:
            self.logger.error(f"Failed to send recap email to complainant {complainant_email}: {e}")


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
  
    
    def send_last_utterance_buttons(self, 
                                     gender_tag: bool, 
                                     has_files: bool, 
                                     dispatcher: CollectingDispatcher) -> None:
        buttons = None
        self.logger.info("send last utterance and buttons")
        try:
            if gender_tag:
                    utterance = self.get_utterance(5) #we are numbering the utterances from 4 since all the utterances in the Class are in the same key in utterance_mapping_rasa.py
                    buttons = self.get_buttons(1)
            elif not has_files:
                utterance = self.get_utterance(6)
            else:
                utterance = self.get_utterance(7)
            
            if buttons:
                dispatcher.utter_message(text=utterance, buttons=buttons)
            else:
                dispatcher.utter_message(text=utterance)
        except Exception as e:
            self.logger.error(f"Error in send_last_utterance_buttons: {e}")

    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any], review: bool = False) -> List[Dict[Text, Any]]:
        self.sensitive_issues_detected = tracker.get_slot("sensitive_issues_detected")
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
            
            #send email to admin
            await self._send_grievance_recap_email_to_admin(grievance_data, dispatcher)
            
            #send email to complainant
            complainant_email = grievance_data.get('complainant_email')

            if complainant_email and self.is_valid_email(complainant_email):
                await self._send_grievance_recap_email_to_complainant(complainant_email, grievance_data, dispatcher)
                
                
            #send the last utterance and buttons
            self.send_last_utterance_buttons(self.sensitive_issues_detected, 
                                              
                                                self._get_attached_files_info(self.grievance_id)["has_files"],
                                                dispatcher=dispatcher)
                
            
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


class ActionSubmitGrievanceReview(BaseActionSubmit):
    def name(self) -> Text:
        return "action_submit_grievance_review"
    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return await super().execute_action(dispatcher, tracker, domain, review = True)