from typing import Any, Text, Dict, List, Optional
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction
from rasa_sdk.forms import FormValidationAction
from .db_actions import GrievanceDB

# Initialize database connection
db = GrievanceDB()

class ActionChooseRetrievalMethod(Action):
    def name(self) -> Text:
        return "action_choose_retrieval_method"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(
            text="How would you like to retrieve your grievance?",
            buttons=[
                {"payload": "/retrieve_with_phone", "title": "Use Phone Number"},
                {"payload": "/retrieve_grievance_with_id", "title": "Use Grievance ID"}
            ]
        )
        return []

class ActionDisplayGrievance(Action):
    def name(self) -> Text:
        return "action_display_grievance"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        grievance_id = tracker.get_slot("grievance_id")
        phone_number = tracker.get_slot("user_contact_phone")

        if grievance_id:
            grievance_details = db.get_grievance_by_id(grievance_id)
            if grievance_details:
                self._display_single_grievance(dispatcher, grievance_details)
            else:
                dispatcher.utter_message(text="Sorry, I couldn't find any grievance with that ID.")
        elif phone_number:
            grievances = db.get_grievances_by_phone(phone_number)
            if grievances:
                self._display_multiple_grievances(dispatcher, grievances)
            else:
                dispatcher.utter_message(text="No grievances found for this phone number.")
        else:
            dispatcher.utter_message(text="Sorry, I need either a grievance ID or phone number to retrieve details.")
        return []

    def _display_single_grievance(self, dispatcher: CollectingDispatcher, grievance: Dict):
        message = [
            f"📝 **Grievance ID:** {grievance['grievance_id']}",
            f"👤 **Filed by:** {grievance['user_full_name']}",
            f"📅 **Filed on:** {grievance['grievance_creation_date']}",
            f"📋 **Category:** {grievance.get('grievance_category', 'Not specified')}",
            f"💬 **Summary:** {grievance['grievance_summary']}"
        ]

        if grievance.get('grievance_date'):
            message.append(f"📅 **Incident Date:** {grievance['grievance_date']}")
            
        if grievance.get('grievance_claimed_amount'):
            message.append(f"💰 **Claimed Amount:** {grievance['grievance_claimed_amount']}")
            
        if grievance.get('grievance_location'):
            message.append(f"📍 **Location:** {grievance['grievance_location']}")

        message.extend([
            f"📊 **Current Status:** {grievance['grievance_status']}",
            f"🕒 **Last Updated:** {grievance['grievance_status_update_date']}"
        ])

        if grievance.get('next_step'):
            message.append(f"➡️ **Next Step:** {grievance['next_step']}")

        if grievance.get('expected_resolution_date'):
            message.append(f"🎯 **Expected Resolution:** {grievance['expected_resolution_date']}")
        
        dispatcher.utter_message(text="\n\n".join(message))
        self._offer_status_check(dispatcher)

    def _display_multiple_grievances(self, dispatcher: CollectingDispatcher, grievances: List[Dict]):
        if len(grievances) == 1:
            self._display_single_grievance(dispatcher, grievances[0])
            return

        dispatcher.utter_message(text=f"📋 Found {len(grievances)} grievances:")
        
        for grievance in grievances:
            message = [
                f"🔍 **ID:** {grievance['grievance_id']}",
                f"📝 **Summary:** {grievance['grievance_summary']}",
                f"📊 **Status:** {grievance['grievance_status']}",
                f"📅 **Filed:** {grievance['grievance_creation_date']}"
            ]
            
            if grievance.get('next_step'):
                message.append(f"➡️ **Next Step:** {grievance['next_step']}")
                
            message.append("-------------------")
            
            dispatcher.utter_message(text="\n".join(message))
        
        dispatcher.utter_message(
            text="Which grievance would you like to check?",
            buttons=[{"payload": f"/check_status{{'grievance_id': '{g['grievance_id']}'}}", 
                     "title": f"Check {g['grievance_id']}"} for g in grievances]
        )

    def _offer_status_check(self, dispatcher: CollectingDispatcher):
        dispatcher.utter_message(
            text="Would you like to check the detailed status?",
            buttons=[
                {"payload": "/check_status", "title": "Check Status"}
            ]
        )

