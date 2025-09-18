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
                 "complainant_municipality",
                 "complainant_village",
                 "complainant_address",
                 "grievance_id",
                 "grievance_description",
                 "otp_verified",
                 ]

        if review:
            review_keys = ["grievance_categories",
                           "grievance_summary"]
            keys = keys + review_keys
        
        
        # collect the data from the tracker
        grievance_data={k : tracker.get_slot(k) for k in keys}
        
        grievance_data["grievance_status"] = self.GRIEVANCE_STATUS["SUBMITTED"]

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
    
    def _prepare_recap_email(self, 
                                          to_emails: List[str],
                                          email_data: Dict[str, Any],
                                          body_name: str) -> Tuple[str]:
        """Send a recap email to the user."""
        try:
            self.logger.debug(f"_prepare_recap_email called with body_name: {body_name}")
            self.logger.debug(f"_prepare_recap_email email_data keys: {list(email_data.keys())}")
            self.logger.debug(f"_prepare_recap_email email_data: {email_data}")
            
            json_data = json.dumps(email_data, indent=2, ensure_ascii=False)
            
            if email_data.get('grievance_categories') and email_data.get('grievance_categories') != self.NOT_PROVIDED:
                categories_html = ''.join(f'<li>{category}</li>' for category in (email_data['grievance_categories'] or []))
            else:
                self.logger.debug(f"_prepare_recap_email no grievance_categories or it's NOT_PROVIDED")
                categories_html = ""
            # Create email body using template
            self.logger.debug(f"_prepare_recap_email checking EMAIL_TEMPLATES for body_name: {body_name}")
            self.logger.debug(f"_prepare_recap_email available EMAIL_TEMPLATES keys: {list(EMAIL_TEMPLATES.keys())}")
            
            if body_name == "GRIEVANCE_RECAP_COMPLAINANT_BODY":
                self.logger.debug(f"_prepare_recap_email using COMPLAINANT template")
                if body_name not in EMAIL_TEMPLATES:
                    self.logger.error(f"Template {body_name} not found in EMAIL_TEMPLATES")
                    return "", ""
                body = EMAIL_TEMPLATES[body_name][self.language_code]
                subject = EMAIL_TEMPLATES["GRIEVANCE_SUBJECT_COMPLAINANT"][self.language_code]

            elif body_name == "GRIEVANCE_RECAP_ADMIN_BODY":
                self.logger.debug(f"_prepare_recap_email using ADMIN template")
                if body_name not in EMAIL_TEMPLATES:
                    self.logger.error(f"Template {body_name} not found in EMAIL_TEMPLATES")
                    return "", ""
                body = EMAIL_TEMPLATES[body_name][self.language_code]
                subject = EMAIL_TEMPLATES["GRIEVANCE_SUBJECT_ADMIN"][self.language_code]
            else:
                self.logger.error(f"Unknown body_name: {body_name}")
                return "", ""

            self.logger.debug(f"_prepare_recap_email formatting subject and body")
            #format subject and body
            subject = subject.format(
                grievance_id=email_data.get('grievance_id', '')
            )
            body = body.format(
            complainant_name=email_data.get('complainant_full_name', self.NOT_PROVIDED),
            grievance_description=email_data.get('grievance_description', self.NOT_PROVIDED),
            project=email_data.get('complainant_project', self.NOT_PROVIDED),
            complainant_municipality=email_data.get('complainant_municipality', self.NOT_PROVIDED),
            complainant_village=email_data.get('complainant_village', self.NOT_PROVIDED),
            complainant_address=email_data.get('complainant_address', self.NOT_PROVIDED),
            complainant_phone=email_data.get('complainant_phone', self.NOT_PROVIDED),
            grievance_id=email_data.get('grievance_id', ''),
            complainant_email=email_data.get('complainant_email', self.NOT_PROVIDED),
            grievance_timeline=email_data.get('grievance_timeline', self.NOT_PROVIDED),
            grievance_timestamp=email_data.get('grievance_timestamp', self.NOT_PROVIDED),
            categories_html=categories_html,
            grievance_summary=email_data.get('grievance_summary', self.NOT_PROVIDED)
            )
            
            self.logger.debug(f"_prepare_recap_email successfully prepared email")
            return body, subject

            
        except Exception as e:
            self.logger.error(f"Failed to prepare recap email: {e}")
            return "", ""
        
    
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
            self.logger.debug(f"_send_grievance_recap_email_to_admin called with grievance_data keys: {list(grievance_data.keys())}")
            await self._send_grievance_recap_email(ADMIN_EMAILS, 
                                                grievance_data, 
                                                body_name = "GRIEVANCE_RECAP_ADMIN_BODY"
                                                )
        except Exception as e:
            self.logger.error(f"Failed to send recap email to admin: {e}")
            self.logger.error(f"Admin email error details: {traceback.format_exc()}")


    async def _send_grievance_recap_email_to_complainant(self, 
                                                         complainant_email: str,
                                                         grievance_data: Dict[str, Any],
                                                         dispatcher: CollectingDispatcher) -> None:
        """Send a recap email to the complainant."""
        try:
            self.logger.debug(f"_send_grievance_recap_email_to_complainant called with email: {complainant_email}")
            self.logger.debug(f"_send_grievance_recap_email_to_complainant grievance_data keys: {list(grievance_data.keys())}")
            await self._send_grievance_recap_email([complainant_email], 
                                                grievance_data, 
                                                body_name = "GRIEVANCE_RECAP_COMPLAINANT_BODY"
                                                )
            message = self.get_utterance(3)
            utterance = message.format(complainant_email=complainant_email)
            dispatcher.utter_message(text=utterance)
        except Exception as e:
            self.logger.error(f"Failed to send recap email to complainant {complainant_email}: {e}")
            self.logger.error(f"Complainant email error details: {traceback.format_exc()}")

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


