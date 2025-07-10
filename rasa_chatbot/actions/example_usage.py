"""
Example usage of the BackendRepository in Rasa actions.

This file demonstrates how to use the new repository pattern to clean up Rasa actions.
"""

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from typing import Dict, Any, List

from .backend_repository import backend_repo


class ExampleGrievanceAction(Action):
    """Example action showing how to use the BackendRepository."""
    
    def name(self) -> str:
        return "action_example_grievance"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Example of creating a grievance using the repository."""
        
        # Log the action
        backend_repo.log_action("action_example_grievance", {"tracker_id": tracker.sender_id})
        
        try:
            # Get complainant data from slots
            complainant_data = {
                "complainant_name": tracker.get_slot("complainant_name"),
                "complainant_phone": tracker.get_slot("complainant_phone"),
                "complainant_email": tracker.get_slot("complainant_email"),
                "complainant_province": tracker.get_slot("complainant_province"),
                "complainant_district": tracker.get_slot("complainant_district"),
                "complainant_municipality": tracker.get_slot("complainant_municipality"),
            }
            
            # Create complainant
            complainant_created = backend_repo.create_complainant(complainant_data)
            
            if complainant_created:
                # Get grievance data
                grievance_data = {
                    "grievance_description": tracker.get_slot("grievance_description"),
                    "grievance_category": tracker.get_slot("grievance_category"),
                    "source": "bot"
                }
                
                # Create grievance
                grievance_created = backend_repo.create_grievance(grievance_data)
                
                if grievance_created:
                    # Send confirmation SMS
                    phone = tracker.get_slot("complainant_phone")
                    message = "Your grievance has been submitted successfully. We will contact you soon."
                    backend_repo.send_sms(phone, message)
                    
                    dispatcher.utter_message(text="Your grievance has been submitted successfully!")
                else:
                    dispatcher.utter_message(text="Sorry, there was an error submitting your grievance.")
            else:
                dispatcher.utter_message(text="Sorry, there was an error creating your profile.")
                
        except Exception as e:
            error_info = backend_repo.handle_error(e, "action_example_grievance")
            dispatcher.utter_message(text="Sorry, an error occurred. Please try again later.")
        
        return []


class ExampleLocationValidationAction(Action):
    """Example action showing location validation using the repository."""
    
    def name(self) -> str:
        return "action_validate_location"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Example of validating location using the repository."""
        
        try:
            # Get location from user input
            location_text = tracker.get_slot("location_text")
            
            # Validate location using the repository
            validation_result = backend_repo.validate_location(
                location_text, 
                tracker=tracker
            )
            
            if validation_result.get("province") and validation_result.get("district"):
                # Location is valid, update slots
                return [
                    {"slot": "complainant_province", "value": validation_result["province"]},
                    {"slot": "complainant_district", "value": validation_result["district"]},
                    {"slot": "complainant_municipality", "value": validation_result.get("municipality")}
                ]
            else:
                dispatcher.utter_message(text="I couldn't understand that location. Please try again.")
                
        except Exception as e:
            error_info = backend_repo.handle_error(e, "action_validate_location")
            dispatcher.utter_message(text="Sorry, there was an error validating the location.")
        
        return []


class ExampleOTPAction(Action):
    """Example action showing OTP functionality using the repository."""
    
    def name(self) -> str:
        return "action_send_otp"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Example of sending OTP using the repository."""
        
        try:
            phone = tracker.get_slot("complainant_phone")
            
            if phone:
                # Generate OTP (in real implementation, you'd generate and store it)
                otp = "123456"  # Placeholder
                
                # Send OTP using the repository
                otp_sent = backend_repo.send_otp(phone, otp)
                
                if otp_sent:
                    dispatcher.utter_message(text=f"OTP sent to {phone}")
                else:
                    dispatcher.utter_message(text="Failed to send OTP. Please try again.")
            else:
                dispatcher.utter_message(text="Phone number not found.")
                
        except Exception as e:
            error_info = backend_repo.handle_error(e, "action_send_otp")
            dispatcher.utter_message(text="Sorry, there was an error sending the OTP.")
        
        return [] 