class ActionCheckStatus(Action):
    def name(self) -> Text:
        return "action_check_status"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        grievance_id = tracker.get_slot("grievance_id")
        if not grievance_id:
            dispatcher.utter_message(text="Sorry, I couldn't determine which grievance to check.")
            return []

        history = db.get_grievance_history(grievance_id)
        if not history:
            dispatcher.utter_message(text="Sorry, I couldn't retrieve the status history at this moment.")
            return []

        latest = history[0]
        message = [
            f"📊 **Current Status:** {latest['new_status']}",
            f"🕒 **Last Updated:** {latest['update_date']}"
        ]

        if latest.get('next_step'):
            message.append(f"➡️ **Next Step:** {latest['next_step']}")

        if latest.get('expected_resolution_date'):
            message.append(f"🎯 **Expected Resolution:** {latest['expected_resolution_date']}")

        if latest.get('notes'):
            message.append(f"📝 **Notes:** {latest['notes']}")

        dispatcher.utter_message(text="\n\n".join(message))

        dispatcher.utter_message(
            text="Would you like to see the full status history?",
            buttons=[
                {"payload": "/show_status_history", "title": "View History"},
                {"payload": "/retrieve_another_grievance", "title": "Check Another Grievance"}
            ]
        )
        return []

class GrievanceIDForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_grievance_id_form"

    def validate_grievance_id(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        if db.is_valid_grievance_id(slot_value):
            return {"grievance_id": slot_value}
        else:
            dispatcher.utter_message(text="This grievance ID appears to be invalid. Please check and try again.")
            return {"grievance_id": None}

class ActionRetrieveWithPhone(Action):
    def name(self) -> Text:
        return "action_retrieve_with_phone"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [
            SlotSet("verification_context", "retrieval"),
            FollowupAction("action_initiate_otp_verification")
        ]

class ActionShowStatusHistory(Action):
    def name(self) -> Text:
        return "action_show_status_history"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        grievance_id = tracker.get_slot("grievance_id")
        if not grievance_id:
            dispatcher.utter_message(text="Sorry, I couldn't determine which grievance to show history for.")
            return []

        # Get full history
        history = db.get_grievance_history(grievance_id)
        if not history:
            dispatcher.utter_message(text="No status history found for this grievance.")
            return []

        # Display header
        dispatcher.utter_message(text=f"📋 **Status History for Grievance {grievance_id}:**\n")

        # Display each status change
        for entry in history:
            message = []
            
            # Status change
            if entry['previous_status']:
                message.append(f"🔄 Status changed from '{entry['previous_status']}' to '{entry['new_status']}'")
            else:
                message.append(f"📝 Initial status: '{entry['new_status']}'")
            
            # Date and updater
            message.append(f"📅 On: {entry['update_date']}")
            if entry.get('updated_by'):
                message.append(f"👤 By: {entry['updated_by']}")
            
            # Next steps and resolution date
            if entry.get('next_step'):
                message.append(f"➡️ Next Step: {entry['next_step']}")
            if entry.get('expected_resolution_date'):
                message.append(f"🎯 Expected Resolution: {entry['expected_resolution_date']}")
            
            # Notes
            if entry.get('notes'):
                message.append(f"📝 Notes: {entry['notes']}")
            
            # Send each entry as a separate message with a divider
            dispatcher.utter_message(text="\n".join(message))
            dispatcher.utter_message(text="-------------------")

        # Offer next actions
        dispatcher.utter_message(
            text="What would you like to do next?",
            buttons=[
                {"payload": "/check_status", "title": "Check Current Status"},
                {"payload": "/retrieve_another_grievance", "title": "Check Another Grievance"},
                {"payload": "/goodbye", "title": "End Conversation"}
            ]
        )
        return []