class ActionGrievanceOutro(BaseActionSubmit):
    def name(self) -> Text:
        return "action_grievance_outro"

    def _prepare_grievance_outro_data(self, tracker: Tracker) -> Dict[str, Any]:
        """Prepare the grievance outro data from the slots and updating the categories to the english ones"""
        # Get original slot values for messaging (not encrypted database values)
        grievance_data = self.collect_grievance_data(tracker, review = True)
        
        # Get categories from slots and convert to English if needed
        grievance_categories_local = tracker.get_slot("grievance_categories_local")

        
        # Use the current slot values for categories (these are the user-confirmed values)
        current_categories = tracker.get_slot("grievance_categories")

        
        # If we have local language categories, convert them to English
        if grievance_categories_local and self.language_code != "en":
            grievance_categories_en = self._get_categories_in_english(grievance_categories_local)
            grievance_data["grievance_categories"] = grievance_categories_en
        elif current_categories:
            grievance_data["grievance_categories"] = current_categories

        return grievance_data

    
    async def execute_action(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Any]:
        
        self.sensitive_issues_detected = tracker.get_slot("sensitive_issues_detected")
        self.logger.info("send last utterance and buttons")
        grievance_id = tracker.get_slot("grievance_id")
        buttons = None
        try:
            if self.sensitive_issues_detected:
                    utterance = self.get_utterance(1) #we are numbering the utterances from 4 since all the utterances in the Class are in the same key in utterance_mapping_rasa.py
                    buttons = self.get_buttons(1)
                    
            elif not self._get_attached_files_info(grievance_id)["has_files"]:
                utterance = self.get_utterance(2)
            else:
                utterance = self.get_utterance(3)
            self.logger.debug(f"action_grievance_outro - utterance: {utterance} - buttons: {buttons if buttons else 'None'}")
            
            if buttons:
                dispatcher.utter_message(text=utterance, buttons=buttons)
            else:
                dispatcher.utter_message(text=utterance)
            self.logger.debug(f"action_grievance_outro - outro sent")

            #final saving to the database
            grievance_data = self._prepare_grievance_outro_data(tracker)
           
            self.db_manager.submit_grievance_to_db(grievance_data)
            self.logger.debug(f"action_grievance_outro - grievance data saved to the database: {grievance_data}")

            #send email to admin
            await self._send_grievance_recap_email_to_admin(grievance_data, dispatcher)
            
            #send email to complainant
            complainant_email = grievance_data.get('complainant_email')

            if complainant_email and self.is_valid_email(complainant_email):
                await self._send_grievance_recap_email_to_complainant(complainant_email, grievance_data, dispatcher)

            return []
        except Exception as e:
            self.logger.error(f"Error in action_grievance_outro: {e}")