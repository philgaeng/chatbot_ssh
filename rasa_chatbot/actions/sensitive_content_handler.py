import logging
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet, FollowupAction
from .utterance_mapping_rasa import get_utterance, get_buttons

logger = logging.getLogger(__name__)

class ActionHandleSensitiveContentAffirm(Action):
    """Handle when user confirms sensitive content detection"""
    
    def name(self) -> Text:
        return "action_handle_sensitive_content_affirm"
    
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        """Handle user confirmation of sensitive content"""
        
        language_code = tracker.get_slot("language_code") or "en"
        category = tracker.get_slot("sensitive_content_category")
        level = tracker.get_slot("sensitive_content_level")
        
        print(f"🚨 HANDLING SENSITIVE CONTENT AFFIRM: {category} - {level}")
        
        # Clear sensitive content slots
        slots_to_set = {
            "sensitive_content_detected": False,
            "sensitive_content_category": None,
            "sensitive_content_level": None,
            "sensitive_content_message": None,
            "sensitive_content_confidence": None
        }
        
        # Generate appropriate response based on category
        if language_code == "ne":
            if category == "sexual_assault":
                message = "यौन हिंसाको रिपोर्ट दिन तपाईंलाई धन्यवाद। यो गम्भीर मुद्दा हो र हामी यसलाई उचित अधिकारीहरूलाई सुम्पनेछौं।"
            elif category == "harassment":
                message = "उत्पीडनको रिपोर्ट दिन तपाईंलाई धन्यवाद। हामी यसलाई उचित अधिकारीहरूलाई सुम्पनेछौं।"
            elif category == "violence":
                message = "हिंसाको रिपोर्ट दिन तपाईंलाई धन्यवाद। यो गम्भीर मुद्दा हो र हामी यसलाई तुरुन्तै उचित अधिकारीहरूलाई सुम्पनेछौं।"
            elif category == "land_issues":
                message = "जग्गा सम्बन्धित समस्याको रिपोर्ट दिन तपाईंलाई धन्यवाद। हामी यसलाई उचित अधिकारीहरूलाई सुम्पनेछौं।"
            else:
                message = "यसको रिपोर्ट दिन तपाईंलाई धन्यवाद। हामी यसलाई उचित अधिकारीहरूलाई सुम्पनेछौं।"
        else:
            if category == "sexual_assault":
                message = "Thank you for reporting sexual assault. This is a serious matter and we will forward it to the appropriate authorities."
            elif category == "harassment":
                message = "Thank you for reporting harassment. We will forward this to the appropriate authorities."
            elif category == "violence":
                message = "Thank you for reporting violence. This is a serious matter and we will forward it immediately to the appropriate authorities."
            elif category == "land_issues":
                message = "Thank you for reporting land-related issues. We will forward this to the appropriate authorities."
            else:
                message = "Thank you for reporting this. We will forward it to the appropriate authorities."
        
        dispatcher.utter_message(text=message)
        
        # Continue with grievance process
        return [SlotSet(key, value) for key, value in slots_to_set.items()] + [
            FollowupAction("action_ask_grievance_description_form_grievance_temp")
        ]

class ActionHandleSensitiveContentDeny(Action):
    """Handle when user denies sensitive content detection"""
    
    def name(self) -> Text:
        return "action_handle_sensitive_content_deny"
    
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        """Handle user denial of sensitive content"""
        
        language_code = tracker.get_slot("language_code") or "en"
        
        print("🚨 HANDLING SENSITIVE CONTENT DENY")
        
        # Clear sensitive content slots
        slots_to_set = {
            "sensitive_content_detected": False,
            "sensitive_content_category": None,
            "sensitive_content_level": None,
            "sensitive_content_message": None,
            "sensitive_content_confidence": None
        }
        
        # Generate appropriate response
        if language_code == "ne":
            message = "माफ गर्नुहोस्, मैले गलत बुझेको हुन सक्छु। कृपया आफ्नो समस्या बताउनुहोस्।"
        else:
            message = "I apologize, I may have misunderstood. Please tell me about your problem."
        
        dispatcher.utter_message(text=message)
        
        # Continue with grievance process
        return [SlotSet(key, value) for key, value in slots_to_set.items()] + [
            FollowupAction("action_ask_grievance_description_form_grievance_temp")
        ] 